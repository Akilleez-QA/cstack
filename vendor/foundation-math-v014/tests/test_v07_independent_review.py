"""Independent v0.7 boundary review: original tiny synthetic polynomials only.

Tests pin inherited definitions, not an external manifest's self-report. No
network, repository operations, credentials, or formal-proof claims are used.
"""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math import polynomial_witness as adapter
from foundation_math.domains import DomainError, domain_handler
from foundation_math_bridge import server
from foundation_math_bridge.schemas import tool_definitions
from polynomial_witness.contract import Limits, MAX_WIRE_BYTES

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'characteristic_zero_unrestricted_formal_polynomial'
BASE_DEFINITIONS = {
    'exact_scalar': 'f36d0f145c7704dbfdc61e5504ee5bb8a413e34748791806890c538e18715c26',
    'polynomial_identity': 'b61b8563638f18572c343d4d381a5e78980d8fa8172ecda89a4c382e23a66325',
    'finite_box_search': 'c6804f2b38e63bf159e643c1053e941849926427f8c5fcf5d622f754246bb77d',
    'check_finite_box_witness': '03c09cee65e35964b86f8b4af97b0e29b7fd9b6211a71830458cfe3122fba471',
    'certify_rational_matrix': '765e34bd7cadd99097034791080ed04d456087dbce2efd1a1c3a2e6b5744742d',
    'check_rational_matrix_certificate': '7f5cabe7387e1d7288b26ce51c6fc12b9e2c3d7196f626ec974308475a6775db',
}
LAB_FILES = {
    '__init__.py': '5db5c09de73dd544823e8393aa5dfb8500213bea1b459369f4739b3eb3ce2e53',
    '__main__.py': '80aee4cf885ec72caba9a40f5a7c140a30628d57a2c05441000fd8287792d103',
    '_vendor/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    '_vendor/calculator.py': '146ec4fc9fca0c3400331c06595894fd9cb6a23668abae5c7b8d196e06bad54e',
    '_vendor/polynomial.py': 'b700a069e0af9609a7b9e63d6a8185d9b430630d6d2f55f5a6ac2e5155022b9b',
    'api.py': 'b5d43b961ea87df91ab65248c53ffb8a6917d6b31c63bb295c0e8d0308ecf01b',
    'checker.py': 'b2c0a826e0769ec3c65f082c3115b455ef9841154229d1a820e19f528a00891c',
    'contract.py': 'd7d3aa19dcb6d1fccff25e3ce94723d4e7fb6ed56802a8986fd7eb2b83ba50dc',
    'producer.py': 'a26f8c10f085bebe3fb42cc3ca0581670067a75007634182336bf4c902da0129',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def q(n, d=1):
    return {'type': 'rational', 'numerator': n, 'denominator': d}


def v(name):
    return {'type': 'variable', 'name': name}


def binary(kind, a, b):
    return {'type': kind, 'operands': [a, b]}


def request(left=None, right=None, variables=None):
    return {'domain': 'polynomial_ring', 'coefficient_field': 'Q',
            'variables': ['x', 'y'] if variables is None else variables,
            'operation': 'verify_identity',
            'operands': [binary('multiply', v('x'), binary('add', v('y'), q(-1)))
                         if left is None else left, q(0) if right is None else right]}


def frame(method, params=None, identifier=1):
    data = {'jsonrpc': '2.0', 'id': identifier, 'method': method}
    if params is not None:
        data['params'] = params
    return canonical(data)


class IndependentV07Review(unittest.TestCase):
    def setUp(self):
        self.req = request()
        self.bridge = server.Bridge()
        self.bridge.handle(frame('initialize', {'protocolVersion': server.PROTOCOL}))

    def scope(self, receipt):
        self.assertEqual(receipt['scope'], SCOPE)
        self.assertEqual(receipt['coefficient_field'], 'Q')
        self.assertEqual(receipt['characteristic'], 0)
        self.assertIs(receipt['formal_proof'], False)
        self.assertIs(receipt['runtime_goal_acceptance'], False)

    def no_evidence(self, receipt, status='error'):
        self.scope(receipt)
        self.assertEqual(receipt['status'], status)
        for field in ('accepted', 'witness', 'result', 'verification', 'request_sha256', 'implementation', 'construction_bound'):
            self.assertNotIn(field, receipt)
        self.assertLess(len(canonical(receipt)), 2048)

    def call(self, name, arguments):
        return self.bridge.handle(frame('tools/call', {'name': name, 'arguments': arguments}))

    def cli(self, *arguments, optimized=None):
        optimized = bool(sys.flags.optimize) if optimized is None else optimized
        command = [sys.executable, '-B'] + (['-O'] if optimized else [])
        return subprocess.run(command + ['-m', 'foundation_math', *map(str, arguments)],
                              cwd=ROOT, capture_output=True, timeout=10, check=False)

    def test_six_inherited_definitions_exactly_pinned(self):
        definitions = tool_definitions()
        self.assertEqual([t['name'] for t in definitions[:6]], list(BASE_DEFINITIONS))
        self.assertEqual([t['name'] for t in definitions[6:8]],
                         ['construct_polynomial_witness', 'check_polynomial_witness'])
        for definition in definitions[:6]:
            self.assertEqual(sha256(canonical(definition)).hexdigest(), BASE_DEFINITIONS[definition['name']])
        self.assertEqual(server.TOOL_NAMES, frozenset(t['name'] for t in definitions))

    def test_all_nine_frozen_lab_modules_pinned(self):
        for name, digest in LAB_FILES.items():
            self.assertEqual(sha256((ROOT / 'polynomial_witness' / name).read_bytes()).hexdigest(), digest, name)

    def test_runtime_and_legacy_math_files_preserved(self):
        baseline = json.loads((ROOT / 'docs/BASE-V06-FROZEN-FILES.json').read_text())['files']
        paths = [name for name in baseline if name.endswith('.py') and
                 name.startswith(('foundation_math/', 'bounded_counterexample/', 'exact_linalg/'))
                 and name != 'foundation_math/cli.py']
        self.assertGreater(len(paths), 20)
        for name in paths:
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), baseline[name], name)

    def test_new_tool_inputs_are_closed_and_fixed(self):
        for definition in tool_definitions()[6:8]:
            schema = definition['inputSchema']
            self.assertIs(schema['additionalProperties'], False)
            self.assertIs(definition['readOnly'], True)
            self.assertEqual(set(schema['properties']), {'request', 'witness'} if
                             definition['name'] == 'check_polynomial_witness' else {'request'})
            for key, value in [('limits', {}), ('path', 'private-sentinel'), ('code', 'private-sentinel'),
                               ('formal_proof', True), ('runtime_goal_acceptance', True)]:
                args = {'request': self.req, key: value}
                if definition['name'] == 'check_polynomial_witness':
                    args['witness'] = {}
                response = self.call(definition['name'], args)
                self.assertEqual(response['error']['code'], -32602)
                self.assertNotIn('private-sentinel', canonical(response).decode())

    def test_nonpromotion_remains_explicit_and_runtime_rejects_new_domains(self):
        result = adapter.construct_polynomial_witness(self.req)
        self.scope(result)
        for label in ('polynomial_witness', SCOPE, 'construct_polynomial_witness'):
            with self.assertRaises(DomainError):
                domain_handler(label)
        with self.assertRaises(DomainError):
            domain_handler('polynomial_ring').validate_expected(result, self.req)

    def test_notification_calls_do_not_execute_new_tools(self):
        for name in ('construct_polynomial_witness', 'check_polynomial_witness'):
            notification = {'jsonrpc': '2.0', 'method': 'tools/call',
                            'params': {'name': name, 'arguments': {'request': self.req}}}
            with patch.object(server, name, side_effect=RuntimeError('must not execute')) as target:
                self.assertIsNone(self.bridge.handle(canonical(notification)))
                target.assert_not_called()

    def test_bridge_unexpected_failure_is_private(self):
        with patch.object(server, 'construct_polynomial_witness', side_effect=RuntimeError('private-sentinel')):
            response = self.call('construct_polynomial_witness', {'request': self.req})
        self.assertEqual(response['error']['code'], -32603)
        self.assertNotIn('private-sentinel', canonical(response).decode())
        self.assertNotIn('result', response)


    def test_constructed_values_and_identity_are_different_evidence(self):
        constructed = adapter.construct_polynomial_witness(self.req)
        self.scope(constructed)
        self.assertEqual(constructed['status'], 'success')
        lab = constructed['result']
        self.assertEqual(lab['verification']['status'], 'accepted')
        witness = lab['result']['witness']
        self.assertEqual(witness['assignment'], {'x': 1, 'y': 0})
        self.assertEqual(witness['difference_value'], {'numerator': -1, 'denominator': 1})
        identity_request = request(v('x'), v('x'))
        identity = adapter.construct_polynomial_witness(identity_request, Limits(0, 0, 0, 0))
        self.scope(identity)
        self.assertEqual(identity['result']['result']['kind'], 'coefficient_identity')
        self.assertEqual(identity['result']['verification']['status'], 'not_applicable')
        self.assertNotIn('witness', identity['result']['result'])
        self.assertEqual(identity['result']['usage']['substitution_trials'], 0)
        response = self.call('construct_polynomial_witness', {'request': identity_request})['result']
        self.assertIs(response['isError'], False)
        self.assertEqual(response['structuredContent']['assessment'], 'polynomial_coefficient_identity')

    def test_hashes_bind_original_request_operation_and_complete_witness(self):
        composite = {'operation': 'construct', 'request': self.req}
        constructed = adapter.calculate_polynomial_witness(composite)
        self.assertEqual(constructed['request_sha256'], sha256(canonical(composite)).hexdigest())
        reordered = dict(reversed(list(composite.items())))
        self.assertEqual(adapter.calculate_polynomial_witness(reordered), constructed)
        witness = constructed['result']['result']['witness']
        verified = adapter.check_polynomial_witness(self.req, witness)
        expected = {'operation': 'verify', 'request': self.req, 'witness': witness}
        self.assertEqual(verified['request_sha256'], sha256(canonical(expected)).hexdigest())
        self.assertNotEqual(verified['request_sha256'], constructed['request_sha256'])
        alternate = deepcopy(witness)
        alternate['assignment'] = {'x': 2, 'y': 3}
        alternate['left_value'] = alternate['difference_value'] = {'numerator': 4, 'denominator': 1}
        second = adapter.check_polynomial_witness(self.req, alternate)
        self.assertEqual(second['status'], 'success')
        self.assertNotEqual(second['request_sha256'], verified['request_sha256'])
        self.assertEqual(second['result']['assignment'], alternate['assignment'])
        for name, digest in constructed['implementation']['source_sha256'].items():
            self.assertFalse(Path(name).is_absolute())
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(len(constructed['implementation']['source_sha256']), 10)

    def test_request_binding_rejects_same_polynomial_different_original_ast(self):
        req = request(binary('multiply', q(2, 2), v('x')), variables=['x'])
        witness = adapter.construct_polynomial_witness(req)['result']['result']['witness']
        changed = deepcopy(req)
        changed['operands'][0]['operands'][0] = q(1)
        result = adapter.check_polynomial_witness(changed, witness)
        self.no_evidence(result, 'rejected')
        self.assertEqual(result['error']['code'], 'binding_mismatch')
        self.assertNotEqual(witness['input_sha256'], witness['request_sha256'])

    def test_forged_receipts_values_and_hashes_are_not_witnesses(self):
        receipt = adapter.construct_polynomial_witness(self.req)
        witness = receipt['result']['result']['witness']
        candidates = [receipt, receipt['result'], {'accepted': True, 'formal_proof': True},
                      {**witness, 'accepted': True}, {**witness, 'request_sha256': '0'*64},
                      {**witness, 'difference_value': {'numerator': 1, 'denominator': 1}},
                      {**witness, 'assignment': {'x': 0, 'y': 0}},
                      {**witness, 'assignment': {'x': True, 'y': 0}}]
        for candidate in candidates:
            self.no_evidence(adapter.check_polynomial_witness(self.req, candidate), 'rejected')
        forged = deepcopy(receipt)
        forged['formal_proof'] = forged['runtime_goal_acceptance'] = True
        forged['result']['verification']['status'] = 'accepted'
        self.no_evidence(adapter.check_polynomial_witness(self.req, forged), 'rejected')

    def test_checker_does_not_use_producer_or_polynomial_normalization(self):
        witness = adapter.construct_polynomial_witness(self.req)['result']['result']['witness']
        with patch('polynomial_witness.api.produce', side_effect=RuntimeError('producer called')) as producer, \
             patch('polynomial_witness._vendor.polynomial._normalize', side_effect=RuntimeError('normalizer called')) as normalizer:
            checked = adapter.check_polynomial_witness(self.req, witness)
        self.assertEqual(checked['status'], 'success')
        producer.assert_not_called()
        normalizer.assert_not_called()

    def test_manual_point_can_be_checked_beyond_normalizer_degree_cap(self):
        def product(count):
            if count == 1:
                return v('x')
            return binary('multiply', product(count // 2), product(count - count // 2))
        req = request(product(33), variables=['x'])
        self.no_evidence(adapter.construct_polynomial_witness(req))
        digest = sha256(canonical(req)).hexdigest()
        witness = {'schema_version': '1.0', 'input_sha256': digest, 'request_sha256': digest,
                   'ring': {'kind': 'commutative_polynomial_ring', 'coefficient_field': 'Q', 'variables': ['x']},
                   'assignment': {'x': 1}, 'left_value': {'numerator': 1, 'denominator': 1},
                   'right_value': {'numerator': 0, 'denominator': 1},
                   'difference_value': {'numerator': 1, 'denominator': 1}}
        checked = adapter.check_polynomial_witness(req, witness)
        self.scope(checked)
        self.assertEqual(checked['status'], 'success')
        self.assertEqual(checked['result']['difference_value']['numerator'], 1)
        self.assertEqual(checked['result']['usage']['evaluation_nodes'], 66)

    def test_constructor_withholds_false_or_unchecked_producer_witness(self):
        lab = adapter.construct_polynomial_witness(self.req)['result']
        forged = deepcopy(lab)
        forged['result']['witness']['difference_value']['numerator'] = 19
        with patch('polynomial_witness.api.produce', return_value=forged):
            failure = adapter.construct_polynomial_witness(self.req)
        self.no_evidence(failure)
        self.assertEqual(failure['error']['code'], 'witness_check_failed')
        failure = adapter.construct_polynomial_witness(self.req, replace(Limits(), max_evaluation_nodes=0))
        self.no_evidence(failure)
        self.assertEqual(failure['error']['code'], 'witness_check_failed')

    def test_limits_are_only_lowerable_and_failure_never_implies_absence(self):
        composite = {'operation': 'construct', 'request': self.req}
        for limits in [None, {}, Limits(max_trials=True), Limits(max_trials=265), Limits(max_value_bits=-1)]:
            result = adapter.calculate_polynomial_witness(composite, limits)
            self.no_evidence(result)
            self.assertEqual(result['error']['code'], 'invalid_limits')
        for limits in [Limits(max_trials=0), Limits(max_substitution_term_visits=0), Limits(max_value_bits=0)]:
            result = adapter.calculate_polynomial_witness(composite, limits)
            self.no_evidence(result)
            self.assertEqual(result['error']['code'], 'resource_limit')
        witness = adapter.construct_polynomial_witness(self.req)['result']['result']['witness']
        limited = adapter.check_polynomial_witness(self.req, witness, Limits(max_evaluation_nodes=0))
        self.no_evidence(limited)
        self.assertEqual(limited['error']['code'], 'resource_limit')
        oversized = deepcopy(witness)
        oversized['left_value']['numerator'] = 1 << 4096
        self.no_evidence(adapter.check_polynomial_witness(self.req, oversized))

    def test_invalid_expected_request_is_error_not_false_witness(self):
        witness = adapter.construct_polynomial_witness(self.req)['result']['result']['witness']
        for change in [{'coefficient_field': 'F2'}, {'domain': 'quotient_ring'},
                       {'constraints': []}, {'operation': 'normalize'}]:
            self.no_evidence(adapter.check_polynomial_witness({**self.req, **change}, witness))
        self.no_evidence(adapter.check_polynomial_witness({}, {}))

    def test_snapshot_rejects_non_json_cycles_depth_nodes_and_bits(self):
        cycle = []; cycle.append(cycle)
        for raw in [cycle, {'operation': 'construct', 'request': cycle},
                    {'operation': 'construct', 'request': [0] * 16385},
                    {'operation': 'construct', 'request': {1: 0}},
                    {'operation': 'construct', 'request': object()},
                    {'operation': 'construct', 'request': 1.0},
                    {'operation': 'construct', 'request': 1 << 4096}]:
            self.no_evidence(adapter.calculate_polynomial_witness(raw))
        composite = {'operation': 'construct', 'request': self.req}
        before = deepcopy(composite)
        output = adapter.calculate_polynomial_witness(composite)
        self.assertEqual(composite, before)
        output['result']['request']['variables'][0] = 'mutated'
        self.assertEqual(composite, before)

    def test_strict_json_raw_byte_limit_and_duplicates(self):
        encoded = canonical({'operation': 'construct', 'request': self.req})
        exact = encoded + b' ' * (MAX_WIRE_BYTES - len(encoded))
        self.assertEqual(adapter.calculate_polynomial_witness_json(exact)['status'], 'success')
        self.no_evidence(adapter.calculate_polynomial_witness_json(exact + b' '))
        duplicate = encoded.replace(b'\"operation\":\"construct\"',
                                    b'\"operation\":\"construct\",\"\\u006fperation\":\"construct\"', 1)
        failure = adapter.calculate_polynomial_witness_json(duplicate)
        self.no_evidence(failure)
        self.assertEqual(failure['error']['code'], 'invalid_json')
        for raw in [b'{"operation":"construct","\\u006fperation":"verify"}',
                    b'{"operation":NaN}', b'{"operation":1.0}', b'\xff',
                    '[' * 500 + ']' * 500]:
            self.no_evidence(adapter.calculate_polynomial_witness_json(raw))
        self.no_evidence(adapter.calculate_polynomial_witness_json(' ' * (MAX_WIRE_BYTES - 1) + 'é'))

    def test_complete_output_byte_cap_withholds_every_mathematical_field(self):
        result = adapter.construct_polynomial_witness(self.req)
        size = len(canonical(result))
        with patch.object(adapter, 'MAX_OUTPUT_BYTES', size):
            self.assertEqual(adapter.construct_polynomial_witness(self.req)['status'], 'success')
        with patch.object(adapter, 'MAX_OUTPUT_BYTES', size - 1):
            self.no_evidence(adapter.construct_polynomial_witness(self.req))
        with patch.object(adapter, '_implementation', side_effect=OSError('private-sentinel')):
            failure = adapter.construct_polynomial_witness(self.req)
        self.no_evidence(failure)
        self.assertNotIn('private-sentinel', canonical(failure).decode())

    def test_bridge_rejection_differs_from_resource_error_and_recovers(self):
        witness = adapter.construct_polynomial_witness(self.req)['result']['result']['witness']
        false = deepcopy(witness); false['assignment']['x'] = 0
        rejected = self.call('check_polynomial_witness', {'request': self.req, 'witness': false})['result']
        self.assertIs(rejected['isError'], False)
        self.assertEqual(rejected['structuredContent']['assessment'], 'polynomial_witness_rejected')
        self.no_evidence(rejected['structuredContent']['receipt'], 'rejected')
        huge = deepcopy(self.req); huge['operands'][1] = q(1 << 256)
        failed = self.call('construct_polynomial_witness', {'request': huge})['result']
        self.assertIs(failed['isError'], True)
        self.assertEqual(failed['structuredContent']['assessment'], 'tool_error')
        self.no_evidence(failed['structuredContent']['receipt'])
        good = self.call('check_polynomial_witness', {'request': self.req, 'witness': witness})['result']
        self.assertEqual(good['structuredContent']['assessment'], 'polynomial_witness_valid')
        self.assertIs(good['isError'], False)

    def test_bridge_input_and_output_caps_withhold_partial_results(self):
        data = frame('tools/call', {'name': 'construct_polynomial_witness', 'arguments': {'request': self.req}})
        exact = data + b' ' * (server.MAX_FRAME_BYTES - len(data))
        self.assertIs(self.bridge.handle(exact)['result']['isError'], False)
        response = self.bridge.handle(exact + b' ')
        self.assertEqual(response['error']['code'], -32002)
        self.assertNotIn('result', response)
        success = self.bridge.handle(data)
        with patch.object(server, 'MAX_OUTPUT_BYTES', 100):
            encoded = server.encode_response(success)
        self.assertEqual(json.loads(encoded)['error']['code'], -32002)
        for private in (b'nonzero_evaluation', b'input_sha256', b'assignment'):
            self.assertNotIn(private, encoded)

    def test_cli_exit_codes_output_protection_and_byte_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            req_path = Path(directory) / 'request.json'
            witness_path = Path(directory) / 'witness.json'
            raw = canonical(self.req)
            req_path.write_bytes(raw + b' ' * (MAX_WIRE_BYTES - len(raw)))
            constructed = self.cli('polynomial-witness', req_path)
            self.assertEqual(constructed.returncode, 0, constructed.stderr)
            self.assertEqual(constructed.stderr, b'')
            receipt = json.loads(constructed.stdout)
            witness = receipt['result']['result']['witness']
            witness_path.write_bytes(canonical(witness))
            checked = self.cli('polynomial-witness-check', req_path, witness_path)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.scope(json.loads(checked.stdout))
            original = req_path.read_bytes()
            protected = self.cli('polynomial-witness', req_path, '--output', req_path)
            self.assertEqual(protected.returncode, 2)
            self.assertEqual(req_path.read_bytes(), original)
            self.assertEqual(protected.stdout, b'')
            req_path.write_bytes(original + b' ')
            failed = self.cli('polynomial-witness', req_path)
            self.assertEqual(failed.returncode, 2)
            self.no_evidence(json.loads(failed.stdout))
            req_path.write_bytes(raw)
            witness_path.write_bytes(canonical(receipt))
            rejected = self.cli('polynomial-witness-check', req_path, witness_path)
            self.assertEqual(rejected.returncode, 1)
            self.no_evidence(json.loads(rejected.stdout), 'rejected')
            witness_path.write_bytes(b' ' * (MAX_WIRE_BYTES + 1))
            failed = self.cli('polynomial-witness-check', req_path, witness_path)
            self.assertEqual(failed.returncode, 2)
            self.no_evidence(json.loads(failed.stdout))

    def assert_construction_bound(self, receipt, variables, trials, coordinate_sum):
        self.assertEqual(receipt['construction_bound'], {
            'kind': 'normalizer_total_degree_cap', 'variable_count': variables,
            'normalizer_total_degree_cap': 32, 'substitution_trial_bound': variables + 32,
            'actual_substitution_trials': trials, 'sum_chosen_coordinates': coordinate_sum,
            'legacy_hard_trial_cap': 264, 'exact_difference_degree_recomputed': False,
            'point_checker_certifies_bound': False})

    def balanced(self, kind, items):
        if not items:
            return q(1 if kind == 'multiply' else 0)
        if len(items) == 1:
            return items[0]
        middle = len(items) // 2
        return binary(kind, self.balanced(kind, items[:middle]), self.balanced(kind, items[middle:]))

    def test_sharp_forty_trial_bound_without_changing_frozen_limits(self):
        names = ['x'] + ['u' + str(i) for i in range(7)]
        roots = self.balanced('multiply', [binary('add', v('x'), q(-i)) for i in range(32)])
        req = request(roots, variables=names)
        receipt = adapter.construct_polynomial_witness(req, Limits(max_trials=40))
        self.assertEqual(receipt['status'], 'success')
        self.assert_construction_bound(receipt, 8, 40, 32)
        self.assertEqual(receipt['result']['result']['witness']['assignment'],
                         {'x': 32, **{'u' + str(i): 0 for i in range(7)}})
        self.assertEqual(Limits().max_trials, 264)
        self.no_evidence(adapter.construct_polynomial_witness(req, Limits(max_trials=39)))

    def test_sparse_power_sum_has_coarse_264_but_actual_nine(self):
        names = ['x' + str(i) for i in range(8)]
        expr = self.balanced('add', [self.balanced('multiply', [v(name)] * 32) for name in names])
        receipt = adapter.construct_polynomial_witness(request(expr, variables=names))
        self.assertEqual(receipt['status'], 'success')
        self.assert_construction_bound(receipt, 8, 9, 1)
        self.assertEqual(receipt['result']['result']['current_degree_trial_bound'], 264)
        self.assertEqual(receipt['result']['result']['initial_degree_trial_bound'], 264)

    def test_total_degree_metadata_constants_identity_cancellation_and_verify(self):
        self.assert_construction_bound(adapter.construct_polynomial_witness(request(q(1), variables=[])), 0, 0, 0)
        self.assert_construction_bound(adapter.construct_polynomial_witness(request(q(1), variables=['x', 'y'])), 2, 2, 0)
        identity = adapter.construct_polynomial_witness(request(q(0), variables=['x', 'y']))
        self.assertEqual(identity['result']['result']['kind'], 'coefficient_identity')
        self.assertNotIn('construction_bound', identity)
        power = self.balanced('multiply', [v('x')] * 32)
        left = binary('add', binary('add', power, binary('multiply', q(-1), power)), v('y'))
        req = request(left)
        receipt = adapter.construct_polynomial_witness(req)
        self.assert_construction_bound(receipt, 2, 3, 1)
        checked = adapter.check_polynomial_witness(req, receipt['result']['result']['witness'])
        self.assertEqual(checked['status'], 'success')
        self.assertNotIn('construction_bound', checked)
        # A truthful but nonminimal point need not satisfy the constructor's
        # total-degree cap corollary. Independent point checking still accepts.
        req = request(q(1))
        witness = adapter.construct_polynomial_witness(req)['result']['result']['witness']
        witness['assignment'] = {'x': 32, 'y': 32}
        checked = adapter.check_polynomial_witness(req, witness)
        self.assertEqual(checked['status'], 'success')
        self.assertNotIn('construction_bound', checked)

    def test_bound_metadata_requires_no_additional_normalization(self):
        lab = adapter.construct_polynomial_witness(self.req)['result']
        with patch.object(adapter, 'construct', return_value=lab), \
             patch('polynomial_witness._vendor.polynomial._normalize', side_effect=RuntimeError('extra normalization')) as normalization:
            receipt = adapter.construct_polynomial_witness(self.req)
        self.assertEqual(receipt['status'], 'success')
        self.assert_construction_bound(receipt, 2, 3, 1)
        normalization.assert_not_called()

    def test_bound_variable_count_uses_original_not_producer_repeated_request(self):
        lab = adapter.construct_polynomial_witness(self.req)['result']
        lab['request']['variables'] = ['invented']
        with patch.object(adapter, 'construct', return_value=lab):
            receipt = adapter.construct_polynomial_witness(self.req)
        self.assertEqual(receipt['status'], 'success')
        self.assert_construction_bound(receipt, 2, 3, 1)

    def test_bound_metadata_contradictions_fail_without_partial_evidence(self):
        original = adapter.construct_polynomial_witness(self.req)['result']
        for claimed in (True, 0, 40, 265):
            forged = deepcopy(original); forged['usage']['substitution_trials'] = claimed
            with patch('polynomial_witness.api.produce', return_value=forged):
                failure = adapter.construct_polynomial_witness(self.req)
            self.no_evidence(failure)
            self.assertNotIn('construction_bound', failure)
            self.assertEqual(failure['error']['code'], 'internal_invariant')
        req = request(q(1))
        forged = adapter.construct_polynomial_witness(req)['result']
        forged['result']['witness']['assignment'] = {'x': 32, 'y': 32}
        forged['usage']['substitution_trials'] = 66
        with patch('polynomial_witness.api.produce', return_value=forged):
            failure = adapter.construct_polynomial_witness(req)
        self.no_evidence(failure)
        self.assertEqual(failure['error']['code'], 'internal_invariant')

    def test_normal_and_optimized_cli_and_stdio_transcripts_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'request.json'; path.write_bytes(canonical(self.req))
            plain = self.cli('polynomial-witness', path, optimized=False)
            optimized = self.cli('polynomial-witness', path, optimized=True)
            self.assertEqual((plain.returncode, plain.stderr), (0, b''))
            self.assertEqual((optimized.returncode, optimized.stderr), (0, b''))
            self.assertEqual(plain.stdout, optimized.stdout)
        witness = json.loads(plain.stdout)['result']['result']['witness']
        transcript = b'\n'.join([
            frame('initialize', {'protocolVersion': server.PROTOCOL}, 'init'),
            frame('tools/list', identifier='list'),
            canonical({'jsonrpc': '2.0', 'method': 'tools/call', 'params':
                       {'name': 'construct_polynomial_witness', 'arguments': {'request': self.req}}}),
            frame('tools/call', {'name': 'construct_polynomial_witness', 'arguments': {'request': self.req}}, 'construct'),
            frame('tools/call', {'name': 'check_polynomial_witness', 'arguments': {'request': self.req, 'witness': {}}}, 'reject'),
            frame('tools/call', {'name': 'check_polynomial_witness', 'arguments': {'request': self.req, 'witness': witness}}, 'verify'),
            frame('ping', identifier='end')]) + b'\n'
        outputs = []
        for optimized in (False, True):
            command = [sys.executable, '-B'] + (['-O'] if optimized else []) + ['-m', 'foundation_math_bridge']
            process = subprocess.run(command, cwd=ROOT, input=transcript, capture_output=True, timeout=10)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
            outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])
        responses = [json.loads(line) for line in outputs[0].splitlines()]
        self.assertEqual([r['id'] for r in responses], ['init', 'list', 'construct', 'reject', 'verify', 'end'])
        self.assertEqual(responses[3]['result']['structuredContent']['assessment'], 'polynomial_witness_rejected')


if __name__ == '__main__':
    unittest.main()

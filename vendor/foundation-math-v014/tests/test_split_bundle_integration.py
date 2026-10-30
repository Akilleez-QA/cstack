"""Synthetic formal-splitting arithmetic, ingress and nonpromotion regressions.

No active research instance, geometric recognition, map-rank inference or formal
proof is exercised. Schema conformance and checked arithmetic remain distinct.
"""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.split_bundle import (calculate_split_bundle, check_split_bundle_certificate,
    split_bundle_error_receipt, split_bundle_exit_code, IMPLEMENTATION_FILES)
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL, MAX_FRAME_BYTES
from foundation_math_bridge.split_bundle_schemas import CALCULATE, CHECK, LABELS, SCOPE, ASSUMPTIONS

ROOT = Path(__file__).resolve().parents[1]
DIMS = (1, 2, 3, 4, 5, 6, 4, 2, 3)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def block(irrep='1', twist=0, multiplicity=1):
    return {'irrep': irrep, 'twist': twist, 'multiplicity': multiplicity}


def coh(bundle=None, twists=None):
    return {'schema': 'fm-split-bundle-request-v1', 'operation': 'cohomology',
            'bundle': [block()] if bundle is None else bundle,
            'twists': [0] if twists is None else twists}


def hom(source, target):
    return {'schema': 'fm-split-bundle-request-v1', 'operation': 'hom', 'source': source, 'target': target}


def one(label, multiplicity=1):
    return [multiplicity * int(item == label) for item in LABELS]


def invoke(name, arguments):
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                     'params': {'protocolVersion': PROTOCOL}})
    return bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                            'params': {'name': name, 'arguments': arguments}})


def run_python(arguments, *, input=None, optimized=False):
    return subprocess.run([sys.executable, '-B'] + (['-O'] if optimized else []) + arguments,
        cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), input=input,
        capture_output=True, timeout=90)


class SplitBundleIntegrationTests(unittest.TestCase):
    def assert_scope(self, receipt):
        self.assertEqual(receipt['schema_version'], 1)
        self.assertEqual(receipt['scope'], SCOPE)
        self.assertEqual(receipt['computational_field'], 'Q(sqrt(5))')
        for flag in ('formal_proof', 'runtime_goal_acceptance', 'geometric_realization', 'map_rank_claim'):
            self.assertIs(receipt[flag], False)
        for flag in ('table_group_identification_assumed', 'supplied_splitting_assumed'):
            self.assertIs(receipt[flag], True)

    def assert_error(self, receipt, code=None):
        self.assert_scope(receipt)
        self.assertEqual(receipt['status'], 'error')
        self.assertEqual(set(receipt), {'schema_version', 'scope', 'computational_field', 'formal_proof',
            'runtime_goal_acceptance', 'table_group_identification_assumed', 'supplied_splitting_assumed',
            'geometric_realization', 'map_rank_claim', 'status', 'error'})
        self.assertEqual(set(receipt['error']), {'code', 'message'})
        self.assertIs(type(receipt['error']['message']), str)
        if code is not None:
            self.assertEqual(receipt['error']['code'], code)

    def calculate(self, value):
        receipt = calculate_split_bundle(value)
        self.assert_scope(receipt)
        self.assertEqual(receipt['status'], 'success', receipt)
        return receipt['result']['certificate']

    def test_twelve_prior_tool_contracts_are_exactly_preserved_and_new_contracts_detached(self):
        frozen = json.loads((ROOT / 'docs/BASE-V09-BRIDGE-TOOLS.json').read_text())['tools']
        actual = tool_definitions()
        self.assertEqual(len(frozen), 12)
        self.assertEqual(len(actual), 19)
        self.assertEqual(actual[:12], frozen)
        self.assertEqual([item['name'] for item in actual[12:14]], [CALCULATE, CHECK])
        self.assertTrue(all(item['readOnly'] is True for item in actual[12:14]))
        actual[12]['inputSchema']['properties'].clear()
        actual[13]['outputSchema']['$defs']['block']['properties'].clear()
        self.assertTrue(tool_definitions()[12]['inputSchema']['properties'])
        self.assertTrue(tool_definitions()[13]['outputSchema']['$defs']['block']['properties'])

    def test_calculate_then_independent_check_and_exact_source_binding(self):
        value = coh([block('1', -10), block('1', -8), block('V', -8)], [8])
        produced = calculate_split_bundle(value)
        self.assertEqual((produced['status'], produced['operation']), ('success', 'calculate'))
        self.assertEqual(set(produced['result']), {'certificate', 'verification'})
        certificate = produced['result']['certificate']
        checked = check_split_bundle_certificate(value, certificate)
        self.assertEqual((checked['status'], checked['operation']), ('success', 'verify'))
        self.assertEqual(set(checked['result']), {'verification'})
        self.assertEqual(checked['result']['verification'], produced['result']['verification'])
        verification = checked['result']['verification']
        self.assertEqual(verification['schema'], 'fm-split-bundle-verification-v1')
        self.assertEqual(verification['status'], 'verified_arithmetic')
        self.assertEqual(certificate['assumptions'], ASSUMPTIONS)
        for obj in (produced, checked, certificate, verification):
            self.assertEqual(obj['scope'], SCOPE)
            self.assertEqual(obj['request_sha256'], sha256(canonical(value)).hexdigest())
        for receipt in (produced, checked):
            self.assert_scope(receipt)
            self.assertEqual(receipt['implementation']['name'], 'foundation-math-formal-split-bundle')
            self.assertEqual(receipt['implementation']['version'], '0.10.0-dev')
            self.assertEqual(receipt['implementation']['source_sha256'],
                {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in IMPLEMENTATION_FILES})
        self.assertEqual(verification['certificate_sha256'], sha256(canonical(certificate)).hexdigest())
        for flag in ('runtime_acceptance', 'lean_proof', 'geometric_realization'):
            self.assertIs(verification[flag], False)

    def test_negative_h1_control_does_not_replace_cohomology_with_euler(self):
        result = self.calculate(coh([block('1', -10), block('1', -8), block('V', -8)], [8]))['result']
        row = result['twists'][0]
        self.assertEqual(row['h0']['multiplicities'], [a + b for a, b in zip(one('1'), one('V'))])
        self.assertEqual(row['h1']['multiplicities'], one('1'))
        self.assertEqual(row['euler']['multiplicities'], one('V'))
        self.assertEqual(result['bundle'], {'rank': 5, 'degree': -42})
        self.assertEqual((row['rank'], row['degree']), (5, -2))
        self.assertEqual((row['h0']['dimension'], row['h1']['dimension'], row['euler']['dimension']), (4, 1, 3))

    def test_equal_euler_characters_do_not_identify_splittings_or_cohomology(self):
        twists = [-64, -5, -2, -1, 0, 1, 2, 5, 64]
        left = self.calculate(coh([block('1', 0), block('1', -2)], twists))['result']['twists']
        right = self.calculate(coh([block('W', -1)], twists))['result']['twists']
        for a, b in zip(left, right):
            self.assertEqual(a['euler'], b['euler'])
        self.assertEqual(left[4]['h0']['multiplicities'], one('1'))
        self.assertEqual(left[4]['h1']['multiplicities'], one('1'))
        self.assertEqual(right[4]['h0']['multiplicities'], [0] * 9)
        self.assertEqual(right[4]['h1']['multiplicities'], [0] * 9)

    def test_zero_signed_dimension_can_be_a_nonzero_proper_virtual_character(self):
        row = self.calculate(coh([block('W'), block('1', -2, 2)]))['result']['twists'][0]
        euler = row['euler']
        self.assertEqual(euler['dimension'], 0)
        self.assertEqual(euler['multiplicities'], [-2, 1, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual((euler['classification'], euler['center_parity']), ('proper_virtual', 'mixed'))
        self.assertEqual((euler['even_dimension'], euler['odd_dimension']), (-2, 2))
        self.assertEqual(euler['negative_multiplicities'], {'1': -2})
        self.assertEqual(row['h0']['classification'], 'genuine')
        self.assertEqual(row['h1']['classification'], 'genuine')

    def test_all_physical_labels_all_cohomology_regimes_and_riemann_roch(self):
        twists = [-64, -2, -1, 0, 1, 2, 64]
        for label, dim in zip(LABELS, DIMS):
            result = self.calculate(coh([block(label, 0, 3)], twists))['result']
            for twist, row in zip(twists, result['twists']):
                with self.subTest(label=label, twist=twist):
                    self.assertEqual(row['h0']['dimension'], 3 * dim * max(twist + 1, 0))
                    self.assertEqual(row['h1']['dimension'], 3 * dim * max(-twist - 1, 0))
                    self.assertEqual(row['euler']['dimension'], row['degree'] + row['rank'])
                    self.assertEqual((row['rank'], row['degree']), (3 * dim, 3 * dim * twist))
                    self.assertEqual(row['euler']['multiplicities'],
                        [a - b for a, b in zip(row['h0']['multiplicities'], row['h1']['multiplicities'])])
            self.assertEqual(result['twists'][1]['h1']['multiplicities'], one(label, 3))
            self.assertEqual(result['twists'][3]['h0']['multiplicities'], one(label, 3))
        self.assertEqual(self.calculate(coh(twists=[2]))['result']['twists'][0]['h0']['multiplicities'], one('A'))

    def test_hom_space_dimension_is_not_map_rank_and_orientation_matters(self):
        result = self.calculate(hom([block('W', -3)], [block('W', -3)]))['result']
        self.assertEqual(result['equivariant_hom_dimension'], 1)
        self.assertEqual(result['hom_character']['dimension'], 4)
        self.assertEqual(result['hom_character']['multiplicities'], [1, 0, 1, 0, 0, 0, 0, 0, 0])
        self.assertEqual(result['conclusion'], 'dimension_of_equivariant_map_space_only_no_map_rank_or_embedding_claim')
        self.assertNotIn('map_rank', result)
        self.assertNotIn('embedding_exists', result)
        for a, b in [('W', 'Wp'), ('A', 'V')]:
            self.assertEqual(self.calculate(hom([block(a)], [block(b)]))['result']['equivariant_hom_dimension'], 0)
        self.assertEqual(self.calculate(hom([block('1', 1)], [block()]))['result']['hom_character']['dimension'], 0)
        self.assertEqual(self.calculate(hom([block()], [block('1', 1)]))['result']['hom_character']['multiplicities'], one('W'))

    def test_zero_bundles_zero_multiplicities_duplicate_blocks_and_detached_data(self):
        for value in (coh([], [-64, -1, 0, 64]), coh([block('V', 64, 0)], [64])):
            for row in self.calculate(value)['result']['twists']:
                self.assertEqual(row['rank'], 0)
                for key in ('h0', 'h1', 'euler'):
                    self.assertEqual(row[key]['multiplicities'], [0] * 9)
                    self.assertEqual((row[key]['classification'], row[key]['center_parity']), ('genuine', 'zero'))
        for value in (hom([], []), hom([], [block()]), hom([block()], [])):
            self.assertEqual(self.calculate(value)['result']['equivariant_hom_dimension'], 0)
        value = coh([block('V', 0, 2), block('V', 0, 3)], [0])
        certificate = self.calculate(value)
        self.assertEqual(certificate['result']['twists'][0]['h0']['multiplicities'], one('V', 5))
        value['bundle'][0]['multiplicity'] = 9
        self.assertEqual(certificate['request']['bundle'][0]['multiplicity'], 2)

    def test_count_multiplicity_and_extreme_degree_boundaries(self):
        value = coh([block(LABELS[i % 9], 64, 1000000) for i in range(32)], list(range(33, 65)))
        result = self.calculate(value)['result']
        self.assertEqual(len(result['twists']), 32)
        self.assertEqual(result['twists'][-1]['h0']['dimension'], result['bundle']['rank'] * 129)
        row = self.calculate(coh([block('1', -64)], [-64]))['result']['twists'][0]
        self.assertEqual(row['h1']['dimension'], 127)
        result = self.calculate(hom([block('W', -64, 1000000)], [block('Wp', 64, 1000000)]))['result']
        self.assertEqual(result['hom_character']['dimension'], 4 * 129 * 1000000 ** 2)
        for value in (coh([block()] * 33), coh(twists=list(range(33))), coh([block(multiplicity=1000001)]),
                      coh([block(twist=65)]), coh(twists=[-65])):
            self.assert_error(calculate_split_bundle(value), 'E_BUDGET')

    def test_invalid_requests_are_rejected_at_both_independent_boundaries(self):
        good = coh(); certificate = self.calculate(good)
        invalid = [None, [], {}, {'schema': 'fm-split-bundle-request-v1', 'operation': 'map_rank'}]
        for key, values in [('multiplicity', [-1, 1000001, True, 1.0, '1', None]),
                            ('twist', [-65, 65, True, 1.0, '0', None]),
                            ('irrep', ['wp', 'B', 'A=V', 'W=Wp', 'trivial', 0, None])]:
            for value in values:
                request = coh(); request['bundle'][0][key] = value; invalid.append(request)
        for twists in ([], [0, 0], [65], [-65], [True], [1.0], list(range(33)), None):
            invalid.append(coh(twists=twists) if twists is not None else {**good, 'twists': None})
        for replacement in ({'schema': 'wrong'}, {'operation': []}, {'bundle': [block()] * 33},
                            {'bundle': {}}, {'bundle': None}, {'source': []}):
            invalid.append({**good, **replacement})
        for key in ('limits', 'path', 'code', 'command', 'group', 'point', 'map_rank', 'geometric_realization', 'formal_proof'):
            invalid.append({**good, key: True})
        bad = coh(); del bad['bundle'][0]['irrep']; invalid.append(bad)
        bad = coh(); bad['bundle'][0]['selected_point'] = [0, 0]; invalid.append(bad)
        for value in invalid:
            with self.subTest(value=value):
                self.assert_error(calculate_split_bundle(value))
                self.assert_error(check_split_bundle_certificate(value, certificate))

    def test_nonplain_python_values_cycles_and_global_data_budgets(self):
        class IntSubclass(int): pass
        class StrSubclass(str): pass
        class DictSubclass(dict): pass
        class ListSubclass(list): pass
        good = coh(); certificate = self.calculate(good)
        invalid = [DictSubclass(good), {**good, 'bundle': ListSubclass(good['bundle'])},
                   {**good, 'schema': StrSubclass(good['schema'])}, coh([block(multiplicity=IntSubclass(1))]),
                   {'x': 'a' * 257}, {'x': [0] * 8192}, {'x': 1 << 300}]
        cycle = []; cycle.append(cycle); invalid.append(cycle)
        for value in invalid:
            self.assert_error(calculate_split_bundle(value))
            self.assert_error(check_split_bundle_certificate(value, certificate))
        candidates = [None, [], DictSubclass(certificate)]
        for key, value in [('schema', StrSubclass(certificate['schema'])), ('extra', cycle),
                           ('extra', 'a' * 257), ('extra', [0] * 8192), ('extra', 1 << 300)]:
            bad = deepcopy(certificate); bad[key] = value; candidates.append(bad)
        bad = deepcopy(certificate); bad['result']['twists'] = ListSubclass(bad['result']['twists']); candidates.append(bad)
        for value in candidates:
            self.assert_error(check_split_bundle_certificate(good, value))

    def test_every_certificate_claim_and_class_value_is_recomputed(self):
        value = coh([block('1', -10), block('1', -8), block('V', -8)], [8])
        certificate = self.calculate(value)
        paths = [('schema',), ('catalog_sha256',), ('request_sha256',), ('scope',),
                 ('request', 'bundle', 0, 'twist'), ('result', 'bundle', 'rank'), ('result', 'bundle', 'degree')]
        paths += [('assumptions', key) for key in ASSUMPTIONS]
        paths += [('result', 'twists', 0, key) for key in ('twist', 'rank', 'degree')]
        for kind in ('h0', 'h1', 'euler'):
            base = ('result', 'twists', 0, kind)
            paths += [base + ('multiplicities', i) for i in range(9)]
            paths += [base + (key,) for key in ('dimension', 'classification', 'center_parity', 'even_dimension', 'odd_dimension')]
            paths += [base + ('class_values', i, j) for i in range(9) for j in range(4)]
        for path in paths:
            bad = deepcopy(certificate); target = bad
            for part in path[:-1]: target = target[part]
            before = target[path[-1]]; target[path[-1]] = before + 1 if type(before) is int else 'mutated'
            with self.subTest(path=path):
                self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')
        for replacement in (True, 1.0):
            bad = deepcopy(certificate); bad['result']['bundle']['rank'] = replacement
            self.assert_error(check_split_bundle_certificate(value, bad), 'E_TYPE')
        bad = deepcopy(certificate); bad['result']['twists'][0]['h1']['negative_multiplicities'] = {'1': -1}
        self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')
        bad = deepcopy(certificate); bad['result']['embedding_exists'] = 1
        self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')
        value = hom([block('W')], [block('W')]); certificate = self.calculate(value)
        for key, replacement in [('equivariant_hom_dimension', 2), ('conclusion', 'rank_one_map')]:
            bad = deepcopy(certificate); bad['result'][key] = replacement
            self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')

    def test_external_request_binding_rejects_equivalent_presentations_and_reordering(self):
        value = coh([block('V', 0, 2), block('V', 0, 3)], [-1, 0, 1])
        certificate = self.calculate(value)
        variants = [coh([block('V', 0, 5)], [-1, 0, 1]),
                    coh(list(reversed(value['bundle'])), [-1, 0, 1]),
                    coh(value['bundle'] + [block(multiplicity=0)], [-1, 0, 1]),
                    coh(value['bundle'], [1, 0, -1]), hom([block('V')], [block('V')])]
        for expected in variants:
            self.assert_error(check_split_bundle_certificate(expected, certificate), 'E_CERTIFICATE')
        bad = deepcopy(certificate); bad['request_sha256'] = '0' * 64
        self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')
        bad = deepcopy(certificate); bad['request'] = variants[0]
        bad['request_sha256'] = sha256(canonical(variants[0])).hexdigest()
        self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')

    def test_corrupt_producer_and_unexpected_exceptions_withhold_all_results(self):
        value = coh(); certificate = self.calculate(value)
        bad = deepcopy(certificate); bad['result']['twists'][0]['h0']['dimension'] += 1
        with patch('split_bundle.producer.calculate', return_value=bad):
            self.assert_error(calculate_split_bundle(value), 'E_CERTIFICATE')
        for target in ('split_bundle.producer.calculate', 'split_bundle.verifier.verify'):
            with patch(target, side_effect=RuntimeError('private implementation detail')):
                receipt = calculate_split_bundle(value)
                self.assert_error(receipt, 'E_INTERNAL')
                self.assertNotIn('private implementation detail', json.dumps(receipt))
        with patch('split_bundle.verifier.verify', side_effect=RuntimeError('private implementation detail')):
            receipt = check_split_bundle_certificate(value, certificate)
            self.assert_error(receipt, 'E_INTERNAL')
            self.assertNotIn('private implementation detail', json.dumps(receipt))
        with patch('foundation_math.split_bundle.Path.read_bytes', side_effect=OSError('private source path')):
            for receipt in (calculate_split_bundle(value), check_split_bundle_certificate(value, certificate)):
                self.assert_error(receipt, 'E_INTERNAL')
                self.assertNotIn('private source path', json.dumps(receipt))

    def test_known_catalog_character_and_riemann_roch_errors_are_not_internal_errors(self):
        from character_ring.contract import DomainError
        from character_ring.verifier import VerificationError as CharacterVerificationError
        from split_bundle.verifier import VerificationError
        value = coh(); certificate = self.calculate(value)
        with patch('split_bundle.producer.catalog', side_effect=DomainError('E_CATALOG', 'fixed catalog rejected')):
            self.assert_error(calculate_split_bundle(value), 'E_CATALOG')
        for error in (CharacterVerificationError('E_CATALOG', 'fixed catalog rejected'),
                      CharacterVerificationError('E_CHARACTER', 'character decomposition rejected'),
                      VerificationError('E_RIEMANN_ROCH', 'signed dimension rejected')):
            with patch('split_bundle.verifier.check_catalog', side_effect=error):
                self.assert_error(calculate_split_bundle(value), error.code)
                self.assert_error(check_split_bundle_certificate(value, certificate), error.code)

    def test_checker_imports_neither_producer_nor_either_contract_normal_and_optimized(self):
        value = hom([block('W')], [block('Wp', 2)]); certificate = self.calculate(value)
        script = '''import importlib.abc,json,sys
forbidden=('split_bundle.producer','split_bundle.contract','character_ring.producer','character_ring.contract')
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in forbidden: raise RuntimeError('forbidden dependency '+fullname)
sys.meta_path.insert(0,Block())
from foundation_math.split_bundle import check_split_bundle_certificate
request,certificate=json.loads(sys.stdin.read())
receipt=check_split_bundle_certificate(request,certificate)
if receipt['status']!='success': raise RuntimeError(receipt)
if any(name in sys.modules for name in forbidden): raise RuntimeError('forbidden dependency loaded')
print(json.dumps(receipt,sort_keys=True))
'''
        outputs = []
        for optimized in (False, True):
            process = run_python(['-c', script], input=canonical([value, certificate]), optimized=optimized)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
            outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_dependency_import_failure_is_a_structured_sanitized_internal_error(self):
        script = '''import importlib.abc,json,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='split_bundle.verifier': raise ImportError('private dependency detail')
sys.meta_path.insert(0,Block())
from foundation_math.split_bundle import calculate_split_bundle,check_split_bundle_certificate
value=json.loads(sys.stdin.read())
print(json.dumps([calculate_split_bundle(value),check_split_bundle_certificate(value,{})]))
'''
        for optimized in (False, True):
            process = run_python(['-c', script], input=canonical(coh()), optimized=optimized)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
            for receipt in json.loads(process.stdout):
                self.assert_error(receipt, 'E_INTERNAL')
                self.assertNotIn('private dependency detail', json.dumps(receipt))

    def test_bridge_success_error_assessments_and_strict_argument_allowlists(self):
        value = coh(); certificate = self.calculate(value)
        for name, args, assessment in [(CALCULATE, {'request': value}, 'formal_split_bundle_arithmetic_checked'),
                (CHECK, {'request': value, 'certificate': certificate}, 'formal_split_bundle_certificate_valid')]:
            wire = invoke(name, args)['result']; self.assertIs(wire['isError'], False)
            content = wire['structuredContent']; self.assertEqual(content['assessment'], assessment)
            self.assertIs(content['formal_proof'], False); self.assertIs(content['runtime_goal_acceptance'], False)
            self.assert_scope(content['receipt'])
            for key in ('limits', 'path', 'command', 'code', 'group', 'formal_proof', 'map_rank'):
                self.assertEqual(invoke(name, {**args, key: True})['error']['code'], -32602)
            self.assertEqual(invoke(name, {})['error']['code'], -32602)
            bad = deepcopy(args); bad['request']['bundle'][0]['multiplicity'] = True
            failure = invoke(name, bad)['result']; self.assertTrue(failure['isError'])
            self.assertEqual(failure['structuredContent']['assessment'], 'tool_error')
            self.assert_error(failure['structuredContent']['receipt'], 'E_TYPE')

    def test_bridge_notifications_and_unexpected_exceptions_never_claim_results(self):
        for name, target in [(CALCULATE, 'calculate_split_bundle'), (CHECK, 'check_split_bundle_certificate')]:
            with patch('foundation_math_bridge.server.' + target, side_effect=RuntimeError('private detail')) as mocked:
                self.assertIsNone(Bridge().dispatch({'jsonrpc': '2.0', 'method': 'tools/call',
                    'params': {'name': name, 'arguments': {}}}))
                mocked.assert_not_called()
                args = {'request': coh()}
                if name == CHECK: args['certificate'] = {}
                failure = invoke(name, args)
                self.assertEqual(failure['error']['code'], -32603)
                self.assertNotIn('private detail', json.dumps(failure))
                self.assertNotIn('result', failure)

    def test_bridge_frame_cap_duplicate_numeric_ingress_and_recovery(self):
        bridge = Bridge()
        bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}})
        message = canonical({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                             'params': {'name': CALCULATE, 'arguments': {'request': coh()}}})
        self.assertFalse(bridge.handle(message + b' ' * (MAX_FRAME_BYTES - len(message)))['result']['isError'])
        self.assertEqual(bridge.handle(message + b' ' * (MAX_FRAME_BYTES + 1 - len(message)))['error']['code'], -32002)
        for raw in (b'{"id":1,"id":2}', b'NaN', b'1.0', b'\xff', b'[' * 81 + b']' * 81):
            self.assertIn('error', bridge.handle(raw))
        decimal = message.replace(b'"multiplicity":1', b'"multiplicity":1.0')
        self.assertEqual(bridge.handle(decimal)['error']['code'], -32700)
        self.assertFalse(bridge.handle(message)['result']['isError'])

    def test_bridge_stdio_normal_and_optimized_round_trips(self):
        value = coh(); certificate = self.calculate(value)
        messages = [
            {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}},
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': CALCULATE, 'arguments': {'request': value}}},
            {'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': CALCULATE, 'arguments': {'request': value}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': CHECK, 'arguments': {'request': value, 'certificate': certificate}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': CALCULATE, 'arguments': {'request': coh(twists=[0, 0])}}},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'ping', 'params': {}},
        ]
        wire = b'\n'.join(canonical(value) for value in messages) + b'\n'; outputs = []
        for optimized in (False, True):
            process = run_python(['-m', 'foundation_math_bridge'], input=wire, optimized=optimized)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
            replies = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual([reply['id'] for reply in replies], list(range(6)))
            self.assertEqual(replies[1]['result']['tools'], tool_definitions())
            self.assertFalse(replies[2]['result']['isError']); self.assertFalse(replies[3]['result']['isError'])
            self.assertTrue(replies[4]['result']['isError'])
            self.assert_error(replies[4]['result']['structuredContent']['receipt'], 'E_SCHEMA')
            self.assertEqual(replies[5]['result'], {}); outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_runtime_domain_registry_does_not_accept_receipts_or_new_domain_aliases(self):
        from foundation_math.domains import domain_handler, DomainError
        for name in ('split_bundle', 'formal_split_bundle', 'cohomology', 'hom', 'P(W)', 'Q(sqrt(5))',
                     SCOPE, CALCULATE, CHECK, 'fm-split-bundle-request-v1', 'fm-split-bundle-certificate-v1'):
            with self.assertRaises(DomainError): domain_handler(name)
        for name in ('Z', 'Q', 'polynomial_ring'):
            self.assertEqual(domain_handler(name).name, name)
        with self.assertRaises(DomainError): domain_handler(calculate_split_bundle(coh()))
        frozen = json.loads((ROOT / 'docs/BASE-V09-SOURCE-MANIFEST.json').read_text())
        # The adapter's presence must not modify runtime acceptance machinery.
        expected = frozen['files']['foundation_math/domains.py']
        self.assertEqual(sha256((ROOT / 'foundation_math/domains.py').read_bytes()).hexdigest(), expected)

    def test_cli_success_normal_and_optimized_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); source = folder / 'request.json'; certfile = folder / 'certificate.json'
            value = hom([block('W')], [block('W')]); certificate = self.calculate(value)
            source.write_bytes(canonical(value)); certfile.write_bytes(canonical(certificate))
            snapshots = (source.read_bytes(), certfile.read_bytes())
            for command in [('split-bundle-calculate', source), ('split-bundle-check', source, certfile)]:
                outputs = []
                for optimized in (False, True):
                    process = run_python(['-m', 'foundation_math', *map(str, command)], optimized=optimized)
                    self.assertEqual((process.returncode, process.stderr), (0, b''))
                    receipt = json.loads(process.stdout); self.assert_scope(receipt)
                    self.assertEqual(receipt['status'], 'success'); outputs.append(process.stdout)
                self.assertEqual(outputs[0], outputs[1])
            self.assertEqual((source.read_bytes(), certfile.read_bytes()), snapshots)
            output = folder / 'output.json'; output.write_text('preserve existing file')
            process = run_python(['-m', 'foundation_math', 'split-bundle-calculate', str(source), '--output', str(output)])
            self.assertEqual((process.returncode, process.stdout), (2, b''))
            self.assert_error(json.loads(process.stderr), 'E_USAGE')
            self.assertEqual(output.read_text(), 'preserve existing file')

    def test_cli_request_and_certificate_raw_byte_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'request.json'; certfile = Path(directory) / 'certificate.json'
            value = coh(); raw = canonical(value); cert_raw = canonical(self.calculate(value))
            source.write_bytes(raw + b' ' * (65536 - len(raw)))
            certfile.write_bytes(cert_raw + b' ' * (262144 - len(cert_raw)))
            for command in [('split-bundle-calculate', source), ('split-bundle-check', source, certfile)]:
                process = run_python(['-m', 'foundation_math', *map(str, command)])
                self.assertEqual((process.returncode, process.stderr), (0, b''))
            source.write_bytes(source.read_bytes() + b' ')
            process = run_python(['-m', 'foundation_math', 'split-bundle-calculate', str(source)])
            self.assertEqual((process.returncode, process.stdout), (2, b''))
            self.assert_error(json.loads(process.stderr), 'E_BUDGET')
            source.write_bytes(raw); certfile.write_bytes(certfile.read_bytes() + b' ')
            process = run_python(['-m', 'foundation_math', 'split-bundle-check', str(source), str(certfile)])
            self.assertEqual((process.returncode, process.stdout), (2, b''))
            self.assert_error(json.loads(process.stderr), 'E_BUDGET')

    def test_cli_error_streams_usage_and_strict_json_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'request.json'; certfile = Path(directory) / 'certificate.json'; certfile.write_text('{}')
            cases = [(b'{}', 'E_SCHEMA'), (b'{"schema":1,"schema":2}', 'E_JSON'), (b'NaN', 'E_TYPE'),
                     (b'\xff', 'E_JSON'), (canonical(coh([block(multiplicity=True)])), 'E_TYPE'),
                     (canonical(coh([block(multiplicity=1.0)])), 'E_TYPE'),
                     (b'{"x":' + b'1' * 91 + b'}', 'E_BUDGET'), (b'[' * 17 + b']' * 17, 'E_BUDGET')]
            for optimized in (False, True):
                for raw, code in cases:
                    source.write_bytes(raw)
                    process = run_python(['-m', 'foundation_math', 'split-bundle-calculate', str(source)], optimized=optimized)
                    self.assertEqual((process.returncode, process.stdout), (2, b''))
                    self.assert_error(json.loads(process.stderr), code)
                    self.assertNotIn(b'Traceback', process.stderr)
                source.write_bytes(canonical(coh()))
                for args, code in [(['split-bundle-calculate'], 'E_USAGE'),
                                   (['split-bundle-check', str(source)], 'E_USAGE'),
                                   (['split-bundle-check', str(source), str(certfile)], 'E_CERTIFICATE'),
                                   (['split-bundle-calculate', str(source) + '.absent'], 'E_IO')]:
                    process = run_python(['-m', 'foundation_math', *args], optimized=optimized)
                    self.assertEqual((process.returncode, process.stdout), (2, b''))
                    self.assert_error(json.loads(process.stderr), code)

    def test_cli_internal_failure_is_sanitized_with_exit_four(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'request.json'; source.write_bytes(canonical(coh()))
            script = '''import sys
from unittest.mock import patch
from foundation_math.split_bundle import split_bundle_cli
with patch('split_bundle.producer.calculate',side_effect=RuntimeError('private path or secret')):
 raise SystemExit(split_bundle_cli(['split-bundle-calculate',sys.argv[1]]))
'''
            for optimized in (False, True):
                process = run_python(['-c', script, str(source)], optimized=optimized)
                self.assertEqual((process.returncode, process.stdout), (4, b''))
                self.assert_error(json.loads(process.stderr), 'E_INTERNAL')
                self.assertNotIn(b'private path or secret', process.stderr)
                self.assertNotIn(b'Traceback', process.stderr)

    def test_error_normalization_and_exit_mapping(self):
        for code in ('E_USAGE', 'E_IO', 'E_JSON', 'E_TYPE', 'E_SCHEMA', 'E_BUDGET', 'E_CATALOG',
                     'E_CHARACTER', 'E_EXPECTATION', 'E_CERTIFICATE', 'E_RIEMANN_ROCH', 'E_INTERNAL'):
            receipt = split_bundle_error_receipt(code, 'test rejection'); self.assert_error(receipt, code)
            self.assertEqual(split_bundle_exit_code(receipt), 4 if code == 'E_INTERNAL' else 2)
        for code in ('UNTRUSTED_CODE', None, True, []):
            receipt = split_bundle_error_receipt(code, 'private detail')
            self.assert_error(receipt, 'E_INTERNAL'); self.assertNotIn('private detail', json.dumps(receipt))
        self.assertEqual(split_bundle_exit_code(calculate_split_bundle(coh())), 0)

    def test_structural_schema_does_not_claim_arithmetic_or_request_binding(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('No preinstalled jsonschema; installation is not attempted')
        definitions = {item['name']: item for item in tool_definitions()}
        for name in (CALCULATE, CHECK):
            for key in ('inputSchema', 'outputSchema'):
                Draft202012Validator.check_schema(definitions[name][key])
        value = coh(); certificate = self.calculate(value)
        check = Draft202012Validator(definitions[CHECK]['inputSchema'])
        bad = deepcopy(certificate); bad['result']['twists'][0]['h0']['dimension'] += 1
        self.assertTrue(check.is_valid({'request': value, 'certificate': bad}))
        self.assert_error(check_split_bundle_certificate(value, bad), 'E_CERTIFICATE')
        alternative = coh([block(), block(multiplicity=0)])
        self.assertTrue(check.is_valid({'request': alternative, 'certificate': certificate}))
        self.assert_error(check_split_bundle_certificate(alternative, certificate), 'E_CERTIFICATE')
        decimal = coh([block(multiplicity=1.0)])
        self.assertTrue(Draft202012Validator(definitions[CALCULATE]['inputSchema']).is_valid({'request': decimal}))
        self.assert_error(calculate_split_bundle(decimal), 'E_TYPE')
        for name, args in [(CALCULATE, {'request': value}), (CHECK, {'request': value, 'certificate': certificate})]:
            content = invoke(name, args)['result']['structuredContent']
            validator = Draft202012Validator(definitions[name]['outputSchema'])
            self.assertTrue(validator.is_valid(content))
            for flag in ('formal_proof', 'runtime_goal_acceptance', 'geometric_realization', 'map_rank_claim'):
                bad = deepcopy(content); bad['receipt'][flag] = True
                self.assertFalse(validator.is_valid(bad))
            for flag in ('table_group_identification_assumed', 'supplied_splitting_assumed'):
                bad = deepcopy(content); bad['receipt'][flag] = False
                self.assertFalse(validator.is_valid(bad))


if __name__ == '__main__':
    unittest.main()

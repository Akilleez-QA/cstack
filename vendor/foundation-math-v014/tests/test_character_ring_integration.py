"""Synthetic fixed-table integration, strict ingress and nonpromotion checks.

These tests do not identify the table with a group, instantiate geometry, or
establish a formal theorem. Frozen arithmetic review is a separate artifact.
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

from foundation_math.character_ring import (
    calculate_character, check_character_certificate, IMPLEMENTATION_FILES,
    character_error_receipt, character_exit_code,
)
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL, MAX_FRAME_BYTES
from foundation_math_bridge.character_ring_schemas import CALCULATE, CHECK, LABELS, SCOPE

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = (1, 2, 3, 4, 5, 6, 4, 2, 3)
SIGNS = (1, -1, 1, -1, 1, -1, 1, -1, 1)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def irrep(label):
    return {'op': 'irrep', 'label': label}


def virtual(coefficients):
    return {'op': 'virtual', 'coefficients': coefficients}


def binary(op, left, right):
    return {'op': op, 'left': left, 'right': right}


def request(expression=None, classification='any', equals=None):
    return {'schema': 'fm-character-request-v1',
            'expression': irrep('W') if expression is None else expression,
            'expectation': {'classification': classification, 'equals': equals}}


def invoke(name, arguments):
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                     'params': {'protocolVersion': PROTOCOL}})
    return bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                            'params': {'name': name, 'arguments': arguments}})


def run_python(arguments, *, cwd=ROOT, input=None, optimized=False):
    return subprocess.run([sys.executable, '-B'] + (['-O'] if optimized else []) + arguments,
        cwd=cwd, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), input=input,
        capture_output=True, timeout=30)


class CharacterRingIntegrationTests(unittest.TestCase):
    def assert_scope(self, receipt):
        self.assertEqual(receipt['schema_version'], 1)
        self.assertEqual(receipt['scope'], SCOPE)
        self.assertEqual(receipt['computational_field'], 'Q(sqrt(5))')
        for flag in ('formal_proof', 'runtime_goal_acceptance', 'geometric_realization'):
            self.assertIs(receipt[flag], False)
        self.assertIs(receipt['table_group_identification_assumed'], True)

    def assert_error(self, receipt, code=None):
        self.assert_scope(receipt)
        self.assertEqual(receipt['status'], 'error')
        self.assertEqual(set(receipt) - {'error', 'status'}, {
            'schema_version', 'scope', 'computational_field', 'formal_proof',
            'runtime_goal_acceptance', 'table_group_identification_assumed', 'geometric_realization'})
        self.assertEqual(set(receipt['error']), {'code', 'message'})
        self.assertIs(type(receipt['error']['message']), str)
        self.assertNotIn('result', receipt)
        self.assertNotIn('certificate', receipt)
        if code is not None:
            self.assertEqual(receipt['error']['code'], code)

    def test_original_ten_tools_are_unchanged_and_appended_schemas_are_detached(self):
        frozen = json.loads((ROOT / 'docs/BASE-V08-BRIDGE-TOOLS.json').read_text())['tools']
        actual = tool_definitions()
        self.assertEqual(len(frozen), 10)
        self.assertEqual(len(actual), 19)
        self.assertEqual(actual[:10], frozen)
        self.assertEqual([tool['name'] for tool in actual[10:12]], [CALCULATE, CHECK])
        self.assertTrue(all(tool['readOnly'] is True for tool in actual[10:12]))
        actual[10]['inputSchema']['properties'].clear()
        actual[11]['outputSchema']['$defs']['request']['properties'].clear()
        self.assertTrue(tool_definitions()[10]['inputSchema']['properties'])
        self.assertTrue(tool_definitions()[11]['outputSchema']['$defs']['request']['properties'])

    def test_calculate_verifies_and_check_never_returns_producer_certificate(self):
        value = request(binary('tensor', irrep('W'), irrep('W')), 'genuine', {'1': 1, 'A': 1})
        produced = calculate_character(value)
        self.assert_scope(produced)
        self.assertEqual((produced['status'], produced['operation']), ('success', 'calculate'))
        self.assertEqual(set(produced['result']), {'verification', 'certificate'})
        certificate = produced['result']['certificate']
        checked = check_character_certificate(value, certificate)
        self.assert_scope(checked)
        self.assertEqual((checked['status'], checked['operation']), ('success', 'verify'))
        self.assertEqual(set(checked['result']), {'verification'})
        self.assertEqual(checked['result']['verification'], produced['result']['verification'])
        for receipt in (produced, checked):
            verification = receipt['result']['verification']
            self.assertEqual(verification['schema'], 'fm-character-verification-v1')
            self.assertEqual(verification['status'], 'verified_arithmetic')
            self.assertEqual(verification['scope'], SCOPE)
            self.assertIs(verification['runtime_acceptance'], False)
            self.assertIs(verification['lean_proof'], False)

    def test_request_certificate_and_source_hashes_bind_exact_bytes(self):
        value = request(binary('tensor', irrep('P'), irrep('W')), 'genuine', {'T6': 1, 'Wp': 1})
        produced = calculate_character(value)
        certificate = produced['result']['certificate']
        verification = produced['result']['verification']
        request_hash = sha256(canonical(value)).hexdigest()
        self.assertEqual(produced['request_sha256'], request_hash)
        self.assertEqual(certificate['request_sha256'], request_hash)
        self.assertEqual(verification['request_sha256'], request_hash)
        self.assertEqual(verification['certificate_sha256'], sha256(canonical(certificate)).hexdigest())
        self.assertEqual(check_character_certificate(value, certificate)['request_sha256'], request_hash)
        implementation = produced['implementation']
        self.assertEqual(implementation['name'], 'foundation-math-fixed-character-ring')
        self.assertEqual(implementation['version'], '0.9.0-dev')
        self.assertEqual(set(implementation['source_sha256']), set(IMPLEMENTATION_FILES))
        for name, digest in implementation['source_sha256'].items():
            self.assertEqual(digest, sha256((ROOT / name).read_bytes()).hexdigest())
        self.assertEqual(certificate['catalog_sha256'], sha256((ROOT / 'character_ring/catalog.json').read_bytes()).hexdigest())

    def test_nine_physical_labels_keep_dimensions_and_support_parities(self):
        for index, label in enumerate(LABELS):
            result = calculate_character(request(irrep(label)))['result']['verification']['result']
            self.assertEqual(result['multiplicities'], [int(i == index) for i in range(9)])
            self.assertEqual(result['dimension'], DIMENSIONS[index])
            self.assertEqual(result['center_parity'], 'even' if SIGNS[index] == 1 else 'odd')
            self.assertEqual(result['classification'], 'genuine')
        for first, second in [('A', 'V'), ('W', 'Wp')]:
            a = calculate_character(request(irrep(first)))['result']['certificate']
            b = calculate_character(request(irrep(second)))['result']['certificate']
            self.assertEqual(a['result']['dimension'], b['result']['dimension'])
            self.assertNotEqual(a['result']['multiplicities'], b['result']['multiplicities'])
            self.assertNotEqual(a['class_values'], b['class_values'])
        square = calculate_character(request(binary('tensor', irrep('W'), irrep('W'))))
        self.assertEqual(square['result']['verification']['result']['multiplicities'], [1, 0, 1, 0, 0, 0, 0, 0, 0])
        self.assert_error(calculate_character(request(binary('tensor', irrep('W'), irrep('W')), equals={'1': 1, 'V': 1})), 'E_EXPECTATION')

    def test_exact_field_values_are_not_floats_or_dimension_only_summaries(self):
        certificate = calculate_character(request(irrep('W')))['result']['certificate']
        self.assertTrue(any(value[2] for value in certificate['class_values']))
        for value in certificate['class_values']:
            self.assertEqual(len(value), 4)
            self.assertTrue(all(type(component) is int for component in value))
            self.assertGreater(value[1], 0)
            self.assertGreater(value[3], 0)
        self.assertEqual(certificate['class_values'][0], [2, 1, 0, 1])

    def test_zero_signed_virtual_and_mixed_parity_are_distinguished(self):
        cases = [({}, 0, 'genuine', 'zero', 0, 0),
                 ({'A': 1, 'W': -1}, 1, 'proper_virtual', 'mixed', 3, -2),
                 ({'A': 1, 'V': -1}, 0, 'proper_virtual', 'even', 0, 0),
                 ({'W': -1}, -2, 'proper_virtual', 'odd', 0, -2),
                 ({'1': 1, 'W': 1}, 3, 'genuine', 'mixed', 1, 2)]
        for coefficients, dimension, classification, parity, even, odd in cases:
            value = request(virtual(coefficients), classification, coefficients)
            receipt = calculate_character(value)
            self.assertEqual(receipt['status'], 'success')
            result = receipt['result']['verification']['result']
            self.assertEqual((result['dimension'], result['classification'], result['center_parity'],
                              result['even_dimension'], result['odd_dimension']),
                             (dimension, classification, parity, even, odd))
            self.assertEqual(result['negative_multiplicities'], {k: v for k, v in coefficients.items() if v < 0})
            self.assertEqual(check_character_certificate(value, receipt['result']['certificate'])['status'], 'success')

    def test_expectation_failure_is_not_arithmetic_or_theorem_success(self):
        for value in [request(virtual({'A': 1, 'W': -1}), 'genuine'),
                      request(virtual({}), 'proper_virtual'), request(irrep('W'), equals={'Wp': 1})]:
            self.assert_error(calculate_character(value), 'E_EXPECTATION')
            neutral = deepcopy(value); neutral['expectation'] = {'classification': 'any', 'equals': None}
            certificate = calculate_character(neutral)['result']['certificate']
            self.assert_error(check_character_certificate(value, certificate), 'E_EXPECTATION')
            wire = invoke(CALCULATE, {'request': value})['result']
            self.assertTrue(wire['isError'])
            self.assertEqual(wire['structuredContent']['assessment'], 'tool_error')
            self.assert_error(wire['structuredContent']['receipt'], 'E_EXPECTATION')

    def test_certificate_mutations_scope_and_noncanonical_fractions_are_rejected(self):
        value = request(irrep('W'))
        certificate = calculate_character(value)['result']['certificate']
        variants = []
        for key, replacement in [('scope', 'formal_proof'), ('schema', 'other'),
                                  ('catalog_sha256', '0' * 64), ('request_sha256', '0' * 64)]:
            bad = deepcopy(certificate); bad[key] = replacement; variants.append(bad)
        for key in ('formal_proof', 'runtime_goal_acceptance', 'geometric_realization', 'theorem_refuted'):
            bad = deepcopy(certificate); bad[key] = True; variants.append(bad)
        for key, replacement in [('dimension', 3), ('classification', 'proper_virtual'),
                                  ('center_parity', 'even'), ('odd_dimension', 0),
                                  ('negative_multiplicities', {'W': -1}), ('multiplicities', [0] * 9)]:
            bad = deepcopy(certificate); bad['result'][key] = replacement; variants.append(bad)
        bad = deepcopy(certificate); bad['class_values'][0] = [4, 2, 0, 1]; variants.append(bad)
        bad = deepcopy(certificate); bad['class_values'][0][0] = True; variants.append(bad)
        bad = deepcopy(certificate); bad['class_values'].pop(); variants.append(bad)
        bad = deepcopy(certificate); bad['result']['multiplicities'][1] = 1.0; variants.append(bad)
        for bad in variants:
            self.assert_error(check_character_certificate(value, bad), 'E_CERTIFICATE')
        wire = invoke(CHECK, {'request': value, 'certificate': variants[0]})['result']
        self.assertTrue(wire['isError'])
        self.assertEqual(wire['structuredContent']['assessment'], 'tool_error')
        self.assert_error(wire['structuredContent']['receipt'], 'E_CERTIFICATE')

    def test_external_request_binding_includes_expression_and_expectation(self):
        value = request(irrep('W'))
        certificate = calculate_character(value)['result']['certificate']
        alternatives = [request(irrep('Wp')), request(binary('add', irrep('W'), virtual({}))),
                        request(irrep('W'), 'genuine'), request(irrep('W'), equals={'W': 1})]
        for expected in alternatives:
            self.assert_error(check_character_certificate(expected, certificate), 'E_CERTIFICATE')
        forged = deepcopy(certificate)
        forged['request'] = request(irrep('Wp'))
        forged['request_sha256'] = sha256(canonical(forged['request'])).hexdigest()
        self.assert_error(check_character_certificate(forged['request'], forged), 'E_CERTIFICATE')
        self.assert_error(check_character_certificate({'schema': 'invented'}, certificate), 'E_SCHEMA')

    def test_both_requests_and_certificates_are_detached_from_callers(self):
        value = request(virtual({'W': 1}))
        original = deepcopy(value)
        produced = calculate_character(value)
        self.assertEqual(value, original)
        certificate = produced['result']['certificate']
        before = deepcopy(certificate)
        checked = check_character_certificate(value, certificate)
        self.assertEqual(certificate, before)
        value['expression']['coefficients']['W'] = 77
        self.assertEqual(certificate['request'], original)
        certificate['result']['multiplicities'][1] = 77
        self.assertEqual(checked['result']['verification']['result']['multiplicities'][1], 1)

    def test_nonplain_types_custom_keys_cycles_and_unknown_fields_fail_closed(self):
        class DictSubclass(dict): pass
        class ListSubclass(list): pass
        class StrSubclass(str): pass
        class IntSubclass(int): pass
        class EqualKey:
            def __hash__(self): return hash('schema')
            def __eq__(self, other): return other == 'schema'
        good = request()
        bad_requests = [None, [], DictSubclass(good), {**good, 'schema': StrSubclass(good['schema'])},
                        {EqualKey(): good['schema'], 'expression': good['expression'], 'expectation': good['expectation']},
                        request(virtual({'W': True})), request(virtual({'W': 1.0})),
                        request(virtual({'W': '1'})), request(virtual({'W': IntSubclass(1)})),
                        request(virtual({StrSubclass('W'): 1})), request(virtual({'W': 0})),
                        request({'op': 'symmetric_power', 'degree': True}),
                        request({'op': 'symmetric_power', 'degree': 2, 'representation': irrep('Wp')}),
                        request(irrep('3')), request(irrep('A/V')), request({'op': 'eval', 'source': '1+1'})]
        for key in ('limits', 'path', 'code', 'command', 'group', 'formal_proof', 'theorem'):
            bad_requests.append({**good, key: True})
        cycle = binary('add', irrep('1'), virtual({})); cycle['right'] = cycle
        bad_requests.append(request(cycle))
        for value in bad_requests:
            self.assert_error(calculate_character(value))
        certificate = calculate_character(good)['result']['certificate']
        for value in bad_requests:
            self.assert_error(check_character_certificate(value, certificate))
        bad_certificates = [None, [], DictSubclass(certificate)]
        changed = deepcopy(certificate); changed['class_values'] = ListSubclass(changed['class_values']); bad_certificates.append(changed)
        changed = deepcopy(certificate); changed['schema'] = StrSubclass(changed['schema']); bad_certificates.append(changed)
        changed = deepcopy(certificate); changed['cycle'] = changed; bad_certificates.append(changed)
        for candidate in bad_certificates:
            self.assert_error(check_character_certificate(good, candidate))

    def test_degree_coefficient_depth_and_node_boundaries(self):
        for degree in (0, 1, 2, 256):
            value = request({'op': 'symmetric_power', 'degree': degree})
            produced = calculate_character(value)
            self.assertEqual(produced['status'], 'success')
            self.assertEqual(produced['result']['verification']['result']['dimension'], degree + 1)
        for degree in (-1, 257):
            self.assert_error(calculate_character(request({'op': 'symmetric_power', 'degree': degree})), 'E_BUDGET')
        endpoint = (1 << 63) - 1
        for coefficient in (-endpoint, endpoint):
            self.assertEqual(calculate_character(request(virtual({'1': coefficient})))['status'], 'success')
        for coefficient in (-(1 << 63), 1 << 63):
            self.assert_error(calculate_character(request(virtual({'1': coefficient}))), 'E_BUDGET')
        expression = irrep('1')
        for _ in range(15): expression = binary('add', expression, virtual({}))
        self.assertEqual(calculate_character(request(expression))['status'], 'success')
        self.assert_error(calculate_character(request(binary('add', expression, virtual({})))), 'E_BUDGET')
        expression = irrep('1')
        for _ in range(6): expression = binary('add', expression, expression)
        self.assertEqual(calculate_character(request(expression))['result']['verification']['result']['dimension'], 64)
        self.assert_error(calculate_character(request(binary('add', expression, virtual({})))), 'E_BUDGET')

    def test_intermediate_overflow_is_rejected_before_ancestor_cancellation(self):
        leaf = virtual({'1': (1 << 63) - 1})
        square = binary('tensor', leaf, leaf)
        fourth = binary('tensor', square, square)
        self.assertEqual(calculate_character(request(fourth))['status'], 'success')
        overflow = binary('tensor', fourth, virtual({'1': 32}))
        self.assert_error(calculate_character(request(overflow)), 'E_BUDGET')
        self.assert_error(calculate_character(request(binary('subtract', overflow, overflow))), 'E_BUDGET')

    def test_producer_outputs_are_independently_checked_before_success(self):
        value = request()
        certificate = calculate_character(value)['result']['certificate']
        bad = deepcopy(certificate); bad['result']['dimension'] += 1
        with patch('character_ring.producer.calculate', return_value=bad):
            self.assert_error(calculate_character(value), 'E_CERTIFICATE')
        with patch('character_ring.verifier.verify', side_effect=RuntimeError('secret exception')):
            for receipt in (calculate_character(value), check_character_certificate(value, certificate)):
                self.assert_error(receipt, 'E_INTERNAL')
                self.assertNotIn('secret exception', json.dumps(receipt))
        with patch('character_ring.producer.calculate', side_effect=RuntimeError('secret exception')):
            self.assert_error(calculate_character(value), 'E_INTERNAL')

    def test_catalog_and_provenance_failures_withhold_all_acceptance(self):
        from character_ring.contract import DomainError
        from character_ring.verifier import VerificationError
        value = request()
        certificate = calculate_character(value)['result']['certificate']
        with patch('character_ring.producer.catalog', side_effect=DomainError('E_CATALOG', 'fixed catalog rejected')):
            self.assert_error(calculate_character(value), 'E_CATALOG')
        with patch('character_ring.verifier.check_catalog', side_effect=VerificationError('E_CATALOG', 'fixed catalog rejected')):
            self.assert_error(calculate_character(value), 'E_CATALOG')
            self.assert_error(check_character_certificate(value, certificate), 'E_CATALOG')
        with patch('foundation_math.character_ring.Path.read_bytes', side_effect=OSError('private source path')):
            for receipt in (calculate_character(value), check_character_certificate(value, certificate)):
                self.assert_error(receipt, 'E_INTERNAL')
                self.assertNotIn('private source path', json.dumps(receipt))

    def test_verifier_only_import_has_no_producer_or_contract_dependency(self):
        value = request(binary('tensor', irrep('P'), irrep('W')))
        certificate = calculate_character(value)['result']['certificate']
        script = '''import importlib.abc,json,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname in ('character_ring.producer','character_ring.contract'):
   raise RuntimeError('forbidden dependency: '+fullname)
sys.meta_path.insert(0,Block())
from foundation_math.character_ring import check_character_certificate
request,certificate=json.loads(sys.stdin.read())
receipt=check_character_certificate(request,certificate)
if receipt['status']!='success': raise RuntimeError(receipt)
if any(n in sys.modules for n in ('character_ring.producer','character_ring.contract')):
 raise RuntimeError('producer/parser dependency loaded')
print(json.dumps(receipt,sort_keys=True))
'''
        outputs = []
        for optimized in (False, True):
            result = run_python(['-c', script], input=canonical([value, certificate]), optimized=optimized)
            self.assertEqual((result.returncode, result.stderr), (0, b''))
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_dependency_import_failure_is_structured_internal_error(self):
        script = '''import importlib.abc,json,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname=='character_ring.verifier': raise ImportError('private dependency detail')
sys.meta_path.insert(0,Block())
from foundation_math.character_ring import calculate_character,check_character_certificate
value=json.loads(sys.stdin.read())
print(json.dumps([calculate_character(value),check_character_certificate(value,{})]))
'''
        result = run_python(['-c', script], input=canonical(request()))
        self.assertEqual((result.returncode, result.stderr), (0, b''))
        for receipt in json.loads(result.stdout):
            self.assert_error(receipt, 'E_INTERNAL')
            self.assertNotIn('private dependency detail', json.dumps(receipt))

    def test_bridge_success_errors_and_exact_argument_allowlists(self):
        value = request()
        certificate = calculate_character(value)['result']['certificate']
        for name, args, assessment in [(CALCULATE, {'request': value}, 'fixed_character_arithmetic_checked'),
                (CHECK, {'request': value, 'certificate': certificate}, 'fixed_character_certificate_valid')]:
            wire = invoke(name, args)['result']
            self.assertIs(wire['isError'], False)
            content = wire['structuredContent']
            self.assertEqual(content['assessment'], assessment)
            self.assertIs(content['formal_proof'], False)
            self.assertIs(content['runtime_goal_acceptance'], False)
            self.assert_scope(content['receipt'])
            for key in ('limits', 'path', 'command', 'code', 'group', 'formal_proof'):
                self.assertEqual(invoke(name, {**args, key: True})['error']['code'], -32602)
            self.assertEqual(invoke(name, {})['error']['code'], -32602)
            bad_args = deepcopy(args); bad_args['request']['expression'] = virtual({'W': True})
            failed = invoke(name, bad_args)['result']
            self.assertTrue(failed['isError'])
            self.assertEqual(failed['structuredContent']['assessment'], 'tool_error')
            self.assert_error(failed['structuredContent']['receipt'], 'E_TYPE')

    def test_bridge_notifications_and_unexpected_exceptions_never_claim_results(self):
        for name, target in [(CALCULATE, 'calculate_character'), (CHECK, 'check_character_certificate')]:
            bridge = Bridge()
            with patch('foundation_math_bridge.server.' + target, side_effect=RuntimeError('private detail')) as mock:
                self.assertIsNone(bridge.dispatch({'jsonrpc': '2.0', 'method': 'tools/call',
                    'params': {'name': name, 'arguments': {}}}))
                mock.assert_not_called()
                args = {'request': request()}
                if name == CHECK: args['certificate'] = {}
                failed = invoke(name, args)
                self.assertEqual(failed['error']['code'], -32603)
                self.assertNotIn('private detail', json.dumps(failed))
                self.assertNotIn('result', failed)

    def test_bridge_frame_cap_duplicate_json_and_recovery(self):
        bridge = Bridge()
        bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}})
        message = canonical({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                             'params': {'name': CALCULATE, 'arguments': {'request': request()}}})
        self.assertFalse(bridge.handle(message + b' ' * (MAX_FRAME_BYTES - len(message)))['result']['isError'])
        self.assertEqual(bridge.handle(message + b' ' * (MAX_FRAME_BYTES + 1 - len(message)))['error']['code'], -32002)
        for raw in (b'{"id":1,"id":2}', b'NaN', b'1.0', b'\xff', b'[' * 81 + b']' * 81):
            self.assertIn('error', bridge.handle(raw))
        self.assertFalse(bridge.handle(message)['result']['isError'])

    def test_bridge_stdio_round_trip_lists_and_calls_all_new_tools(self):
        value = request()
        certificate = calculate_character(value)['result']['certificate']
        messages = [
            {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}},
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
             'params': {'name': CALCULATE, 'arguments': {'request': value}}},
            {'jsonrpc': '2.0', 'method': 'tools/call',
             'params': {'name': CALCULATE, 'arguments': {'request': value}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
             'params': {'name': CHECK, 'arguments': {'request': value, 'certificate': certificate}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
             'params': {'name': CALCULATE, 'arguments': {'request': request(irrep('W'), equals={'Wp': 1})}}},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'ping', 'params': {}},
        ]
        wire = b'\n'.join(canonical(message) for message in messages) + b'\n'
        outputs = []
        for optimized in (False, True):
            process = run_python(['-m', 'foundation_math_bridge'], input=wire, optimized=optimized)
            self.assertEqual((process.returncode, process.stderr), (0, b''))
            replies = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual([reply['id'] for reply in replies], list(range(6)))
            self.assertEqual(replies[1]['result']['tools'], tool_definitions())
            self.assertFalse(replies[2]['result']['isError'])
            self.assertFalse(replies[3]['result']['isError'])
            self.assertTrue(replies[4]['result']['isError'])
            self.assert_error(replies[4]['result']['structuredContent']['receipt'], 'E_EXPECTATION')
            self.assertEqual(replies[5]['result'], {})
            outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_runtime_registry_rejects_character_receipts_and_domain_aliases(self):
        from foundation_math.domains import domain_handler, DomainError
        for name in ('character_ring', 'fixed_character', 'Q(sqrt(5))', SCOPE, CALCULATE, CHECK,
                     'fm-character-request-v1', 'fm-character-certificate-v1'):
            with self.assertRaises(DomainError): domain_handler(name)
        for name in ('Z', 'Q', 'polynomial_ring'):
            self.assertEqual(domain_handler(name).name, name)
        with self.assertRaises(DomainError): domain_handler(calculate_character(request()))

    def test_cli_success_normal_and_optimized_are_identical_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            value = request(binary('tensor', irrep('P'), irrep('W')), 'genuine', {'T6': 1, 'Wp': 1})
            certificate = calculate_character(value)['result']['certificate']
            source, certfile = folder / 'request.json', folder / 'certificate.json'
            source.write_bytes(canonical(value)); certfile.write_bytes(canonical(certificate))
            snapshots = (source.read_bytes(), certfile.read_bytes())
            for command in [('character-calculate', source), ('character-check', source, certfile)]:
                outputs = []
                for optimized in (False, True):
                    result = run_python(['-m', 'foundation_math', *map(str, command)], optimized=optimized)
                    self.assertEqual((result.returncode, result.stderr), (0, b''))
                    receipt = json.loads(result.stdout)
                    self.assert_scope(receipt)
                    self.assertEqual(receipt['status'], 'success')
                    outputs.append(result.stdout)
                self.assertEqual(outputs[0], outputs[1])
            self.assertEqual((source.read_bytes(), certfile.read_bytes()), snapshots)
            output = folder / 'output.json'; output.write_text('preserve existing file')
            result = run_python(['-m', 'foundation_math', 'character-calculate', str(source), '--output', str(output)])
            self.assertEqual((result.returncode, result.stdout), (2, b''))
            self.assert_error(json.loads(result.stderr), 'E_USAGE')
            self.assertEqual(output.read_text(), 'preserve existing file')

    def test_cli_request_and_certificate_raw_byte_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); source = folder / 'request.json'; certfile = folder / 'certificate.json'
            value = request(); raw = canonical(value)
            certificate = calculate_character(value)['result']['certificate']; cert_raw = canonical(certificate)
            source.write_bytes(raw + b' ' * (65536 - len(raw)))
            certfile.write_bytes(cert_raw + b' ' * (262144 - len(cert_raw)))
            for command in [('character-calculate', source), ('character-check', source, certfile)]:
                result = run_python(['-m', 'foundation_math', *map(str, command)])
                self.assertEqual((result.returncode, result.stderr), (0, b''))
            source.write_bytes(source.read_bytes() + b' ')
            result = run_python(['-m', 'foundation_math', 'character-calculate', str(source)])
            self.assertEqual((result.returncode, result.stdout), (2, b''))
            self.assert_error(json.loads(result.stderr), 'E_BUDGET')
            source.write_bytes(raw); certfile.write_bytes(certfile.read_bytes() + b' ')
            result = run_python(['-m', 'foundation_math', 'character-check', str(source), str(certfile)])
            self.assertEqual((result.returncode, result.stdout), (2, b''))
            self.assert_error(json.loads(result.stderr), 'E_BUDGET')

    def test_cli_error_stream_codes_and_usage_are_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'request.json'; certfile = Path(directory) / 'certificate.json'
            certfile.write_text('{}')
            cases = [(b'{}', 'E_SCHEMA', 2), (b'{"schema":1,"schema":2}', 'E_JSON', 2),
                     (b'NaN', 'E_TYPE', 2), (b'\xff', 'E_JSON', 2),
                     (canonical(request(virtual({'W': True}))), 'E_TYPE', 2),
                     (canonical(request(irrep('W'), equals={'Wp': 1})), 'E_EXPECTATION', 3),
                     (b'{"x":' + b'1' * 91 + b'}', 'E_BUDGET', 2)]
            for optimized in (False, True):
                for raw, code, exit_code in cases:
                    source.write_bytes(raw)
                    result = run_python(['-m', 'foundation_math', 'character-calculate', str(source)], optimized=optimized)
                    self.assertEqual((result.returncode, result.stdout), (exit_code, b''))
                    self.assert_error(json.loads(result.stderr), code)
                    self.assertNotIn(b'Traceback', result.stderr)
                source.write_bytes(canonical(request()))
                for args, code in [(['character-calculate'], 'E_USAGE'),
                                   (['character-check', str(source)], 'E_USAGE'),
                                   (['character-check', str(source), str(certfile)], 'E_CERTIFICATE'),
                                   (['character-calculate', str(source) + '.absent'], 'E_IO')]:
                    result = run_python(['-m', 'foundation_math', *args], optimized=optimized)
                    self.assertEqual((result.returncode, result.stdout), (2, b''))
                    self.assert_error(json.loads(result.stderr), code)

    def test_cli_injected_internal_failure_has_exit_four_and_no_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'request.json'; source.write_bytes(canonical(request()))
            script = '''import sys
from unittest.mock import patch
from foundation_math.character_ring import character_cli
with patch('character_ring.producer.calculate',side_effect=RuntimeError('private path or secret')):
 raise SystemExit(character_cli(['character-calculate',sys.argv[1]]))
'''
            for optimized in (False, True):
                result = run_python(['-c', script, str(source)], optimized=optimized)
                self.assertEqual((result.returncode, result.stdout), (4, b''))
                self.assert_error(json.loads(result.stderr), 'E_INTERNAL')
                self.assertNotIn(b'private path or secret', result.stderr)
                self.assertNotIn(b'Traceback', result.stderr)

    def test_error_code_normalization_and_exit_mapping(self):
        for code, expected in [('E_EXPECTATION', 3), ('E_INTERNAL', 4), ('E_SCHEMA', 2),
                               ('E_CERTIFICATE', 2), ('E_BUDGET', 2)]:
            receipt = character_error_receipt(code, 'test rejection')
            self.assert_error(receipt, code)
            self.assertEqual(character_exit_code(receipt), expected)
        self.assert_error(character_error_receipt('UNTRUSTED_CODE', 'private detail'), 'E_INTERNAL')
        self.assertEqual(character_exit_code(calculate_character(request())), 0)


if __name__ == '__main__':
    unittest.main()

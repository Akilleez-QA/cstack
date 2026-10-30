"""Synthetic integration contracts, ingress, schema and nonpromotion tests."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.linear_systems import (
    Limits, MathError, calculate_system, calculate_system_json,
    solve_system, check_system_certificate, IMPLEMENTATION_FILES,
)
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL, MAX_FRAME_BYTES
from foundation_math_bridge.linear_systems_schemas import SOLVE, CHECK

ROOT = Path(__file__).resolve().parents[1]


def system(a, b, cols=None, domain='Z'):
    return {'matrix': {'domain': domain, 'rows': len(a),
                       'cols': len(a[0]) if a else (cols or 0), 'entries': a}, 'rhs': b}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def invoke(name, arguments):
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}})
    return bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                            'params': {'name': name, 'arguments': arguments}})


class LinearSystemIntegrationTests(unittest.TestCase):
    def test_all_eight_prior_tool_definitions_are_exactly_pinned(self):
        frozen = json.loads((ROOT/'docs/BASE-V07-PORTABLE-BRIDGE-TOOLS.json').read_text())['tools']
        tools = tool_definitions()
        self.assertEqual(len(tools), 19)
        self.assertEqual(tools[:8], frozen)
        self.assertEqual([t['name'] for t in tools[8:10]], [SOLVE, CHECK])
        tools[8]['inputSchema']['properties'].clear()
        self.assertTrue(tool_definitions()[8]['inputSchema']['properties'])

    def test_both_outcomes_are_successful_checked_results(self):
        for value, outcome in [(system([[2]], [1]), 'consistent'),
                               (system([[1], [1]], [0, 1]), 'inconsistent')]:
            receipt = solve_system(value)
            self.assertEqual(receipt['status'], 'success')
            self.assertEqual(receipt['result']['verification']['outcome'], outcome)
            certificate = receipt['result']['certificate']
            checked = check_system_certificate(value, certificate)
            self.assertEqual(checked['status'], 'success')
            self.assertNotIn('certificate', checked['result'])
            for name, args in [(SOLVE, {'system': value}), (CHECK, {'system': value, 'certificate': certificate})]:
                response = invoke(name, args)['result']
                self.assertFalse(response['isError'])
                self.assertNotEqual(response['structuredContent']['assessment'], 'tool_error')
                actual = response['structuredContent']['receipt']['result']['verification']
                self.assertEqual(actual['outcome'], outcome)
                for flag in ('formal_proof', 'runtime_goal_acceptance', 'family_or_generic_claim'):
                    self.assertIs(actual[flag], False)
                    self.assertIs(receipt[flag], False)
        self.assertEqual(solve_system(system([[2]], [1]))['result']['verification']['particular'], [{'num': 1, 'den': 2}])

    def test_empty_shapes_and_full_kernel_are_retained(self):
        for value, outcome, nullity in [(system([], [], 3), 'consistent', 3),
                                        (system([[], []], [0, 0]), 'consistent', 0),
                                        (system([[], []], [0, 1]), 'inconsistent', None),
                                        (system([], [], 0), 'consistent', 0),
                                        (system([[0, 0]], [0]), 'consistent', 2)]:
            result = solve_system(value)['result']['verification']
            self.assertEqual(result['outcome'], outcome)
            self.assertEqual(result['rows'], value['matrix']['rows'])
            self.assertEqual(result['cols'], value['matrix']['cols'])
            self.assertEqual(result.get('nullity'), nullity)

    def test_receipt_binds_request_and_all_implementation_bytes(self):
        value = system([[2, 1]], [1])
        request = {'operation': 'solve', 'system': value}
        receipt = calculate_system(request)
        self.assertEqual(receipt['request_sha256'], sha256(canonical(request)).hexdigest())
        hashes = receipt['implementation']['source_sha256']
        self.assertEqual(set(hashes), set(IMPLEMENTATION_FILES))
        self.assertEqual(len(hashes), 13)
        for name, digest in hashes.items():
            self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(), digest)

    def test_bad_certificates_and_external_rebindings_never_carry_results(self):
        for value in [system([[2, 1]], [1]), system([[0]], [1])]:
            certificate = solve_system(value)['result']['certificate']
            variants = [{}, {**certificate, 'formal_proof': True}]
            bad = deepcopy(certificate)
            if bad['outcome'] == 'consistent':
                bad['particular'][0] = 33
            else:
                bad['rhs_pairing'] = 0
            variants.append(bad)
            for forged in variants:
                receipt = check_system_certificate(value, forged)
                self.assertEqual(receipt['status'], 'error')
                self.assertNotIn('result', receipt)
                self.assertNotIn('certificate', receipt)
                wire = invoke(CHECK, {'system': value, 'certificate': forged})['result']
                self.assertTrue(wire['isError'])
                self.assertEqual(wire['structuredContent']['assessment'], 'tool_error')
            changed = deepcopy(value); changed['rhs'][0] += 1
            self.assertEqual(check_system_certificate(changed, certificate)['status'], 'error')
            changed = deepcopy(value); changed['matrix']['domain'] = 'Q'
            self.assertEqual(check_system_certificate(changed, certificate)['status'], 'error')

    def test_only_explicit_exact_one_rhs_inputs_are_supported(self):
        value = system([[1]], [0])
        bad_values = [None, [], {'matrix': value['matrix'], 'rhs': [[0]]},
                      {**value, 'rhs': [True]}, {**value, 'rhs': [0.0]},
                      {**value, 'rhs': ['0']}, {**value, 'rhs': [{'num': 0, 'den': 2}]},
                      {**value, 'rhs': [{'num': 1, 'den': 2}]}, {**value, 'rhs': []},
                      {**value, 'family': True}, {**value, 'domain': 'Q'}]
        for bad in bad_values:
            self.assertEqual(solve_system(bad)['status'], 'error', bad)
        for key in ('limits', 'path', 'command', 'code', 'backend', 'formal_proof'):
            self.assertEqual(calculate_system({'operation': 'solve', 'system': value, key: {}})['status'], 'error')
            self.assertEqual(invoke(SOLVE, {'system': value, key: {}})['error']['code'], -32602)
        for op in ('generic_rank', 'integer_solve', 'eval', None, True, []):
            self.assertEqual(calculate_system({'operation': op, 'system': value})['status'], 'error')

    def test_strict_json_ingress_and_byte_boundary(self):
        request = canonical({'operation': 'solve', 'system': system([], [], 0)})
        cap = Limits().max_input_bytes
        self.assertEqual(calculate_system_json(request + b' ' * (cap-len(request)))['status'], 'success')
        for raw in [request + b' ' * (cap+1-len(request)), b'NaN', b'{}{}', b'\xff',
                    b'{"operation":"solve","operation":"verify"}', b'['*33+b']'*33]:
            self.assertEqual(calculate_system_json(raw)['status'], 'error')

    def test_nonbuiltin_cycles_and_resource_errors(self):
        class DictSubclass(dict): pass
        bad = []; bad.append(bad)
        for request in [DictSubclass(operation='solve', system=system([], [], 0)), bad,
                        {'operation': 'solve', 'system': system([[1 << 129]], [1])}]:
            self.assertEqual(calculate_system(request)['status'], 'error')
        value = system([[2]], [1])
        for limits in [Limits(max_output_bytes=0), Limits(max_work=0), Limits(max_cells=0),
                       Limits(max_dimension=0), Limits(max_nodes=0), Limits(max_input_bytes=0)]:
            receipt = solve_system(value, limits)
            self.assertEqual(receipt['status'], 'error')
            self.assertNotIn('result', receipt)
        with patch('foundation_math.linear_systems._implementation', side_effect=OSError('hidden path')):
            receipt = solve_system(value)
            self.assertEqual(receipt['error']['code'], 'INTERNAL_ERROR')
            self.assertNotIn('hidden path', json.dumps(receipt))
        with patch('foundation_math.linear_systems.handle_request', side_effect=RuntimeError('defect')):
            with self.assertRaises(RuntimeError): solve_system(value)

    def test_final_receipt_output_limit_is_checked_not_just_backend(self):
        value = system([[1]], [1])
        good = solve_system(value)
        exact = len(canonical(good))
        self.assertEqual(solve_system(value, Limits(max_output_bytes=exact))['status'], 'success')
        self.assertEqual(solve_system(value, Limits(max_output_bytes=exact-1))['status'], 'error')

    def test_notifications_do_not_execute_new_tools(self):
        bridge = Bridge()
        for name, target in [(SOLVE, 'solve_system'), (CHECK, 'check_system_certificate')]:
            with patch('foundation_math_bridge.server.' + target, side_effect=RuntimeError('must not execute')) as mock:
                self.assertIsNone(bridge.dispatch({'jsonrpc': '2.0', 'method': 'tools/call',
                                                  'params': {'name': name, 'arguments': {}}}))
                mock.assert_not_called()

    def test_unexpected_backend_exception_is_generic_bridge_error(self):
        with patch('foundation_math_bridge.server.solve_system', side_effect=RuntimeError('private detail')):
            response = invoke(SOLVE, {'system': system([], [], 0)})
            self.assertEqual(response['error']['code'], -32603)
            self.assertNotIn('private detail', json.dumps(response))

    def test_wire_ingress_exact_frame_bound_and_error_recovery(self):
        bridge = Bridge()
        init = {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}}
        bridge.dispatch(init)
        msg = canonical({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                         'params': {'name': SOLVE, 'arguments': {'system': system([], [], 0)}}})
        self.assertIn('result', bridge.handle(msg+b' '*(MAX_FRAME_BYTES-len(msg))))
        self.assertEqual(bridge.handle(msg+b' '*(MAX_FRAME_BYTES+1-len(msg)))['error']['code'], -32002)
        for malformed in [b'{"id":1,"id":2}', b'NaN', b'1.2', b'\xff', b'['*81+b']'*81]:
            self.assertIn('error', bridge.handle(malformed))
        self.assertIn('result', bridge.handle(msg))

    def test_unregistered_runtime_domains_remain_rejected(self):
        from foundation_math.domains import domain_handler, DomainError
        for name in ('linear_system', 'rational_linear_system', 'one_explicit_linear_system', SOLVE, CHECK):
            with self.assertRaises(DomainError): domain_handler(name)

    def test_file_cli_success_errors_optimized_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); value = system([[1], [1]], [0, 1])
            source = root/'system.json'; certfile=root/'certificate.json'; output=root/'receipt.json'
            source.write_bytes(canonical(value)); certificate=solve_system(value)['result']['certificate']
            certfile.write_bytes(canonical(certificate))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            for command in [('system-solve', source), ('system-check', source, certfile)]:
                outputs = []
                for optimized in (False, True):
                    p=subprocess.run([sys.executable,'-B']+(['-O'] if optimized else [])+['-m','foundation_math', *map(str,command)], cwd=ROOT,env=env,capture_output=True,timeout=10)
                    self.assertEqual((p.returncode,p.stderr),(0,b'')); outputs.append(p.stdout)
                    self.assertEqual(json.loads(p.stdout)['result']['verification']['outcome'], 'inconsistent')
                self.assertEqual(outputs[0],outputs[1])
            output.write_text('do not overwrite')
            p=subprocess.run([sys.executable,'-B','-m','foundation_math','system-solve',str(source),'--output',str(output)],cwd=ROOT,env=env,capture_output=True,timeout=10)
            self.assertEqual(p.returncode,2);self.assertEqual(output.read_text(),'do not overwrite')
            for data in [b'{}',b'NaN',b'{"matrix":{},"matrix":{}}', b' '*1000001]:
                source.write_bytes(data)
                p=subprocess.run([sys.executable,'-B','-m','foundation_math','system-solve',str(source)],cwd=ROOT,env=env,capture_output=True,timeout=10)
                self.assertEqual((p.returncode,p.stderr),(2,b''));self.assertEqual(json.loads(p.stdout)['status'],'error')


if __name__ == '__main__': unittest.main()

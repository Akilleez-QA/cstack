from dataclasses import replace
from fractions import Fraction
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from exact_linalg.contract import (Budget, Limits, MathError, check_tree,
                                  loads_bounded, parse_coefficient)
from exact_linalg.producer import produce
from exact_linalg.api import handle_request
from exact_linalg.verifier import verify


BASE = {'domain': 'Z', 'rows': 2, 'cols': 2, 'entries': [[2, 1], [1, 1]]}


class ContractTests(unittest.TestCase):
    def reject_matrix(self, value, code=None, limits=Limits()):
        with self.assertRaises(MathError) as context:
            produce(value, limits)
        if code is not None:
            self.assertEqual(context.exception.code, code)

    def test_unknown_domain_and_matrix_fields(self):
        for domain in ('R', 'F2', 'QQ', '', 2, True, None):
            value = dict(BASE, domain=domain)
            self.reject_matrix(value, 'INVALID_DOMAIN')
        self.reject_matrix(dict(BASE, symbolic='x'), 'INVALID_SCHEMA')
        value = dict(BASE)
        del value['cols']
        self.reject_matrix(value, 'INVALID_SCHEMA')

    def test_dimensions_are_explicit_strict_and_bounded(self):
        for key in ('rows', 'cols'):
            for number in (True, False, -1, 17, '2', None, 2.0):
                self.reject_matrix(dict(BASE, **{key: number}))
        for entries in ([], [[1]], [[1, 2]], [[1, 2], [3]], [[1, 2], [3, 4], [5, 6]], ((1, 2), (3, 4))):
            self.reject_matrix(dict(BASE, entries=entries))
        self.reject_matrix({'domain': 'Z', 'rows': 3, 'cols': 0, 'entries': []}, 'DIMENSION_MISMATCH')
        self.reject_matrix({'domain': 'Z', 'rows': 0, 'cols': 3, 'entries': [[]]}, 'DIMENSION_MISMATCH')

    def test_no_float_bool_expression_or_foreign_types(self):
        for value in (True, False, 0.1, float('inf'), float('nan'), '1/2', 'x', '1+1', Fraction(1, 2), None, [1, 2], (1, 2), {'numerator': 1, 'denominator': 2}):
            self.reject_matrix({'domain': 'Q', 'rows': 1, 'cols': 1, 'entries': [[value]]})

    def test_canonical_rational_contract(self):
        for value in ({'num': 2, 'den': 4}, {'num': 1, 'den': -2}, {'num': 1, 'den': 0},
                      {'num': 1, 'den': 1}, {'num': 0, 'den': 2}, {'num': True, 'den': 2},
                      {'num': 1, 'den': True}, {'num': 1, 'den': 2, 'extra': 3}):
            self.reject_matrix({'domain': 'Q', 'rows': 1, 'cols': 1, 'entries': [[value]]})
        self.assertEqual(parse_coefficient({'num': -5, 'den': 7}, 128, '$'), Fraction(-5, 7))
        self.reject_matrix({'domain': 'Z', 'rows': 1, 'cols': 1, 'entries': [[{'num': 1, 'den': 2}]]}, 'INVALID_COEFFICIENT')

    def test_input_bit_ceiling_exact_boundary(self):
        allowed = {'domain': 'Z', 'rows': 1, 'cols': 1, 'entries': [[2**127]]}
        verify(allowed, produce(allowed))
        self.reject_matrix(dict(allowed, entries=[[2**128]]), 'BIT_LIMIT')
        self.reject_matrix(dict(allowed, entries=[[-2**128]]), 'BIT_LIMIT')
        self.reject_matrix({'domain': 'Q', 'rows': 1, 'cols': 1, 'entries': [[{'num': 1, 'den': 2**128 + 1}]]}, 'BIT_LIMIT')
        self.reject_matrix(dict(allowed, entries=[[1 << 100000]]), 'BIT_LIMIT')

    def test_limits_only_lower_ceiling(self):
        for changes in ({'max_dimension': 17}, {'max_work': 2000001}, {'max_dimension': True}, {'max_input_bits': 0},
                        {'max_intermediate_bits': 127}, {'max_nodes': -1}, {'max_output_bytes': 1000001}):
            with self.assertRaises(MathError) as context:
                Limits(**changes)
            self.assertEqual(context.exception.code, 'INVALID_LIMIT')
        self.reject_matrix(BASE, 'INVALID_LIMIT', limits={})

    def test_each_resource_guard(self):
        self.reject_matrix(BASE, 'INVALID_INTEGER', Limits(max_dimension=1))
        self.reject_matrix(BASE, 'CELL_LIMIT', Limits(max_cells=3))
        self.reject_matrix(BASE, 'WORK_LIMIT', Limits(max_work=0))
        self.reject_matrix(BASE, 'OPERATION_LIMIT', Limits(max_operations=0))
        self.reject_matrix(BASE, 'OUTPUT_LIMIT', Limits(max_output_bytes=1))
        self.reject_matrix(BASE, 'INPUT_LIMIT', Limits(max_input_bytes=1))
        self.reject_matrix(BASE, 'NODE_LIMIT', Limits(max_nodes=1))
        self.reject_matrix(BASE, 'DEPTH_LIMIT', Limits(max_depth=1))
        self.reject_matrix({'domain': 'Z', 'rows': 2, 'cols': 1, 'entries': [[0], [0]]}, 'CELL_LIMIT', Limits(max_cells=2))
        self.reject_matrix({'domain': 'Z', 'rows': 0, 'cols': 2, 'entries': []}, 'CELL_LIMIT', Limits(max_cells=2))
        self.reject_matrix({'domain': 'Z', 'rows': 2, 'cols': 2, 'entries': [[7, 6], [6, 7]]},
                           'BIT_LIMIT', Limits(max_input_bits=3, max_intermediate_bits=3))

    def test_primitive_work_and_intermediate_bounds(self):
        budget = Budget(Limits(max_input_bits=3, max_intermediate_bits=3))
        with self.assertRaises(MathError) as context:
            budget.mul(Fraction(7), Fraction(2))
        self.assertEqual(context.exception.code, 'BIT_LIMIT')
        with self.assertRaises(MathError) as context:
            budget.div(Fraction(1), Fraction(0))
        self.assertEqual(context.exception.code, 'DIVISION_BY_ZERO')
        with self.assertRaises(MathError):
            Budget(Limits()).tick(-1)

    def test_cycle_and_deep_tree_rejected_without_recursion(self):
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(MathError) as context:
            check_tree(cyclic, Limits())
        self.assertEqual(context.exception.code, 'DEPTH_LIMIT')
        deeply = 0
        for _ in range(100):
            deeply = [deeply]
        with self.assertRaises(MathError):
            check_tree(deeply, Limits())

    def test_strict_json_ingress(self):
        for raw, code in ((b'{"a":1,"a":2}', 'DUPLICATE_KEY'), (b'1.0', 'INVALID_COEFFICIENT'),
                          (b'NaN', 'INVALID_COEFFICIENT'), (b'Infinity', 'INVALID_COEFFICIENT'),
                          (b'{} {}', 'INVALID_JSON'), (b'\xff', 'INVALID_JSON'),
                          (b'[' * 100 + b'0' + b']' * 100, 'DEPTH_LIMIT'),
                          (b'"\\ud800"', 'INVALID_JSON'), (b'9' * 5000, 'BIT_LIMIT')):
            with self.assertRaises(MathError) as context:
                loads_bounded(raw)
            self.assertEqual(context.exception.code, code)
        self.assertEqual(loads_bounded(b'{"a":[1,-2,null]}'), {'a': [1, -2, None]})
        with self.assertRaises(MathError):
            loads_bounded(b' {} ', Limits(max_input_bytes=2))

    def test_output_cap_exact_boundary(self):
        cert = produce(BASE)
        size = len(json.dumps(cert, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        self.assertEqual(produce(BASE, Limits(max_output_bytes=size)), cert)
        self.reject_matrix(BASE, 'OUTPUT_LIMIT', Limits(max_output_bytes=size - 1))

    def test_maximum_dimension_identity_and_zero(self):
        for identity in (False, True):
            matrix = {'domain': 'Z', 'rows': 16, 'cols': 16,
                      'entries': [[int(identity and i == j) for j in range(16)] for i in range(16)]}
            cert = produce(matrix)
            result = verify(matrix, cert)
            self.assertEqual(result.rank, 16 if identity else 0)
            self.assertEqual(result.determinant, 1 if identity else 0)

    def test_bools_not_equal_integer_certificate_fields(self):
        good = produce(BASE)
        for path in ('rank', 'pivots', 'free_columns'):
            bad = copy.deepcopy(good)
            bad[path] = True if path == 'rank' else [False, True]
            with self.assertRaises(MathError):
                verify(BASE, bad)

    def test_schema_version_and_domain_binding(self):
        cert = produce(BASE)
        for key, value in (('schema', 'foundation-math-rational-matrix/2'), ('unexpected', 1)):
            bad = copy.deepcopy(cert)
            bad[key] = value
            with self.assertRaises(MathError):
                verify(BASE, bad)
        with self.assertRaises(MathError):
            verify(dict(BASE, domain='Q'), cert)


class AdapterTests(unittest.TestCase):
    def test_checked_production_and_reverification(self):
        result = handle_request({'operation': 'certify', 'matrix': BASE})
        self.assertTrue(result['ok'])
        self.assertTrue(result['verification']['accepted'])
        self.assertEqual(result['verification']['scope'], 'one_explicit_matrix')
        again = handle_request({'operation': 'verify', 'matrix': BASE, 'certificate': result['certificate']})
        self.assertTrue(again['ok'])
        self.assertEqual(again['verification'], result['verification'])

    def test_errors_never_contain_partial_acceptance(self):
        requests = [None, [], {'operation': 'eval', 'expression': '2+2'},
                    {'operation': 'certify', 'matrix': BASE, 'expression': 'x'},
                    {'operation': 'verify', 'matrix': BASE},
                    {'operation': 'certify', 'matrix': dict(BASE, rows=True)}]
        for request in requests:
            response = handle_request(request)
            self.assertFalse(response['ok'])
            self.assertEqual(set(response), {'ok', 'error'})
            self.assertEqual(set(response['error']), {'code', 'message', 'path'})
        result = handle_request({'operation': 'certify', 'matrix': BASE}, Limits(max_output_bytes=0))
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'OUTPUT_LIMIT')

    def test_verify_guardrails(self):
        certificate = produce(BASE)
        for limits, code in ((Limits(max_work=0), 'WORK_LIMIT'), (Limits(max_operations=0), 'OPERATION_LIMIT'),
                             (Limits(max_output_bytes=0), 'OUTPUT_LIMIT')):
            result = handle_request({'operation': 'verify', 'matrix': BASE, 'certificate': certificate}, limits)
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], code)

    def run_cli(self, raw, optimized=False):
        command = [sys.executable] + (['-O'] if optimized else []) + ['-m', 'exact_linalg']
        return subprocess.run(command, input=raw, capture_output=True, timeout=5, cwd=Path(__file__).parents[1])

    def test_one_shot_cli_and_optimized_parity(self):
        raw = json.dumps({'operation': 'certify', 'matrix': BASE}).encode()
        ordinary, optimized = self.run_cli(raw), self.run_cli(raw, True)
        self.assertEqual(ordinary.returncode, 0)
        self.assertEqual(ordinary.stderr, b'')
        self.assertEqual(ordinary.stdout, optimized.stdout)
        self.assertEqual(optimized.returncode, 0)
        self.assertTrue(json.loads(ordinary.stdout)['ok'])
        rejected = self.run_cli(b'{"operation":"verify","operation":"certify"}')
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(json.loads(rejected.stdout)['error']['code'], 'DUPLICATE_KEY')
        self.assertNotIn(b'Traceback', rejected.stdout + rejected.stderr)

    def test_cli_large_input_is_bounded(self):
        result = self.run_cli(b' ' * 1_000_001)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'INPUT_LIMIT')
        self.assertLess(len(result.stdout), 512)

    def test_verifier_import_does_not_load_producer(self):
        code = 'import sys; import exact_linalg.verifier; sys.exit(int("exact_linalg.producer" in sys.modules))'
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parents[1], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

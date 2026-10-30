"""Fresh independent audit: Laplace minors, semantic mutations, and exact limits.

All matrices are tiny original synthetic fixtures. This is validation evidence,
not a formal proof or a guarantee about Python's trusted arithmetic/runtime.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
import json
import random
import unittest

from exact_linalg.api import handle_request
from exact_linalg.contract import Limits, MathError, loads_bounded
from exact_linalg.producer import produce
from exact_linalg.verifier import verify


def token(value):
    value = Fraction(value)
    if value.denominator == 1:
        return value.numerator
    return {"num": value.numerator, "den": value.denominator}


def number(value):
    if type(value) is int:
        return Fraction(value)
    return Fraction(value["num"], value["den"])


def spec(entries, cols=None, domain="Q"):
    return {"domain": domain, "rows": len(entries),
            "cols": len(entries[0]) if entries else (0 if cols is None else cols),
            "entries": [[token(x) for x in row] for row in entries]}


def laplace(entries):
    """Cofactor expansion, independent of elimination and permutation oracles."""
    if not entries:
        return Fraction(1)
    return sum(((-1) ** j * entries[0][j]
                * laplace([row[:j] + row[j + 1:] for row in entries[1:]])
                for j in range(len(entries))), Fraction(0))


def rank_by_minors(entries, rows, cols):
    for size in range(min(rows, cols), 0, -1):
        for rr in combinations(range(rows), size):
            for cc in combinations(range(cols), size):
                if laplace([[entries[i][j] for j in cc] for i in rr]):
                    return size
    return 0


def json_size(value):
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii"))


class IndependentAdversarialAudit(unittest.TestCase):
    def reject(self, matrix, certificate, code=None, limits=Limits()):
        with self.assertRaises(MathError) as caught:
            verify(matrix, certificate, limits)
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def check_oracles(self, matrix):
        certificate = produce(matrix)
        result = verify(matrix, certificate)
        entries = [[number(x) for x in row] for row in matrix["entries"]]
        m, n = matrix["rows"], matrix["cols"]
        expected = rank_by_minors(entries, m, n)
        self.assertEqual(result.rank, expected)
        # Pivot columns are exactly the columns where prefix-column rank rises.
        prefix_ranks = [rank_by_minors([row[:j] for row in entries], m, j)
                        for j in range(n + 1)]
        self.assertEqual(result.pivots, tuple(j for j in range(n)
                                            if prefix_ranks[j + 1] > prefix_ranks[j]))
        if m == n:
            self.assertEqual(result.determinant, laplace(entries))
        else:
            self.assertIsNone(result.determinant)
        basis = [[number(x) for x in row]
                 for row in certificate["nullspace"]["entries"]]
        self.assertEqual(rank_by_minors(basis, n, n - expected), n - expected)
        for row in entries:
            for column in range(n - expected):
                self.assertEqual(sum((row[k] * basis[k][column]
                                      for k in range(n)), Fraction(0)), 0)

    def test_binary_3_by_3_with_laplace_and_prefix_rank(self):
        for values in product((0, 1), repeat=9):
            self.check_oracles(spec([values[i:i + 3] for i in (0, 3, 6)], domain="Z"))

    def test_fresh_seeded_rational_minors_and_nullspace_independence(self):
        rng = random.Random(20261024)
        for m, n in [(4, 4), (3, 4), (4, 3), (2, 4), (4, 2)]:
            for _ in range(12):
                entries = [[Fraction(rng.randrange(-3, 4), rng.randrange(1, 6))
                            for _ in range(n)] for _ in range(m)]
                self.check_oracles(spec(entries))

    def test_every_derived_coefficient_rejects_shape_preserving_forgery(self):
        # Include rank deficiency, skipped pivots, Q inputs, and both empty axes.
        matrices = [spec([[0, 2, 1], [0, 4, 2]]),
                    spec([[Fraction(1, 3), 1], [1, Fraction(-1, 2)]]),
                    spec([[1, 0, 2, 3], [0, 1, 4, 5]]),
                    spec([[0, 0], [0, 0]]), spec([], cols=3), spec([[], []])]
        for matrix in matrices:
            original = produce(matrix)
            for field in ("matrix", "rref", "transform", "nullspace"):
                for i, row in enumerate(original[field]["entries"]):
                    for j, value in enumerate(row):
                        for delta in (-1, 1):
                            forged = deepcopy(original)
                            forged[field]["entries"][i][j] = token(number(value) + delta)
                            with self.subTest(shape=(matrix["rows"], matrix["cols"]),
                                              field=field, i=i, j=j, delta=delta):
                                self.reject(matrix, forged, "INVALID_CERTIFICATE")
            if original["determinant"] is not None:
                forged = deepcopy(original)
                forged["determinant"] = token(number(original["determinant"]) + 1)
                self.reject(matrix, forged, "INVALID_CERTIFICATE")
            for index, operation in enumerate(original["operations"]):
                if "factor" in operation:
                    forged = deepcopy(original)
                    forged["operations"][index]["factor"] = token(-number(operation["factor"]))
                    self.reject(matrix, forged, "INVALID_CERTIFICATE")

    def test_nonproducer_identity_traces_are_accepted(self):
        for matrix in [spec([[1, 2], [0, 1]]), spec([[0, 0], [0, 0]]),
                       spec([[], []]), spec([[Fraction(2, 3)]])]:
            certificate = produce(matrix)
            operations = [
                {"op": "scale", "i": 0, "factor": {"num": -2, "den": 3}},
                {"op": "scale", "i": 0, "factor": {"num": -3, "den": 2}},
            ]
            if matrix["rows"] >= 2:
                operations += [{"op": "swap", "i": 0, "j": 1}] * 2
                operations += [
                    {"op": "add", "target": 0, "source": 1, "factor": 3},
                    {"op": "add", "target": 0, "source": 1, "factor": -3},
                ]
            certificate["operations"] = operations + certificate["operations"]
            self.assertEqual(verify(matrix, certificate).rank, certificate["rank"])

    def test_empty_shapes_through_dimension_ceiling(self):
        for dimension in range(17):
            for matrix in [spec([], cols=dimension), spec([[] for _ in range(dimension)])]:
                certificate = produce(matrix)
                result = verify(matrix, certificate)
                self.assertEqual(result.rank, 0)
                self.assertEqual(result.free_columns, tuple(range(matrix["cols"])))
                self.assertEqual(result.determinant, Fraction(1) if dimension == 0 else None)
        empty = spec([])
        limits = Limits(max_dimension=0, max_cells=0, max_operations=0)
        self.assertEqual(verify(empty, produce(empty, limits), limits).determinant, 1)

    def test_exact_output_limits_include_adapter_envelope(self):
        matrix = spec([[1, 2, 3], [0, 1, 4]])
        certificate = produce(matrix)
        result = verify(matrix, certificate)
        for function, size in [(lambda limits: produce(matrix, limits), json_size(certificate)),
                               (lambda limits: verify(matrix, certificate, limits), json_size(result.to_dict()))]:
            function(Limits(max_output_bytes=size))
            with self.assertRaises(MathError) as caught:
                function(Limits(max_output_bytes=size - 1))
            self.assertEqual(caught.exception.code, "OUTPUT_LIMIT")
        request = {"operation": "certify", "matrix": matrix}
        response_size = json_size(handle_request(request))
        self.assertTrue(handle_request(request, Limits(max_output_bytes=response_size))["ok"])
        rejected = handle_request(request, Limits(max_output_bytes=response_size - 1))
        self.assertEqual(set(rejected), {"ok", "error"})
        self.assertEqual(rejected["error"]["code"], "OUTPUT_LIMIT")

    def test_exact_work_and_operation_boundaries(self):
        matrix = spec([[0, 2, 3], [1, 3, 4]])
        certificate = produce(matrix)
        count = len(certificate["operations"])
        verify(matrix, certificate, Limits(max_operations=count))
        self.reject(matrix, certificate, "OPERATION_LIMIT", Limits(max_operations=count - 1))
        low, high = 0, 10000
        while low < high:
            middle = (low + high) // 2
            try:
                verify(matrix, certificate, Limits(max_work=middle))
                high = middle
            except MathError as error:
                self.assertEqual(error.code, "WORK_LIMIT")
                low = middle + 1
        verify(matrix, certificate, Limits(max_work=low))
        self.reject(matrix, certificate, "WORK_LIMIT", Limits(max_work=low - 1))

    def test_trace_determinant_growth_is_bounded_even_when_U_stays_small(self):
        matrix = spec([[], []])
        certificate = produce(matrix)
        certificate["operations"] = [
            {"op": "scale", "i": 0, "factor": 7},
            {"op": "scale", "i": 1, "factor": 7},
            {"op": "scale", "i": 0, "factor": {"num": 1, "den": 7}},
            {"op": "scale", "i": 1, "factor": {"num": 1, "den": 7}},
        ]
        verify(matrix, certificate)
        self.reject(matrix, certificate, "BIT_LIMIT",
                    Limits(max_input_bits=3, max_intermediate_bits=3))

    def test_strict_ingress_escaped_keys_unicode_and_structural_limits(self):
        for raw, code in [(b'{"x":1,"\\u0078":2}', "DUPLICATE_KEY"),
                          (b'{"\\ud800":0}', "INVALID_JSON"),
                          (b'[-Infinity]', "INVALID_COEFFICIENT"),
                          (b'1e999999', "INVALID_COEFFICIENT"),
                          (b'\xef\xbb\xbf{}', "INVALID_JSON")]:
            with self.assertRaises(MathError) as caught:
                loads_bounded(raw)
            self.assertEqual(caught.exception.code, code)
        for payload in [{"a": [0] * 10}, [[[[0]]]]]:
            with self.assertRaises(MathError):
                loads_bounded(json.dumps(payload).encode(), Limits(max_nodes=4))
        for value in [True, False, 0.0, "1", {"num": 0, "den": 2}, {"num": 1, "den": True}]:
            response = handle_request({"operation": "certify", "matrix": {
                "domain": "Q", "rows": 1, "cols": 1, "entries": [[value]]}})
            self.assertFalse(response["ok"])
            self.assertEqual(set(response), {"ok", "error"})

    def test_computation_field_is_explicit_for_integer_input(self):
        matrix = spec([[2, 1]], domain="Z")
        response = handle_request({"operation": "certify", "matrix": matrix})
        self.assertTrue(response["ok"])
        self.assertEqual(response["verification"]["computational_field"], "Q")
        self.assertEqual(response["certificate"]["nullspace"]["entries"],
                         [[{"num": -1, "den": 2}], [1]])


if __name__ == "__main__":
    unittest.main()

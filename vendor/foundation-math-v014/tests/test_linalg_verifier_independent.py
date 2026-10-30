"""Verifier tests with hand-built certificates, not producer-generated fixtures."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import ast
from pathlib import Path
import unittest

from exact_linalg.contract import Limits, MathError
from exact_linalg.verifier import VerifiedMatrix, verify


def matrix(entries, rows=None, cols=None, domain="Q"):
    rows = len(entries) if rows is None else rows
    cols = (len(entries[0]) if entries else 0) if cols is None else cols
    return {"domain": domain, "rows": rows, "cols": cols, "entries": entries}


def identity(size):
    return matrix([[int(i == j) for j in range(size)] for i in range(size)])


def rectangular_fixture():
    original = matrix([[1, 2, 3], [0, 1, 4]], domain="Z")
    certificate = {
        "schema": "foundation-math-rational-matrix/1",
        "matrix": deepcopy(original),
        "rref": matrix([[1, 0, -5], [0, 1, 4]]),
        "transform": matrix([[1, -2], [0, 1]]),
        "rank": 2,
        "pivots": [0, 1],
        "free_columns": [2],
        "nullspace": matrix([[5], [-4], [1]]),
        "operations": [{"op": "add", "target": 0, "source": 1, "factor": -2}],
        "determinant": None,
    }
    return original, certificate


def as_claimed_rref(entries, rank, pivots, free, nullspace):
    original = matrix(entries)
    m, n = original["rows"], original["cols"]
    return original, {
        "schema": "foundation-math-rational-matrix/1",
        "matrix": deepcopy(original), "rref": deepcopy(original),
        "transform": identity(m), "rank": rank,
        "pivots": pivots, "free_columns": free,
        "nullspace": matrix(nullspace, rows=n, cols=n-rank),
        "operations": [], "determinant": (1 if rank == n else 0) if m == n else None,
    }


class IndependentVerifierTests(unittest.TestCase):
    def assert_rejected(self, original, certificate, code="INVALID_CERTIFICATE"):
        with self.assertRaises(MathError) as caught:
            verify(original, certificate)
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsInstance(caught.exception.to_dict()["path"], str)

    def test_manual_rectangular_certificate(self):
        original, certificate = rectangular_fixture()
        saved = deepcopy((original, certificate))
        result = verify(original, certificate)
        self.assertEqual(result, VerifiedMatrix(2, 3, 2, (0, 1), (2,), None))
        self.assertEqual(result.to_dict(), {
            "accepted": True, "scope": "one_explicit_matrix", "computational_field": "Q", "rows": 2,
            "cols": 3, "rank": 2, "pivots": [0, 1], "free_columns": [2],
            "determinant": None,
        })
        self.assertEqual((original, certificate), saved)
        with self.assertRaises(FrozenInstanceError):
            result.rank = 0

    def test_manual_square_scalings_and_additions(self):
        original = matrix([[2, 1], [1, 1]], domain="Z")
        certificate = {
            "schema": "foundation-math-rational-matrix/1",
            "matrix": deepcopy(original), "rref": identity(2),
            "transform": matrix([[1, -1], [-1, 2]]), "rank": 2,
            "pivots": [0, 1], "free_columns": [],
            "nullspace": matrix([[], []], cols=0),
            "operations": [
                {"op": "scale", "i": 0, "factor": {"num": 1, "den": 2}},
                {"op": "add", "target": 1, "source": 0, "factor": -1},
                {"op": "scale", "i": 1, "factor": 2},
                {"op": "add", "target": 0, "source": 1,
                 "factor": {"num": -1, "den": 2}},
            ], "determinant": 1,
        }
        self.assertEqual(verify(original, certificate).determinant, Fraction(1))

    def test_manual_swap_determinant_sign(self):
        original = matrix([[0, 1], [1, 0]], domain="Z")
        certificate = {
            "schema": "foundation-math-rational-matrix/1", "matrix": original,
            "rref": identity(2), "transform": matrix([[0, 1], [1, 0]]),
            "rank": 2, "pivots": [0, 1], "free_columns": [],
            "nullspace": matrix([[], []], cols=0),
            "operations": [{"op": "swap", "i": 0, "j": 1}], "determinant": -1,
        }
        self.assertEqual(verify(original, certificate).determinant, Fraction(-1))
        certificate["determinant"] = 1
        self.assert_rejected(original, certificate)

    def test_manual_rational_determinant(self):
        original = matrix([[{"num": -3, "den": 2}]])
        certificate = {
            "schema": "foundation-math-rational-matrix/1", "matrix": original,
            "rref": identity(1), "transform": matrix([[{"num": -2, "den": 3}]]),
            "rank": 1, "pivots": [0], "free_columns": [],
            "nullspace": matrix([[]], cols=0),
            "operations": [{"op": "scale", "i": 0, "factor": {"num": -2, "den": 3}}],
            "determinant": {"num": -3, "den": 2},
        }
        self.assertEqual(verify(original, certificate).to_dict()["determinant"],
                         {"num": -3, "den": 2})
        certificate["determinant"] = 0
        self.assert_rejected(original, certificate)

    def test_manual_singular_square_certificate(self):
        original = matrix([[1, 2], [2, 4]], domain="Z")
        certificate = {
            "schema": "foundation-math-rational-matrix/1", "matrix": original,
            "rref": matrix([[1, 2], [0, 0]]),
            "transform": matrix([[1, 0], [-2, 1]]),
            "rank": 1, "pivots": [0], "free_columns": [1],
            "nullspace": matrix([[-2], [1]]),
            "operations": [{"op": "add", "target": 1, "source": 0, "factor": -2}],
            "determinant": 0,
        }
        self.assertEqual(verify(original, certificate).determinant, Fraction(0))
        certificate["determinant"] = 1
        self.assert_rejected(original, certificate)

    def test_manual_all_zero_and_empty_dimensions(self):
        for m, n in [(0, 0), (0, 3), (3, 0), (3, 4), (3, 3), (1, 0), (0, 1)]:
            with self.subTest(rows=m, cols=n):
                original = matrix([[0] * n for _ in range(m)], rows=m, cols=n, domain="Z")
                certificate = {
                    "schema": "foundation-math-rational-matrix/1", "matrix": original,
                    "rref": matrix([[0] * n for _ in range(m)], rows=m, cols=n),
                    "transform": identity(m), "rank": 0, "pivots": [],
                    "free_columns": list(range(n)), "nullspace": identity(n),
                    "operations": [],
                    "determinant": (1 if n == 0 else 0) if m == n else None,
                }
                result = verify(original, certificate)
                self.assertEqual((result.rows, result.cols, result.rank), (m, n, 0))
                self.assertEqual(result.determinant, certificate["determinant"])

    def test_matrix_binding_includes_domain(self):
        for field, value in [("entries", [[1, 2, 4], [0, 1, 4]]), ("domain", "Q")]:
            original, certificate = rectangular_fixture()
            certificate["matrix"][field] = value
            with self.subTest(field=field):
                self.assert_rejected(original, certificate)

    def test_forged_rank_with_consistent_counts(self):
        original, certificate = rectangular_fixture()
        certificate.update(rank=1, pivots=[0], free_columns=[1, 2],
                           nullspace=matrix([[0, 0], [1, 0], [0, 1]]))
        self.assert_rejected(original, certificate)

    def test_forged_pivots_and_free_columns(self):
        for pivots, free in [([1, 0], [2]), ([0, 0], [2]), ([0, 2], [1]), ([0, 1], [1])]:
            original, certificate = rectangular_fixture()
            certificate["pivots"], certificate["free_columns"] = pivots, free
            with self.subTest(pivots=pivots, free=free):
                self.assert_rejected(original, certificate)

    def test_forged_rref_transform_and_log(self):
        for field, replacement in [
            ("rref", matrix([[1, 0, -4], [0, 1, 4]])),
            ("transform", identity(2)),
            ("operations", []),
            ("operations", [{"op": "add", "target": 0, "source": 1, "factor": -3}]),
        ]:
            original, certificate = rectangular_fixture()
            certificate[field] = replacement
            with self.subTest(field=field, replacement=replacement):
                self.assert_rejected(original, certificate)

    def test_UA_identity_alone_does_not_prove_invertible_U(self):
        original, certificate = as_claimed_rref([[1, 0], [0, 0]], 1, [0], [1], [[0], [1]])
        self.assertEqual(verify(original, certificate).rank, 1)
        certificate["transform"] = matrix([[1, 0], [0, 0]])
        # This singular U still satisfies U*A=R. Identity replay must reject it.
        self.assert_rejected(original, certificate)

    def test_honest_replay_of_non_rref_is_rejected(self):
        cases = [
            ([[2, 0], [0, 1]], 2, [0, 1], [], [[], []]),
            ([[1, 1], [0, 1]], 2, [0, 1], [], [[], []]),
            ([[0, 0], [0, 1]], 1, [1], [0], [[1], [0]]),
            ([[0, 1], [1, 0]], 2, [0, 1], [], [[], []]),
            ([[1, 0], [1, 0]], 1, [0], [1], [[0], [1]]),
        ]
        for entries, rank, pivots, free, nullspace in cases:
            with self.subTest(entries=entries):
                self.assert_rejected(*as_claimed_rref(entries, rank, pivots, free, nullspace))

    def test_nullspace_membership_and_completeness_are_both_required(self):
        for entries in [[[6], [-4], [1]], [[0], [0], [0]], [[10], [-8], [2]]]:
            original, certificate = rectangular_fixture()
            certificate["nullspace"] = matrix(entries)
            with self.subTest(entries=entries):
                self.assert_rejected(original, certificate)

    def test_duplicate_kernel_columns_are_rejected(self):
        original, certificate = as_claimed_rref([[1, 0, 0]], 1, [0], [1, 2],
                                              [[0, 0], [1, 0], [0, 1]])
        self.assertEqual(verify(original, certificate).rank, 1)
        certificate["nullspace"] = matrix([[0, 0], [1, 1], [0, 0]])
        self.assert_rejected(original, certificate)

    def test_invalid_operations(self):
        for operation in [
            {"op": "swap", "i": 0, "j": 0},
            {"op": "scale", "i": 0, "factor": 0},
            {"op": "add", "target": 0, "source": 0, "factor": 1},
            {"op": "add", "target": 0, "source": 1, "factor": 0},
            {"op": "scale", "i": -1, "factor": 1},
            {"op": "scale", "i": 2, "factor": 1},
            {"op": "scale", "i": True, "factor": 1},
            {"op": "multiply", "i": 0, "factor": 1},
            [],
        ]:
            original, certificate = rectangular_fixture()
            certificate["operations"] = [operation]
            with self.subTest(operation=operation):
                self.assert_rejected(original, certificate)

    def test_no_operations_on_empty_rows(self):
        original = matrix([], rows=0, cols=0)
        certificate = {"schema": "foundation-math-rational-matrix/1", "matrix": original,
                       "rref": original, "transform": original, "rank": 0,
                       "pivots": [], "free_columns": [], "nullspace": original,
                       "operations": [{"op": "scale", "i": 0, "factor": 1}],
                       "determinant": 1}
        self.assert_rejected(original, certificate)

    def test_nonsquare_has_no_determinant(self):
        original, certificate = rectangular_fixture()
        certificate["determinant"] = 1
        self.assert_rejected(original, certificate)

    def test_output_matrices_require_rational_domain_and_right_shapes(self):
        for field in ["rref", "transform", "nullspace"]:
            original, certificate = rectangular_fixture()
            certificate[field]["domain"] = "Z"
            with self.subTest(field=field):
                self.assert_rejected(original, certificate)
        original, certificate = rectangular_fixture()
        certificate["transform"] = identity(3)
        self.assert_rejected(original, certificate)

    def test_strict_schema_and_canonical_coefficients(self):
        mutations = [
            lambda c: c.update(extra="not allowed"),
            lambda c: c.update(rank=True),
            lambda c: c.update(pivots=[False, 1]),
            lambda c: c["operations"][0].update(extra=0),
            lambda c: c["operations"][0].update(factor=-2.0),
            lambda c: c["operations"][0].update(factor="-2"),
            lambda c: c["operations"][0].update(factor={"num": -2, "den": 1}),
            lambda c: c["operations"][0].update(factor={"num": -4, "den": 2}),
            lambda c: c["operations"][0].update(factor={"num": 2, "den": -1}),
            lambda c: c["operations"][0].update(factor={"num": -2, "den": 0}),
            lambda c: c.update(operations={}),
        ]
        for mutate in mutations:
            original, certificate = rectangular_fixture()
            mutate(certificate)
            with self.subTest(certificate=certificate):
                self.assert_rejected(original, certificate, code=None)

    def test_bounded_work_operations_outputs_and_derived_matrix_cells(self):
        original, certificate = rectangular_fixture()
        for limits, code in [
            (replace(Limits(), max_work=0), "WORK_LIMIT"),
            (replace(Limits(), max_output_bytes=1), "OUTPUT_LIMIT"),
            (replace(Limits(), max_cells=5), "CELL_LIMIT"),
        ]:
            with self.subTest(limits=limits), self.assertRaises(MathError) as caught:
                verify(original, certificate, limits)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(MathError) as caught:
            verify(original, certificate, replace(Limits(), max_operations=0))
        self.assertEqual(caught.exception.code, "OPERATION_LIMIT")
        # A itself is small enough; its required transform is not.
        original, certificate = as_claimed_rref([[1], [0], [0]], 1, [0], [], [[]])
        with self.assertRaises(MathError) as caught:
            verify(original, certificate, replace(Limits(), max_cells=3))
        self.assertEqual(caught.exception.code, "CELL_LIMIT")

    def test_intermediate_bit_limit_checks_replay_not_just_final_values(self):
        original, certificate = as_claimed_rref([[1]], 1, [0], [], [[]])
        certificate["operations"] = [
            {"op": "scale", "i": 0, "factor": 64},
            {"op": "scale", "i": 0, "factor": 64},
            {"op": "scale", "i": 0, "factor": {"num": 1, "den": 64}},
            {"op": "scale", "i": 0, "factor": {"num": 1, "den": 64}},
        ]
        self.assertEqual(verify(original, certificate).rank, 1)
        with self.assertRaises(MathError) as caught:
            verify(original, certificate,
                   replace(Limits(), max_input_bits=8, max_intermediate_bits=8))
        self.assertEqual(caught.exception.code, "BIT_LIMIT")

    def test_source_has_no_producer_or_elimination_dependency(self):
        import exact_linalg.verifier as module
        tree = ast.parse(Path(module.__file__).read_text())
        dependencies = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                dependencies.append(node.module or "")
        self.assertNotIn("producer", dependencies)
        self.assertTrue(set(dependencies) <= {"dataclasses", "fractions", "contract"})


if __name__ == "__main__":
    unittest.main()

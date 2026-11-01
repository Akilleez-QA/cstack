"""Bounded certificate checking for one explicit rational matrix.

This module intentionally does not import the producer or run an elimination
algorithm.  It checks a supplied computation by replaying invertible elementary
row operations, then checks the claimed algebraic consequences independently.
"""

from dataclasses import dataclass
from fractions import Fraction

from .contract import (
    Budget,
    Limits,
    MathError,
    Matrix,
    check_output,
    check_tree,
    encode_coefficient,
    parse_coefficient,
    parse_matrix,
    require_int,
    strict_keys,
)


_SCHEMA = "foundation-math-rational-matrix/1"
_FIELDS = {
    "schema", "matrix", "rref", "transform", "rank", "pivots",
    "free_columns", "nullspace", "operations", "determinant",
}
_ZERO = Fraction(0)
_ONE = Fraction(1)


@dataclass(frozen=True)
class VerifiedMatrix:
    """Accepted claims, scoped exclusively to the supplied explicit matrix."""

    rows: int
    cols: int
    rank: int
    pivots: tuple[int, ...]
    free_columns: tuple[int, ...]
    determinant: Fraction | None

    def to_dict(self) -> dict:
        return {
            "accepted": True,
            "scope": "one_explicit_matrix",
            "computational_field": "Q",
            "rows": self.rows,
            "cols": self.cols,
            "rank": self.rank,
            "pivots": list(self.pivots),
            "free_columns": list(self.free_columns),
            "determinant": (
                None if self.determinant is None
                else encode_coefficient(self.determinant)
            ),
        }


def _invalid(message: str, path: str = "$.certificate") -> None:
    raise MathError("INVALID_CERTIFICATE", message, path)


def _shape(value: Matrix, rows: int, cols: int, path: str) -> None:
    if value.domain != "Q":
        _invalid("Certificate output matrices must have domain Q.", path + ".domain")
    if value.rows != rows or value.cols != cols:
        _invalid(f"Expected a {rows} by {cols} matrix.", path)


def _indices(value: object, size: int, budget: Budget, path: str) -> tuple[int, ...]:
    if type(value) is not list:
        _invalid("Expected an ordered list of column indices.", path)
    result = []
    for position, item in enumerate(value):
        budget.tick()
        if type(item) is not int or not 0 <= item < size:
            _invalid("Column index is outside the matrix.", f"{path}[{position}]")
        result.append(item)
    return tuple(result)


def _row_index(value: object, rows: int, path: str) -> int:
    if type(value) is not int or not 0 <= value < rows:
        _invalid("Row index is outside the matrix.", path)
    return value


def _equal_entries(actual: list[list[Fraction]], expected: Matrix,
                   budget: Budget, path: str) -> None:
    for i in range(expected.rows):
        for j in range(expected.cols):
            budget.tick()
            if actual[i][j] != expected.entries[i][j]:
                _invalid("Matrix does not agree with replayed row operations.",
                         f"{path}.entries[{i}][{j}]")


def _check_product(left: Matrix, right: Matrix, expected: Matrix | None,
                   budget: Budget, path: str) -> None:
    """Check a product against a matrix, or against zero if expected is None."""
    if left.cols != right.rows:
        _invalid("Incompatible dimensions in a required matrix product.", path)
    for i in range(left.rows):
        for j in range(right.cols):
            total = _ZERO
            budget.tick()
            for k in range(left.cols):
                total = budget.add(total, budget.mul(left.entries[i][k],
                                                    right.entries[k][j]))
            wanted = _ZERO if expected is None else expected.entries[i][j]
            if total != wanted:
                _invalid("Required matrix product identity is false.",
                         f"{path}[{i}][{j}]")


def _check_rref(rref: Matrix, budget: Budget) -> tuple[int, ...]:
    """Inspect echelon conditions directly; never reduce the matrix."""
    pivots = []
    saw_zero_row = False
    for i in range(rref.rows):
        leading = None
        for j in range(rref.cols):
            budget.tick()
            if rref.entries[i][j] != _ZERO:
                leading = j
                break
        if leading is None:
            saw_zero_row = True
            continue
        path = f"$.certificate.rref.entries[{i}][{leading}]"
        if saw_zero_row:
            _invalid("A nonzero row follows a zero row in the claimed RREF.", path)
        if pivots and leading <= pivots[-1]:
            _invalid("RREF leading columns must increase strictly.", path)
        if rref.entries[i][leading] != _ONE:
            _invalid("Every RREF leading entry must be one.", path)
        for other in range(rref.rows):
            budget.tick()
            if other != i and rref.entries[other][leading] != _ZERO:
                _invalid("A pivot column has another nonzero entry.",
                         f"$.certificate.rref.entries[{other}][{leading}]")
        pivots.append(leading)
    return tuple(pivots)


def verify(matrix: object, certificate: object,
           limits: Limits = Limits()) -> VerifiedMatrix:
    """Verify a bounded exact certificate or raise a structured ``MathError``.

    The row-operation log provides the invertibility proof for U.  Checking the
    free rows of N form an identity matrix proves its columns independent; the
    checked RREF rank proves those n-rank kernel vectors are a complete basis.
    No claim here covers symbolic parameters or any other matrix.
    """
    check_tree(matrix, limits)
    check_tree(certificate, limits)
    budget = Budget(limits)
    original = parse_matrix(matrix, limits, "$.matrix")
    strict_keys(certificate, _FIELDS, "$.certificate")
    if certificate["schema"] != _SCHEMA:
        _invalid("Unknown certificate schema.", "$.certificate.schema")
    bound = parse_matrix(certificate["matrix"], limits, "$.certificate.matrix")
    budget.tick(original.rows * original.cols + 1)
    if bound != original:
        _invalid("Certificate is not bound to this exact matrix and domain.",
                 "$.certificate.matrix")

    m, n = original.rows, original.cols
    rank = require_int(certificate["rank"], 0, min(m, n), "$.certificate.rank")
    pivots = _indices(certificate["pivots"], n, budget, "$.certificate.pivots")
    free = _indices(certificate["free_columns"], n, budget,
                    "$.certificate.free_columns")
    if len(pivots) != rank or len(free) != n - rank:
        _invalid("Rank, pivot count, and free-column count disagree.")

    rref = parse_matrix(certificate["rref"], limits, "$.certificate.rref",
                        coefficient_bits=limits.max_intermediate_bits)
    transform = parse_matrix(certificate["transform"], limits,
                             "$.certificate.transform",
                             coefficient_bits=limits.max_intermediate_bits)
    nullspace = parse_matrix(certificate["nullspace"], limits,
                             "$.certificate.nullspace",
                             coefficient_bits=limits.max_intermediate_bits)
    _shape(rref, m, n, "$.certificate.rref")
    _shape(transform, m, m, "$.certificate.transform")
    _shape(nullspace, n, n - rank, "$.certificate.nullspace")

    operations = certificate["operations"]
    if type(operations) is not list:
        _invalid("Row operations must be a list.", "$.certificate.operations")
    if len(operations) > limits.max_operations:
        raise MathError("OPERATION_LIMIT", "Too many row operations.",
                        "$.certificate.operations")
    budget.tick(m * n + m * m)
    replay = [list(row) for row in original.entries]
    replay_u = [[_ONE if i == j else _ZERO for j in range(m)] for i in range(m)]
    determinant_u = _ONE

    for number, operation in enumerate(operations):
        path = f"$.certificate.operations[{number}]"
        budget.tick()
        if type(operation) is not dict:
            _invalid("Each row operation must be an object.", path)
        kind = operation.get("op")
        if kind == "swap":
            strict_keys(operation, {"op", "i", "j"}, path)
            i = _row_index(operation["i"], m, path + ".i")
            j = _row_index(operation["j"], m, path + ".j")
            if i == j:
                _invalid("A swap must name distinct rows.", path)
            replay[i], replay[j] = replay[j], replay[i]
            replay_u[i], replay_u[j] = replay_u[j], replay_u[i]
            determinant_u = budget.mul(Fraction(-1), determinant_u)
        elif kind == "scale":
            strict_keys(operation, {"op", "i", "factor"}, path)
            i = _row_index(operation["i"], m, path + ".i")
            factor = parse_coefficient(operation["factor"],
                                       limits.max_intermediate_bits, path + ".factor")
            if factor == _ZERO:
                _invalid("A scaling factor must be nonzero.", path + ".factor")
            replay[i] = [budget.mul(factor, cell) for cell in replay[i]]
            replay_u[i] = [budget.mul(factor, cell) for cell in replay_u[i]]
            determinant_u = budget.mul(factor, determinant_u)
        elif kind == "add":
            strict_keys(operation, {"op", "target", "source", "factor"}, path)
            target = _row_index(operation["target"], m, path + ".target")
            source = _row_index(operation["source"], m, path + ".source")
            if target == source:
                _invalid("Row addition must name distinct rows.", path)
            factor = parse_coefficient(operation["factor"],
                                       limits.max_intermediate_bits, path + ".factor")
            if factor == _ZERO:
                _invalid("A row-addition factor must be nonzero.", path + ".factor")
            for rows in (replay, replay_u):
                rows[target] = [
                    budget.add(a, budget.mul(factor, b))
                    for a, b in zip(rows[target], rows[source])
                ]
        else:
            _invalid("Unknown row operation.", path + ".op")

    _equal_entries(replay, rref, budget, "$.certificate.rref")
    _equal_entries(replay_u, transform, budget, "$.certificate.transform")
    _check_product(transform, original, rref, budget, "$.certificate.UA_equals_R")
    actual_pivots = _check_rref(rref, budget)
    if pivots != actual_pivots or rank != len(actual_pivots):
        _invalid("Claimed pivots or rank disagree with the checked RREF.",
                 "$.certificate.pivots")
    pivot_set = set(actual_pivots)
    budget.tick(n)
    expected_free = tuple(j for j in range(n) if j not in pivot_set)
    if free != expected_free:
        _invalid("Free columns must be the ordered complement of the pivots.",
                 "$.certificate.free_columns")

    _check_product(original, nullspace, None, budget, "$.certificate.AN_equals_zero")
    for j, free_row in enumerate(free):
        for k in range(n - rank):
            budget.tick()
            wanted = _ONE if j == k else _ZERO
            if nullspace.entries[free_row][k] != wanted:
                _invalid("Nullspace free rows must form an identity matrix; "
                         "kernel vectors alone do not establish completeness.",
                         f"$.certificate.nullspace.entries[{free_row}][{k}]")

    determinant = None
    if m == n:
        determinant = parse_coefficient(certificate["determinant"],
                                        limits.max_intermediate_bits,
                                        "$.certificate.determinant")
        # A square RREF is I when full rank, otherwise it has a zero row.
        # This also gives det([])=1 for the zero-by-zero matrix.
        determinant_r = _ONE if rank == n else _ZERO
        if budget.mul(determinant, determinant_u) != determinant_r:
            _invalid("Determinant violates the row-operation determinant relation.",
                     "$.certificate.determinant")
    elif certificate["determinant"] is not None:
        _invalid("A nonsquare matrix must have determinant null.",
                 "$.certificate.determinant")

    result = VerifiedMatrix(m, n, rank, pivots, free, determinant)
    check_output(result.to_dict(), limits)
    return result

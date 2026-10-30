"""Deterministic certificate production by Gauss-Jordan row reduction.

This module is never imported by the mathematical verifier.
"""
from __future__ import annotations
from fractions import Fraction
from .contract import (Budget, Limits, MathError, Matrix, MatrixCertificate,
                       RowOperation, check_output, check_tree, encode_coefficient,
                       encode_matrix, parse_matrix)


def produce(matrix: object, limits: Limits = Limits()) -> MatrixCertificate:
    """Certify RREF, rank, a Q-nullspace basis and (for square A) determinant.

    Input domain Z constrains the coefficient tokens, not the solution ring:
    row reduction and nullspace are always over Q. No integer lattice is claimed.
    Resource exhaustion raises MathError and returns no partial certificate.
    """
    check_tree(matrix, limits)
    original = parse_matrix(matrix, limits)
    budget = Budget(limits)
    m, n = original.rows, original.cols
    if m * m > limits.max_cells:
        raise MathError('CELL_LIMIT', 'Row transformation matrix exceeds the cell limit.')
    reduced = [list(row) for row in original.entries]
    transform = [[Fraction(int(i == j)) for j in range(m)] for i in range(m)]
    operations: list[RowOperation] = []
    det_u = Fraction(1)

    def record(op: RowOperation) -> None:
        if len(operations) >= limits.max_operations:
            raise MathError('OPERATION_LIMIT', 'Row-operation certificate limit exhausted.')
        budget.tick()
        operations.append(op)

    def swap(i: int, j: int) -> None:
        nonlocal det_u
        record({'op': 'swap', 'i': i, 'j': j})
        reduced[i], reduced[j] = reduced[j], reduced[i]
        transform[i], transform[j] = transform[j], transform[i]
        det_u = budget.mul(det_u, Fraction(-1))

    def scale(i: int, factor: Fraction) -> None:
        nonlocal det_u
        if not factor:
            raise MathError('INTERNAL_ERROR', 'Attempted noninvertible row operation.')
        record({'op': 'scale', 'i': i, 'factor': encode_coefficient(factor)})
        for array in (reduced, transform):
            array[i] = [budget.mul(factor, value) for value in array[i]]
        det_u = budget.mul(det_u, factor)

    def add(target: int, source: int, factor: Fraction) -> None:
        record({'op': 'add', 'target': target, 'source': source, 'factor': encode_coefficient(factor)})
        for array in (reduced, transform):
            array[target] = [budget.add(value, budget.mul(factor, other))
                             for value, other in zip(array[target], array[source])]

    pivots = []
    next_row = 0
    for column in range(n):
        chosen = None
        for row in range(next_row, m):
            budget.tick()
            if reduced[row][column]:
                chosen = row
                break
        if chosen is None:
            continue
        if chosen != next_row:
            swap(chosen, next_row)
        pivot = reduced[next_row][column]
        if pivot != 1:
            scale(next_row, budget.div(Fraction(1), pivot))
        for row in range(m):
            budget.tick()
            if row != next_row and reduced[row][column]:
                add(row, next_row, budget.mul(Fraction(-1), reduced[row][column]))
        pivots.append(column)
        next_row += 1
        if next_row == m:
            break
    rank = len(pivots)
    free = [column for column in range(n) if column not in pivots]
    if n * len(free) > limits.max_cells:
        raise MathError('CELL_LIMIT', 'Nullspace matrix exceeds the cell limit.')
    basis = [[Fraction(0) for _ in free] for _ in range(n)]
    for j, column in enumerate(free):
        basis[column][j] = Fraction(1)
        for i, pivot in enumerate(pivots):
            basis[pivot][j] = budget.mul(Fraction(-1), reduced[i][column])
    determinant = None
    if m == n:
        determinant = encode_coefficient(budget.div(Fraction(int(rank == n)), det_u))
    certificate: MatrixCertificate = {
        'schema': 'foundation-math-rational-matrix/1',
        'matrix': encode_matrix(original),
        'rref': encode_matrix(Matrix('Q', m, n, tuple(tuple(row) for row in reduced))),
        'transform': encode_matrix(Matrix('Q', m, m, tuple(tuple(row) for row in transform))),
        'rank': rank, 'pivots': pivots, 'free_columns': free,
        'nullspace': encode_matrix(Matrix('Q', n, len(free), tuple(tuple(row) for row in basis))),
        'operations': operations, 'determinant': determinant,
    }
    check_output(certificate, limits)
    return certificate

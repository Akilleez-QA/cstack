"""Construct system certificates; never the authority that accepts them."""
from __future__ import annotations

from fractions import Fraction
from exact_linalg.producer import produce as produce_matrix
from .contract import (
    Budget, Limits, SCHEMA, SystemCertificate, check_output, check_tree,
    encode_coefficient, encode_system, encode_vector, parse_matrix,
    parse_system, split_work,
)


def produce(system: object, limits: Limits = Limits()) -> SystemCertificate:
    """Produce x0 and a certified complete Q-kernel, or a separating y.

    Z restricts both A and b tokens only. This is not integer feasibility.
    Resource exhaustion raises MathError without a partial certificate.
    The caller should use the independent verifier before trusting output.
    """
    check_tree(system, limits)
    original = parse_system(system, limits)
    matrix_limits, local_limits = split_work(limits)
    matrix_certificate = produce_matrix(system['matrix'], matrix_limits)
    budget = Budget(local_limits)
    transform = parse_matrix(matrix_certificate['transform'], limits,
                             '$.matrix_certificate.transform',
                             coefficient_bits=limits.max_intermediate_bits)
    m, n = original.matrix.rows, original.matrix.cols
    transformed_rhs = []
    for row in transform.entries:
        total = Fraction(0)
        budget.tick()
        for entry, value in zip(row, original.rhs):
            total = budget.add(total, budget.mul(entry, value))
        transformed_rhs.append(total)
    rank = matrix_certificate['rank']
    for index in range(rank, m):
        budget.tick()
        if transformed_rhs[index]:
            certificate: SystemCertificate = {
                'schema': SCHEMA,
                'system': encode_system(original),
                'outcome': 'inconsistent',
                'left_nullvector': encode_vector(transform.entries[index]),
                'rhs_pairing': encode_coefficient(transformed_rhs[index]),
            }
            check_output(certificate, limits)
            return certificate
    particular = [Fraction(0) for _ in range(n)]
    for row, column in enumerate(matrix_certificate['pivots']):
        budget.tick()
        particular[column] = transformed_rhs[row]
    certificate = {
        'schema': SCHEMA,
        'system': encode_system(original),
        'outcome': 'consistent',
        'matrix_certificate': matrix_certificate,
        'particular': encode_vector(particular),
    }
    check_output(certificate, limits)
    return certificate

"""Independent certificate checker. No producer import or elimination.

Consistent: check frozen matrix proof and A*x0=b directly.
Inconsistent: check y^T*A=0 and y^T*b!=0 directly, without any matrix proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal
from exact_linalg.verifier import verify as verify_matrix
from .contract import (
    Budget, Limits, MathError, Matrix, SCHEMA, check_output, check_tree,
    encode_coefficient, encode_matrix, encode_vector, parse_coefficient,
    parse_matrix, parse_system, parse_vector, split_work, strict_keys,
)


@dataclass(frozen=True)
class VerifiedSystem:
    rows: int
    cols: int
    input_domain: str
    outcome: Literal['consistent', 'inconsistent']
    particular: tuple[Fraction, ...] | None = None
    nullspace: Matrix | None = None
    rank: int | None = None
    left_nullvector: tuple[Fraction, ...] | None = None
    rhs_pairing: Fraction | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            'accepted': True,
            'scope': 'one_explicit_linear_system',
            'computational_field': 'Q',
            'input_domain': self.input_domain,
            'rows': self.rows, 'cols': self.cols, 'outcome': self.outcome,
            'formal_proof': False,
            'runtime_goal_acceptance': False,
            'family_or_generic_claim': False,
        }
        if self.outcome == 'consistent':
            if self.particular is None or self.nullspace is None or self.rank is None:
                raise MathError('INTERNAL_ERROR', 'Incomplete verified consistent result.')
            result.update(particular=encode_vector(self.particular),
                          nullspace=encode_matrix(self.nullspace), rank=self.rank,
                          nullity=self.cols - self.rank)
        else:
            if self.left_nullvector is None or self.rhs_pairing is None:
                raise MathError('INTERNAL_ERROR', 'Incomplete verified inconsistent result.')
            result.update(left_nullvector=encode_vector(self.left_nullvector),
                          rhs_pairing=encode_coefficient(self.rhs_pairing))
        return result


def _invalid(message: str, path: str = '$.certificate') -> None:
    raise MathError('INVALID_CERTIFICATE', message, path)


def verify(system: object, certificate: object,
           limits: Limits = Limits()) -> VerifiedSystem:
    """Check against separately supplied A,b; return no unverified claims.

    The embedded system is not trusted as the expected input. Binding includes
    dimensions, exact domain tags and every coefficient of both A and b.
    """
    check_tree({'system': system, 'certificate': certificate}, limits)
    original = parse_system(system, limits)
    if type(certificate) is not dict:
        _invalid('Certificate must be an object.')
    outcome = certificate.get('outcome')
    if type(outcome) is not str or outcome not in ('consistent', 'inconsistent'):
        _invalid('Outcome must be consistent or inconsistent.', '$.certificate.outcome')
    common = {'schema', 'system', 'outcome'}
    extra = ({'matrix_certificate', 'particular'} if outcome == 'consistent'
             else {'left_nullvector', 'rhs_pairing'})
    strict_keys(certificate, common | extra, '$.certificate')
    if type(certificate['schema']) is not str or certificate['schema'] != SCHEMA:
        _invalid('Unknown system certificate schema.', '$.certificate.schema')
    bound = parse_system(certificate['system'], limits, '$.certificate.system')
    matrix_limits, local_limits = split_work(limits)
    budget = Budget(local_limits)
    budget.tick(original.matrix.rows * original.matrix.cols + original.matrix.rows + 1)
    if bound != original:
        _invalid('Certificate is not bound to this exact system and domain.', '$.certificate.system')
    matrix, rhs = original.matrix, original.rhs
    m, n = matrix.rows, matrix.cols
    if outcome == 'consistent':
        particular = parse_vector(certificate['particular'], n, limits, '$.certificate.particular')
        checked = verify_matrix(system['matrix'], certificate['matrix_certificate'], matrix_limits)
        # Only parse/expose this basis after the independent frozen checker accepts it.
        nullspace = parse_matrix(certificate['matrix_certificate']['nullspace'], limits,
                                 '$.certificate.matrix_certificate.nullspace',
                                 coefficient_bits=limits.max_intermediate_bits)
        for i, row in enumerate(matrix.entries):
            total = Fraction(0)
            budget.tick()
            for entry, value in zip(row, particular):
                total = budget.add(total, budget.mul(entry, value))
            if total != rhs[i]:
                _invalid('The particular solution does not satisfy A*x=b.',
                         f'$.certificate.particular[{i}]')
        result = VerifiedSystem(m, n, matrix.domain, outcome,
                                particular=particular, nullspace=nullspace, rank=checked.rank)
    else:
        witness = parse_vector(certificate['left_nullvector'], m, limits,
                               '$.certificate.left_nullvector')
        claimed = parse_coefficient(certificate['rhs_pairing'], limits.max_intermediate_bits,
                                    '$.certificate.rhs_pairing')
        for j in range(n):
            total = Fraction(0)
            budget.tick()
            for i in range(m):
                total = budget.add(total, budget.mul(witness[i], matrix.entries[i][j]))
            if total != 0:
                _invalid('The witness does not satisfy y^T*A=0.', '$.certificate.left_nullvector')
        total = Fraction(0)
        for value, entry in zip(witness, rhs):
            total = budget.add(total, budget.mul(value, entry))
        if total == 0 or total != claimed:
            _invalid('The exact claimed y^T*b must equal the computed nonzero pairing.',
                     '$.certificate.rhs_pairing')
        result = VerifiedSystem(m, n, matrix.domain, outcome,
                                left_nullvector=witness, rhs_pairing=total)
    check_output(result.to_dict(), limits)
    return result

"""Data-only contracts for one bounded explicit rational linear system.

The exact_linalg contract is vendored, byte-identical, from frozen v0.6.
Only this contract module is shared between system producer and verifier.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal, NotRequired, TypedDict

from exact_linalg.contract import (
    Budget, Coefficient, Limits, MathError, Matrix, MatrixCertificate,
    MatrixSpec, check_output, check_tree, encode_coefficient, encode_matrix,
    loads_bounded, parse_coefficient, parse_matrix, strict_keys, validate_limits,
)

SCHEMA = 'foundation-math-rational-linear-system/1'


class SystemSpec(TypedDict):
    matrix: MatrixSpec
    rhs: list[Coefficient]


class ConsistentCertificate(TypedDict):
    schema: Literal['foundation-math-rational-linear-system/1']
    system: SystemSpec
    outcome: Literal['consistent']
    matrix_certificate: MatrixCertificate
    particular: list[Coefficient]


class InconsistentCertificate(TypedDict):
    schema: Literal['foundation-math-rational-linear-system/1']
    system: SystemSpec
    outcome: Literal['inconsistent']
    left_nullvector: list[Coefficient]
    rhs_pairing: Coefficient


SystemCertificate = ConsistentCertificate | InconsistentCertificate


class SystemRequest(TypedDict):
    operation: Literal['solve', 'verify']
    system: SystemSpec
    certificate: NotRequired[SystemCertificate]


@dataclass(frozen=True)
class System:
    matrix: Matrix
    rhs: tuple[Fraction, ...]


def parse_vector(value: object, size: int, limits: Limits, path: str,
                 *, input_domain: str | None = None) -> tuple[Fraction, ...]:
    if type(value) is not list or len(value) != size:
        raise MathError('DIMENSION_MISMATCH', 'Vector length does not match the explicit dimension.', path)
    bits = limits.max_input_bits if input_domain is not None else limits.max_intermediate_bits
    result = []
    for index, item in enumerate(value):
        item_path = f'{path}[{index}]'
        if input_domain == 'Z' and type(item) is not int:
            raise MathError('INVALID_COEFFICIENT', 'Z inputs permit only integer coefficient tokens.', item_path)
        result.append(parse_coefficient(item, bits, item_path))
    return tuple(result)


def parse_system(value: object, limits: Limits, path: str = '$.system') -> System:
    strict_keys(value, {'matrix', 'rhs'}, path)
    matrix = parse_matrix(value['matrix'], limits, path + '.matrix')
    rhs = parse_vector(value['rhs'], matrix.rows, limits, path + '.rhs',
                       input_domain=matrix.domain)
    return System(matrix, rhs)


def encode_vector(value: tuple[Fraction, ...] | list[Fraction]) -> list[Coefficient]:
    return [encode_coefficient(item) for item in value]


def encode_system(system: System) -> SystemSpec:
    return {'matrix': encode_matrix(system.matrix), 'rhs': encode_vector(system.rhs)}


def split_work(limits: Limits) -> tuple[Limits, Limits]:
    """Partition, never duplicate, the parent arithmetic/scan work ceiling.

    Each child gets a deterministic allotment. Unused work is not transferable.
    Structural, bit, per-matrix cell, operation-log and byte caps still apply
    independently to each relevant object and stage.
    """
    validate_limits(limits)
    first = limits.max_work // 2
    return replace(limits, max_work=first), replace(limits, max_work=limits.max_work - first)

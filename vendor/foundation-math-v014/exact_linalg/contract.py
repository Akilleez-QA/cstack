"""Strict bounded data contract shared by producer and verifier, not algorithms."""
from __future__ import annotations

from dataclasses import dataclass, fields
from fractions import Fraction
import json
from math import gcd
from typing import Literal, NotRequired, TypedDict


class RationalSpec(TypedDict):
    num: int
    den: int


Coefficient = int | RationalSpec


class MatrixSpec(TypedDict):
    domain: Literal['Z', 'Q']
    rows: int
    cols: int
    entries: list[list[Coefficient]]


class RowOperation(TypedDict):
    op: Literal['swap', 'scale', 'add']
    i: NotRequired[int]
    j: NotRequired[int]
    target: NotRequired[int]
    source: NotRequired[int]
    factor: NotRequired[Coefficient]


class MatrixCertificate(TypedDict):
    schema: str
    matrix: MatrixSpec
    rref: MatrixSpec
    transform: MatrixSpec
    rank: int
    pivots: list[int]
    free_columns: list[int]
    nullspace: MatrixSpec
    operations: list[RowOperation]
    determinant: Coefficient | None


class MathError(ValueError):
    """Stable machine-readable failure; never a successful mathematical verdict."""
    def __init__(self, code: str, message: str, path: str = '$') -> None:
        super().__init__(message)
        self.code, self.message, self.path = code, message, path

    def to_dict(self) -> dict[str, str]:
        return {'code': self.code, 'message': self.message, 'path': self.path}


_HARD = {
    'max_dimension': 16, 'max_cells': 256, 'max_input_bits': 128,
    'max_intermediate_bits': 2048, 'max_operations': 1024,
    'max_work': 2_000_000, 'max_output_bytes': 1_000_000,
    'max_input_bytes': 1_000_000, 'max_nodes': 100_000, 'max_depth': 32,
}


@dataclass(frozen=True)
class Limits:
    max_dimension: int = 16
    max_cells: int = 256
    max_input_bits: int = 128
    max_intermediate_bits: int = 2048
    max_operations: int = 1024
    max_work: int = 2_000_000
    max_output_bytes: int = 1_000_000
    max_input_bytes: int = 1_000_000
    max_nodes: int = 100_000
    max_depth: int = 32

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            minimum = 1 if field.name.endswith('bits') else 0
            if type(value) is not int or not minimum <= value <= _HARD[field.name]:
                raise MathError('INVALID_LIMIT', 'Limits may only lower the hard ceilings.', '$.limits.' + field.name)
        if self.max_input_bits > self.max_intermediate_bits:
            raise MathError('INVALID_LIMIT', 'Input bit limit exceeds intermediate bit limit.', '$.limits')


def validate_limits(limits: Limits) -> None:
    if type(limits) is not Limits:
        raise MathError('INVALID_LIMIT', 'Expected a Limits value.', '$.limits')
    limits.__post_init__()


def strict_keys(obj: object, expected: set[str], path: str) -> None:
    if type(obj) is not dict or set(obj) != expected:
        raise MathError('INVALID_SCHEMA', 'Object fields do not match the exact schema.', path)


def require_int(value: object, minimum: int, maximum: int, path: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise MathError('INVALID_INTEGER', 'Expected an integer within the allowed bounds.', path)
    return value


def _bit_check(value: int, max_bits: int, path: str) -> None:
    if value.bit_length() > max_bits:
        raise MathError('BIT_LIMIT', 'Exact coefficient exceeds the bit limit.', path)


def parse_coefficient(value: object, max_bits: int, path: str) -> Fraction:
    if type(value) is int:
        _bit_check(value, max_bits, path)
        return Fraction(value)
    strict_keys(value, {'num', 'den'}, path)
    num, den = value['num'], value['den']
    if type(num) is not int or type(den) is not int:
        raise MathError('INVALID_COEFFICIENT', 'Rational numerator and denominator must be integers.', path)
    _bit_check(num, max_bits, path + '.num')
    _bit_check(den, max_bits, path + '.den')
    if den <= 1 or num == 0 or gcd(num, den) != 1:
        raise MathError('NONCANONICAL_RATIONAL', 'Use a reduced rational with denominator > 1; encode integers as integers.', path)
    return Fraction(num, den)


def encode_coefficient(value: Fraction) -> Coefficient:
    return value.numerator if value.denominator == 1 else {'num': value.numerator, 'den': value.denominator}


@dataclass(frozen=True)
class Matrix:
    domain: str
    rows: int
    cols: int
    entries: tuple[tuple[Fraction, ...], ...]


def parse_matrix(obj: object, limits: Limits, path: str = '$', coefficient_bits: int | None = None) -> Matrix:
    strict_keys(obj, {'domain', 'rows', 'cols', 'entries'}, path)
    if type(obj['domain']) is not str or obj['domain'] not in ('Z', 'Q'):
        raise MathError('INVALID_DOMAIN', 'Only literal Z and Q coefficient domains are supported.', path + '.domain')
    rows = require_int(obj['rows'], 0, limits.max_dimension, path + '.rows')
    cols = require_int(obj['cols'], 0, limits.max_dimension, path + '.cols')
    if rows * cols > limits.max_cells:
        raise MathError('CELL_LIMIT', 'Matrix exceeds the cell limit.', path)
    entries = obj['entries']
    if type(entries) is not list or len(entries) != rows:
        raise MathError('DIMENSION_MISMATCH', 'Entry rows do not match explicit dimensions.', path + '.entries')
    result = []
    bits = limits.max_input_bits if coefficient_bits is None else coefficient_bits
    for i, row in enumerate(entries):
        row_path = f'{path}.entries[{i}]'
        if type(row) is not list or len(row) != cols:
            raise MathError('DIMENSION_MISMATCH', 'Entry columns do not match explicit dimensions.', row_path)
        parsed = []
        for j, value in enumerate(row):
            entry_path = f'{row_path}[{j}]'
            if obj['domain'] == 'Z' and type(value) is not int:
                raise MathError('INVALID_COEFFICIENT', 'Z inputs permit only integer coefficient tokens.', entry_path)
            parsed.append(parse_coefficient(value, bits, entry_path))
        result.append(tuple(parsed))
    return Matrix(obj['domain'], rows, cols, tuple(result))


def encode_matrix(matrix: Matrix) -> MatrixSpec:
    return {'domain': matrix.domain, 'rows': matrix.rows, 'cols': matrix.cols,
            'entries': [[encode_coefficient(x) for x in row] for row in matrix.entries]}


class Budget:
    """Bounded rational arithmetic. Intermediates are checked after each primitive."""
    def __init__(self, limits: Limits) -> None:
        validate_limits(limits)
        self.limits, self.work = limits, 0

    def tick(self, amount: int = 1) -> None:
        if type(amount) is not int or amount < 0:
            raise MathError('INTERNAL_ERROR', 'Invalid work charge.')
        self.work += amount
        if self.work > self.limits.max_work:
            raise MathError('WORK_LIMIT', 'Exact arithmetic work budget exhausted.')

    def check(self, value: Fraction) -> Fraction:
        _bit_check(value.numerator, self.limits.max_intermediate_bits, '$.arithmetic')
        _bit_check(value.denominator, self.limits.max_intermediate_bits, '$.arithmetic')
        return value

    def mul(self, left: Fraction, right: Fraction) -> Fraction:
        self.tick()
        self.check(left)
        self.check(right)
        return self.check(left * right)

    def add(self, left: Fraction, right: Fraction) -> Fraction:
        self.tick()
        self.check(left)
        self.check(right)
        return self.check(left + right)

    def div(self, left: Fraction, right: Fraction) -> Fraction:
        self.tick()
        self.check(left)
        self.check(right)
        if not right:
            raise MathError('DIVISION_BY_ZERO', 'Division by zero is not defined.')
        return self.check(left / right)


def check_tree(obj: object, limits: Limits) -> None:
    """Bound input objects before recursive codecs or Fraction construction."""
    validate_limits(limits)
    stack = [(obj, 0)]
    nodes, byte_floor = 0, 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > limits.max_nodes or nodes + len(stack) > limits.max_nodes:
            raise MathError('NODE_LIMIT', 'Payload exceeds the structural node limit.')
        if depth > limits.max_depth:
            raise MathError('DEPTH_LIMIT', 'Payload exceeds the nesting limit.')
        kind = type(value)
        if kind is dict:
            children = len(value) * 2
            if nodes + len(stack) + children > limits.max_nodes:
                raise MathError('NODE_LIMIT', 'Payload exceeds the structural node limit.')
            if any(type(key) is not str for key in value):
                raise MathError('INVALID_SCHEMA', 'Object keys must be strings.')
            stack.extend((item, depth + 1) for pair in value.items() for item in pair)
            byte_floor += 2 + max(0, len(value) - 1) + len(value)
        elif kind is list:
            if nodes + len(stack) + len(value) > limits.max_nodes:
                raise MathError('NODE_LIMIT', 'Payload exceeds the structural node limit.')
            stack.extend((item, depth + 1) for item in value)
            byte_floor += 2 + max(0, len(value) - 1)
        elif kind is str:
            if len(value) > limits.max_input_bytes:
                raise MathError('INPUT_LIMIT', 'Payload exceeds the byte limit.')
            try:
                byte_floor += len(value.encode('utf-8')) + 2
            except UnicodeEncodeError:
                raise MathError('INVALID_JSON', 'Unpaired Unicode surrogate is not supported.') from None
        elif kind is int:
            _bit_check(value, limits.max_intermediate_bits, '$')
            byte_floor += len(str(value))
        elif value is None or kind is bool:
            byte_floor += 4 if value is None or value is True else 5
        else:
            raise MathError('INVALID_TYPE', 'Only JSON-like data values are supported.')
        if byte_floor > limits.max_input_bytes:
            raise MathError('INPUT_LIMIT', 'Payload exceeds the byte limit.')
    # Bounds above ensure this final exact size calculation is itself bounded.
    if len(json.dumps(obj, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')) > limits.max_input_bytes:
        raise MathError('INPUT_LIMIT', 'Payload exceeds the byte limit.')


def check_output(obj: object, limits: Limits) -> None:
    if len(json.dumps(obj, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')) > limits.max_output_bytes:
        raise MathError('OUTPUT_LIMIT', 'Result exceeds the output byte limit.')


def loads_bounded(raw: bytes, limits: Limits = Limits()) -> object:
    """Parse bounded strict JSON, rejecting duplicate fields before schema checks."""
    validate_limits(limits)
    if type(raw) is not bytes:
        raise MathError('INVALID_TYPE', 'JSON input must be bytes.')
    if len(raw) > limits.max_input_bytes:
        raise MathError('INPUT_LIMIT', 'JSON input exceeds the byte limit.')
    # Scan nesting before invoking Python's recursive JSON parser.
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > limits.max_depth:
                raise MathError('DEPTH_LIMIT', 'JSON input exceeds the nesting limit.')
        elif byte in (93, 125):
            depth -= 1
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in items:
            if key in result:
                raise MathError('DUPLICATE_KEY', 'Duplicate JSON object key.')
            result[key] = value
        return result
    def integer(token: str) -> int:
        # Avoid conversion of enormous decimal tokens; 2048 bits needs <=617 digits.
        if len(token.lstrip('-')) > limits.max_intermediate_bits:
            raise MathError('BIT_LIMIT', 'Integer token exceeds the bit limit.')
        value = int(token)
        _bit_check(value, limits.max_intermediate_bits, '$')
        return value
    def reject_number(token: str) -> None:
        raise MathError('INVALID_COEFFICIENT', 'Floating-point and nonfinite tokens are not supported.')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_int=integer,
                            parse_float=reject_number, parse_constant=reject_number)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, MathError):
            raise
        raise MathError('INVALID_JSON', 'Input is not valid bounded UTF-8 JSON.') from None
    check_tree(result, limits)
    return result

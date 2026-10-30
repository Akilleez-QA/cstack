"""Exact small integer polynomial witnesses, outside runtime goal acceptance.

Only unrestricted formal polynomials in algebraically independent variables over
Q, characteristic zero. Resource failure is inconclusive, never absence of a
witness. The frozen lab's point checker is not an identity or trace checker.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, NotRequired, TypedDict
from polynomial_witness.api import construct
from polynomial_witness.checker import verify_witness
from polynomial_witness.contract import (CAUGHT_ERRORS, Limits, WitnessError, strict_json,
                                         validate_limits, HARD_LIMITS)
from polynomial_witness._vendor.polynomial import PolynomialRequest, MAX_DEGREE

VERSION = '0.7.0-dev'
MAX_INPUT_BYTES = 262144
MAX_OUTPUT_BYTES = 1048576
MAX_NODES = 16384
MAX_DEPTH = 80
SCOPE = 'characteristic_zero_unrestricted_formal_polynomial'

class PolynomialWitnessRequest(TypedDict):
    operation: Literal['construct', 'verify']
    request: PolynomialRequest
    witness: NotRequired[dict]

def _common() -> dict:
    return {'schema_version': 1, 'scope': SCOPE, 'coefficient_field': 'Q',
            'characteristic': 0, 'formal_proof': False, 'runtime_goal_acceptance': False}

def witness_error_receipt(error: Exception) -> dict:
    return {**_common(), 'status': 'error',
            'error': {'code': getattr(error, 'code', 'representation_limit'), 'message': str(error)},
            'conclusion': 'No mathematical conclusion: failure is not absence of a counterexample.'}

def _bounded_json(value: object, maximum: int, label: str) -> bytes:
    chunks, size = [], 0
    for chunk in json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).iterencode(value):
        data = chunk.encode('ascii')
        size += len(data)
        if size > maximum:
            raise WitnessError('resource_limit', f'{label} exceeds byte limit; no result is promoted')
        chunks.append(data)
    return b''.join(chunks)

def _snapshot(raw: object) -> tuple[dict, bytes]:
    # Bound depth, shape and integer size before serializing, even for Python API
    # input. Cycles hit these explicit caps; never follow caller-selected paths.
    stack, nodes = [(raw, 0)], 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise WitnessError('resource_limit', 'request node/depth budget exceeded')
        kind = type(value)
        if kind is dict:
            if len(value) > MAX_NODES:
                raise WitnessError('resource_limit', 'request object exceeds node budget')
            for key, child in value.items():
                if type(key) is not str:
                    raise WitnessError('invalid_input', 'JSON object keys must be strings')
                if nodes + len(stack) + 2 > MAX_NODES:
                    raise WitnessError('resource_limit', 'request node budget exceeded before traversal allocation')
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif kind is list:
            if len(value) > MAX_NODES:
                raise WitnessError('resource_limit', 'request array exceeds node budget')
            if nodes + len(stack) + len(value) > MAX_NODES:
                raise WitnessError('resource_limit', 'request node budget exceeded before traversal allocation')
            stack.extend((child, depth + 1) for child in value)
        elif kind is str:
            if len(value) > 4096:
                raise WitnessError('resource_limit', 'request string exceeds bound')
        elif kind is int:
            if value.bit_length() > 4096:
                raise WitnessError('resource_limit', 'request integer exceeds wire bit bound')
        elif kind not in (bool, type(None)):
            raise WitnessError('invalid_input', 'only exact JSON data types are accepted; no floats or custom objects')
    encoded = _bounded_json(raw, MAX_INPUT_BYTES, 'combined request')
    snapshot = json.loads(encoded)
    if type(snapshot) is not dict:
        raise WitnessError('invalid_input', 'request must be an object')
    operation = snapshot.get('operation')
    if type(operation) is not str or operation not in ('construct', 'verify'):
        raise WitnessError('unsupported_operation', 'operation must be construct or verify')
    expected = {'operation', 'request'} | ({'witness'} if operation == 'verify' else set())
    if set(snapshot) != expected:
        raise WitnessError('invalid_input', 'request has missing or unexpected fields')
    return snapshot, encoded

def _implementation() -> dict:
    root = Path(__file__).resolve().parents[1]
    names = ('polynomial_witness/__init__.py', 'polynomial_witness/__main__.py',
             'polynomial_witness/api.py', 'polynomial_witness/checker.py',
             'polynomial_witness/contract.py', 'polynomial_witness/producer.py',
             'polynomial_witness/_vendor/__init__.py', 'polynomial_witness/_vendor/calculator.py',
             'polynomial_witness/_vendor/polynomial.py', 'foundation_math/polynomial_witness.py')
    return {'name': 'foundation-math-small-polynomial-witness', 'version': VERSION,
            'source_sha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in names}}

def _construction_bound(result: dict, original_request: dict) -> dict:
    """No extra normalization: executable cap corollary, not exact-D metadata.

    First-preserving substitutions satisfy sum(chosen)<=deg(nonzero difference).
    The frozen producer already bounded that total degree by MAX_DEGREE. The
    point checker does not certify this theorem or the construction trace.
    """
    variables = original_request['variables']
    if type(variables) is not list or not 0 <= len(variables) <= 8:
        raise WitnessError('internal_invariant', 'Construction bound needs the validated original variable list')
    variable_count = len(variables)
    coordinate_sum = sum(result['verification']['assignment'].values())
    actual = result['usage']['substitution_trials']
    bound = variable_count + MAX_DEGREE
    if (type(actual) is not int or actual != variable_count + coordinate_sum
            or not 0 <= coordinate_sum <= MAX_DEGREE or not 0 <= actual <= bound):
        raise WitnessError('internal_invariant', 'Producer trial count violates the total-degree bound; no result is promoted')
    return {'kind': 'normalizer_total_degree_cap', 'variable_count': variable_count,
            'normalizer_total_degree_cap': MAX_DEGREE, 'substitution_trial_bound': bound,
            'actual_substitution_trials': actual, 'sum_chosen_coordinates': coordinate_sum,
            'legacy_hard_trial_cap': HARD_LIMITS.max_trials,
            'exact_difference_degree_recomputed': False, 'point_checker_certifies_bound': False}

def calculate_polynomial_witness(raw: object, limits: Limits = Limits()) -> dict:
    """Bounded operation envelope, not a registered runtime goal domain."""
    try:
        limits = validate_limits(limits)
        request, encoded = _snapshot(raw)
        operation = request['operation']
        result = (construct(request['request'], limits) if operation == 'construct'
                  else verify_witness(request['request'], request['witness'], limits))
        if result['status'] == 'error':
            return witness_error_receipt(WitnessError(result['error']['code'], result['error']['message']))
        if result['status'] == 'rejected':
            return {**_common(), 'status': 'rejected', 'operation': 'verify',
                    'error': result['error'],
                    'conclusion': 'Only this supplied witness is rejected; no conclusion about other possible witnesses.'}
        receipt = {**_common(), 'status': 'success', 'operation': operation,
                   'request_sha256': sha256(encoded).hexdigest(), 'implementation': _implementation(),
                   'result': result}
        if operation == 'construct' and result['result']['kind'] == 'nonzero_evaluation':
            receipt['construction_bound'] = _construction_bound(result, request['request'])
        _bounded_json(receipt, MAX_OUTPUT_BYTES, 'complete receipt')
        return receipt
    except CAUGHT_ERRORS as error:
        return witness_error_receipt(error)
    except OSError:
        return witness_error_receipt(WitnessError('internal_error', 'Implementation provenance could not be read; no evidence result is available.'))

def construct_polynomial_witness(request: object, limits: Limits = Limits()) -> dict:
    return calculate_polynomial_witness({'operation': 'construct', 'request': request}, limits)

def check_polynomial_witness(request: object, witness: object, limits: Limits = Limits()) -> dict:
    return calculate_polynomial_witness({'operation': 'verify', 'request': request, 'witness': witness}, limits)

def calculate_polynomial_witness_json(raw: bytes | str, limits: Limits = Limits()) -> dict:
    try:
        return calculate_polynomial_witness(strict_json(raw), limits)
    except CAUGHT_ERRORS as error:
        return witness_error_receipt(error)

__all__ = ['Limits', 'WitnessError', 'PolynomialRequest', 'PolynomialWitnessRequest',
           'construct_polynomial_witness', 'check_polynomial_witness',
           'calculate_polynomial_witness', 'calculate_polynomial_witness_json', 'witness_error_receipt']

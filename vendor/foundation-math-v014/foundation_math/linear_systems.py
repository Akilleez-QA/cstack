"""Checked explicit rational linear systems, never runtime-goal acceptance.

Z restricts input tokens, not the solution field. One RHS only. No lattice,
generic/family theorem, formal proof or unrestricted expression evaluation.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from exact_systems.api import handle_request
from exact_systems.contract import (
    Limits, MathError, SystemSpec, SystemCertificate, SystemRequest,
    check_output, loads_bounded,
)

VERSION = '0.8.0-dev'
MAX_INPUT_BYTES = Limits().max_input_bytes
IMPLEMENTATION_FILES = tuple(
    f'{package}/{name}.py' for package in ('exact_linalg', 'exact_systems')
    for name in ('__init__', '__main__', 'api', 'contract', 'producer', 'verifier')
) + ('foundation_math/linear_systems.py',)


def _common() -> dict[str, object]:
    return {'schema_version': 1, 'scope': 'one_explicit_linear_system',
            'computational_field': 'Q', 'formal_proof': False,
            'runtime_goal_acceptance': False, 'family_or_generic_claim': False}


def system_error_receipt(error: MathError) -> dict[str, object]:
    """No accepted outcome or partial certificate accompanies an error."""
    return {**_common(), 'status': 'error', 'error': error.to_dict()}


def _implementation() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return {'name': 'foundation-math-exact-linear-systems', 'version': VERSION,
            'source_sha256': {name: sha256((root / name).read_bytes()).hexdigest()
                              for name in IMPLEMENTATION_FILES}}


def calculate_system(request: object, limits: Limits = Limits()) -> dict[str, object]:
    """Produce then check, or check against separate expected A,b.

    The frozen API bounds exact builtins and the combined request before parsing.
    It partitions work across production/verification. Provenance hashes bind
    bytes only, not authenticity; fixed owned files are never caller-selected.
    """
    response = handle_request(request, limits)
    if not response['ok']:
        error = response['error']
        return system_error_receipt(MathError(error['code'], error['message'], error['path']))
    try:
        encoded = json.dumps(request, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode('ascii')
        receipt = {**_common(), 'status': 'success', 'operation': request['operation'],
                   'request_sha256': sha256(encoded).hexdigest(),
                   'implementation': _implementation(), 'result': response}
        check_output(receipt, limits)
        return receipt
    except MathError as error:
        return system_error_receipt(error)
    except OSError:
        return system_error_receipt(MathError('INTERNAL_ERROR', 'Implementation provenance could not be read.'))


def solve_system(system: object, limits: Limits = Limits()) -> dict[str, object]:
    return calculate_system({'operation': 'solve', 'system': system}, limits)


def check_system_certificate(system: object, certificate: object,
                             limits: Limits = Limits()) -> dict[str, object]:
    return calculate_system({'operation': 'verify', 'system': system,
                             'certificate': certificate}, limits)


def calculate_system_json(raw: bytes, limits: Limits = Limits()) -> dict[str, object]:
    try:
        return calculate_system(loads_bounded(raw, limits), limits)
    except MathError as error:
        return system_error_receipt(error)


__all__ = ['Limits', 'MathError', 'SystemSpec', 'SystemCertificate', 'SystemRequest',
           'calculate_system', 'calculate_system_json', 'solve_system',
           'check_system_certificate', 'system_error_receipt']

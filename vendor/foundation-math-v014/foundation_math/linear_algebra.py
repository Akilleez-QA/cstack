"""Explicit bounded Q-matrix certificates, separate from runtime goal acceptance.

Z restricts input coefficient tokens only. Nullspace is a Q-vector-space basis,
never an integer-module/lattice basis or a symbolic/generic-rank claim.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from exact_linalg.api import handle_request
from exact_linalg.contract import (Limits, MathError, MatrixCertificate, MatrixSpec,
                                   check_output, loads_bounded)

VERSION = '0.6.0-dev'
MAX_INPUT_BYTES = Limits().max_input_bytes


class MatrixCalculationRequest(TypedDict):
    operation: Literal['certify', 'verify']
    matrix: MatrixSpec
    certificate: NotRequired[MatrixCertificate]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _implementation() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    names = ('exact_linalg/__init__.py', 'exact_linalg/contract.py',
             'exact_linalg/producer.py', 'exact_linalg/verifier.py',
             'exact_linalg/api.py', 'foundation_math/linear_algebra.py')
    # Fixed owned implementation files only; request data never selects paths.
    return {'name': 'foundation-math-exact-linear-algebra', 'version': VERSION,
            'source_sha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in names}}


def matrix_error_receipt(error: MathError) -> dict[str, object]:
    """A structured failure never carries acceptance or a partial certificate."""
    return {'schema_version': 1, 'status': 'error', 'scope': 'one_explicit_matrix',
            'computational_field': 'Q', 'formal_proof': False,
            'runtime_goal_acceptance': False, 'error': error.to_dict()}


def calculate_matrix(request: object, limits: Limits = Limits()) -> dict[str, object]:
    """Checked matrix request adapter with source/request-bound audit metadata.

    This function is deliberately not a registered work-queue goal domain.
    Hashes support reproducibility, not authentication or proof by themselves.
    """
    response = handle_request(request, limits)
    if not response['ok']:
        error = response['error']
        return matrix_error_receipt(MathError(error['code'], error['message'], error['path']))
    try:
        receipt = {
            'schema_version': 1, 'status': 'success', 'operation': request['operation'],
            'scope': 'one_explicit_matrix', 'computational_field': 'Q',
            'formal_proof': False, 'runtime_goal_acceptance': False,
            'request_sha256': sha256(_canonical(request)).hexdigest(),
            'implementation': _implementation(), 'result': response,
        }
        check_output(receipt, limits)
        return receipt
    except MathError as error:
        return matrix_error_receipt(error)
    except OSError:
        return matrix_error_receipt(MathError('INTERNAL_ERROR', 'Implementation provenance could not be read.'))


def certify_matrix(matrix: object, limits: Limits = Limits()) -> dict[str, object]:
    """Produce and independently verify a certificate for one explicit matrix."""
    return calculate_matrix({'operation': 'certify', 'matrix': matrix}, limits)


def check_matrix_certificate(matrix: object, certificate: object,
                             limits: Limits = Limits()) -> dict[str, object]:
    """Freshly check supplied certificate against a separately supplied matrix."""
    return calculate_matrix({'operation': 'verify', 'matrix': matrix,
                             'certificate': certificate}, limits)


def calculate_matrix_json(raw: bytes, limits: Limits = Limits()) -> dict[str, object]:
    """Strict bounded JSON entrypoint; errors are structured non-acceptances."""
    try:
        return calculate_matrix(loads_bounded(raw, limits), limits)
    except MathError as error:
        return matrix_error_receipt(error)


__all__ = ['Limits', 'MathError', 'MatrixSpec', 'MatrixCertificate',
           'MatrixCalculationRequest', 'calculate_matrix', 'calculate_matrix_json',
           'certify_matrix', 'check_matrix_certificate', 'matrix_error_receipt']

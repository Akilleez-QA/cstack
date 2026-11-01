"""Typed request adapter: no arbitrary expressions, paths, programs, or models."""
from __future__ import annotations
from typing import Literal, NotRequired, TypedDict
from .contract import (Limits, MathError, MatrixCertificate, MatrixSpec,
                       check_output, check_tree, strict_keys)
from .producer import produce
from .verifier import verify


class MatrixRequest(TypedDict):
    operation: Literal['certify', 'verify']
    matrix: MatrixSpec
    certificate: NotRequired[MatrixCertificate]


def handle_request(request: object, limits: Limits = Limits()) -> dict[str, object]:
    """Return structured success/error. Success is limited to one explicit matrix.

    Certify produces a certificate, then checks it with the independent verifier.
    Verify requires both the expected matrix and a certificate to bind the claim.
    Errors contain no acceptance or partial mathematical result.
    """
    try:
        check_tree(request, limits)
        if type(request) is not dict or request.get('operation') not in ('certify', 'verify'):
            raise MathError('INVALID_OPERATION', 'Operation must be certify or verify.')
        operation = request['operation']
        strict_keys(request, {'operation', 'matrix'} | ({'certificate'} if operation == 'verify' else set()), '$')
        certificate = produce(request['matrix'], limits) if operation == 'certify' else request['certificate']
        result = verify(request['matrix'], certificate, limits)
        response: dict[str, object] = {'ok': True, 'verification': result.to_dict()}
        if operation == 'certify':
            response['certificate'] = certificate
        check_output(response, limits)
        return response
    except MathError as error:
        return {'ok': False, 'error': error.to_dict()}

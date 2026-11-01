"""Bounded structured requests only. Never evaluate agent expressions."""
from __future__ import annotations

from .contract import (
    Limits, MathError, SystemRequest, check_output, check_tree, split_work,
    strict_keys,
)
from .producer import produce
from .verifier import verify


def handle_request(request: object, limits: Limits = Limits()) -> dict[str, object]:
    """Solve-and-check, or independently verify; errors never carry acceptance.

    Work ceilings are partitioned between stages, not reset at each stage.
    """
    try:
        check_tree(request, limits)
        if type(request) is not dict or request.get('operation') not in ('solve', 'verify'):
            raise MathError('INVALID_OPERATION', 'Operation must be solve or verify.')
        operation = request['operation']
        strict_keys(request, {'operation', 'system'} | ({'certificate'} if operation == 'verify' else set()), '$')
        if operation == 'solve':
            producer_limits, verifier_limits = split_work(limits)
            certificate = produce(request['system'], producer_limits)
            result = verify(request['system'], certificate, verifier_limits)
        else:
            certificate = request['certificate']
            result = verify(request['system'], certificate, limits)
        response: dict[str, object] = {'ok': True, 'verification': result.to_dict()}
        if operation == 'solve':
            response['certificate'] = certificate
        check_output(response, limits)
        return response
    except MathError as error:
        return {'ok': False, 'error': error.to_dict()}

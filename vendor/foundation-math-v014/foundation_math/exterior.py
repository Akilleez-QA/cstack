"""Formal exterior arithmetic adapter; never a geometric or proof acceptance path."""
import json
import sys
from exterior_power.contract import DomainError

MAX_OUTPUT_BYTES = 2097152  # Whole CLI envelope, distinct from the bridge's limits.


def common():
    return {'schema_version': 1, 'scope': 'formal_exterior_arithmetic_only',
            'formal_proof': False, 'runtime_goal_acceptance': False,
            'geometric_realization': False, 'map_existence_or_injectivity': False,
            'table_group_identification_assumed': True, 'supplied_splitting_assumed': True}


def error_receipt(code, message):
    return {**common(), 'status': 'error', 'error': {'code': code, 'message': message}}


def calculate_exterior(request):
    try:
        from exterior_power.producer import calculate
        from exterior_power.verifier import verify
        certificate = calculate(request)
        verification = verify(request, certificate)
        return {**common(), 'status': 'success', 'operation': 'calculate',
                'result': {'certificate': certificate, 'verification': verification}}
    except DomainError as error:
        return error_receipt(error.code, str(error))
    except Exception:
        return error_receipt('E_INTERNAL', 'Unexpected implementation failure; result withheld')


def check_exterior_certificate(request, certificate):
    # This path never imports producer or fusion; the checker uses Adams/Newton.
    try:
        from exterior_power.verifier import verify
        verification = verify(request, certificate)
        return {**common(), 'status': 'success', 'operation': 'verify', 'result': {'verification': verification}}
    except DomainError as error:
        return error_receipt(error.code, str(error))
    except Exception:
        return error_receipt('E_INTERNAL', 'Unexpected implementation failure; result withheld')


def exterior_cli(argv):
    from exterior_power.contract import BUDGETS, DomainError, read_json
    try:
        if len(argv) == 2 and argv[0] == 'exterior-calculate':
            receipt = calculate_exterior(read_json(argv[1], BUDGETS['request_bytes']))
        elif len(argv) == 3 and argv[0] == 'exterior-check':
            receipt = check_exterior_certificate(read_json(argv[1], BUDGETS['request_bytes']),
                                                read_json(argv[2], BUDGETS['certificate_bytes']))
        else:
            receipt = error_receipt('E_USAGE', 'Usage: exterior-calculate REQUEST.json | exterior-check REQUEST.json CERTIFICATE.json')
    except DomainError as error:
        receipt = error_receipt(error.code, str(error))
    except Exception:
        receipt = error_receipt('E_INTERNAL', 'Unexpected implementation failure; result withheld')
    output = json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:
        receipt = error_receipt('E_BUDGET', 'Whole CLI envelope exceeds byte budget; result withheld')
        output = json.dumps(receipt, sort_keys=True, separators=(',', ':'))
    try:
        sys.stdout.write(output + '\n')
    except (OSError, BrokenPipeError):
        return 2
    return 0 if receipt['status'] == 'success' else 4 if receipt['error']['code'] == 'E_INTERNAL' else 2

"""Explicit fixed-table character arithmetic, outside all runtime goal domains.

Calculate produces and independently verifies. Check never imports the producer.
Content hashes bind bytes; the table-to-group identification remains assumed.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path

VERSION = '0.9.0-dev'
IMPLEMENTATION_FILES = (
    'character_ring/__init__.py', 'character_ring/__main__.py',
    'character_ring/catalog.json', 'character_ring/contract.py',
    'character_ring/producer.py', 'character_ring/types.py',
    'character_ring/verifier.py', 'foundation_math/character_ring.py',
)
ERROR_CODES = frozenset(('E_USAGE', 'E_IO', 'E_JSON', 'E_TYPE', 'E_SCHEMA',
    'E_BUDGET', 'E_CATALOG', 'E_CHARACTER', 'E_EXPECTATION', 'E_CERTIFICATE', 'E_INTERNAL'))


def _common():
    return {'schema_version': 1, 'scope': 'universal_representation_arithmetic_only',
            'computational_field': 'Q(sqrt(5))', 'formal_proof': False,
            'runtime_goal_acceptance': False, 'table_group_identification_assumed': True,
            'geometric_realization': False}


def character_error_receipt(code, message):
    # Only explicit bounded known-domain errors can describe rejected input.
    if type(code) is not str or code not in ERROR_CODES:
        code, message = 'E_INTERNAL', 'Unexpected implementation failure'
    return {**_common(), 'status': 'error', 'error': {'code': code, 'message': message}}


def character_exit_code(receipt):
    if receipt['status'] == 'success':
        return 0
    code = receipt['error']['code']
    return 3 if code == 'E_EXPECTATION' else 4 if code == 'E_INTERNAL' else 2


def _success(operation, verification, certificate=None):
    root = Path(__file__).resolve().parents[1]
    implementation = {'name': 'foundation-math-fixed-character-ring', 'version': VERSION,
        'source_sha256': {name: sha256((root / name).read_bytes()).hexdigest()
                          for name in IMPLEMENTATION_FILES}}
    result = {'verification': verification}
    if operation == 'calculate':
        result['certificate'] = certificate
    return {**_common(), 'status': 'success', 'operation': operation,
            'request_sha256': verification['request_sha256'],
            'implementation': implementation, 'result': result}


def calculate_character(request):
    """Produce then check against the original request; failure has no result."""
    try:
        from character_ring.contract import DomainError
        from character_ring.producer import calculate
        from character_ring.verifier import VerificationError, verify
    except Exception:
        return character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    try:
        certificate = calculate(request)
        verification = verify(request, certificate)
        return _success('calculate', verification, certificate)
    except (DomainError, VerificationError) as error:
        return character_error_receipt(error.code, str(error))
    except Exception:
        return character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')


def check_character_certificate(expected_request, certificate):
    """Independent re-evaluation, without importing the producer or contract."""
    try:
        from character_ring.verifier import VerificationError, verify
    except Exception:
        return character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    try:
        verification = verify(expected_request, certificate)
        return _success('verify', verification)
    except VerificationError as error:
        return character_error_receipt(error.code, str(error))
    except Exception:
        return character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')


def character_cli(argv):
    """Same failure codes and output streams as the frozen standalone CLI.

    No output-file mutation is supported. Requests and certificates use distinct
    lab byte caps; the verification boundary remains independently authoritative.
    """
    import json
    import sys
    try:
        from character_ring.contract import BUDGETS, DomainError, read_json
    except Exception:
        receipt = character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
        print(json.dumps(receipt, sort_keys=True), file=sys.stderr)
        return 4
    try:
        if len(argv) == 2 and argv[0] == 'character-calculate':
            receipt = calculate_character(read_json(argv[1], BUDGETS['request_bytes']))
        elif len(argv) == 3 and argv[0] == 'character-check':
            receipt = check_character_certificate(
                read_json(argv[1], BUDGETS['request_bytes']),
                read_json(argv[2], BUDGETS['certificate_bytes']))
        else:
            receipt = character_error_receipt('E_USAGE',
                'Usage: character-calculate REQUEST.json | character-check REQUEST.json CERTIFICATE.json')
    except DomainError as error:
        receipt = character_error_receipt(error.code, str(error))
    except Exception:
        receipt = character_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    print(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False),
          file=sys.stdout if receipt['status'] == 'success' else sys.stderr)
    return character_exit_code(receipt)


__all__ = ['calculate_character', 'check_character_certificate',
           'character_error_receipt', 'character_exit_code', 'character_cli']

"""Explicit formal supplied-splitting arithmetic, outside all runtime goal domains.

Calculate produces and independently verifies. Check never imports the producer.
Content hashes bind bytes; the table-to-group identification remains assumed.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path

VERSION = '0.10.0-dev'
IMPLEMENTATION_FILES = (
    'character_ring/__init__.py', 'character_ring/__main__.py',
    'character_ring/catalog.json', 'character_ring/contract.py',
    'character_ring/producer.py', 'character_ring/types.py',
    'character_ring/verifier.py', 'split_bundle/__init__.py', 'split_bundle/__main__.py',
    'split_bundle/contract.py', 'split_bundle/producer.py', 'split_bundle/verifier.py',
    'foundation_math/split_bundle.py',
)
ERROR_CODES = frozenset(('E_USAGE', 'E_IO', 'E_JSON', 'E_TYPE', 'E_SCHEMA',
    'E_BUDGET', 'E_CATALOG', 'E_CHARACTER', 'E_EXPECTATION', 'E_CERTIFICATE', 'E_RIEMANN_ROCH', 'E_INTERNAL'))


def _common():
    return {'schema_version': 1, 'scope': 'formal_supplied_split_bundle_arithmetic_only',
            'computational_field': 'Q(sqrt(5))', 'formal_proof': False,
            'runtime_goal_acceptance': False, 'table_group_identification_assumed': True,
            'supplied_splitting_assumed': True, 'geometric_realization': False, 'map_rank_claim': False}


def split_bundle_error_receipt(code, message):
    # Only explicit bounded known-domain errors can describe rejected input.
    if type(code) is not str or code not in ERROR_CODES:
        code, message = 'E_INTERNAL', 'Unexpected implementation failure'
    return {**_common(), 'status': 'error', 'error': {'code': code, 'message': message}}


def split_bundle_exit_code(receipt):
    if receipt['status'] == 'success':
        return 0
    code = receipt['error']['code']
    return 4 if code == 'E_INTERNAL' else 2


def _success(operation, verification, certificate=None):
    root = Path(__file__).resolve().parents[1]
    implementation = {'name': 'foundation-math-formal-split-bundle', 'version': VERSION,
        'source_sha256': {name: sha256((root / name).read_bytes()).hexdigest()
                          for name in IMPLEMENTATION_FILES}}
    result = {'verification': verification}
    if operation == 'calculate':
        result['certificate'] = certificate
    return {**_common(), 'status': 'success', 'operation': operation,
            'request_sha256': verification['request_sha256'],
            'implementation': implementation, 'result': result}


def calculate_split_bundle(request):
    """Produce then check against the original request; failure has no result."""
    try:
        from split_bundle.contract import DomainError
        from split_bundle.producer import calculate
        from split_bundle.verifier import VerificationError, verify
        from character_ring.verifier import VerificationError as CharacterVerificationError
    except Exception:
        return split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    try:
        certificate = calculate(request)
        verification = verify(request, certificate)
        return _success('calculate', verification, certificate)
    except (DomainError, VerificationError, CharacterVerificationError) as error:
        return split_bundle_error_receipt(error.code, str(error))
    except Exception:
        return split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')


def check_split_bundle_certificate(expected_request, certificate):
    """Independent re-evaluation, without importing the producer or contract."""
    try:
        from split_bundle.verifier import VerificationError, verify
        from character_ring.verifier import VerificationError as CharacterVerificationError
    except Exception:
        return split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    try:
        verification = verify(expected_request, certificate)
        return _success('verify', verification)
    except (VerificationError, CharacterVerificationError) as error:
        return split_bundle_error_receipt(error.code, str(error))
    except Exception:
        return split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')


def split_bundle_cli(argv):
    """Same failure codes and output streams as the frozen standalone CLI.

    No output-file mutation is supported. Requests and certificates use distinct
    lab byte caps; the verification boundary remains independently authoritative.
    """
    import json
    import sys
    try:
        from split_bundle.contract import BUDGETS, DomainError, read_json
    except Exception:
        receipt = split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
        print(json.dumps(receipt, sort_keys=True), file=sys.stderr)
        return 4
    try:
        if len(argv) == 2 and argv[0] == 'split-bundle-calculate':
            receipt = calculate_split_bundle(read_json(argv[1], BUDGETS['request_bytes']))
        elif len(argv) == 3 and argv[0] == 'split-bundle-check':
            receipt = check_split_bundle_certificate(
                read_json(argv[1], BUDGETS['request_bytes']),
                read_json(argv[2], BUDGETS['certificate_bytes']))
        else:
            receipt = split_bundle_error_receipt('E_USAGE',
                'Usage: split-bundle-calculate REQUEST.json | split-bundle-check REQUEST.json CERTIFICATE.json')
    except DomainError as error:
        receipt = split_bundle_error_receipt(error.code, str(error))
    except Exception:
        receipt = split_bundle_error_receipt('E_INTERNAL', 'Unexpected implementation failure')
    print(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False),
          file=sys.stdout if receipt['status'] == 'success' else sys.stderr)
    return split_bundle_exit_code(receipt)


__all__ = ['calculate_split_bundle', 'check_split_bundle_certificate',
           'split_bundle_error_receipt', 'split_bundle_exit_code', 'split_bundle_cli']

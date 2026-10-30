"""Pure applicability adapter and bounded stdin CLI. Never a theorem verifier.

The accepted claim_revision implementation is reused without changing its semantics.
Replaying with this adapter is not independent verification of that implementation.
"""
import json
import sys

from claim_revision import LedgerError, loads, replay
from claim_revision.core import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES


def _common():
    return {'schema_version': 1, 'scope': 'bounded_dependency_applicability',
            'formal_proof': False, 'runtime_goal_acceptance': False,
            'proof_accepted': False, 'truth_assessment': 'not_assessed'}


def ledger_error_receipt(error):
    return {**_common(), 'status': 'error', 'error': {
        'code': error.code, 'path': error.path, 'message': str(error)}}


def replay_claim_ledger(document):
    """Return all-required dependency blockers, not evidence or truth acceptance."""
    try:
        return {**_common(), 'status': 'success', 'result': replay(document)}
    except LedgerError as error:
        return ledger_error_receipt(error)


def claim_ledger_cli(argv):
    """Read a single bounded JSON stdin document; no paths or extra options."""
    try:
        if argv != ['claim-ledger-replay']:
            raise LedgerError('arguments', '$', 'Read one ledger from standard input; no paths or options')
        document = loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        receipt = replay_claim_ledger(document)
    except LedgerError as error:
        receipt = ledger_error_receipt(error)
    except OSError:
        receipt = ledger_error_receipt(LedgerError('input_io', '$', 'Unable to read ledger from standard input'))
    # Bound the complete adapter envelope, not only the inner pure report.
    output = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:
        receipt = ledger_error_receipt(LedgerError('budget_exceeded', '$', 'CLI output byte budget exceeded; result withheld'))
        output = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    try:
        sys.stdout.write(output + '\n')
    except (BrokenPipeError, OSError):
        return 2
    return 0 if receipt['status'] == 'success' else 2

"""Pure authored-premise matcher and bounded stdin CLI, never a theorem verifier.

The frozen standalone matcher is reused unchanged. Replaying it is not an
independent proof of truth, geometry, adequacy of a rule, or authenticity.
"""
import json
import sys

from hypothesis_scope import ScopeError, check, loads
from hypothesis_scope.core import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES


def _common():
    return {'schema_version': 1, 'scope': 'exact_authored_premise_matching_only',
            'formal_proof': False, 'runtime_goal_acceptance': False,
            'fact_truth_checked': False, 'rule_soundness_checked': False,
            'geometry_checked': False, 'truth_assessment': 'not_assessed'}


def scope_error_receipt(error):
    return {**_common(), 'status': 'error', 'error': {
        'code': error.code, 'path': error.path, 'message': error.message}}


def check_hypothesis_scope(document):
    """Successful computation may report unmatched premises; it never proves them."""
    try:
        return {**_common(), 'status': 'success', 'result': check(document)}
    except ScopeError as error:
        return scope_error_receipt(error)


def hypothesis_scope_cli(argv):
    """Read one bounded JSON stdin document; no paths, options or caller budgets."""
    try:
        if argv != ['hypothesis-scope-check']:
            raise ScopeError('arguments', '$', 'Read one scope document from standard input; no paths or options')
        receipt = check_hypothesis_scope(loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
    except ScopeError as error:
        receipt = scope_error_receipt(error)
    except OSError:
        receipt = scope_error_receipt(ScopeError('input_io', '$', 'Unable to read scope document from standard input'))
    output = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:
        receipt = scope_error_receipt(ScopeError('budget_exceeded', '$', 'CLI output byte budget exceeded; result withheld'))
        output = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    try:
        sys.stdout.write(output + '\n')
    except (BrokenPipeError, OSError):
        return 2
    return 0 if receipt['status'] == 'success' else 2

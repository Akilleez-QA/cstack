"""Pure declared-evidence classification; never an executor or skip authority."""
import json
import sys
from validation_receipt import PlanError, loads, plan

MAX_INPUT_BYTES = 262144
MAX_OUTPUT_BYTES = 524288


def common():
    return {'schema_version': 1, 'scope': 'declared_validation_evidence_planning_only',
            'formal_proof': False, 'runtime_goal_acceptance': False,
            'execution_performed': False, 'skip_authorized': False, 'fresh_pass_claimed': False}


def error_receipt(error):
    return {**common(), 'status': 'error', 'error': {'code': error.code, 'path': error.path, 'message': error.message}}


def plan_validation_evidence(document):
    try:
        return {**common(), 'status': 'success', 'result': plan(document)}
    except PlanError as error:
        return error_receipt(error)


def validation_evidence_cli(argv):
    try:
        if argv != ['validation-evidence-plan']:
            raise PlanError('arguments', '$', 'Read one JSON document from stdin; no paths, options or execution')
        receipt = plan_validation_evidence(loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
    except PlanError as error:
        receipt = error_receipt(error)
    except OSError:
        receipt = error_receipt(PlanError('input_io', '$', 'Unable to read standard input'))
    output = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:
        receipt = error_receipt(PlanError('budget_exceeded', '$', 'Whole CLI envelope exceeds byte budget; result withheld'))
        output = json.dumps(receipt, sort_keys=True, separators=(',', ':'))
    try:
        sys.stdout.write(output + '\n')
    except (OSError, BrokenPipeError):
        return 2
    return 0 if receipt['status'] == 'success' else 2

"""One bounded JSON stdin document; commands in it are never executed."""
import json
import sys
from .core import MAX_INPUT_BYTES, PlanError, loads, plan


def main():
    try:
        if sys.argv[1:]:
            raise PlanError('arguments', '$', 'no CLI arguments supported')
        report = plan(loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
    except PlanError as exc:
        report = {'schema': 'foundation-math-validation-receipt-error/1', 'code': exc.code, 'path': exc.path, 'message': exc.message}
        print(json.dumps(report, sort_keys=True, separators=(',', ':')))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    sys.exit(main())

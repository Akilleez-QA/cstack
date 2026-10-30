"""One bounded JSON request on stdin; one JSON response, exit 0 or 2."""
from __future__ import annotations
import json
import sys
from .api import handle_request
from .contract import Limits, MathError, loads_bounded


def main() -> int:
    limits = Limits()
    try:
        raw = sys.stdin.buffer.read(limits.max_input_bytes + 1)
        response = handle_request(loads_bounded(raw, limits), limits)
    except MathError as error:
        response = {'ok': False, 'error': error.to_dict()}
    except Exception:
        response = {'ok': False, 'error': {'code': 'INTERNAL_ERROR',
                    'message': 'Unexpected internal failure.', 'path': '$'}}
    sys.stdout.write(json.dumps(response, separators=(',', ':'), sort_keys=True) + '\n')
    return 0 if response['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

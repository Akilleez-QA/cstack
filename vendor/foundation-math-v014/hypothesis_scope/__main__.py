"""One bounded stdin document, one JSON report; no paths, options, or backend calls."""
import json
import sys
from .core import MAX_INPUT_BYTES, ScopeError, check, loads


def main():
    try:
        if len(sys.argv) != 1:
            raise ScopeError("arguments", "$", "This command accepts stdin only")
        report = check(loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
        print(json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        return 0
    except ScopeError as exc:
        print(json.dumps({"error": {"code": exc.code, "path": exc.path, "message": exc.message}}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())

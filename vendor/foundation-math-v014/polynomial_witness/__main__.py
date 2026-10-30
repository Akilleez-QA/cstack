"""Bounded stdin JSON command line. No file paths or executable input accepted."""
import json
import sys
from .api import construct_json, verify_json
from .contract import MAX_WIRE_BYTES, WitnessError, error_result

def main() -> int:
    args = sys.argv[1:]
    if args not in ([], ["construct"], ["verify"]):
        result = error_result(WitnessError("invalid_command", "use construct (default) or verify, with JSON on stdin"))
    else:
        data = sys.stdin.buffer.read(MAX_WIRE_BYTES + 1)
        result = verify_json(data) if args == ["verify"] else construct_json(data)
    print(json.dumps(result, sort_keys=True, indent=2))
    if result["status"] == "error":
        return 2
    if result["status"] == "rejected":
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

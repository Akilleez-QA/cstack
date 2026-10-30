"""CLI: python -B -m claim_revision < document.json"""
import json
import sys

from .core import LedgerError, MAX_INPUT_BYTES, loads, replay


def main() -> int:
    try:
        if len(sys.argv) != 1:
            raise LedgerError("arguments", "$", "Read one ledger from standard input; no path or command evaluation")
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        report = replay(loads(data))
    except LedgerError as exc:
        print(json.dumps({"status": "rejected", "code": exc.code, "path": exc.path, "message": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

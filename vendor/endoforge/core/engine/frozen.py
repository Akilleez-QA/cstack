import json
from pathlib import Path
import sys

from core.ledger.frozen import FrozenEvaluators
from core.ledger.ledger import Ledger


def main():
    request = json.load(sys.stdin)
    if not Path(request["ledger"]).is_file():
        raise ValueError("frozen ledger must already exist")
    ledger = Ledger(request["ledger"])
    record = next((r for r in ledger.records() if r["id"] == request["identity"]), None)
    if record is None or record["kind"] != "frozen_evaluator" or "freeze" not in record["data"]:
        raise ValueError("content-hashed frozen evaluator required")
    stored = json.loads(record["data"]["content"])
    bundle = FrozenEvaluators(ledger).require_frozen(
        record["id"], request["root"],
        **{key: stored[key] for key in ("configuration", "residual", "invariant_version")})
    print(json.dumps(dict(identity=record["id"], digest=record["data"]["freeze"]["digest"], bundle=bundle)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, FileNotFoundError, NotADirectoryError) as error:
        print(error, file=sys.stderr)
        sys.exit(3)
    except Exception as error:
        if not isinstance(error, (OSError, MemoryError)) and type(error).__module__ != "sqlite3":
            raise
        print(error, file=sys.stderr)
        sys.exit(75)

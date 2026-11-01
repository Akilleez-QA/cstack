"""Small standalone CLI. Inputs are data; output files are never overwritten."""
import argparse
import json
from pathlib import Path
import sys

from .core import MAX_INPUT_BYTES, check_witness_json, search_counterexample_json


def _read(path: str) -> bytes:
    with Path(path).open("rb") as source:
        return source.read(MAX_INPUT_BYTES + 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact counterexample search only in a declared finite integer box")
    subparsers = parser.add_subparsers(dest="command", required=True)
    search = subparsers.add_parser("search")
    search.add_argument("request")
    check = subparsers.add_parser("check-witness")
    check.add_argument("request")
    check.add_argument("assignment")
    for subparser in (search, check):
        subparser.add_argument("--output", help="create a new receipt file; never overwrite")
    args = parser.parse_args(argv)
    try:
        request = _read(args.request)
        receipt = search_counterexample_json(request) if args.command == "search" else check_witness_json(request, _read(args.assignment))
        rendered = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            with Path(args.output).open("x", encoding="utf-8") as output:
                output.write(rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"I/O error: {error}\n")
        return 2
    if receipt["status"] != "success":
        return 2
    if args.command == "search":
        return 1 if receipt["result"]["outcome"] == "counterexample_found" else 0
    return 0 if receipt["result"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Wrap one step (for example a codex-task run) in workspace snapshots: capture, run, capture, diff.

usage: python -B tools/snapshot_step.py [--timeout SECONDS] [--label TEXT] <repo> -- <command...>

Runs the command in <repo> without a shell; its output goes to stderr and stdout carries one JSON
receipt. Exit: the command's own; 3 if the before-snapshot is refused (the command is not run);
4 if the after-snapshot is refused; 124 on timeout; 127 if it cannot start; 2 on usage error.
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import workspace_snapshots as ws  # noqa: E402

SCHEMA = "cstack.snapshot-step/0.1"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    split = argv.index("--")
    parser = argparse.ArgumentParser(prog="snapshot_step.py")
    parser.add_argument("repo")
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--label")
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    receipt = {"schema": SCHEMA, "command": command, "label": args.label}
    try:
        before = ws.capture(args.repo, label=args.label and args.label + ":before")
    except ws.SnapshotRefused as refused:
        print(json.dumps(dict(receipt, ok=False, stage="before", refusal=refused.receipt), sort_keys=True))
        return 3
    receipt.update(repo=before["repo"], before=before["snapshot_id"])
    exit_code, timed_out = None, False
    try:
        exit_code = subprocess.run(command, cwd=before["repo"], stdin=subprocess.DEVNULL, stdout=sys.stderr,
                                   stderr=sys.stderr, timeout=args.timeout).returncode
    except subprocess.TimeoutExpired:
        exit_code, timed_out = 124, True
    except OSError as err:
        exit_code = 127
        receipt["start_error"] = type(err).__name__
    receipt.update(exit_code=exit_code, timed_out=timed_out)
    try:
        after = ws.capture(before["repo"], label=args.label and args.label + ":after")
    except ws.SnapshotRefused as refused:
        print(json.dumps(dict(receipt, ok=False, stage="after", refusal=refused.receipt), sort_keys=True))
        return 4
    change = ws.diff(before["repo"], before["snapshot_id"], after["snapshot_id"])
    receipt.update(ok=True, after=after["snapshot_id"], before_tree=before["tree"], after_tree=after["tree"],
                   diff={k: v for k, v in change.items() if k not in ("schema", "operation", "ok", "repo")})
    print(json.dumps(receipt, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""Print the ReadModelFace projections (ADR 005 item 8b) for one exported ledger, as JSON or a Scheduled-brief block.

Reads `<state-root>/ledger-events.json`: a JSON list of ledger events, or an object holding them under "events"
(the `cli.py` run result) or "ledger". It only reads. Durable ledgers (#20, #25) can feed the same projections
through their own `read()` once they land.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.read_models import NAMES, project  # noqa: E402

EVENTS_FILE = "ledger-events.json"
MAX_BYTES = 64 * 1024 * 1024


def file_reader(path):
    def read():
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Ledger export exceeds the read budget")
        document = json.loads(path.read_text(encoding="utf-8"))
        if type(document) is dict:
            document = document.get("events", document.get("ledger"))
        return document
    return read


def scheduled_brief(projections):
    """At most five lines, citing as_of and the source."""
    stuck, closure, repairs = (projections[n] for n in NAMES)
    src, conf = stuck.source, stuck.confidence
    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(stuck.as_of))
    lines = [f"Read models as of {when} from {src['ledger']}, events {src['first_sequence']}-{src['last_sequence']} "
             f"({conf.level}).",
             f"Goals with no live path: {stuck.summary['without_live_path']} of {stuck.summary['open_goals']} open"
             + (": " + ", ".join(f"{r['goal_id']} ({r['reason']})" for r in stuck.rows[:3]) + "." if stuck.rows else "."),
             f"Evidence-backed goals: {closure.summary['evidence_backed']} of {closure.summary['goals']} "
             "(not closure; the core never closes a goal).",
             f"Founder manual repairs: {repairs.summary['total']}"
             + "".join(f", {k} {v}" for k, v in repairs.summary["by_kind"].items() if v) + "."]
    if conf.level != "complete":
        lines += [f"Confidence {conf.level}: {conf.reason}."]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Project POODO ledger events into read models. Never writes.")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "brief"), default="json")
    parser.add_argument("--approver", default="owner-via-approver")
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args(argv)
    path = args.state_root / EVENTS_FILE
    try:
        projections = project(file_reader(path), source_id=str(path), clock=lambda: int(time.time()),
                              approver=args.approver, written_at=int(path.stat().st_mtime),
                              max_age=args.max_age_hours * 3600)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"read_models: {error}\n")
        return 2
    if args.format == "brief":
        print(scheduled_brief(projections))
    else:
        print(json.dumps({n: projections[n].to_dict() for n in NAMES}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

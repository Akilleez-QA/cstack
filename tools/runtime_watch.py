"""Read-only runtime watcher (ADR 005 decision 6). A host tool on host-a: it reports and alarms, and never acts.

For each runtime's POODO ledger it reports the time of the last event, attempts dispatched but never settled,
outcomes with `unknown` certainty, refusals, and open goals with no live path (replayed from the ledger the way
PoodoCore.liveness() judges them). Alarms print to stderr and exit 75, for a systemd timer or the phone board.
Nothing here calls back into a runtime.

Freshness (Healthchecks' late-is-not-down): each source has a host-set `period` and `grace` (`--config`, else
`--stale-after` as period with no grace, today's rule). Age <= period is `fresh`; up to period + grace is `late`,
shown in the report and brief but not an alarm; past it is `down`, which raises STALE. `late_since` and
`down_since` are the last time plus each threshold, so they do not move with the watcher's run time. No event
time at all is `down`. Every alarm carries `alarm_id` = sha256(code, subject, down_since): a consumer notifies
once per new id and nags on its own timer; this watcher stays a one-shot reader.

Ledgers read, never written or locked:
- MemoryLedger-shaped JSON exports (a list of events, or {"events": [...]});
- DurableLedger SQLite files (#20), copied with any WAL into a private temporary directory, read with mode=ro;
- `<state_root>/<bot>/*.ledger.json|*.ledger.db`, and the ADR 004 node log named by `<state_root>/ledger.json`
  (the MCP server's layout, #57), read through products/hmi/ledger/ledger.py's Log reader, which needs
  `cryptography`. Only Log's constructor runs (it reads and verifies); no lock, append or checkpoint call is made.
Every POODO chain is re-verified. A missing, unreadable or broken ledger is an alarm, never a pass.

Event times: the node log stamps each entry. MemoryLedger and DurableLedger events carry no time, so their
freshness is the file's mtime (`time_source: file_mtime`): an exporter that rewrites an unchanged ledger makes it
look fresh. Prefer the witnessed node log where it exists. Empty ledgers have no event time. Where event times exist, an attempt with no outcome after the
source's `run_grace` is UNSETTLED even while the runtime keeps writing; elsewhere an attempt is abandoned once
any event follows it or it is down.

Host config (`--config`, owned by the host like bootstrap's paths, never by request data):
  {"default": {"period": 3600, "grace": 600, "run_grace": 1800}, "runtimes": {"grok-bot": {"period": 300}}}
A runtime matches its full name, then its bot name; unset keys fall back to "default", then `--stale-after`.
"""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import shutil
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poodo_core.models import canonical, digest  # noqa: E402  (pure functions; no ledger adapter is imported)

SCHEMA = "cstack.runtime-watch/0.1"
EXIT_ALARM = 75
SHOWN = 20  # list items kept per runtime in the JSON; counts are always exact
REFUSALS = ("denied", "budget_refused", "declined")
_EVENT_KEYS = {"sequence", "kind", "data", "prior_event_sha256", "event_sha256"}
_HMI_LEDGER = Path(__file__).resolve().parents[1] / "products/hmi/ledger/ledger.py"
POLICY_KEYS = ("period", "grace", "run_grace")


class WatchError(Exception):
    code = "LEDGER_INVALID"


class NoLedger(WatchError):
    code = "NO_LEDGER"


def verify_chain(events):
    """Re-check a MemoryLedger-shaped list: contiguous from 1, chained, and every digest exact."""
    prior = None
    for number, event in enumerate(events, 1):
        ok = type(event) is dict and set(event) == _EVENT_KEYS
        if ok:
            frame = {"sequence": number, "kind": event["kind"], "data": event["data"], "prior_event_sha256": prior}
            ok = canonical(event) == canonical({**frame, "event_sha256": digest(frame)})
        if not ok:
            raise WatchError(f"ledger chain broken at event {number}")
        prior = event["event_sha256"]
    return events


def _mtime(path):
    times = [os.stat(p).st_mtime for p in (str(path), f"{path}-wal") if os.path.exists(p)]
    return int(max(times))


def read_export(path):
    value = json.loads(Path(path).read_text())
    events = verify_chain(value["events"] if type(value) is dict else value)
    return events, int(Path(path).stat().st_mtime) if events else None


@contextlib.contextmanager
def read_only_snapshot(path, companions=()):
    """Keep reader side effects in a private copy, including any format-specific sidecars."""
    path = Path(path)
    if not path.is_file():
        raise NoLedger("no such ledger file")
    with tempfile.TemporaryDirectory(prefix="runtime-watch-") as directory:
        snapshot = Path(directory) / path.name
        shutil.copyfile(path, snapshot)
        for suffix in companions:
            companion = Path(f"{path}{suffix}")
            if companion.exists():
                shutil.copyfile(companion, f"{snapshot}{suffix}")
        yield snapshot


def read_sqlite(path):
    path = Path(path)
    if not path.is_file():
        raise NoLedger("no such ledger file")
    last_at = _mtime(path)
    # mode=ro can create WAL/SHM beside the source, while immutable=1 ignores
    # committed WAL rows. Let SQLite recover/read only a disposable private copy.
    with read_only_snapshot(path, ("-wal",)) as snapshot:
        db = sqlite3.connect(f"{snapshot.as_uri()}?mode=ro", uri=True, timeout=30)
        try:
            rows = db.execute("SELECT event FROM events ORDER BY sequence").fetchall()
        finally:
            db.close()
    events = verify_chain([json.loads(text) for (text,) in rows])
    return events, last_at if events else None


@contextlib.contextmanager
def _no_alarm_file():
    """ledger.py's Alarm() appends to $LEDGER_ALARMS; a watcher reports alarms itself and writes nothing."""
    saved = os.environ.pop("LEDGER_ALARMS", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["LEDGER_ALARMS"] = saved


def hmi_ledger():
    """The ADR 004 ledger library from Grok Bot's slice, loaded read-only (products/hmi is never edited here)."""
    if importlib.util.find_spec("cryptography") is None:
        raise WatchError("'cryptography' is missing, so the witnessed node log cannot be verified")
    spec = importlib.util.spec_from_file_location("cstack_witnessed_ledger_reader", _HMI_LEDGER)
    lib = importlib.util.module_from_spec(spec)
    # Execute source directly so the loader cannot cache bytecode beside ledger.py.
    exec(compile(_HMI_LEDGER.read_text(), str(_HMI_LEDGER), "exec"), vars(lib))
    return lib


def read_node_log(lib, roster, path, origin):
    """Verify the log and checkpoints using the same isolated reads as SQLite."""
    with read_only_snapshot(path, (".cp",)) as snapshot, _no_alarm_file():
        return lib.Log(str(snapshot), origin, roster)


def _poodo_event(body):
    """#25 stores body.event_json (canonical string); #47 reads body.event (object). Accept either."""
    if type(body) is not dict:
        return None
    if type(body.get("event_json")) is str:
        return json.loads(body["event_json"])
    return body.get("event") if type(body.get("event")) is dict else None


def read_witnessed(state_root):
    """{(bot, stream): (events, last_ts, gate_denials, {sequence: entry ts}) or WatchError} from the node log named
    by <state_root>/ledger.json. Entry times let run_grace judge an open attempt.

    #25 named streams: each core of a bot writes its own POODO chain, body.stream ("<bot>.<domain>"), on the one
    node log, so a writer's entries are grouped by stream and each chain is verified on its own. Entries with no
    stream (written before streams) are stream None."""
    lib = hmi_ledger()
    config = json.loads((state_root / "ledger.json").read_text())
    if not (state_root / config["log"]).is_file():
        raise NoLedger(f"node log {config['log']} does not exist")
    with _no_alarm_file():
        try:
            log = read_node_log(lib, lib.load_roster(state_root / config["roster"]),
                                state_root / config["log"], config.get("node", os.uname().nodename))
        except lib.LedgerError as error:
            raise WatchError(f"node log failed verification: {error}") from None
    found = {}
    for bot, writer in config["writers"].items():
        mine = [e for e in log.entries if e["writer"] == writer["writer"]]
        last_ts = max((e["ts"] for e in mine), default=None)  # liveness stays per writer: an idle domain is not down
        streams = {}
        for e in mine:
            body = e.get("body") if type(e.get("body")) is dict else {}
            stream = body.get("stream")
            if stream is None and _poodo_event(body) is None and type(body.get("poodo_denied")) is not dict:
                continue  # not a POODO entry (a check-in, say): it only counts toward last_ts
            streams.setdefault(stream if stream is None or type(stream) is str else repr(stream), []).append(e)
        for stream, entries in (streams or {None: []}).items():
            found[(bot, stream)] = _stream_report(entries, last_ts)
    return found


def _stream_report(mine, last_ts):
    """One stream's verified events, the writer's last entry time, gate denials and entry times, or its WatchError."""
    dated = [(ev, e["ts"]) for ev, e in ((_poodo_event(e.get("body")), e) for e in mine) if ev is not None]
    events = [ev for ev, _ in dated]
    denials = [{"action": "ledger_gate_denied", "node_seq": e["seq"], **e["body"]["poodo_denied"]}
               for e in mine if type(e.get("body")) is dict and type(e["body"].get("poodo_denied")) is dict]
    try:  # one stream's broken chain is its own alarm; it never hides the other streams or bots
        return verify_chain(events), last_ts, denials, {ev["sequence"]: ts for ev, ts in dated}
    except WatchError as error:
        return error


def freshness(last_at, *, period, grace, now):
    """fresh to period, late to period + grace, down past it; the since-times are fixed by last_at, not by now."""
    if last_at is None:
        return {"freshness": "down", "late_since": None, "down_since": None}
    age = now - last_at
    return {"freshness": "fresh" if age <= period else "late" if age <= period + grace else "down",
            "late_since": last_at + period, "down_since": last_at + period + grace}


def alarm_id(code, subject, down_since):
    return digest({"code": code, "subject": subject, "down_since": down_since})


def with_ids(alarms, subject_key):
    """Stamp each alarm with its stable id (down_since is None when the condition has no time). An alarm may name
    a finer `subject` than its runtime or origin, so two conditions under one origin keep distinct ids."""
    for a in alarms:
        a.setdefault("down_since", None)
        a["alarm_id"] = alarm_id(a["code"], a.get("subject", a[subject_key]), a["down_since"])
    return alarms


def load_config(path, sections=("runtimes",)):
    """Validate a host watch config: {"default": POLICY, section: {name: POLICY}}. Raises ValueError."""
    config = json.loads(Path(path).read_text())
    if type(config) is not dict or not set(config) <= {"schema", "default", *sections}:
        raise ValueError(f"top-level keys must be among default, {', '.join(sections)}")
    tables = [("default", config.get("default", {}))]
    for section in sections:
        if type(config.get(section, {})) is not dict:
            raise ValueError(f"{section} must be an object")
        tables += [(f"{section}.{n}", v) for n, v in config.get(section, {}).items()]
    for where, policy in tables:
        if type(policy) is not dict or not set(policy) <= set(POLICY_KEYS):
            raise ValueError(f"{where}: keys must be among {', '.join(POLICY_KEYS)}")
        for key, value in policy.items():
            if type(value) is not int or value < (0 if key == "grace" else 1):
                raise ValueError(f"{where}.{key} must be an integer >= {0 if key == 'grace' else 1}")
    return config


def policy_for(config, section, names, stale_after):
    """The first named entry wins per key, then "default", then --stale-after (period, grace 0, no run_grace)."""
    chain = [(config.get(section) or {}).get(n, {}) for n in names] + [config.get("default", {})]
    fallback = {"period": stale_after, "grace": 0, "run_grace": None}
    policy = {k: next((p[k] for p in chain if k in p), fallback[k]) for k in POLICY_KEYS}
    if policy["period"] is None:
        raise ValueError(f"no period for {names[0]}: give --stale-after or a config default")
    return policy


def discover(state_root):
    """Yield (runtime, source, loader) for every ledger under one MCP state root."""
    root = Path(state_root)
    if not root.is_dir():
        yield f"{root}", str(root), NoLedger("state root does not exist")
        return
    for bot_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = sorted([*bot_dir.glob("*.ledger.json"), *bot_dir.glob("*.ledger.db")])
        if not files and not (root / "ledger.json").exists():
            yield bot_dir.name, str(bot_dir), NoLedger("no durable ledger (MemoryLedger is not watchable)")
        for path in files:
            name = f"{bot_dir.name}/{path.name.split('.ledger.')[0]}"
            yield name, str(path), (lambda p=path: (read_sqlite(p) if p.suffix == ".db" else read_export(p)) + ([],))
    if (root / "ledger.json").exists():
        try:
            found = read_witnessed(root)
        except (WatchError, OSError, ValueError, KeyError, TypeError) as error:
            yield f"{root.name}@witnessed", str(root / "ledger.json"), \
                error if isinstance(error, WatchError) else WatchError(str(error))
            return
        for (bot, stream), value in found.items():
            yield f"{bot}@witnessed" + (f"/{stream}" if stream is not None else ""), str(root / "ledger.json"), \
                value if isinstance(value, WatchError) else (lambda v=value: v)


def evaluate(events, *, now, policy, last_event_at, gate_denials=(), event_times=None):
    """Pure report over one verified event list. event_times: {sequence: ts} where the source dates events.
    Raises KeyError/TypeError on a malformed POODO event."""
    goals, liveness, precommits, answered, approvers = {}, {}, {}, set(), {}
    attempts, settled, unknown, refusals = {}, set(), [], list(gate_denials)
    for event in events:
        kind, data, seq = event["kind"], event["data"], event["sequence"]
        action = data.get("action")
        if kind in ("proposal", "correction") and action in ("start_goal", "revise_goal"):
            contract = data["snapshot"]["contract"]
            goals[contract["goal_id"]] = (contract["revision"], data["snapshot"]["closed"] is True)
        elif kind == "decision" and action == "liveness_set":
            liveness[data["liveness"]["goal_id"]] = data["liveness"]
        elif kind == "decision" and action == "precommit":
            req = data["request"]
            precommits[req["decision_id"]] = (req["goal_id"], req["goal_revision"], data.get("approval_required") is True)
        elif kind == "observation" and action == "approval_pending":
            approvers[data["decision_id"]] = data.get("approver")
        elif kind == "decision" and action in REFUSALS:
            refusals.append({"action": action, "sequence": seq, "decision_id": data.get("decision_id"),
                             "reason": data.get("reason")})
            if action == "declined":
                answered.add(data["decision_id"])
        elif kind == "action":
            attempts[(data["decision_id"], data["attempt_id"])] = seq
            answered.add(data["decision_id"])
        elif kind == "outcome":
            outcome = data["outcome"]
            settled.add((outcome["decision_id"], outcome["attempt_id"]))
            if outcome["execution_certainty"] == "unknown":
                unknown.append({"sequence": seq, "decision_id": outcome["decision_id"],
                                "attempt_id": outcome["attempt_id"], "status": outcome["execution_status"]})
    age = None if last_event_at is None else now - last_event_at
    fresh = freshness(last_event_at, period=policy["period"], grace=policy["grace"], now=now)
    stale = fresh["freshness"] == "down"
    last_seq = events[-1]["sequence"] if events else 0
    # A core appends nothing while it executes, so a later event (or a down runtime) means the attempt was abandoned.
    # With event times, a start with no outcome after run_grace is overdue however busy the runtime is.
    unsettled = []
    for (d, a), s in sorted(attempts.items(), key=lambda x: x[1]):
        if (d, a) in settled:
            continue
        row = {"decision_id": d, "attempt_id": a, "sequence": s,
               "state": "abandoned" if s < last_seq or stale else "in_flight"}
        started = (event_times or {}).get(s)
        if started is not None and policy["run_grace"] is not None:
            row.update(started_at=started, overdue_since=started + policy["run_grace"])
            if row["state"] == "in_flight" and now > row["overdue_since"]:
                row["state"] = "overdue"
        unsettled.append(row)
    no_path = []
    for goal_id, (revision, closed) in sorted(goals.items()):
        record, reason = liveness.get(goal_id), None
        if closed:
            continue
        if record is None:
            reason = "no_next_action_owner"
        elif record["goal_revision"] != revision:
            reason = "liveness_names_stale_revision"
        elif record.get("review_by") is not None and now > record["review_by"]:
            reason = "wait_expired"
        elif record["waiting_on"] == "approval":
            pending = [d for d, (g, r, ask) in precommits.items() if ask and g == goal_id and r == revision
                       and d not in answered]
            named = {approvers[d] for d in pending if approvers.get(d)}
            if not pending:
                reason = "no_pending_approval"
            elif named and record["owner"] not in named:
                reason = "approval_wait_names_wrong_owner"
        if reason:
            no_path.append({"goal_id": goal_id, "goal_revision": revision, "reason": reason})
    return {"events": len(events), "last_event_at": last_event_at, "age_seconds": age, "stale": stale,
            **policy, **fresh,
            "unsettled_attempts": unsettled, "unknown_outcomes": unknown, "refusals": refusals,
            "goals_without_live_path": no_path}


def watch(sources, *, now, stale_after=None, required=(), config=None):
    """sources: [(runtime, source_label, loader_or_error, time_source)]; a loader returns (events, last_at,
    gate_denials[, {sequence: ts}]). Returns the full JSON report."""
    runtimes, alarms = [], []
    for name, label, loader, time_source in sources:
        row = {"runtime": name, "source": label, "time_source": time_source}
        policy = policy_for(config or {}, "runtimes", [name, name.split("/")[0].split("@")[0]], stale_after)
        try:
            if isinstance(loader, Exception):
                raise loader
            events, last_at, denials, *times = loader()
            row.update(evaluate(events, now=now, policy=policy, last_event_at=last_at, gate_denials=denials,
                                event_times=times[0] if times else None))
        except FileNotFoundError:
            alarms.append({"code": "NO_LEDGER", "runtime": name, "detail": f"{label}: not found"})
            runtimes.append({**row, "status": "no_ledger"})
            continue
        except (WatchError, OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
            code = getattr(error, "code", "LEDGER_INVALID")
            alarms.append({"code": code, "runtime": name, "detail": f"{label}: {error}"})
            runtimes.append({**row, "status": code.lower()})
            continue
        if row["stale"]:
            when = "no event time" if row["age_seconds"] is None else f"last event {row['age_seconds']}s ago"
            alarms.append({"code": "STALE", "runtime": name, "down_since": row["down_since"],
                           "detail": f"{when} (period {policy['period']}s, grace {policy['grace']}s)"})
        abandoned = [u for u in row["unsettled_attempts"] if u["state"] in ("abandoned", "overdue")]
        if abandoned:
            overdue = [u["overdue_since"] for u in abandoned if u["state"] == "overdue"]
            alarms.append({"code": "UNSETTLED", "runtime": name, "down_since": min(overdue, default=None),
                           "detail": f"{len(abandoned)} attempt(s) dispatched and never settled"
                           + (f" ({len(overdue)} past run_grace {policy['run_grace']}s)" if overdue else "")})
        row["counts"] = {k: len(row[k]) for k in ("unsettled_attempts", "unknown_outcomes", "refusals",
                                                   "goals_without_live_path")}
        for key in row["counts"]:
            row[key] = row[key][-SHOWN:]
        row["status"] = "alarm" if any(a["runtime"] == name for a in alarms) else "ok"
        runtimes.append(row)
    seen = {r["runtime"] for r in runtimes} | {r["runtime"].split("/")[0].split("@")[0] for r in runtimes}
    for name in required:
        if name not in seen:
            alarms.append({"code": "NO_LEDGER", "runtime": name, "detail": "required runtime has no ledger"})
    if not runtimes and not required:
        alarms.append({"code": "NO_LEDGER", "runtime": "*", "detail": "no ledger was given or found"})
    report = {"schema": SCHEMA, "now": now, "stale_after": stale_after, "runtimes": runtimes,
              "alarms": with_ids(alarms, "runtime")}
    report["brief"] = brief(report)
    return report


def brief(report):
    """At most three lines for Friday's brief."""
    alarms, rows = report["alarms"], [r for r in report["runtimes"] if "counts" in r]
    codes = {}
    for a in alarms:
        codes[a["code"]] = codes.get(a["code"], 0) + 1
    head = ", ".join(f"{c} {n}" for c, n in sorted(codes.items())) or "no alarms"
    late = [f"{r['runtime']} late {r['age_seconds']}s" for r in rows if r["freshness"] == "late"]
    lines = [f"Runtime watch: {len(report['runtimes'])} runtime(s), {head}" + (f"; {', '.join(late)}" if late else "")
             + "."]
    if alarms:
        shown = "; ".join(f"{a['runtime']} {a['code']}" for a in alarms[:4])
        lines.append(f"Alarms: {shown}" + (f"; +{len(alarms) - 4} more" if len(alarms) > 4 else "") + ".")
    total = {k: sum(r["counts"][k] for r in rows) for k in ("unsettled_attempts", "unknown_outcomes", "refusals",
                                                             "goals_without_live_path")}
    lines.append(f"Unsettled {total['unsettled_attempts']}, unknown outcomes {total['unknown_outcomes']}, "
                 f"refusals {total['refusals']}, goals without a live path {total['goals_without_live_path']}.")
    return [line[:240] for line in lines]


def _named(spec):
    name, sep, path = spec.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError("use NAME=PATH")
    return name, path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stale-after", type=int, help="seconds; default period (grace 0) for sources --config omits")
    ap.add_argument("--config", help="host watch config: per-runtime period, grace and run_grace")
    ap.add_argument("--state-root", action="append", default=[], help="an MCP <state_root> (repeatable)")
    ap.add_argument("--export", action="append", default=[], type=_named, help="NAME=PATH to a MemoryLedger export")
    ap.add_argument("--sqlite", action="append", default=[], type=_named, help="NAME=PATH to a DurableLedger file")
    ap.add_argument("--require", action="append", default=[], help="a runtime or bot that must have a ledger")
    ap.add_argument("--now", type=int, help="epoch seconds (tests)")
    ap.add_argument("--brief", action="store_true", help="print only the brief lines")
    args = ap.parse_args(argv)
    if args.stale_after is not None and args.stale_after < 1:
        ap.error("--stale-after must be positive")
    try:
        config = load_config(args.config, ("runtimes", "deadman")) if args.config else {}  # one file, both watchers
    except (OSError, ValueError) as error:
        ap.error(f"--config: {error}")
    if args.stale_after is None and "period" not in config.get("default", {}):
        ap.error("give --stale-after or a config default period")
    sources = [(n, p, lambda p=p: read_export(p) + ([],), "file_mtime") for n, p in args.export]
    sources += [(n, p, lambda p=p: read_sqlite(p) + ([],), "file_mtime") for n, p in args.sqlite]
    for root in args.state_root:
        sources += [(n, s, ld, "entry_ts" if n.endswith("@witnessed") else "file_mtime") for n, s, ld in discover(root)]
    report = watch(sources, now=int(time.time()) if args.now is None else args.now,
                   stale_after=args.stale_after, required=args.require, config=config)
    print("\n".join(report["brief"]) if args.brief else json.dumps(report, indent=1, sort_keys=True))
    for alarm in report["alarms"]:
        print(f"ALARM {alarm['code']} {alarm['runtime']}: {alarm['detail']}", file=sys.stderr)
    return EXIT_ALARM if report["alarms"] else 0


if __name__ == "__main__":
    sys.exit(main())

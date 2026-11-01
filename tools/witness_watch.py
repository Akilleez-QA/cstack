"""Witness-staleness watcher for the ADR 004 witnesses (ADR 005 decision 6). Host tool on example-host; read only.

For each origin (default `box`, Example Agent's node) it reports the age of the newest witnessed checkpoint and raises
WITNESS_STALE past the host-set bound. Where cosigned checkpoints live (adapters/ledger.py):
- `<log>.cp` next to a writer's own node log: each line is {size, head, cosigs}, every cosig {name, ts, sig}.
  Only checkpoints with a verified roster quorum count; their time is when the quorum-th cosignature was made.
  Box's own `.cp` stays on the box, so example-host sees this only for logs it holds (`--checkpoints ORIGIN=LOG`).
- `<witness dir>/<origin>.replica.jsonl` on each witness: the verified replica a witness grows only when it
  cosigns. It keeps no cosignature time, so the age is that of the newest witnessed entry. That is one witness's
  view, not proof of quorum, and an idle origin with nothing new to witness ages too (`--replicas DIR`).
No data for an origin is NO_WITNESS_DATA, data that cannot be verified (no roster, no `cryptography`, a broken
replica) is WITNESS_UNVERIFIABLE: neither is ever healthy. Alarms print to stderr and exit 75. Nothing is written.

Dead-man (issue #95, writer #96): the box's poller signs a `checkin` entry {machine, level, outcome, cseq, ts} into
its own node log on change and at least every SHIELDS_LEDGER_CHECKIN_SEC (300 s), and pushes it to the witnesses.
From the verified witness copies of `--deadman-origin`'s log, the newest `checkin` for `--deadman-machine` is aged
by its signed entry `ts` on runtime_watch's late-is-not-down model: period 300 s (the check-in interval) and grace
600 s, so `down` keeps today's 900 s bound. Up to the period is `fresh`; to period + grace is `late`, briefed but no
alarm; past it, or no check-in at all, is `down` and DEADMAN. A last check-in whose signed `outcome` is a failure
(FAILED_OUTCOMES) is down at once, as a Healthchecks /fail ping is. A source that fails verification (a forged or
broken entry) is WITNESS_UNVERIFIABLE and none of its entries count. A `ts` more than CLOCK_SKEW ahead of this host
is CLOCK_SKEW and never fresh. A last level above 0 is SHIELDS_UP. Report only.

WATCHER_BLIND replaces DEADMAN when example-host cannot see the box's push path at all (no witness copy of the log here,
or the roster is missing or unreadable): the box may be fine, but this host cannot tell, so it still exits 75. While
the box is DEADMAN, WITNESS_STALE for the same origin shares that cause and is listed under `suppressed` with the
DEADMAN alarm_id, not dropped. Every alarm has runtime_watch's stable `alarm_id`. Period and grace come from
`--deadman-period`/`--deadman-grace`, overridden per key by `deadman."ORIGIN/MACHINE"` in the shared `--config`
(its "default" is for runtimes and does not apply here). `--deadman-after` is a deprecated alias for period + grace.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.runtime_watch import (EXIT_ALARM, WatchError, _named, freshness, hmi_ledger,  # noqa: E402
                                 load_config, read_node_log, with_ids)

SCHEMA = "cstack.witness-watch/0.3"
CLOCK_SKEW = 60  # seconds a signed ts may lead this host's clock before it is an anomaly
DEADMAN_PERIOD = 300  # #96's default SHIELDS_LEDGER_CHECKIN_SEC
DEADMAN_GRACE = 600  # period + grace = today's 900 s bound
FAILED_OUTCOMES = ("failed", "unknown")  # the poller could not apply shields, or could not read its level back


def _open(lib, roster, path, origin):
    return read_node_log(lib, roster, path, origin)  # verifies every entry's signature, hash and chain, or raises


def _replica(lib, roster, log, path, origin):
    if not log.entries:
        return None
    return {"source": str(path), "kind": "replica", "size": len(log.entries),
            "witnessed_at": max(e["ts"] for e in log.entries)}


def _checkpoints(lib, roster, log, path, origin):
    best = None
    for cp in log.cps:
        size, head = cp["size"], cp["head"]
        if not 0 < size <= len(log.entries) or log.entries[size - 1]["hash"] != head:
            raise WatchError(f"checkpoint at size {size} does not match the log")
        names = lib.quorum_names(roster, origin, size, head, cp["cosigs"])
        times = sorted(c["ts"] for c in cp["cosigs"] if c.get("name") in names)
        if len(names) >= roster["quorum"]:
            found = {"source": f"{path}.cp", "kind": "quorum_checkpoint", "size": size,
                     "witnessed_at": times[roster["quorum"] - 1]}
            best = found if best is None or found["witnessed_at"] > best["witnessed_at"] else best
    return best


def _checkins(log, path, machine):
    return [{"source": str(path), "seq": e["seq"], "ts": e["ts"],
             **{k: e["body"].get(k) for k in ("level", "outcome", "cseq")}}
            for e in log.entries if e["kind"] == "checkin" and type(e.get("body")) is dict
            and e["body"].get("machine") == machine and type(e["ts"]) is int]


def deadman(checkins, *, now, period, grace, origin, machine, blind=None):
    """checkins: rows from verified sources only; blind: why this host cannot see the push path. (row, alarms)"""
    unique = {(c["seq"], c["ts"]): c for c in checkins}.values()
    future = sorted((c for c in unique if c["ts"] > now + CLOCK_SKEW), key=lambda c: c["seq"])
    alarms = [{"code": "CLOCK_SKEW", "origin": origin, "down_since": c["ts"], "detail": f"check-in seq {c['seq']} "
               f"is dated {c['ts'] - now}s ahead of this host (allowed {CLOCK_SKEW}s); not counted as fresh"}
              for c in future]
    usable = sorted((c for c in unique if c["ts"] <= now + CLOCK_SKEW), key=lambda c: (c["ts"], c["seq"]))
    row = {"origin": origin, "machine": machine, "period": period, "grace": grace, "bound": period + grace,
           "clock_skew": CLOCK_SKEW, "future": len(future)}
    if not usable:
        if blind:
            alarms.append({"code": "WATCHER_BLIND", "origin": origin, "detail": f"{blind}; cannot judge {machine}"})
            return {**row, "status": "blind", "blind": blind}, alarms
        alarms.append({"code": "DEADMAN", "origin": origin,
                       "detail": f"no verified check-in from {machine} in the witnessed {origin} log"})
        return {**row, "status": "missing"}, alarms
    last = usable[-1]
    age = now - last["ts"]
    fresh = freshness(last["ts"], period=period, grace=grace, now=now)
    failed = last["outcome"] in FAILED_OUTCOMES
    row.update(last_checkin=last, age_seconds=age, late_since=fresh["late_since"],
               down_since=last["ts"] if failed else fresh["down_since"],
               status="down" if failed else fresh["freshness"])
    if failed:
        alarms.append({"code": "DEADMAN", "origin": origin, "down_since": last["ts"], "detail": f"{machine} signed "
                       f"outcome {last['outcome']} {age}s ago: down at once, no grace"})
    elif row["status"] == "down":
        alarms.append({"code": "DEADMAN", "origin": origin, "down_since": row["down_since"], "detail": f"last "
                       f"verified check-in from {machine} is {age}s old (period {period}s, grace {grace}s)"})
    since = last["ts"]  # the start of the current run of check-ins at this level, so the id holds while it lasts
    for c in reversed(usable):
        if c["level"] != last["level"]:
            break
        since = c["ts"]
    if type(last["level"]) is not int:
        alarms.append({"code": "CHECKIN_ANOMALY", "origin": origin, "down_since": since,
                       "detail": f"level {last['level']!r} is not an integer"})
    elif last["level"] > 0:
        alarms.append({"code": "SHIELDS_UP", "origin": origin, "subject": f"{origin}/level{last['level']}",
                       "down_since": since, "detail": f"{machine} last reported shields level {last['level']} "
                       f"(outcome {last['outcome']}); reported only, the watcher does not act"})
    return row, alarms


def watch(origins, *, now, stale_after, roster_path=None, replica_dirs=(), checkpoint_logs=(),
          deadman_origin="box", deadman_machine="box", deadman_period=DEADMAN_PERIOD, deadman_grace=DEADMAN_GRACE):
    """checkpoint_logs: [(origin, log_path)]. Returns the JSON report."""
    rows, alarms, checkins, blind = [], [], [], None
    for origin in dict.fromkeys([*origins, deadman_origin]):
        found = [("replica", Path(d) / f"{origin}.replica.jsonl") for d in replica_dirs]
        found += [("checkpoints", Path(p)) for o, p in checkpoint_logs if o == origin]
        present = [(k, p) for k, p in found if (p if k == "replica" else Path(f"{p}.cp")).is_file()]
        row = {"origin": origin, "sources": [str(p) for _, p in present], "witnessed": []}
        if not present:
            alarms.append({"code": "NO_WITNESS_DATA", "origin": origin,
                           "detail": "no replica or checkpoint file: the witness service is not deployed here"})
            rows.append({**row, "status": "no_witness_data"})
            blind = blind or (origin == deadman_origin and f"no witness copy of the {origin} log on this host")
            continue
        lib = None
        try:
            if not roster_path:
                raise WatchError("no --roster, so cosignatures and replicas cannot be verified")
            lib = hmi_ledger()
            roster = lib.load_roster(roster_path)
        except Exception as error:
            if origin == deadman_origin and (lib is not None or not roster_path):  # not a missing 'cryptography'
                blind = blind or f"roster unreadable: {type(error).__name__}: {error}"
            alarms.append({"code": "WITNESS_UNVERIFIABLE", "origin": origin,
                           "detail": f"{type(error).__name__}: {error}"})
            rows.append({**row, "status": "unverifiable"})
            continue
        broken = False
        for kind, path in present:
            try:  # fail closed per source: ours, or ledger.py's LedgerError/Alarm (rollback, bad signature)
                log = _open(lib, roster, path, origin)
                item = (_replica if kind == "replica" else _checkpoints)(lib, roster, log, path, origin)
            except Exception as error:
                broken = True
                alarms.append({"code": "WITNESS_UNVERIFIABLE", "origin": origin,
                               "detail": f"{path}: {type(error).__name__}: {error}; its entries are ignored"})
                continue
            if item:
                row["witnessed"].append(item)
            if origin == deadman_origin:
                checkins += _checkins(log, path, deadman_machine)
        if broken:
            rows.append({**row, "status": "unverifiable"})
            continue
        if not row["witnessed"]:
            alarms.append({"code": "NO_WITNESS_DATA", "origin": origin, "detail": "files exist but hold nothing witnessed"})
            rows.append({**row, "status": "no_witness_data"})
            continue
        newest = max(row["witnessed"], key=lambda w: w["witnessed_at"])
        age = now - newest["witnessed_at"]
        status = "future" if age < -CLOCK_SKEW else "stale" if age > stale_after else "fresh"
        row.update(newest_witnessed_at=newest["witnessed_at"], age_seconds=age, newest_kind=newest["kind"], status=status)
        if status != "fresh":
            alarms.append({"code": "WITNESS_STALE" if status == "stale" else "CLOCK_SKEW", "origin": origin,
                           "down_since": newest["witnessed_at"] + (stale_after if status == "stale" else 0),
                           "detail": f"newest witnessed {newest['kind']} is {age}s old (bound {stale_after}s, "
                           f"skew {CLOCK_SKEW}s)"})
        rows.append(row)
    dead, dead_alarms = deadman(checkins, now=now, period=deadman_period, grace=deadman_grace, origin=deadman_origin,
                                machine=deadman_machine, blind=blind)
    alarms = with_ids(alarms + dead_alarms, "origin")
    # A silent box also starves its witnesses: one cause, one alarm. The suppressed one stays visible.
    cause = next((a for a in alarms if a["code"] == "DEADMAN"), None)
    suppressed = [{**a, "suppressed_by": cause["alarm_id"]} for a in alarms
                  if cause and a["code"] == "WITNESS_STALE" and a["origin"] == deadman_origin]
    alarms = [a for a in alarms if a["alarm_id"] not in {x["alarm_id"] for x in suppressed}]
    report = {"schema": SCHEMA, "now": now, "stale_after": stale_after, "origins": rows, "deadman": dead,
              "alarms": alarms, "suppressed": suppressed}
    report["brief"] = brief(report)
    return report


def brief(report):
    """At most three lines for Scheduled's brief."""
    rows, dead = report["origins"], report["deadman"]
    lines = ["Witness watch: " + "; ".join(
        f"{r['origin']} {r['status']}" + (f" ({r['age_seconds']}s)" if "age_seconds" in r else "") for r in rows) + "."]
    last = dead.get("last_checkin")
    lines.append(f"Dead-man {dead['machine']}@{dead['origin']}: " + (
        f"{dead['status']}, last check-in {dead['age_seconds']}s ago (bound {dead['bound']}s), "
        f"level {last['level']}, outcome {last['outcome']}." if last else
        f"blind, {dead['blind']}." if dead["status"] == "blind" else "no verified check-in."))
    if report["alarms"]:
        codes = {}
        for a in report["alarms"]:
            codes[a["code"]] = codes.get(a["code"], 0) + 1
        hidden = report["suppressed"]
        lines.append("Alarms: " + ", ".join(f"{c} {n}" for c, n in sorted(codes.items()))
                     + (f"; suppressed {hidden[0]['code']} {len(hidden)}" if hidden else "")
                     + ".")
    return [line[:240] for line in lines]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stale-after", type=int, required=True, help="seconds")
    ap.add_argument("--origin", action="append", help="origin to check (repeatable; default box)")
    ap.add_argument("--roster", help="ADR 004 roster.json (public keys only)")
    ap.add_argument("--replicas", action="append", default=[], help="a witness's replica directory (repeatable)")
    ap.add_argument("--checkpoints", action="append", default=[], type=_named, help="ORIGIN=LOG with LOG.cp beside it")
    ap.add_argument("--deadman-origin", default="box", help="node log holding the check-ins (default box)")
    ap.add_argument("--deadman-machine", default="box", help="check-in body.machine (default box)")
    ap.add_argument("--deadman-period", type=int, default=DEADMAN_PERIOD, help=f"seconds (default {DEADMAN_PERIOD})")
    ap.add_argument("--deadman-grace", type=int, default=DEADMAN_GRACE, help=f"seconds (default {DEADMAN_GRACE})")
    ap.add_argument("--deadman-after", type=int, help="deprecated: period + grace in seconds")
    ap.add_argument("--config", help="the shared host watch config (its deadman section)")
    ap.add_argument("--now", type=int, help="epoch seconds (tests)")
    ap.add_argument("--brief", action="store_true")
    args = ap.parse_args(argv)
    if args.stale_after < 1:
        ap.error("--stale-after must be positive")
    if args.deadman_period < 1 or args.deadman_grace < 0 or (args.deadman_after is not None and args.deadman_after < 1):
        ap.error("--deadman-period and --deadman-after must be positive, --deadman-grace not negative")
    period, grace = args.deadman_period, args.deadman_grace
    if args.deadman_after is not None:  # the old single bound: keep the period, the rest is grace
        period = min(period, args.deadman_after)
        grace = args.deadman_after - period
    try:
        config = load_config(args.config, ("runtimes", "deadman")) if args.config else {}
    except (OSError, ValueError) as error:
        ap.error(f"--config: {error}")
    policy = (config.get("deadman") or {}).get(f"{args.deadman_origin}/{args.deadman_machine}", {})
    period, grace = policy.get("period", period), policy.get("grace", grace)
    report = watch(args.origin or ["box"], now=int(time.time()) if args.now is None else args.now,
                   stale_after=args.stale_after, roster_path=args.roster, replica_dirs=args.replicas,
                   checkpoint_logs=args.checkpoints, deadman_origin=args.deadman_origin,
                   deadman_machine=args.deadman_machine, deadman_period=period, deadman_grace=grace)
    print("\n".join(report["brief"]) if args.brief else json.dumps(report, indent=1, sort_keys=True))
    for alarm in report["alarms"]:
        print(f"ALARM {alarm['code']} {alarm['origin']}: {alarm['detail']}", file=sys.stderr)
    return EXIT_ALARM if report["alarms"] else 0


if __name__ == "__main__":
    sys.exit(main())

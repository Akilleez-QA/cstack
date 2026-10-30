#!/usr/bin/env python3
"""Append-only decision ledger for shields level changes (POODO-shaped: decision -> attempt -> receipt).
ledger.py decision --who W --level L --scope box,host-a --reason R [--dry-run]   -> prints decision id
ledger.py attempt ID --machine M --action A
ledger.py receipt ID --machine M --before HASH --after HASH --checks JSON --outcome applied|failed|unknown|not_dispatched
ledger.py hash FILE...   -> sha256 over files (state fingerprint)
Never infers success: outcome must be given explicitly; callers pass 'unknown' when they cannot verify."""
import argparse, hashlib, json, os, sys, time, uuid
L = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.jsonl")
OUT = {"applied", "failed", "unknown", "not_dispatched", "responded"}
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")
def put(rec):
    rec["ts"] = now()
    with open(L, "a") as f: f.write(json.dumps(rec, sort_keys=True) + "\n")
ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="op", required=True)
d = sp.add_parser("decision"); d.add_argument("--who", required=True); d.add_argument("--level", required=True); d.add_argument("--scope", required=True); d.add_argument("--reason", default=""); d.add_argument("--dry-run", action="store_true")
a = sp.add_parser("attempt"); a.add_argument("id"); a.add_argument("--machine", required=True); a.add_argument("--action", required=True)
r = sp.add_parser("receipt"); r.add_argument("id"); r.add_argument("--machine", required=True); r.add_argument("--before", default=""); r.add_argument("--after", default=""); r.add_argument("--checks", default="{}"); r.add_argument("--outcome", required=True, choices=sorted(OUT))
h = sp.add_parser("hash"); h.add_argument("files", nargs="+")
x = ap.parse_args()
if x.op == "hash":
    m = hashlib.sha256()
    for p in x.files:
        try: m.update(open(p, "rb").read())
        except OSError: m.update(b"<missing:" + p.encode() + b">")
    print(m.hexdigest()[:16]); sys.exit(0)
if x.op == "decision":
    if not x.who.strip(): print("fail closed: --who required", file=sys.stderr); sys.exit(3)
    i = "shd-" + time.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    put({"type": "decision", "id": i, "authorized_by": x.who, "level": x.level, "scope": x.scope.split(","), "reason": x.reason, "dry_run": x.dry_run}); print(i)
elif x.op == "attempt": put({"type": "attempt", "id": x.id, "machine": x.machine, "action": x.action})
else:
    try: checks = json.loads(x.checks)
    except ValueError: checks = {"raw": x.checks}
    put({"type": "receipt", "id": x.id, "machine": x.machine, "before": x.before, "after": x.after, "checks": checks, "outcome": x.outcome})

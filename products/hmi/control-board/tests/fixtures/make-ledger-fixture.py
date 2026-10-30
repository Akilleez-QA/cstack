#!/usr/bin/env python3
"""Regenerate ledger-python.json: proofs made by the Python prototype, checked by lib/ledger.ts (cross-implementation test).
Throwaway keys in a temp dir, deleted on exit; the fixture holds public keys and signatures only.
Usage: python3 make-ledger-fixture.py > ledger-python.json   (needs `cryptography`)"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../ledger"))
import ledger as L
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K

ws = {n: K.generate() for n in ("host-a", "host-b", "pi")}
box = K.generate()
roster = {"quorum": 2, "witnesses": {n: L.pub_hex(k) for n, k in ws.items()}, "writers": {"box-bot": {"pub": L.pub_hex(box), "node": "box"}}}
def witness(log, names, size=None):
    size = size or len(log.entries); head = log.entries[size - 1]["hash"]
    cos = [L.cosign(ws[n], n, "box", size, head, ts=1793000000 + i) for i, n in enumerate(names)]
    return log.add_checkpoint(size, head, cos) if len(names) >= 2 else {"size": size, "head": head, "cosigs": cos}
with tempfile.TemporaryDirectory() as d:
    rp = os.path.join(d, "roster.json"); json.dump(roster, open(rp, "w"))
    log = L.Log(os.path.join(d, "box.jsonl"), "box", L.load_roster(rp))
    clear = {"op": "all-clear", "scope": ["box", "host-a"]}
    checkin = {"op": "checkin", "machine": "box", "decision_id": "shd-20261025000000-abc123", "level": 0}
    h1 = log.intent(box, "box-bot", clear)["hash"]
    log.intent(box, "box-bot", {"op": "shields-up", "level": 2})  # unrelated entry so the chain has length > 1
    witness(log, ["host-a", "host-b"])
    ok = L.bundle(log, h1)
    h2 = log.intent(box, "box-bot", checkin)["hash"]
    weak = {"intent": log.entries[-1], "chain": log.entries[-1:], "checkpoint": witness(log, ["pi"])}  # one cosig only
    witness(log, ["host-b", "pi"])
    ck = L.bundle(log, h2)
    log.claim(box, "box-bot", h2, checkin); cp = witness(log, ["host-a", "pi"])
    e2 = next(e for e in log.entries if e["hash"] == h2)
    used = {"intent": e2, "chain": log.entries[e2["seq"] - 1:cp["size"]], "checkpoint": cp}  # chain shows the claim
odd = {"s": "caf\u00e9 \u2603 \U0001F512 \"q\" \\ \n\t\x01\x7f", "n": [1, -2, 0], "b": True, "z": None, "B": {"y": 1, "a": []}}
print(json.dumps({"roster": roster, "canon": {"value": odd, "text": L.canon(odd).decode(), "digest": L.digest(odd)},
                  "allClear": {"action": clear, "bundle": ok}, "checkin": {"action": checkin, "bundle": ck},
                  "unwitnessed": {"action": checkin, "bundle": weak}, "used": {"action": checkin, "bundle": used}}, sort_keys=True))

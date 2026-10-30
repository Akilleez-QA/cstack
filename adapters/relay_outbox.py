"""The cockpit relay's durable outbox (DECISION-006 phase 2, first write path): the owner's messages to the teams.

Intent first, effect after (parts wall: oss-t3code-event-sourced-intent-then-effects). The cstack server appends each
message from the cockpit to `outbox.jsonl` and returns at once; the relay agent (a Claude Code session, RELAY.md) claims
it, delivers it to a team session, and appends what happened to `receipts.jsonl`: claimed, delivered, reply, failed.
Both files are append-only JSON lines under one directory, written under an exclusive lock; a message is never edited,
its state is the latest receipt. `teams.json` is the agent's list of sessions it can reach and `heartbeat` its last
sign of life, both rewritten atomically.

Not an approval path: approvals never pass through the cockpit (ADR 005 decision 5). The agent refuses a message that
reads as one and says why in a failed receipt.
"""
import fcntl
import json
import os
import secrets
import time

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".local", "state", "cstack-relay")
MAX_TEXT, MAX_TO = 4000, 200
TERMINAL = ("delivered", "failed")
# teams that are not Claude Code sessions, always listed: the relay CLI delivers to them itself (tools/cstack_relay.py)
CHANNELS = ({"name": "Agent", "id": "agent", "state": "answers in a minute or two", "kind": "agent"},
            {"name": "Example Agent (Agent box)", "id": "agent-box", "state": "answers when the box pulls", "kind": "agent"})


class RelayError(ValueError):
    pass


class RelayStore:
    def __init__(self, root=DEFAULT_DIR, clock=time.time):
        self.root, self.clock = root, clock
        self.outbox, self.receipts = os.path.join(root, "outbox.jsonl"), os.path.join(root, "receipts.jsonl")

    def _append(self, path, record):
        os.makedirs(self.root, exist_ok=True)
        with open(os.path.join(self.root, ".lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())

    def _replace(self, name, obj):
        os.makedirs(self.root, exist_ok=True)
        tmp = os.path.join(self.root, f".{name}.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        os.replace(tmp, os.path.join(self.root, name))

    @staticmethod
    def _lines(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        except FileNotFoundError:
            return []

    def messages(self):
        return self._lines(self.outbox)

    def receipts_for(self):
        out = {}
        for r in self._lines(self.receipts):
            out.setdefault(r.get("id"), []).append(r)
        return out

    def send(self, to, text, client_id=None, about=None):
        """Append a message from the cockpit; the same client_id twice returns the first (a retried click sends once)."""
        to, text = (to or "auto").strip(), (text or "").strip()
        if not text:
            raise RelayError("empty message")
        if len(text) > MAX_TEXT or len(to) > MAX_TO:
            raise RelayError("message too long")
        if client_id:
            for m in self.messages():
                if m.get("client_id") == client_id:
                    return m
        m = {"id": "m-" + secrets.token_hex(6), "at": round(self.clock(), 3), "from": "owner (cockpit)", "to": to,
             "about": (about or None) and str(about)[:80], "text": text, "client_id": client_id and str(client_id)[:64]}
        self._append(self.outbox, m)
        return m

    def receipt(self, mid, state, **fields):
        if state not in ("claimed", "delivered", "reply", "failed"):
            raise RelayError(f"unknown receipt state {state}")
        if not any(m["id"] == mid for m in self.messages()):
            raise RelayError(f"no message {mid}")
        r = {"id": mid, "state": state, "at": round(self.clock(), 3), **{k: v for k, v in fields.items() if v is not None}}
        self._append(self.receipts, r)
        return r

    def pending(self, stale_claim_s=600):
        """Messages the agent still owes: no terminal receipt, and unclaimed or claimed longer ago than stale_claim_s."""
        rec, now, out = self.receipts_for(), self.clock(), []
        for m in self.messages():
            rs = [r for r in rec.get(m["id"], []) if r["state"] != "reply"]
            if any(r["state"] in TERMINAL for r in rs):
                continue
            claims = [r for r in rs if r["state"] == "claimed"]
            if claims and now - claims[-1]["at"] < stale_claim_s:
                continue
            out.append(m)
        return out

    def set_teams(self, teams):
        clean = [{k: str(t[k])[:120] for k in ("name", "id", "state", "kind") if t.get(k) is not None} for t in teams if t.get("name")]
        ids = {t.get("id") for t in clean}
        clean += [dict(c) for c in CHANNELS if c["id"] not in ids]
        self._replace("teams.json", {"at": round(self.clock(), 3), "teams": clean})
        return clean

    def heartbeat(self, note="alive"):
        self._replace("heartbeat", {"at": round(self.clock(), 3), "note": str(note)[:120]})

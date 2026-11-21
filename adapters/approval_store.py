"""Durable approval store (ADR 003): the host's record of the owner's yes or no, given through the approval channel.

ApprovalWriter.record() is the only way in, and only the trusted host channel calls it. Cores get an
ApprovalReader, which implements ApprovalPort (lookup and consume) and has no write method. consume() is one
atomic UPDATE, so an approval succeeds exactly once across processes and restarts. Rows are never deleted.

Trust boundary: the file is a private 0600 file of this OS user. Any process running as the same user can
still write it directly. Separating writer and reader prevents accidents and keeps bot code paths away from
record(), but it is not protection against hostile code running as the same user.
"""
import os
import json
import sqlite3
from pathlib import Path

from adapters.private_sqlite import open_private_db
from poodo_core import ApprovalRecord, ContractError
from poodo_core.models import identifier

_FIELDS = ("approval_id", "decision_id", "request_sha256", "goal_id", "goal_revision", "approver", "verdict",
           "not_after")
_SCHEMA = """CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE, request_sha256 TEXT NOT NULL,
    goal_id TEXT NOT NULL, goal_revision INTEGER NOT NULL, approver TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'declined')), not_after INTEGER NOT NULL,
    recorded_at INTEGER NOT NULL, consumed_at INTEGER, consumed_by TEXT)"""


class _Store:
    def __init__(self, path, clock):
        if not callable(clock):
            raise ContractError("The approval store needs a host clock")
        self._clock = clock
        self._db, self._fd = open_private_db(Path(path))
        self._db.execute(_SCHEMA)
        self._db.execute("""CREATE TABLE IF NOT EXISTS envelopes (
            approval_id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, goal_revision INTEGER NOT NULL,
            policy TEXT NOT NULL, cap INTEGER NOT NULL, remaining INTEGER NOT NULL,
            scope TEXT NOT NULL, not_after INTEGER NOT NULL, consumed_by TEXT, consumed_at INTEGER)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS envelope_items (
            approval_id TEXT NOT NULL, item_id TEXT NOT NULL, cost INTEGER NOT NULL,
            PRIMARY KEY (approval_id, item_id))""")

        self._db.execute("""CREATE TABLE IF NOT EXISTS commit_policy (
            approval_id TEXT PRIMARY KEY, objects TEXT NOT NULL, caps TEXT NOT NULL)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS commit_debits (
            approval_id TEXT NOT NULL, item_id TEXT NOT NULL, at INTEGER NOT NULL,
            money INTEGER NOT NULL, messages INTEGER NOT NULL, writes INTEGER NOT NULL,
            PRIMARY KEY (approval_id, item_id))""")

    def _now(self):
        now = self._clock()
        if type(now) is not int:
            raise ContractError("The host clock must return integer epoch seconds")
        return now

    def _open(self):
        if self._db is None:
            raise ContractError("Approval store is closed")
        return self._db

    def close(self):
        if self._db is not None:
            self._db.close()
            os.close(self._fd)
            self._db = None


class ApprovalWriter(_Store):
    """Trusted HOST only: the Scheduled channel that records the owner's answer. One final answer per decision."""

    def record(self, approval: ApprovalRecord):
        if type(approval) is not ApprovalRecord:
            raise ContractError("Only an ApprovalRecord can be recorded")
        placeholders = ", ".join("?" * (len(_FIELDS) + 1))
        try:
            self._open().execute(f"INSERT INTO approvals ({', '.join(_FIELDS)}, recorded_at) VALUES ({placeholders})",
                                 (*(getattr(approval, f) for f in _FIELDS), self._now()))
        except sqlite3.IntegrityError:
            raise ContractError("This decision or approval already has a recorded answer") from None

    def record_envelope(self, *, approval_id, goal_id, goal_revision, policy, cap, scope, not_after):
        for value in (approval_id, goal_id, policy):
            identifier(value)
        if (type(cap) is not int or not 0 < cap <= 2 ** 63 - 1 or
                type(goal_revision) is not int or goal_revision < 1 or type(not_after) is not int or
                type(scope) not in (list, tuple) or not scope):
            raise ContractError("Invalid envelope: explicit cap, scope and expiry required")
        for value in scope:
            identifier(value)
        try:
            self._open().execute("INSERT INTO envelopes VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                                 (approval_id, goal_id, goal_revision, policy, cap, cap, json.dumps(scope), not_after))
        except sqlite3.IntegrityError:
            raise ContractError("Envelope already recorded") from None

    def record_commit_policy(self, approval_id, *, objects, per_minute):
        identifier(approval_id)
        if (type(objects) is not tuple or not objects or len(objects) > 32
                or len(set(objects)) != len(objects) or type(per_minute) is not tuple or len(per_minute) != 3
                or any(type(v) is not int or not 0 <= v <= 10**15 for v in per_minute)):
            raise ContractError("Explicit blast radius and resource caps required")
        for value in objects:
            identifier(value)
        db = self._open()
        try:
            changed = db.execute("INSERT INTO commit_policy SELECT approval_id, ?, ? FROM envelopes "
                "WHERE approval_id = ? AND consumed_at IS NULL",
                (json.dumps(objects), json.dumps(per_minute), approval_id))
            if changed.rowcount != 1:
                raise ContractError("Commit policy requires an unlaunched envelope")
        except sqlite3.IntegrityError:
            raise ContractError("Commit policy already recorded") from None


class ApprovalReader(_Store):
    """What a core receives as its ApprovalPort. consumer names the bot whose core spends approvals."""

    def __init__(self, path, *, clock, consumer):
        identifier(consumer)
        self._consumer = consumer
        super().__init__(path, clock)

    def lookup(self, decision_id):
        row = self._open().execute(f"SELECT {', '.join(_FIELDS)} FROM approvals WHERE decision_id = ?",
                                   (decision_id,)).fetchone()
        return ApprovalRecord(*row) if row else None

    def consume(self, approval_id):
        """True exactly once per approved approval that has not expired; False otherwise."""
        now = self._now()
        cursor = self._open().execute(
            "UPDATE approvals SET consumed_at = ?, consumed_by = ? WHERE approval_id = ? AND consumed_at IS NULL "
            "AND verdict = 'approved' AND not_after >= ?", (now, self._consumer, approval_id, now))
        return cursor.rowcount == 1

    def consume_envelope(self, approval_id):
        now = self._now()
        return self._open().execute(
            "UPDATE envelopes SET consumed_at = ?, consumed_by = ? WHERE approval_id = ? "
            "AND consumed_at IS NULL AND remaining > 0 AND not_after >= ?",
            (now, self._consumer, approval_id, now)).rowcount == 1

    def meter(self, approval_id, *, item_id, goal_id, goal_revision, policy, scope, cost, effect="read"):
        if type(cost) is not int or not 0 <= cost <= 2 ** 63 - 1 or effect != "read":
            return False
        identifier(item_id)
        db = self._open()
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT scope FROM envelopes WHERE approval_id = ?", (approval_id,)).fetchone()
            if row is None or scope not in json.loads(row[0]):
                return False
            changed = db.execute(
                "UPDATE envelopes SET remaining = remaining - ? WHERE approval_id = ? AND goal_id = ? "
                "AND goal_revision = ? AND policy = ? AND consumed_by = ? AND consumed_at IS NOT NULL "
                "AND not_after >= ? AND remaining > 0 AND remaining >= ?",
                (cost, approval_id, goal_id, goal_revision, policy, self._consumer, self._now(), cost))
            if changed.rowcount != 1:
                return False
            db.execute("INSERT INTO envelope_items VALUES (?, ?, ?)", (approval_id, item_id, cost))
            db.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            if db.in_transaction:
                db.execute("ROLLBACK")

    def commit_scope(self, approval_id, objects):
        if type(objects) is not tuple or not objects:
            return False
        row = self._open().execute("SELECT objects FROM commit_policy WHERE approval_id = ?",
                                   (approval_id,)).fetchone()
        return row is not None and set(objects) <= set(json.loads(row[0]))

    def meter_commit(self, approval_id, *, item_id, goal_id, goal_revision, policy, scope, objects, resources):
        if (type(resources) is not tuple or len(resources) != 4 or resources[0] == 0
                or any(type(v) is not int or not 0 <= v <= 10**15 for v in resources)):
            return False
        identifier(item_id)
        db, now = self._open(), self._now()
        db.execute("BEGIN IMMEDIATE")
        try:
            if not self.commit_scope(approval_id, objects):
                return False
            row = db.execute("SELECT caps FROM commit_policy WHERE approval_id = ?", (approval_id,)).fetchone()
            used = db.execute("SELECT COALESCE(SUM(money),0), COALESCE(SUM(messages),0), "
                "COALESCE(SUM(writes),0), MAX(at) FROM commit_debits WHERE approval_id = ? AND at > ?",
                (approval_id, now - 60)).fetchone()
            if ((used[3] is not None and used[3] > now)
                    or any(a + b > cap for a, b, cap in zip(used[:3], resources[1:], json.loads(row[0])))):
                return False
            envelope = db.execute("SELECT scope FROM envelopes WHERE approval_id = ?", (approval_id,)).fetchone()
            if envelope is None or scope not in json.loads(envelope[0]):
                return False
            changed = db.execute("UPDATE envelopes SET remaining = remaining - ? WHERE approval_id = ? "
                "AND goal_id = ? AND goal_revision = ? AND policy = ? AND consumed_by = ? "
                "AND consumed_at IS NOT NULL AND not_after >= ? AND remaining > 0 AND remaining >= ?",
                (resources[0], approval_id, goal_id, goal_revision, policy, self._consumer, now, resources[0]))
            if changed.rowcount != 1:
                return False
            db.execute("INSERT INTO envelope_items VALUES (?, ?, ?)", (approval_id, item_id, resources[0]))
            db.execute("INSERT INTO commit_debits VALUES (?, ?, ?, ?, ?, ?)",
                       (approval_id, item_id, now, *resources[1:]))
            db.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            if db.in_transaction:
                db.execute("ROLLBACK")

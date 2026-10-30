"""Durable approval store (ADR 003): the host's record of the owner's yes or no, given through the approval channel.

ApprovalWriter.record() is the only way in, and only the trusted host channel calls it. Cores get an
ApprovalReader, which implements ApprovalPort (lookup and consume) and has no write method. consume() is one
atomic UPDATE, so an approval succeeds exactly once across processes and restarts. Rows are never deleted.

Trust boundary: the file is a private 0600 file of this OS user. Any process running as the same user can
still write it directly. Separating writer and reader prevents accidents and keeps bot code paths away from
record(), but it is not protection against hostile code running as the same user.
"""
import os
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

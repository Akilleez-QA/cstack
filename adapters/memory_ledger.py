"""Bounded single-process append-only events. Hash chaining is not authentication."""
import hashlib
from collections.abc import Sequence

from poodo_core.models import ContractError, Document, canonical, digest


EVENT_KINDS = ("proposal", "observation", "inference", "decision", "action", "outcome", "learning", "correction")


def batch_items(items):
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)) or not items:
        raise ContractError("A nonempty batch sequence is required")
    result = []
    for item in items:
        if (type(item) not in (tuple, list) or len(item) != 2 or item[0] not in EVENT_KINDS
                or type(item[1]) is not dict):
            raise ContractError("Malformed batch item")
        result.append((item[0], Document.capture(item[1]).read()))
    return result


def merkle_root(events):
    level = [hashlib.sha256(b"\x00" + canonical(e).encode("ascii")).digest() for e in events]
    if not level:
        raise ContractError("Empty Merkle tree")
    while len(level) > 1:
        level = [hashlib.sha256(b"\x01" + level[i] + level[min(i + 1, len(level) - 1)]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


class MemoryLedger:
    def __init__(self, *, max_events=1024, max_bytes=32 * 1024 * 1024):
        if type(max_events) is not int or type(max_bytes) is not int or min(max_events, max_bytes) < 1:
            raise ContractError("Invalid ledger budget")
        self._max_events, self._max_bytes = max_events, max_bytes
        self._bytes = 0
        self._events = []

    def reserve(self, event_count, byte_count):
        if len(self._events) + event_count > self._max_events or self._bytes + byte_count > self._max_bytes:
            raise ContractError("Ledger retention budget exhausted before dispatch")

    def append(self, kind, data):
        if kind not in EVENT_KINDS:
            raise ContractError("Unknown event classification")
        body = {"sequence": len(self._events) + 1, "kind": kind, "data": data,
                "prior_event_sha256": self._events[-1].read()["event_sha256"] if self._events else None}
        event = Document.capture({**body, "event_sha256": digest(body)})
        size = len(canonical(event.read()))
        self.reserve(1, size)
        self._events.append(event)
        self._bytes += size
        return event.read()

    def append_batch(self, items):
        items = batch_items(items)
        start, size = len(self._events), self._bytes
        try:
            events = [MemoryLedger.append(self, kind, data) for kind, data in items]
            return merkle_root(events)
        except BaseException:
            del self._events[start:]
            self._bytes = size
            raise

    def read(self):
        return [x.read() for x in self._events]


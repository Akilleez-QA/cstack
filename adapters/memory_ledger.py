"""Bounded single-process append-only events. Hash chaining is not authentication."""
from poodo_core.models import ContractError, Document, canonical, digest


EVENT_KINDS = ("proposal", "observation", "inference", "decision", "action", "outcome", "learning", "correction")


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

    def read(self):
        return [x.read() for x in self._events]


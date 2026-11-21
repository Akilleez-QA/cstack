"""A MemoryLedger that also appends each event to one file and syncs it, so a later core can replay it and recover."""
import hashlib
import json
import os
from pathlib import Path

from adapters.memory_ledger import MemoryLedger, merkle_root
from poodo_core.models import ContractError, Document, canonical


def _sync_parent(path):
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class DurableLedger(MemoryLedger):
    """A torn last line was never acknowledged, so its bytes are set aside on load. One writer at a time; the host owns
    the file. An event that could not be written and synced is taken back and the append raises."""
    def __init__(self, path, **budget):
        super().__init__(**budget)
        self.path = Path(path)
        self.quarantined = []
        if self.path.exists():
            raw = self.path.read_bytes()
            end = raw.rfind(b"\n") + 1
            for line in raw[:end].splitlines():
                record = json.loads(line)
                events = record["events"] if record.get("schema") == "forge.batch/1" else [record]
                if record.get("schema") == "forge.batch/1" and merkle_root(events) != record.get("root"):
                    raise ContractError("Batch root mismatch")
                for value in events:
                    event = Document.capture(value)
                    self._events.append(event)
                    self._bytes += len(canonical(event.read()))
            if end < len(raw):
                self.quarantined.append(self.quarantine_tail(self.path, raw[end:], end))

    @staticmethod
    def quarantine_tail(path, tail, end):
        digest = hashlib.sha256(tail).hexdigest()
        side = path.with_name(f"{path.name}.torn-{digest[:16]}")
        fd = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            DurableLedger._write_all(fd, tail)
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(path, os.O_WRONLY)
        try:
            os.ftruncate(fd, end)
            os.fsync(fd)
        finally:
            os.close(fd)
        _sync_parent(path)
        return {"path": str(side), "bytes": len(tail), "sha256": digest}

    @staticmethod
    def _write_all(fd, data):
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("Incomplete ledger write")
            view = view[written:]

    def append(self, kind, data):
        event = super().append(kind, data)
        line = (canonical(event) + "\n").encode("ascii")
        try:
            created = not self.path.exists()
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        except BaseException:
            self._take_back()
            raise
        start = None
        try:
            start = os.fstat(fd).st_size
            self._write_all(fd, line)
            os.fsync(fd)
            if created:
                _sync_parent(self.path)
        except BaseException:
            self._take_back()
            if start is not None:
                os.ftruncate(fd, start)
                os.fsync(fd)
            raise
        finally:
            os.close(fd)
        return event

    def append_batch(self, items):
        start, size = len(self._events), self._bytes
        try:
            root = MemoryLedger.append_batch(self, items)
            events = [event.read() for event in self._events[start:]]
            line = (canonical({"schema": "forge.batch/1", "root": root, "events": events}) + "\n").encode("ascii")
            created = not self.path.exists()
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            offset = None
            try:
                offset = os.fstat(fd).st_size
                self._write_all(fd, line)
                os.fsync(fd)
                if created:
                    _sync_parent(self.path)
            except BaseException:
                if offset is not None:
                    os.ftruncate(fd, offset)
                    os.fsync(fd)
                raise
            finally:
                os.close(fd)
            return root
        except BaseException:
            del self._events[start:]
            self._bytes = size
            raise

    def _take_back(self):
        self._bytes -= len(canonical(self._events.pop().read()))

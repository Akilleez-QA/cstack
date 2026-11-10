"""A MemoryLedger that also appends each event to one file and syncs it, so a later core can replay it and recover."""
import hashlib
import json
import os
from pathlib import Path

from adapters.memory_ledger import MemoryLedger
from poodo_core.models import Document, canonical


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
                event = Document.capture(json.loads(line))
                self._events.append(event)
                self._bytes += len(canonical(event.read()))
            if end < len(raw):
                self._quarantine(raw[end:], end)

    def _quarantine(self, tail, end):
        digest = hashlib.sha256(tail).hexdigest()
        side = self.path.with_name(f"{self.path.name}.torn-{digest[:16]}")
        fd = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            self._write_all(fd, tail)
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(self.path, os.O_WRONLY)
        try:
            os.ftruncate(fd, end)
            os.fsync(fd)
        finally:
            os.close(fd)
        _sync_parent(self.path)
        self.quarantined.append({"path": str(side), "bytes": len(tail), "sha256": digest})

    @staticmethod
    def _write_all(fd, data):
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]

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
            raise
        finally:
            os.close(fd)
        return event

    def _take_back(self):
        self._bytes -= len(canonical(self._events.pop().read()))

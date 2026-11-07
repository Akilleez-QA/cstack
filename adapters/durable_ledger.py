"""A MemoryLedger that also appends each event to one file and syncs it, so a later core can replay it and recover."""
import json
import os
from pathlib import Path

from adapters.memory_ledger import MemoryLedger
from poodo_core.models import Document, canonical


class DurableLedger(MemoryLedger):
    """A torn last line was never acknowledged, so it's dropped on load. One writer at a time; the host owns the file."""
    def __init__(self, path, **budget):
        super().__init__(**budget)
        self.path = Path(path)
        if self.path.exists():
            raw = self.path.read_bytes()
            complete = raw[:raw.rfind(b"\n") + 1]
            for line in complete.splitlines():
                event = Document.capture(json.loads(line))
                self._events.append(event)
                self._bytes += len(canonical(event.read()))

    def append(self, kind, data):
        event = super().append(kind, data)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (canonical(event) + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return event

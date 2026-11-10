import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from adapters.durable_ledger import DurableLedger
from adapters.endoforge_workcell import core_events


class DurableLedgerFailures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "core.jsonl"

    def numbers(self, ledger=None):
        return [event["data"]["n"] for event in (ledger or DurableLedger(self.path)).read()]

    def test_a_short_write_is_finished_before_the_event_is_acknowledged(self):
        ledger = DurableLedger(self.path)
        real = os.write
        with mock.patch("adapters.durable_ledger.os.write", side_effect=lambda fd, data: real(fd, bytes(data)[:5])):
            ledger.append("observation", {"n": 1})
        self.assertEqual(self.numbers(), [1])

    def test_a_full_disk_raises_and_leaves_no_event_in_the_file_or_in_memory(self):
        ledger = DurableLedger(self.path)
        ledger.append("observation", {"n": 1})
        real, calls = os.write, []

        def full(fd, data):
            calls.append(1)
            if len(calls) == 1:
                return real(fd, bytes(data)[:5])
            raise OSError(28, "No space left on device")

        with mock.patch("adapters.durable_ledger.os.write", side_effect=full):
            with self.assertRaises(OSError):
                ledger.append("observation", {"n": 2})
        self.assertEqual(self.numbers(ledger), [1])
        self.assertEqual(self.numbers(), [1])
        self.assertTrue(self.path.read_bytes().endswith(b"\n"))
        ledger.append("observation", {"n": 2})
        self.assertEqual(self.numbers(), [1, 2])

    def test_a_failed_fsync_raises_and_does_not_keep_the_event(self):
        ledger = DurableLedger(self.path)
        with mock.patch("adapters.durable_ledger.os.fsync", side_effect=OSError(5, "I/O error")):
            with self.assertRaises(OSError):
                ledger.append("observation", {"n": 1})
        self.assertEqual(self.numbers(ledger), [])
        self.assertEqual(self.path.read_bytes(), b"")

    def test_the_budget_counts_only_what_was_kept(self):
        ledger = DurableLedger(self.path)
        with mock.patch("adapters.durable_ledger.os.fsync", side_effect=OSError(5, "I/O error")):
            with self.assertRaises(OSError):
                ledger.append("observation", {"n": 1})
        self.assertEqual(ledger._bytes, 0)

    def test_a_failed_open_keeps_no_phantom_event_and_a_retry_starts_the_chain_clean(self):
        missing = self.dir / "absent" / "core.jsonl"
        ledger = DurableLedger(missing)
        with self.assertRaises(FileNotFoundError):
            ledger.append("observation", {"n": 1})
        self.assertEqual(ledger.read(), [])
        self.assertEqual(ledger._bytes, 0)
        missing.parent.mkdir()
        event = ledger.append("observation", {"n": 1})
        self.assertEqual((event["sequence"], event["prior_event_sha256"]), (1, None))
        self.assertEqual(self.numbers(DurableLedger(missing)), [1])
        self.assertEqual(DurableLedger(missing).read(), ledger.read())

    def test_a_refused_open_on_an_existing_file_keeps_no_phantom_event(self):
        ledger = DurableLedger(self.path)
        ledger.append("observation", {"n": 1})
        size = ledger._bytes
        with mock.patch("adapters.durable_ledger.os.open", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(PermissionError):
                ledger.append("observation", {"n": 2})
        self.assertEqual(self.numbers(ledger), [1])
        self.assertEqual(ledger._bytes, size)
        ledger.append("observation", {"n": 2})
        self.assertEqual(DurableLedger(self.path).read(), ledger.read())

    def test_a_torn_tail_from_a_killed_writer_survives_a_restart_and_the_next_append(self):
        ledger = DurableLedger(self.path)
        ledger.append("observation", {"n": 1})
        ledger.append("observation", {"n": 2})
        torn = b'{"data":{"n":3},"ki'
        with self.path.open("ab") as stream:
            stream.write(torn)
        reopened = DurableLedger(self.path)
        self.assertEqual(self.numbers(reopened), [1, 2])
        reopened.append("observation", {"n": 3})
        self.assertEqual(self.numbers(), [1, 2, 3])
        side = Path(reopened.quarantined[0]["path"])
        self.assertEqual(side.read_bytes(), torn)
        self.assertEqual(reopened.quarantined[0]["bytes"], len(torn))

    def test_core_events_skip_a_torn_tail_that_happens_to_end_in_a_brace(self):
        ledger = DurableLedger(self.path)
        ledger.append("observation", {"n": 1})
        with self.path.open("ab") as stream:
            stream.write(b'{"data":{"n":2}')
        self.assertEqual([event["data"]["n"] for event in core_events(self.path)], [1])

    def test_a_complete_ledger_is_read_back_unchanged(self):
        ledger = DurableLedger(self.path)
        ledger.append("observation", {"n": 1})
        before = self.path.read_bytes()
        self.assertEqual(DurableLedger(self.path).quarantined, [])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(json.loads(before)["data"], {"n": 1})


if __name__ == "__main__":
    unittest.main()

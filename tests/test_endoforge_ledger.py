import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from adapters.endoforge_ledger import EndoforgeLedger
from poodo_core.models import CapabilityOutcome, ContractError, DecisionRecord, Document, canonical, digest
from poodo_core.ports import EndoforgePort
from tests import test_endoforge_port as conformance


class EndoforgeLedgerTests(unittest.TestCase):
    def setUp(self):
        conformance.EndoforgePortTests.setUp(self)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "ledger.jsonl"
        self.port = EndoforgeLedger(self.path)
        self.addCleanup(self.port.close)

    test_append_and_filter_preserve_evidence = conformance.EndoforgePortTests.test_append_and_filter_preserve_evidence

    def test_protocol_and_reopen(self):
        self.assertIsInstance(self.port, EndoforgePort)
        for name in vars(EndoforgePort):
            if not name.startswith("_"):
                self.assertEqual(inspect.signature(getattr(EndoforgePort, name)),
                                 inspect.signature(getattr(EndoforgeLedger, name)))
        first = self.port.append_precommit("s1", self.decision)
        self.port.close()
        with EndoforgeLedger(self.path) as reopened:
            second = reopened.append_outcome("s1", self.outcome)
            self.assertTrue(reopened.verify_chain())
            records = reopened.read_records(session_id="s1")
            self.assertEqual([r.read()["record_id"] for r in records], [first, second])
            for document in records:
                record = document.read()
                record_id = record.pop("record_id")
                self.assertEqual(record_id, digest(record))

    def test_unmatched_and_invalid_inputs_do_not_append(self):
        with self.assertRaises(ContractError):
            self.port.append_outcome("s1", self.outcome)
        self.port.append_precommit("s1", self.decision)
        before = self.path.read_bytes()
        for field, value in (("request_id", "other"), ("decision_id", "other"), ("goal_id", "other"),
                             ("goal_revision", 2), ("capability_id", "other"), ("operation", "other"),
                             ("request_sha256", "0" * 64)):
            payload = {**self.outcome.to_dict(), field: value}
            with self.subTest(field=field), self.assertRaises(ContractError):
                self.port.append_outcome("s1", CapabilityOutcome.from_dict(payload))
        for call in (lambda: self.port.append_outcome("s2", self.outcome),
                     lambda: self.port.append_precommit("bad session", self.decision),
                     lambda: self.port.append_precommit("s1", DecisionRecord(
                         self.request, "0" * 64, "grant", self.decision.precommitment)),
                     lambda: self.port.append_precommit("s1", None),
                     lambda: self.port.append_outcome("s1", CapabilityOutcome(Document.capture({}))),
                     lambda: self.port.read_records(), lambda: self.port.read_records(goal_id="bad id")):
            with self.assertRaises(ContractError):
                call()
        self.assertEqual(self.path.read_bytes(), before)

    def test_corruption_fails_closed(self):
        self.port.append_precommit("s1", self.decision)
        original = self.path.read_bytes()
        record = self.port.read_records(session_id="s1")[0].read()
        altered = {**record, "session_id": "changed"}
        invalid = {**record, "payload": {**record["payload"], "grant_id": "bad id"}}
        invalid["record_id"] = digest({k: v for k, v in invalid.items() if k != "record_id"})
        for data in (original[:-1], b"not json\n", (canonical(altered) + "\n").encode(),
                     (canonical(invalid) + "\n").encode(), original + original):
            with self.subTest(data=data[:40]):
                self.path.write_bytes(data)
                self.assertFalse(self.port.verify_chain())
                for call in (lambda: self.port.read_records(goal_id="missing"),
                             lambda: self.port.append_precommit("s1", self.decision),
                             lambda: self.port.append_outcome("s1", self.outcome)):
                    with self.assertRaises(RuntimeError):
                        call()
                self.assertEqual(self.path.read_bytes(), data)

    def test_concurrent_writer_refused(self):
        script = "from adapters.endoforge_ledger import EndoforgeLedger; import sys; EndoforgeLedger(sys.argv[1])"
        child = subprocess.run([sys.executable, "-B", "-c", script, str(self.path)],
                               capture_output=True, text=True, timeout=10)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("BlockingIOError", child.stderr)
        alias = self.path.with_name("alias")
        os.link(self.path, alias)
        with self.assertRaises(OSError):
            EndoforgeLedger(alias)
        self.assertTrue(self.port.verify_chain())

    def test_io_errors_and_uncertain_acknowledgement(self):
        with patch("adapters.endoforge_ledger.os.write", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                self.port.append_precommit("s1", self.decision)
        self.assertEqual(self.path.read_bytes(), b"")
        with patch("adapters.endoforge_ledger.os.fsync", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                self.port.append_precommit("s1", self.decision)
        self.assertEqual(len(self.port.read_records(session_id="s1")), 1)
        write = os.write
        with patch("adapters.endoforge_ledger.os.write", side_effect=lambda fd, data: write(fd, data[:20])):
            with self.assertRaises(OSError):
                self.port.append_outcome("s1", self.outcome)
        self.assertFalse(self.port.verify_chain())
        self.port.close()
        for call in (self.port.verify_chain, lambda: self.port.read_records(session_id="s1"),
                     lambda: self.port.append_precommit("s1", self.decision)):
            with self.assertRaises(OSError):
                call()

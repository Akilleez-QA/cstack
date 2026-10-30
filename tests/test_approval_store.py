"""ADR 003 PR 4b: the owner's answer is recorded once by the host and consumed once by a core, durably."""
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from adapters.approval_store import ApprovalReader, ApprovalWriter
from adapters.memory_ledger import MemoryLedger
from poodo_core import ApprovalRecord, ContractError
from tests.helpers import request
from tests.test_approval_policy import APPROVER, ASK_GRANT, Foundation, decided


ROOT = Path(__file__).resolve().parent.parent


def in_parallel(code, n):
    """n real processes released together by a file barrier; every one must exit cleanly."""
    with tempfile.TemporaryDirectory() as tmp:
        go = Path(tmp) / "go"
        prelude = f"import pathlib, time\nwhile not pathlib.Path({str(go)!r}).exists(): time.sleep(0.001)\n"
        procs = [subprocess.Popen([sys.executable, "-B", "-c", prelude + code], cwd=ROOT,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(n)]
        go.touch()
        out = [p.communicate(timeout=60) for p in procs]
    for proc, (_, err) in zip(procs, out):
        assert proc.returncode == 0, err.decode()
    return [o.decode().strip() for o, _ in out]


def answer(req, verdict="approved", not_after=2000, approval_id=None):
    return ApprovalRecord(approval_id or "a-" + req.decision_id, req.decision_id, req.sha256, req.goal_id,
                          req.goal_revision, APPROVER, verdict, not_after)


class ApprovalStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "approvals.db"

    def tearDown(self):
        self._tmp.cleanup()

    def writer(self, now=1000):
        return ApprovalWriter(self.path, clock=lambda: now)

    def reader(self, now=1000, consumer="example-agent"):
        return ApprovalReader(self.path, clock=lambda: now, consumer=consumer)

    def test_cores_get_a_reader_without_any_write_path(self):
        self.assertFalse(hasattr(self.reader(), "record"))
        self.assertFalse(hasattr(self.writer(), "consume"))

    def test_consume_succeeds_once_across_restarts_and_records_the_consumer(self):
        req = request("send_report")
        self.writer().record(answer(req))
        first = self.reader(consumer="coordinator")
        self.assertTrue(first.consume("a-d-1"))
        self.assertFalse(first.consume("a-d-1"))
        first.close()
        self.assertFalse(self.reader().consume("a-d-1"))
        row = sqlite3.connect(self.path).execute("SELECT consumed_at, consumed_by FROM approvals").fetchone()
        self.assertEqual(row, (1000, "coordinator"))

    def test_racing_processes_get_exactly_one_yes(self):
        self.writer().record(answer(request("send_report")))
        results = in_parallel("from adapters.approval_store import ApprovalReader as R\n"
                              f"print(R({str(self.path)!r}, clock=lambda: 1000, consumer='x').consume('a-d-1'))", 8)
        self.assertEqual(sorted(results), ["False"] * 7 + ["True"])

    def test_racing_processes_can_create_a_new_store(self):
        fresh = self.root / "fresh.db"
        results = in_parallel("from adapters.approval_store import ApprovalReader as R\n"
                              f"R({str(fresh)!r}, clock=lambda: 1, consumer='x').close(); print('ok')", 8)
        self.assertEqual(results, ["ok"] * 8)

    def test_one_final_answer_per_decision(self):
        req = request("send_report")
        writer = self.writer()
        writer.record(answer(req))
        for duplicate in (answer(req, verdict="declined", approval_id="other"), answer(req)):
            with self.assertRaisesRegex(ContractError, "already has a recorded answer"):
                writer.record(duplicate)
        with self.assertRaises(ContractError):
            writer.record({"approval_id": "x"})
        self.assertEqual(self.reader().lookup(req.decision_id), answer(req))

    def test_declined_expired_and_boundary(self):
        writer = self.writer()
        for i, kwargs in ((1, dict(verdict="declined")), (2, dict(not_after=999)), (3, dict(not_after=1000))):
            writer.record(answer(request("send_report", i=i), **kwargs))
        reader = self.reader(now=1000)
        self.assertEqual([reader.consume(f"a-d-{i}") for i in (1, 2, 3)], [False, False, True])
        self.assertIsNone(reader.lookup("d-missing"))

    def test_bad_clock_symlinks_and_closed_stores_fail_closed(self):
        with self.assertRaisesRegex(ContractError, "integer epoch"):
            ApprovalWriter(self.path, clock=lambda: 1.5).record(answer(request("send_report")))
        link = self.root / "link.db"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ContractError, "Refusing"):
            ApprovalReader(link, clock=lambda: 1, consumer="x")
        reader = self.reader()
        reader.close()
        with self.assertRaisesRegex(ContractError, "closed"):
            reader.lookup("d-1")

    def test_core_with_durable_store_refuses_replay_after_restart(self):
        results = []
        for run in range(2):
            ledger = MemoryLedger()
            reader = self.reader()
            core = Foundation(grants=(ASK_GRANT,), approvals=reader, ledger=ledger)
            req = decided(core, request("send_report"))
            if reader.lookup(req.decision_id) is None:
                self.writer().record(answer(req))
            try:
                results.append(core.execute(req.decision_id).to_dict()["execution_status"])
            except ContractError as error:
                results.append(str(error))
            reader.close()
        self.assertEqual(results[0], "completed")
        self.assertIn("refused to consume", results[1])


if __name__ == "__main__":
    unittest.main()

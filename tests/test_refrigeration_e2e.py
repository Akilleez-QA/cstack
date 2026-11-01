import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import uuid4

from adapters.approval_store import ApprovalWriter
from adapters.endoforge_ledger import EndoforgeLedger
from poodo_core import ApprovalRecord, CapabilityRequest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/refrigeration-e2e.json"


@unittest.skipUnless((ROOT / "foundations/refrigeration").is_dir(), "Refrigeration is absent")
class RefrigerationE2ETests(unittest.TestCase):
    def run_example(self, directory, verdict):
        document = json.loads(EXAMPLE.read_text())
        request = CapabilityRequest.from_dict(document["calls"][0]["request"])
        approval = ApprovalRecord(uuid4().hex, request.decision_id, request.sha256, request.goal_id,
                                  request.goal_revision, "owner-via-approver", verdict, int(time.time()) + 300)
        store = directory / "approvals.db"
        writer = ApprovalWriter(store, clock=lambda: int(time.time()))
        try:
            writer.record(approval)
        finally:
            writer.close()
        config = directory / "host.json"
        ledger = directory / "endoforge.jsonl"
        config.write_text(json.dumps({"endoforge": {"path": ledger.name}}))
        process = subprocess.run([sys.executable, "-B", "cli.py", "--config", str(config),
                                  "--approver=file:" + str(store)], cwd=ROOT,
                                 input=EXAMPLE.read_bytes(), capture_output=True, timeout=60)
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(process.stderr, b"")
        result = json.loads(process.stdout)
        self.assertTrue(result["endoforge_implemented"])
        with EndoforgeLedger(ledger) as port:
            self.assertTrue(port.verify_chain())
            records = [r.read() for r in port.read_records(goal_id=request.goal_id)]
        self.assertEqual(len({r["session_id"] for r in records}), 1)
        decisions = [e["data"] for e in result["events"] if e["kind"] == "decision"]
        gate = next(d for d in decisions if d["action"] == "precommit")
        self.assertTrue(gate["approval_required"])
        self.assertEqual(gate["request_sha256"], request.sha256)
        answer = next(d for d in decisions if d["action"] == verdict)
        self.assertEqual(answer["approval_id"], approval.approval_id)
        witnessed = [r["payload"]["approval"] for r in records if "approval" in r["payload"]]
        self.assertEqual(witnessed, [vars(approval)])
        with sqlite3.connect(store) as db:
            row = db.execute("SELECT approval_id, consumed_at, consumed_by FROM approvals").fetchone()
        self.assertEqual(row[0], answer["approval_id"])
        return result, records, row

    def test_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records, row = self.run_example(Path(directory), "approved")
        self.assertEqual(result["run_status"], "completed")
        self.assertIsNotNone(row[1])
        self.assertEqual(row[2], "local-cli")
        self.assertEqual([r["kind"] for r in records], ["precommit", "precommit", "outcome"])
        outcome = records[-1]["payload"]
        self.assertEqual(outcome["execution_status"], "completed")
        self.assertEqual(outcome["capability_id"], "foundation_refrigeration")
        self.assertEqual(outcome["operation"], "saturation_pressure")
        for record in records[:-1]:
            self.assertEqual(record["payload"]["request_sha256"], outcome["request_sha256"])
            self.assertEqual(record["payload"]["request"]["decision_id"], outcome["decision_id"])
        receipt = outcome["raw_result"]["structuredContent"]["receipt"]
        self.assertEqual(outcome["raw_result"]["structuredContent"]["assessment"], "saturation_pressure_observed")
        views = receipt["result"]["pressure_views"]
        self.assertEqual(round(next(v["value"] for v in views if v["unit"] == "psig"), 2), 33.49)
        self.assertTrue(receipt["evidence"])
        outcomes = [e["data"]["outcome"] for e in result["events"] if e["kind"] == "outcome"]
        self.assertEqual(outcomes, [outcome])
        actions = [e["data"] for e in result["events"] if e["kind"] == "action"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["approval_id"], row[0])
        self.summary = {"endoforge_implemented": result["endoforge_implemented"], "approval_id": row[0],
                        "ledger_events": [r["kind"] for r in records], "verify_chain": True}

    def test_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records, row = self.run_example(Path(directory), "declined")
        self.assertEqual(result["run_status"], "stopped")
        self.assertEqual(result["stopped"]["execution_certainty"], "not_dispatched")
        self.assertFalse(any(e["kind"] in ("action", "outcome") for e in result["events"]))
        self.assertEqual([r["kind"] for r in records], ["precommit", "precommit"])
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])


if __name__ == "__main__":
    if sys.argv[1:] == ["--summary"]:
        test = RefrigerationE2ETests("test_approved")
        test.test_approved()
        print(json.dumps(test.summary, sort_keys=True))
    else:
        unittest.main()

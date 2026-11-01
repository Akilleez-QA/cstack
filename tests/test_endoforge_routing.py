import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.endoforge_ledger import EndoforgeLedger
from adapters.memory_ledger import MemoryLedger
from bootstrap import endoforge_session
from cli import run_document
from poodo_core import ApprovalDeclined, ApprovalRecord, ContractError, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import precommit, request, to_decide
from tests.test_approval_policy import APPROVER, ASK_GRANT, Approvals, Capability, Extension


class EndoforgeRoutingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "evidence.jsonl"
        self.port = EndoforgeLedger(self.path)
        self.addCleanup(self.port.close)

    def core(self):
        self.cap, self.approvals = Capability(), Approvals()
        return PoodoCore(Extension(), {"synthetic_sensor": self.cap}, (ASK_GRANT,), MemoryLedger(),
                         approvals=self.approvals, approver=APPROVER, clock=lambda: 1000,
                         endoforge=self.port, session_id="host-session")

    def decide(self, core, req):
        to_decide(core)
        core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Host selected action"))

    def records(self):
        return [r.read() for r in self.port.read_records(session_id="host-session")]

    def test_precommit_before_dispatch_and_outcome_chain(self):
        core, req = self.core(), request()
        self.decide(core, req)
        self.assertEqual([r["kind"] for r in self.records()], ["precommit"])
        invoke = self.cap.invoke

        def witnessed(*args):
            self.assertEqual([r["kind"] for r in self.records()], ["precommit", "precommit"])
            self.assertTrue(self.port.verify_chain())
            return invoke(*args)

        with patch.object(self.cap, "invoke", side_effect=witnessed):
            outcome = core.execute(req.decision_id)
        self.assertEqual(outcome.to_dict()["execution_status"], "completed")
        self.assertEqual(self.records()[-1]["payload"], outcome.to_dict())
        self.port.close()
        with EndoforgeLedger(self.path) as reopened:
            self.assertTrue(reopened.verify_chain())
            self.assertEqual(len(reopened.read_records(goal_id="g")), 3)

    def test_storage_failures_block_dispatch_and_retry(self):
        for stage in ("decide", "execute"):
            for syscall in ("write", "fsync"):
                with self.subTest(stage=stage, syscall=syscall):
                    core, req = self.core(), request()
                    to_decide(core)
                    if stage == "execute":
                        core.decide(req, precommit())
                        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Host selected action"))
                    operation = lambda: core.decide(req, precommit()) if stage == "decide" else core.execute(req.decision_id)
                    with patch("adapters.endoforge_ledger.os." + syscall, side_effect=OSError("storage failed")):
                        with self.assertRaises(OSError):
                            operation()
                    with self.assertRaises(ContractError):
                        operation()
                    self.assertEqual(self.cap.calls, [])
                    self.assertFalse(any(e["kind"] == "action" for e in core.ledger()))

    def test_failed_outcome_is_not_success_or_retried(self):
        core, req = self.core(), request()
        self.decide(core, req)
        with patch.object(self.port, "append_outcome", side_effect=OSError("storage failed")):
            with self.assertRaises(OSError):
                core.execute(req.decision_id)
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual(len(self.cap.calls), 1)
        self.assertFalse(any(e["kind"] == "outcome" for e in core.ledger()))

    def test_approval_decisions_are_witnessed(self):
        for verdict in ("approved", "declined"):
            with self.subTest(verdict=verdict):
                core, req = self.core(), request("send_report")
                self.decide(core, req)
                approval = ApprovalRecord("approval-1", req.decision_id, req.sha256, "g", 1, APPROVER, verdict, 2000)
                self.approvals.records[req.decision_id] = approval
                invoke = self.cap.invoke

                def witnessed(*args):
                    self.assertEqual(self.records()[-1]["payload"]["approval"], vars(approval))
                    self.assertIn(approval.approval_id, self.approvals.consumed)
                    return invoke(*args)

                with patch.object(self.cap, "invoke", side_effect=witnessed):
                    if verdict == "approved":
                        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
                    else:
                        with self.assertRaises(ApprovalDeclined):
                            core.execute(req.decision_id)
                        self.assertEqual(self.cap.calls, [])
                records = [r for r in self.records() if "approval" in r["payload"]]
                self.assertEqual(records[-1]["payload"]["approval"], vars(approval))
                self.assertEqual(records[-1]["schema"], "poodo.endoforge-record/0.2")
                self.assertTrue(self.port.verify_chain())

    def test_failed_execution_preserves_uncertainty(self):
        core, req = self.core(), request()
        self.decide(core, req)
        with patch.object(self.cap, "invoke", side_effect=RuntimeError("lost response")):
            outcome = core.execute(req.decision_id).to_dict()
        self.assertEqual(outcome["execution_certainty"], "unknown")
        self.assertEqual(self.records()[-1]["payload"], outcome)
        self.assertTrue(self.port.verify_chain())

    def test_cli_uses_only_host_config_and_closes_storage(self):
        self.port.close()
        config = self.path.parent / "cstack.config.json"
        config.write_text(json.dumps({"endoforge": {"path": self.path.name}}))
        document = json.loads((Path(__file__).resolve().parents[1] / "examples/scalar-and-negative.json").read_text())
        with patch("cli.endoforge_session", lambda: endoforge_session(config)):
            for _ in range(2):
                result = run_document(document)
                self.assertTrue(result["endoforge_implemented"])
                self.assertEqual(result["run_status"], "completed")
            with self.assertRaises(ContractError):
                run_document({**document, "endoforge": {"path": "request-selected.jsonl"}})
        with EndoforgeLedger(self.path) as reopened:
            records = reopened.read_records(goal_id=document["goal"]["goal_id"])
            self.assertEqual(len(records), 12)
            self.assertEqual(len({r.read()["session_id"] for r in records}), 2)
            self.assertTrue(reopened.verify_chain())
        with patch("cli.endoforge_session", lambda: endoforge_session(config)), patch.object(
                EndoforgeLedger, "append_outcome", side_effect=OSError("storage failed")):
            stopped = run_document(document)
        self.assertEqual(stopped["run_status"], "stopped")
        self.assertEqual(stopped["stopped"]["execution_certainty"], "unknown")
        self.assertEqual(stopped["stopped"]["reason"], "endoforge_storage_failure")
        self.assertEqual(len([e for e in stopped["events"] if e["kind"] == "action"]), 1)
        config.write_text(json.dumps({"endoforge": {"path": "missing/evidence.jsonl"}}))
        with patch("cli.endoforge_session", lambda: endoforge_session(config)), patch("cli.build_domain") as build:
            with self.assertRaises(OSError):
                run_document(document)
            build.assert_not_called()

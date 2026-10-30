"""ADR 005 item 2b: ToolFace holds with fake.capability.scripted in place of the Foundation stdio bridges."""
import threading
import unittest

from poodo_core import ContractError, Phase, PhaseCheckpoint
from tests.helpers import precommit, request, to_decide
from tests.replaceability.compose import ScriptedCapability, build


def run(*script, cancellation=None):
    core, cap, _ = build(capability=ScriptedCapability(*script), ask=())
    req = request("reading")
    to_decide(core)
    core.decide(req, precommit())
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
    return core, cap, req, core.execute(req.decision_id, cancellation).to_dict()


class ToolFaceScriptedCapabilityTests(unittest.TestCase):
    def test_completed_result_is_a_tool_observation(self):
        core, cap, _, outcome = run("completed")
        self.assertEqual((outcome["execution_status"], outcome["execution_certainty"]), ("completed", "responded"))
        self.assertEqual(core.ledger()[-1]["data"]["interpretation"]["evidence_kind"], "tool_observation")
        self.assertFalse(outcome["formal_proof"] or outcome["runtime_goal_acceptance"])
        self.assertEqual(len(cap.calls), 1)

    def test_tool_error_is_distinct_from_protocol_failure(self):
        *_, tool = run("tool_error")
        *_, protocol = run("protocol_error")
        self.assertEqual(tool["execution_status"], "tool_error")
        self.assertEqual(tool["raw_result"], {"error": "reading out of range"})
        self.assertEqual(protocol["execution_status"], "protocol_error")
        self.assertIsNone(protocol["raw_result"])
        self.assertEqual({tool["epistemic_status"], protocol["epistemic_status"]}, {"unassessed"})

    def test_failure_after_dispatch_is_unknown_and_never_retried(self):
        for step, status in (("timeout", "timed_out"), ("crash", "indeterminate"),
                             ("cancel_after_dispatch", "cancelled")):
            with self.subTest(step=step):
                core, cap, req, outcome = run(step, "completed", cancellation=threading.Event())
                self.assertEqual((outcome["execution_status"], outcome["execution_certainty"]), (status, "unknown"))
                with self.assertRaisesRegex(ContractError, "consumed"):
                    core.execute(req.decision_id)
                self.assertEqual((len(cap.calls), cap.script), (1, ["completed"]))
                self.assertEqual([e["kind"] for e in core.ledger()].count("action"), 1)

    def test_unknown_tool_is_refused_without_dispatch(self):
        core, cap, _ = build(ask=())
        to_decide(core)
        for req in (request("format_disk"), request("reading", capability="shell", i=2)):
            with self.subTest(operation=req.operation, capability=req.capability_id):
                with self.assertRaisesRegex(ContractError, "Undeclared"):
                    core.decide(req, precommit())
        self.assertEqual(cap.calls, [])
        self.assertNotIn("precommit", [e["data"].get("action") for e in core.ledger()])


if __name__ == "__main__":
    unittest.main()

"""ADR 005 item 2a: TruthFace holds with fake.approver.memory in place of Friday and the SQLite approval store."""
import unittest

from poodo_core import ApprovalDeclined, ApprovalPending, ContractError, CostBudget, Phase, PhaseCheckpoint
from tests.helpers import precommit, request, to_decide
from tests.replaceability.compose import AOR, NOW, FixedCost, MemoryApprover, build


def decided(core, req):
    to_decide(core)
    core.decide(req, precommit())
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
    return req


def actions(core):
    return [e["data"].get("action") for e in core.ledger()]


class TruthFaceFakeApproverTests(unittest.TestCase):
    def test_pending_then_approved_executes_exactly_once(self):
        core, cap, approver = build()
        req = decided(core, request("send_report"))
        with self.assertRaises(ApprovalPending):
            core.execute(req.decision_id)
        self.assertEqual((cap.calls, approver.consumed), ([], []))
        self.assertEqual(actions(core)[-1], "approval_pending")
        approver.answer(req)
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual((len(cap.calls), approver.consumed), (1, ["a-d-1"]))
        self.assertEqual(actions(core).count("approved"), 1)

    def test_decline_is_recorded_and_nothing_is_dispatched(self):
        core, cap, approver = build()
        req = decided(core, request("send_report"))
        approver.answer(req, verdict="declined", not_after=1)  # a bound "no" holds even when expired
        with self.assertRaises(ApprovalDeclined):
            core.execute(req.decision_id)
        self.assertEqual(cap.calls, [])
        self.assertEqual(actions(core)[-1], "declined")
        self.assertNotIn("outcome", [e["kind"] for e in core.ledger()])

    def test_expired_approval_is_refused_and_not_spent(self):
        core, cap, approver = build()
        req = decided(core, request("send_report"))
        approver.answer(req, not_after=NOW - 1)
        with self.assertRaisesRegex(ContractError, "used or expired"):
            core.execute(req.decision_id)
        self.assertEqual((cap.calls, approver.consumed), ([], []))

    def test_replayed_approval_is_refused_by_the_port(self):
        approver = MemoryApprover()
        first, first_cap, _ = build(approvals=approver)
        req = decided(first, request("send_report"))
        approver.answer(req)
        first.execute(req.decision_id)
        second, second_cap, _ = build(approvals=approver)  # same exact request and approval, presented again
        decided(second, request("send_report"))
        with self.assertRaisesRegex(ContractError, "refused to consume"):
            second.execute(req.decision_id)
        self.assertEqual((len(first_cap.calls), second_cap.calls), (1, []))

    def test_wrong_approver_cannot_answer(self):
        core, cap, approver = build()
        req = decided(core, request("send_report"))
        approver.answer(req, approver="some-agent")
        with self.assertRaisesRegex(ContractError, "approver"):
            core.execute(req.decision_id)
        self.assertEqual(cap.calls, [])


class TruthFaceFakeBudgetTests(unittest.TestCase):
    def test_unknown_estimate_is_refused_before_dispatch(self):
        core, cap, _ = build(costs=FixedCost(estimate=None), budget=CostBudget(AOR, 10, "usd_micros"))
        to_decide(core)
        with self.assertRaisesRegex(ContractError, "unknown or does not fit"):
            core.decide(request("reading"), precommit())
        refused = [e["data"] for e in core.ledger() if e["data"].get("action") == "budget_refused"]
        self.assertEqual([r["reason"] for r in refused], ["unknown_cost"])
        self.assertEqual(cap.calls, [])

    def test_known_estimate_settles_against_the_fake_budget(self):
        core, cap, _ = build(costs=FixedCost(estimate=4, actual=3), budget=CostBudget(AOR, 10, "usd_micros"))
        req = decided(core, request("reading"))
        core.execute(req.decision_id)
        self.assertEqual((core.budget(AOR)["spent"], core.budget(AOR)["held"], len(cap.calls)), (3, 0, 1))


if __name__ == "__main__":
    unittest.main()

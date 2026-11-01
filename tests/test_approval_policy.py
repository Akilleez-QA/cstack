"""ADR 003: deny wins, ask needs the host approver's exact, single-use, unexpired yes, and a decline is not output."""
import unittest

from adapters.memory_ledger import MemoryLedger
from poodo_core import (ApprovalDeclined, ApprovalPending, ApprovalRecord, AuthorityGrant, ContractError,
                        DomainDescriptor, CapabilityDescriptor, Phase, PhaseCheckpoint, PoodoCore)
from tests.helpers import FakeCapability, FakeExtension, goal, precommit, request, to_decide

APPROVER = "owner-via-approver"
CAP = CapabilityDescriptor("synthetic_sensor", "sensor-v1", ("reading", "send_report", "wipe"), lane="ToolFace")


class Extension(FakeExtension):
    def descriptor(self):
        return DomainDescriptor("synthetic_sensor", "1", (CAP,), "Finite JSON decimal fixture, not a Math field.")


class Capability(FakeCapability):
    def describe(self):
        return CAP


class Approvals:
    """Stands in for the durable host store: consume() succeeds once per approval across every core."""
    def __init__(self):
        self.records, self.consumed = {}, set()

    def lookup(self, decision_id):
        return self.records.get(decision_id)

    def consume(self, approval_id):
        if approval_id in self.consumed:
            return False
        self.consumed.add(approval_id)
        return True


ASK_GRANT = AuthorityGrant("aor", "synthetic_sensor", "synthetic_sensor", ("reading", "send_report"),
                           ("g",), 8, ask_operations=("send_report",), deny_operations=("wipe",), lane="ToolFace")


class Foundation(PoodoCore):
    def __init__(self, grants=None, approvals=None, now=1000, ledger=None):
        self.fake, self.approvals, self.now = Capability(), approvals or Approvals(), now
        super().__init__(Extension(), {"synthetic_sensor": self.fake}, grants or (ASK_GRANT,), ledger or MemoryLedger(),
                         approvals=self.approvals, approver=APPROVER, clock=lambda: self.now)


def approve(core, req, verdict="approved", **overrides):
    fields = dict(approval_id="a-" + req.decision_id, decision_id=req.decision_id, request_sha256=req.sha256,
                  goal_id=req.goal_id, goal_revision=req.goal_revision, approver=APPROVER, verdict=verdict,
                  not_after=2000)
    fields.update(overrides)
    core.approvals.records[req.decision_id] = ApprovalRecord(**fields)


def decided(core, req):
    to_decide(core)
    core.decide(req, precommit())
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
    return req


class ApprovalPolicyTests(unittest.TestCase):
    def test_allow_operations_need_no_approval(self):
        core = Foundation()
        req = decided(core, request("reading"))
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")

    def test_deny_wins_and_is_recorded(self):
        allow_wipe = AuthorityGrant("other", "synthetic_sensor", "synthetic_sensor", ("wipe",), ("g",), 8, lane="ToolFace")
        deny_wipe = AuthorityGrant("aor", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8,
                                   deny_operations=("wipe",), lane="ToolFace")
        core = Foundation(grants=(allow_wipe, deny_wipe))
        to_decide(core)
        with self.assertRaisesRegex(ContractError, "denied by host policy"):
            core.decide(request("wipe"), precommit())
        self.assertEqual(core.ledger()[-1]["data"]["action"], "denied")
        self.assertEqual(core.fake.calls, [])

    def test_ask_without_approval_dispatches_nothing(self):
        core = Foundation()
        req = decided(core, request("send_report"))
        with self.assertRaises(ApprovalPending):
            core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])
        self.assertEqual(core.ledger()[-1]["data"]["action"], "approval_pending")
        approve(core, req)
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        action = next(e for e in core.ledger() if e["kind"] == "action")
        self.assertEqual(action["data"]["approval_id"], "a-" + req.decision_id)

    def test_decline_consumes_the_decision_and_is_not_tool_output(self):
        core = Foundation()
        req = decided(core, request("send_report"))
        approve(core, req, verdict="declined")
        with self.assertRaises(ApprovalDeclined):
            core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])
        self.assertNotIn("outcome", [e["kind"] for e in core.ledger()])
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)

    def test_approval_must_bind_exact_request_revision_approver_and_time(self):
        cases = [dict(request_sha256="0" * 64), dict(goal_revision=2), dict(approver="coordinator"),
                 dict(decision_id="d-other"), dict(not_after=999)]
        for overrides in cases:
            core = Foundation()
            req = decided(core, request("send_report"))
            approve(core, req, **overrides)
            with self.assertRaises(ContractError, msg=str(overrides)):
                core.execute(req.decision_id)
            self.assertEqual(core.fake.calls, [], str(overrides))

    def test_an_approval_cannot_be_reused_for_another_decision(self):
        core = Foundation()
        first = decided(core, request("send_report", i=1))
        approve(core, first)
        core.execute(first.decision_id)
        core.advance("g", Phase.OBSERVE, PhaseCheckpoint("orchestrate", "Next loop"))
        core.advance("g", Phase.ORIENT, PhaseCheckpoint("observe", "Research", ("contracts/RESEARCH.md",)))
        core.advance("g", Phase.DECIDE, PhaseCheckpoint("orient", "IDs", option_ids=tuple(f"o-{i}" for i in range(20))))
        second = request("send_report", i=2)
        core.decide(second, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Second"))
        core.approvals.records[second.decision_id] = core.approvals.records[first.decision_id]
        with self.assertRaises(ContractError):
            core.execute(second.decision_id)
        self.assertEqual(len(core.fake.calls), 1)

    def test_ask_authority_requires_port_approver_and_clock(self):
        grant = AuthorityGrant("aor", "synthetic_sensor", "synthetic_sensor", ("send_report",), ("g",), 8,
                               ask_operations=("send_report",), lane="ToolFace")
        for kwargs in (dict(approver=APPROVER, clock=lambda: 1), dict(approvals=Approvals(), clock=lambda: 1),
                       dict(approvals=Approvals(), approver=APPROVER)):
            with self.assertRaises(ContractError):
                PoodoCore(Extension(), {"synthetic_sensor": Capability()}, (grant,), MemoryLedger(), **kwargs)

    def test_grant_scope_rules(self):
        with self.assertRaises(ContractError):
            AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, ask_operations=("wipe",), lane="ToolFace")
        with self.assertRaises(ContractError):
            AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("wipe",), ("g",), 8, deny_operations=("wipe",), lane="ToolFace")

    def test_port_returning_foreign_objects_is_refused(self):
        core = Foundation()
        req = decided(core, request("send_report"))
        core.approvals.records[req.decision_id] = {"verdict": "approved"}
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])


class ApprovalReviewFindingTests(unittest.TestCase):
    """Regression tests for the independent review of this change (B1, S1–S7, N1–N3)."""

    def test_b1_a_plain_grant_cannot_bypass_an_ask(self):
        plain = AuthorityGrant("plain", "synthetic_sensor", "synthetic_sensor", ("send_report",), ("g",), 8, lane="ToolFace")
        for grants in ((plain, ASK_GRANT), (ASK_GRANT, plain)):
            core = Foundation(grants=grants)
            req = decided(core, request("send_report"))
            with self.assertRaises(ApprovalPending):
                core.execute(req.decision_id)
            self.assertEqual(core.fake.calls, [])

    def test_s1_a_full_ledger_does_not_burn_the_approval(self):
        core = Foundation(ledger=MemoryLedger(max_events=7))
        req = decided(core, request("send_report"))
        approve(core, req)
        with self.assertRaisesRegex(ContractError, "budget"):
            core.execute(req.decision_id)
        self.assertEqual((core.fake.calls, core.approvals.consumed), ([], set()))

    def test_s2_s7_a_decline_is_recorded_before_consuming_and_honoured_when_expired(self):
        core = Foundation()
        req = decided(core, request("send_report"))
        approve(core, req, verdict="declined", not_after=1)
        with self.assertRaises(ApprovalDeclined):
            core.execute(req.decision_id)
        self.assertEqual(core.ledger()[-1]["data"]["action"], "declined")
        self.assertEqual(core.fake.calls, [])

    def test_s3_s4_pending_and_denied_are_recorded_once(self):
        core = Foundation()
        req = decided(core, request("send_report"))
        for _ in range(5):
            with self.assertRaises(ApprovalPending):
                core.execute(req.decision_id)
        self.assertEqual(sum(e["data"].get("action") == "approval_pending" for e in core.ledger()), 1)
        core = Foundation()
        to_decide(core)
        for _ in range(5):
            with self.assertRaises(ContractError):
                core.decide(request("wipe"), precommit())
        self.assertEqual(sum(e["data"].get("action") == "denied" for e in core.ledger()), 1)

    def test_s5_subclasses_cannot_shadow_core_state(self):
        with self.assertRaises(TypeError):
            type("Evil", (Foundation,), {"_needs_approval": property(lambda self: set())})

    def test_s6_one_approval_cannot_run_in_two_cores(self):
        shared, results = Approvals(), []
        for _ in range(2):
            core = Foundation(approvals=shared)
            req = decided(core, request("send_report"))
            approve(core, req)
            try:
                results.append(core.execute(req.decision_id).to_dict()["execution_status"])
            except ContractError:
                results.append("refused")
        self.assertEqual(results, ["completed", "refused"])

    def test_n1_n2_n3_clock_names_and_verdict_types(self):
        core = Foundation(now=1000.5)
        req = decided(core, request("send_report"))
        approve(core, req)
        with self.assertRaisesRegex(ContractError, "integer epoch"):
            core.execute(req.decision_id)
        typo = AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, deny_operations=("wiep",), lane="ToolFace")
        with self.assertRaises(ContractError):
            Foundation(grants=(typo,))
        verdict = type("Sneaky", (str,), {"__eq__": lambda self, other: True, "__hash__": str.__hash__})("x")
        with self.assertRaises(ContractError):
            ApprovalRecord("a", "d-1", "0" * 64, "g", 1, APPROVER, verdict, 2000)


if __name__ == "__main__":
    unittest.main()

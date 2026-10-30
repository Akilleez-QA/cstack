"""ADR 005 item 3: grants and capabilities carry a port lane; the core refuses a mismatch at decide and execute."""
import dataclasses
import unittest
from unittest.mock import patch

from adapters.memory_ledger import MemoryLedger
from poodo_core import (LANES, READ_ONLY_LANES, ApprovalDeclined, AuthorityGrant, CapabilityDescriptor,
                        CapabilityRequest, ContractError, DomainDescriptor, LivenessRecord, Phase, PhaseCheckpoint,
                        PoodoCore, outcome_for)
from tests.helpers import precommit, request, to_decide
from tests.test_budget_hard_stop import Budgeted, Costs
from tests.test_approval_policy import APPROVER, CAP, Approvals, Capability, Extension, approve

GRANT = AuthorityGrant("tool", "synthetic_sensor", "synthetic_sensor", ("reading", "send_report"), ("g",), 8,
                       ask_operations=("send_report",), lane="ToolFace")


class Drifting(Capability):
    """A bound port whose described lane can change after the core is built (a re-attached adapter)."""
    def __init__(self):
        super().__init__()
        self.lane, self.fail = "ToolFace", False

    def describe(self):
        if self.fail:
            raise RuntimeError("describe failed")
        return dataclasses.replace(CAP, lane=self.lane)


class Laned(PoodoCore):
    def __init__(self, grants=(GRANT,), capability=None, extension=None):
        self.fake, self.approvals = capability or Drifting(), Approvals()
        super().__init__(extension or Extension(), {"synthetic_sensor": self.fake}, grants, MemoryLedger(),
                         approvals=self.approvals, approver=APPROVER, clock=lambda: 1000)

    def refusals(self):
        return [e["data"] for e in self.ledger() if e["data"].get("action") == "lane_refused"]


def grant(lane, **kw):
    return AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, lane=lane, **kw)


def decided(core, req):
    to_decide(core)
    core.decide(req, precommit())
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
    return req


class GrantLaneTests(unittest.TestCase):
    def test_the_eight_lanes_are_exact_strings(self):
        self.assertEqual(LANES, ("HMIFace", "TruthFace", "RuntimeFace", "EvidenceFace", "SupervisorFace", "ToolFace",
                                 "ReadModelFace", "LearningFace"))
        self.assertEqual(READ_ONLY_LANES, ("ReadModelFace", "LearningFace"))

    def test_matching_lanes_pass(self):
        core = Laned()
        req = decided(core, request("reading"))
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        self.assertEqual(core.refusals(), [])

    def test_grant_and_descriptor_construction_validate_the_lane(self):
        with self.assertRaises(TypeError):  # required: an old grant without a lane does not construct
            AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8)
        with self.assertRaises(TypeError):
            CapabilityDescriptor("c", "1", ("op",))

        class Sneaky(str):
            def __eq__(self, other):
                return True
            __hash__ = str.__hash__
        for bad in ("toolface", "Tool", "", None, 1, Sneaky("ToolFace"), Sneaky("Anything")):
            with self.assertRaises(ContractError):
                grant(bad)
            with self.assertRaises(ContractError):
                CapabilityDescriptor("c", "1", ("op",), lane=bad)
        for lane in LANES:
            if lane not in READ_ONLY_LANES:
                self.assertEqual(grant(lane).lane, lane)

    def test_read_only_lanes_have_no_execute_path(self):
        for lane in READ_ONLY_LANES:
            with self.assertRaisesRegex(ContractError, "never name an operation for execute"):
                grant(lane)
            read_only = dataclasses.replace(CAP, lane=lane)

            class ReadOnlyExtension(Extension):
                def descriptor(self):
                    return DomainDescriptor("synthetic_sensor", "1", (read_only,), "Fixture.")
            cap = Drifting()
            cap.lane = lane
            with self.assertRaisesRegex(ContractError, "no execute path"):
                Laned(capability=cap, extension=ReadOnlyExtension())

    def test_core_refuses_a_grant_in_another_lane(self):
        with self.assertRaisesRegex(ContractError, "lane does not match"):
            Laned(grants=(grant("EvidenceFace"),))

    def test_mismatch_is_refused_at_decide_and_recorded_once(self):
        core = Laned()
        to_decide(core)
        core.fake.lane = "EvidenceFace"
        req = request("reading")
        for _ in range(3):
            with self.assertRaisesRegex(ContractError, "lane"):
                core.decide(req, precommit())
        [event] = core.refusals()
        self.assertEqual((event["request_sha256"], event["grant_lane"], event["capability_lane"], event["reason"]),
                         (req.sha256, "ToolFace", "ToolFace", "descriptor_drift"))
        self.assertFalse(any(e["data"].get("action") == "precommit" for e in core.ledger()))

    def test_mismatch_is_refused_at_execute_after_an_older_decide(self):
        core = Laned()
        req = decided(core, request("reading"))
        core.fake.lane = "RuntimeFace"
        for _ in range(2):
            with self.assertRaisesRegex(ContractError, "lane"):
                core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])
        self.assertEqual(len(core.refusals()), 1)
        self.assertFalse(any(e["kind"] == "action" for e in core.ledger()))
        core.fake.lane = "ToolFace"  # the decision was not consumed by the refusal
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")

    def test_execute_rechecks_the_current_grant_not_the_one_decide_saw(self):
        core = Laned()
        req = decided(core, request("reading"))
        # Simulates a host re-grant under the same id in another lane after the decision was made.
        core._grants = (dataclasses.replace(GRANT, lane="HMIFace"),)
        with self.assertRaisesRegex(ContractError, "lane"):
            core.execute(req.decision_id)
        self.assertEqual(core.refusals()[0]["reason"], "lane_mismatch")
        self.assertEqual(core.fake.calls, [])

    def test_a_port_that_drifts_to_a_read_only_lane_or_fails_describe_never_dispatches(self):
        core = Laned()
        req = decided(core, request("reading"))
        core.fake.lane = "ReadModelFace"
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        core.fake.lane, core.fake.fail = "ToolFace", True
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])
        self.assertEqual([e["reason"] for e in core.refusals()], ["read_only_lane"])  # once per exact request

    def test_refusal_records_are_bounded(self):
        core = Laned()
        to_decide(core)
        core.fake.lane = "TruthFace"
        with patch.object(PoodoCore, "MAX_NOTED", 2):
            for i in range(1, 6):
                with self.assertRaises(ContractError):
                    core.decide(request("reading", i=i), precommit())
        self.assertEqual(len(core.refusals()), 2)
        with self.assertRaises(TypeError):  # a subclass cannot lift the bound
            type("Unbounded", (Laned,), {"MAX_NOTED": 10**9})

    def test_lane_refusal_precedes_approval_so_nothing_is_spent_or_lost(self):
        core = Laned()
        req = decided(core, request("send_report"))
        approve(core, req)
        core.fake.lane = "SupervisorFace"
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual(core.approvals.consumed, set())
        self.assertFalse(any(e["data"].get("action") in ("approved", "approval_pending") for e in core.ledger()))
        core.fake.lane = "ToolFace"
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        declined = Laned()
        req = decided(declined, request("send_report"))
        approve(declined, req, verdict="declined")
        declined.fake.lane = "HMIFace"
        with self.assertRaises(ContractError):
            declined.execute(req.decision_id)
        declined.fake.lane = "ToolFace"  # the bound "no" still holds once the lane is right again
        with self.assertRaises(ApprovalDeclined):
            declined.execute(req.decision_id)
        self.assertEqual(declined.fake.calls, [])

    def test_a_lane_cannot_be_set_by_a_request_hook_or_tool_text(self):
        data = request("reading").to_dict()
        with self.assertRaises(ContractError):
            CapabilityRequest.from_dict({**data, "lane": "ToolFace"})
        with self.assertRaises(TypeError):
            type("Hook", (Laned,), {"_check_lane": lambda self, grant, req: None})
        with self.assertRaises(TypeError):
            type("Hook", (Laned,), {"_lanes_noted": set()})

        class Chatty(Drifting):
            def invoke(self, request, attempt_id, cancellation=None):
                self.calls.append(request.to_dict())
                return outcome_for(request, attempt_id, "completed", "sensor_returned", certainty="responded",
                                   raw_result={"lane": "ToolFace", "grant": {"lane": "ToolFace"}})
        core = Laned(capability=Chatty())
        to_decide(core)
        first = request("reading")
        smuggled = CapabilityRequest.from_dict({**request("reading", i=2).to_dict(), "arguments": {"lane": "ToolFace"}})
        for req in (first, smuggled):
            core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
        core.execute(first.decision_id)  # tool text claiming a lane is quarantined evidence, not authority
        core.fake.lane = "LearningFace"
        with self.assertRaises(ContractError):
            core.execute(smuggled.decision_id)
        self.assertEqual(len(core.fake.calls), 1)
        self.assertEqual(core.refusals()[0]["request_sha256"], smuggled.sha256)
        self.assertEqual(core.refusals()[0]["described_lane"], "LearningFace")
        ignored = Laned()  # a lane in the arguments neither blocks a matching call nor changes the grant
        req = decided(ignored, CapabilityRequest.from_dict({**request("reading").to_dict(),
                                                            "arguments": {"lane": "ReadModelFace"}}))
        self.assertEqual(ignored.execute(req.decision_id).to_dict()["execution_status"], "completed")

    def test_a_mutated_grant_lane_is_revalidated_at_the_check(self):
        class Targeted(str):
            def __eq__(self, other):
                return other == "ToolFace"
            __hash__ = str.__hash__
        core = Laned()
        req = decided(core, request("reading"))
        shared = core._grants[0]
        object.__setattr__(shared, "lane", Targeted("HMIFace"))  # in-memory tampering, not a supported path
        try:
            with self.assertRaises(ContractError):
                core.execute(req.decision_id)
        finally:
            object.__setattr__(shared, "lane", "ToolFace")
        self.assertEqual(core.fake.calls, [])
        self.assertEqual((core.refusals()[0]["grant_lane"], core.refusals()[0]["reason"]), (None, "lane_mismatch"))

    def test_describe_cannot_re_enter_the_core(self):
        core = Laned()
        req = decided(core, request("reading"))
        seen = []

        class Reentrant(Drifting):
            def describe(inner):
                if not seen:
                    seen.append(1)
                    with self.assertRaises(ContractError):
                        core.execute(req.decision_id)
                return super().describe()
        core.fake.__class__ = Reentrant
        core.execute(req.decision_id)
        self.assertEqual(len(core.fake.calls), 1)
        self.assertEqual(len([e for e in core.ledger() if e["kind"] == "action"]), 1)

    def test_a_lane_blocked_approval_wait_is_not_live(self):
        core = Laned()
        req = decided(core, request("send_report"))
        core.record_liveness(LivenessRecord("g", 1, APPROVER, "approval", "Waiting on the owner"))
        self.assertTrue(core.liveness("g")["live"])
        core.fake.lane = "EvidenceFace"
        with self.assertRaises(ContractError):
            core.execute(req.decision_id)
        self.assertEqual(core.liveness("g")["reason"], "approval_blocked_by_lane")

    def test_lane_refusal_holds_no_budget(self):
        costs = Costs()
        core = Budgeted(costs=costs, capability=Drifting())
        to_decide(core)
        core.fake.lane = "RuntimeFace"
        costs.estimate = lambda req: self.fail("priced a lane-refused call")
        with self.assertRaises(ContractError):
            core.decide(request("reading"), precommit())
        self.assertEqual(core.budget("coordinator")["held"], 0)
        self.assertFalse(any(e["data"].get("action") == "budget_refused" for e in core.ledger()))

if __name__ == "__main__":
    unittest.main()

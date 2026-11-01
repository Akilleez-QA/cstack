"""ADR 005 decision 3: the test-only composition root for the replaceability test.

It mirrors bootstrap.py, but each lane's production adapter is swapped for an in-memory fake. The core under test is
the unmodified PoodoCore. Nothing here is imported by production code, and bootstrap.py stays the only production
composition root.

Fake ids are stable: contracts/ADAPTERS.json rows name them in their `fake` field (ADR 005 item 1).
"""
from adapters.memory_ledger import MemoryLedger
from poodo_core import (ApprovalRecord, DomainDescriptor, PoodoCore,
                        outcome_for)
from tests.helpers import FakeCapability, FakeExtension, make_capability, make_grant

APPROVER = "owner-via-approver"
NOW = 1000
CAP = make_capability("synthetic_sensor", "sensor-v1", ("reading", "send_report"))
AOR = "aor-replaceability"


class Extension(FakeExtension):
    def descriptor(self):
        return DomainDescriptor("synthetic_sensor", "1", (CAP,), "Finite JSON decimal fixture, not a Math field.")


class MemoryApprover:
    """fake.approver.memory: an ApprovalPort plus the host-side writer, replacing the Scheduled channel and the SQLite
    approval store. consume() is True once per approval id across every core that shares this instance."""
    fake_id = "fake.approver.memory"

    def __init__(self):
        self.records, self.consumed = {}, []

    def record(self, approval: ApprovalRecord):
        """Host side only: what the owner's answer through the approval channel would write. Requests never reach this."""
        if type(approval) is not ApprovalRecord or approval.decision_id in self.records:
            raise ValueError("The writer stores one host ApprovalRecord per decision")
        self.records[approval.decision_id] = approval

    def answer(self, request, verdict="approved", not_after=NOW + 600, approver=APPROVER):
        self.record(ApprovalRecord("a-" + request.decision_id, request.decision_id, request.sha256, request.goal_id,
                                   request.goal_revision, approver, verdict, not_after))

    def lookup(self, decision_id):
        return self.records.get(decision_id)

    def consume(self, approval_id):
        if approval_id in self.consumed:
            return False
        self.consumed.append(approval_id)
        return True


class FixedCost:
    """fake.cost.fixed: a CostPort with a fixed estimate and actual. None means the price is unknown."""
    fake_id = "fake.cost.fixed"

    def __init__(self, estimate=1, actual=1):
        self._estimate, self._actual = estimate, actual

    def estimate(self, request):
        return self._estimate

    def actual(self, request, attempt_id, outcome):
        return self._actual


class ScriptedCapability(FakeCapability):
    """fake.capability.scripted: a CapabilityPort replacing the Foundation stdio bridges. Each call plays the next
    scripted step: completed, tool_error, protocol_error, timeout, crash or cancel_after_dispatch."""
    fake_id = "fake.capability.scripted"

    def __init__(self, *script):
        super().__init__()
        self.script = list(script)

    def describe(self):
        return CAP

    def invoke(self, request, attempt_id, cancellation=None):
        step = self.script.pop(0) if self.script else "completed"
        if step == "completed":
            return super().invoke(request, attempt_id, cancellation)
        self.calls.append(request.to_dict())
        if step == "tool_error":
            return outcome_for(request, attempt_id, "tool_error", "tool_reported_error", certainty="responded",
                               raw_result={"error": "reading out of range"})
        if step == "protocol_error":
            return outcome_for(request, attempt_id, "protocol_error", "malformed_frame", certainty="responded")
        if step == "timeout":
            return outcome_for(request, attempt_id, "timed_out", "deadline_after_dispatch", certainty="unknown")
        if step == "cancel_after_dispatch":
            return outcome_for(request, attempt_id, "cancelled", "cancelled_after_dispatch", certainty="unknown")
        if step == "crash":
            raise RuntimeError("bridge process died mid-call")
        raise AssertionError("unknown script step " + step)


FAKES = {cls.fake_id: cls for cls in (MemoryApprover, FixedCost, ScriptedCapability)}

# The named replaceability suites. ADR 005 items 2c (EvidenceFace) and 2d (HMIFace) add their lanes here.
LANE_SUITES = {
    "TruthFace": {"port": "ApprovalPort", "fakes": ("fake.approver.memory", "fake.cost.fixed"),
                  "tests": ("tests.replaceability.test_truthface",)},
    "ToolFace": {"port": "CapabilityPort", "fakes": ("fake.capability.scripted",),
                 "tests": ("tests.replaceability.test_toolface",)},
}


def build(*, capability=None, approvals=None, costs=None, ask=("send_report",), budget=None, max_calls=8):
    """Mirror of bootstrap.build_*: host-chosen fakes, one grant, a MemoryLedger and a fixed host clock."""
    capability = capability or ScriptedCapability()
    approvals = approvals or MemoryApprover()
    grant = make_grant("replaceability-grant", "synthetic_sensor", "synthetic_sensor", CAP.operations, ("g",),
                       max_calls, ask_operations=tuple(ask), aor_id=AOR if budget else None)
    core = PoodoCore(Extension(), {"synthetic_sensor": capability}, (grant,), MemoryLedger(),
                     approvals=approvals, approver=APPROVER, clock=lambda: NOW,
                     budgets=(budget,) if budget else (), costs=costs)
    return core, capability, approvals

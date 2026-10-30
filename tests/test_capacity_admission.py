"""ADR 005 item 5a: a SupervisorFace admission port. Host capacity per AOR, consulted at start_goal, decide (asks)
and execute; refusals are recorded once, bounded, and hold no spend and spend no approval."""
import unittest
from unittest.mock import patch

from adapters.memory_ledger import MemoryLedger
from poodo_core import (AuthorityGrant, CapacityLimits, CapacityRefused, ContractError, CostBudget, Phase,
                        PhaseCheckpoint, PoodoCore, ReentryRefused)
from tests.helpers import goal, precommit, request, to_decide
from tests.test_approval_policy import APPROVER, Approvals, Capability, Extension, approve
from tests.test_budget_hard_stop import GRANT, Costs

AOR = "coordinator"


def limits(**overrides):
    fields = dict(aor_id=AOR, max_open_goals=4, max_live_attempts=2, max_pending_asks=2, live_cap=2)
    fields.update(overrides)
    return CapacityLimits(**fields)


class Port:
    """Host capacity fixture: one record per AOR, replaceable mid-test."""
    def __init__(self, **overrides):
        self.answers = {AOR: limits(**overrides)}

    def set(self, **overrides):
        self.answers[AOR] = limits(**overrides)

    def capacity(self, aor_id):
        return self.answers.get(aor_id)


class Drifting(Capability):
    lane = "ToolFace"

    def describe(self):
        from tests.test_approval_policy import CAP
        return CAP if self.lane == "ToolFace" else type(CAP)(CAP.capability_id, CAP.contract_version,
                                                             CAP.operations, lane=self.lane)


class Admitted(PoodoCore):
    def __init__(self, port=None, grants=None, costs=None, ledger=None, aors=(AOR,)):
        self.fake, self.approvals, self.now, self.port = Drifting(), Approvals(), 1000, port or Port()
        super().__init__(Extension(), {"synthetic_sensor": self.fake}, grants or (GRANT,), ledger or MemoryLedger(),
                         approvals=self.approvals, approver=APPROVER, clock=lambda: self.now,
                         budgets=tuple(CostBudget(a, 10_000, "usd_micros") for a in aors), costs=costs or Costs(),
                         admission=self.port)

    def refusals(self):
        return [e["data"] for e in self.ledger() if e["data"].get("action") == "capacity_refused"]


def decided(core, *reqs):
    to_decide(core)
    for req in reqs:
        core.decide(req, precommit())
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
    return reqs


def back_to_decide(core, start=Phase.ORCHESTRATE):
    steps = {Phase.ORCHESTRATE: (Phase.OBSERVE, PhaseCheckpoint("orchestrate", "Next loop")),
             Phase.PONTIFICATE: (Phase.OBSERVE, PhaseCheckpoint("pontificate", "Revised"))}
    core.advance("g", *steps[start])
    core.advance("g", Phase.ORIENT, PhaseCheckpoint("observe", "Research", ("contracts/RESEARCH.md",)))
    core.advance("g", Phase.DECIDE, PhaseCheckpoint("orient", "IDs", option_ids=tuple(f"o-{n}" for n in range(20))))


class CapacityLimitTests(unittest.TestCase):
    def test_open_goal_limit_counts_this_core_and_the_host(self):
        core = Admitted(Port(max_open_goals=1))
        core.start_goal(goal())
        with self.assertRaises(CapacityRefused):
            core.start_goal(goal(goal_id="h"))
        self.assertEqual({k: core.refusals()[0][k] for k in ("gate", "goal_id", "reason", "limit", "in_use")},
                         {"gate": "start_goal", "goal_id": "h", "reason": "open_goals", "limit": 1, "in_use": 1})
        other = Admitted(Port(max_open_goals=2, other_open_goals=2))
        with self.assertRaises(CapacityRefused):
            other.start_goal(goal())
        other.port.set(max_open_goals=3, other_open_goals=2)
        other.start_goal(goal())

    def test_a_goal_two_aors_cover_needs_room_in_both(self):
        second = AuthorityGrant("second", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8,
                                aor_id="reference-agent", lane="ToolFace")
        port = Port()
        port.answers["reference-agent"] = limits(aor_id="reference-agent", max_open_goals=0)
        core = Admitted(port, grants=(GRANT, second), aors=(AOR, "reference-agent"))
        with self.assertRaises(CapacityRefused):
            core.start_goal(goal())
        self.assertEqual(core.refusals()[0]["aor_id"], "reference-agent")
        core.start_goal(goal(goal_id="h"))  # only the first AOR's grant lists h

    def test_a_goal_no_aor_covers_is_refused(self):
        core = Admitted()
        with self.assertRaises(CapacityRefused):
            core.start_goal(goal(goal_id="unlisted"))
        self.assertEqual(core.refusals()[0]["reason"], "no_aor")

    def test_live_attempt_limit_refuses_before_dispatch_and_keeps_the_decision(self):
        core = Admitted(Port(other_live_attempts=2))
        (req,) = decided(core, request())
        with self.assertRaises(CapacityRefused):
            core.execute(req.decision_id)
        self.assertEqual((core.fake.calls, core.budget(AOR)["held"]), ([], 0))
        self.assertEqual(core.refusals()[0]["reason"], "live_attempts")
        core.port.set(other_live_attempts=1)
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")

    def test_an_attempt_is_live_from_dispatch_until_settled(self):
        core = Admitted()
        seen = []
        core.fake.invoke = lambda r, a, c=None: (seen.append(core._live[AOR]), Capability.invoke(core.fake, r, a, c))[1]
        (req,) = decided(core, request())
        core.execute(req.decision_id)
        self.assertEqual((seen, core._live[AOR]), ([1], 0))

    def test_approval_queue_limit_applies_only_to_asks(self):
        core = Admitted(Port(max_pending_asks=1))
        to_decide(core)
        first = request("send_report", i=1)
        core.decide(first, precommit())
        with self.assertRaises(CapacityRefused):
            core.decide(request("send_report", i=2), precommit())
        self.assertEqual(core.refusals()[0]["reason"], "approval_queue")
        core.decide(request("reading", i=3), precommit())  # not an ask: the queue does not apply
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        approve(core, first)
        core.execute(first.decision_id)  # the queue drains
        back_to_decide(core)
        core.decide(request("send_report", i=2), precommit())
        core.port.set(max_pending_asks=2, other_pending_asks=1)
        with self.assertRaises(CapacityRefused):
            core.decide(request("send_report", i=4), precommit())

    def test_stale_or_exhausted_asks_leave_the_queue(self):
        core = Admitted(Port(max_pending_asks=1))
        to_decide(core)
        core.decide(request("send_report", i=1), precommit())
        core.revise_goal(goal(revision=2))
        back_to_decide(core, Phase.PONTIFICATE)
        core.decide(request("send_report", i=2, revision=2), precommit())  # the revision-1 ask no longer counts
        one = AuthorityGrant("one", "synthetic_sensor", "synthetic_sensor", ("reading", "send_report"), ("g",), 1,
                             ask_operations=("send_report",), aor_id=AOR, lane="ToolFace")
        more = AuthorityGrant("more", "synthetic_sensor", "synthetic_sensor", ("send_report",), ("g",), 8,
                              ask_operations=("send_report",), aor_id=AOR, lane="ToolFace")
        exhausted = Admitted(Port(max_pending_asks=1), grants=(one, more))
        to_decide(exhausted)
        exhausted.decide(request("send_report", i=1), precommit())
        exhausted.decide(request("reading", i=2), precommit())
        exhausted.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        exhausted.execute("d-2")  # uses the grant's only call: d-1 can never execute
        back_to_decide(exhausted)
        exhausted.decide(request("send_report", i=3), precommit())  # d-1 no longer holds the only slot
        self.assertEqual((exhausted.refusals(), exhausted._decisions["d-3"].grant_id), ([], "more"))

    def test_an_outcome_that_fails_to_record_stays_live(self):
        class Failing(MemoryLedger):
            def append(self, kind, data):
                if kind == "outcome":
                    raise OSError("disk full")
                return super().append(kind, data)
        core = Admitted(Port(max_live_attempts=1, live_cap=1), ledger=Failing())
        first, second = decided(core, request(i=1), request(i=2))
        with self.assertRaises(OSError):
            core.execute(first.decision_id)
        with self.assertRaises(CapacityRefused):
            core.execute(second.decision_id)
        self.assertEqual(core.refusals()[0]["in_use"], 1)

    def test_a_zero_cap_pauses_start_and_execute(self):
        core = Admitted()
        (req,) = decided(core, request())
        core.port.set(live_cap=0)
        with self.assertRaises(CapacityRefused):
            core.start_goal(goal(goal_id="h"))
        with self.assertRaises(CapacityRefused):
            core.execute(req.decision_id)
        self.assertEqual([r["reason"] for r in core.refusals()], ["paused", "paused"])
        self.assertEqual(core.fake.calls, [])
        core.port.set(live_cap=1)
        core.start_goal(goal(goal_id="h"))
        core.execute(req.decision_id)

    def test_soonest_reset_at_is_recorded_only_when_supplied(self):
        core = Admitted(Port(live_cap=0, soonest_reset_at=1_800_000_000))
        with self.assertRaises(CapacityRefused) as caught:
            core.start_goal(goal())
        self.assertEqual((caught.exception.soonest_reset_at, core.refusals()[0]["soonest_reset_at"]),
                         (1_800_000_000, 1_800_000_000))
        plain = Admitted(Port(live_cap=0))
        with self.assertRaises(CapacityRefused):
            plain.start_goal(goal())
        self.assertNotIn("soonest_reset_at", plain.refusals()[0])


class OrderingTests(unittest.TestCase):
    def test_deny_precedes_capacity(self):
        allow = AuthorityGrant("allow", "synthetic_sensor", "synthetic_sensor", ("wipe",), ("g",), 8,
                               ask_operations=("wipe",), aor_id=AOR, lane="ToolFace")
        deny = AuthorityGrant("deny", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8,
                              deny_operations=("wipe",), aor_id=AOR, lane="ToolFace")
        core = Admitted(Port(max_pending_asks=0), grants=(allow, deny))
        to_decide(core)
        with self.assertRaisesRegex(ContractError, "denied"):
            core.decide(request("wipe"), precommit())
        self.assertEqual(core.refusals(), [])

    def test_lane_precedes_capacity(self):
        core = Admitted(Port(max_pending_asks=0))
        to_decide(core)
        core.fake.lane = "HMIFace"
        with self.assertRaisesRegex(ContractError, "lane"):
            core.decide(request("send_report"), precommit())
        self.assertEqual(core.refusals(), [])
        core = Admitted()
        (req,) = decided(core, request())
        core.port.set(live_cap=0)
        core.fake.lane = "HMIFace"
        with self.assertRaisesRegex(ContractError, "lane"):
            core.execute(req.decision_id)
        self.assertEqual(core.refusals(), [])

    def test_capacity_precedes_budget_and_approval_so_nothing_is_spent(self):
        core = Admitted(costs=Costs(estimate={"reading": None, "send_report": 40}))
        to_decide(core)
        core.port.set(max_pending_asks=0)
        with self.assertRaises(CapacityRefused):  # an unknown price would refuse too, but capacity comes first
            core.decide(request("send_report"), precommit())
        core.port.set()
        req = request("send_report")
        core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        approve(core, req)
        core.port.set(live_cap=0)
        with self.assertRaises(CapacityRefused):
            core.execute(req.decision_id)
        self.assertEqual((core.approvals.consumed, core.budget(AOR)["held"], core.budget(AOR)["spent"]), (set(), 0, 0))
        self.assertFalse(any(e["data"].get("action") in ("approved", "approval_pending", "budget_refused")
                             for e in core.ledger()))
        core.port.set()
        self.assertEqual(core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        self.assertEqual(core.approvals.consumed, {"a-" + req.decision_id})


class RecordingTests(unittest.TestCase):
    def test_refusal_is_recorded_once_per_exact_request(self):
        core = Admitted()
        (req,) = decided(core, request())
        core.port.set(live_cap=0)
        for _ in range(3):
            with self.assertRaises(CapacityRefused):
                core.execute(req.decision_id)
        self.assertEqual(len(core.refusals()), 1)

    def test_refusal_records_are_bounded(self):
        core = Admitted(Port(live_cap=0))
        with patch.object(PoodoCore, "MAX_NOTED", 2):
            for i in range(5):
                with self.assertRaises(CapacityRefused):
                    core.start_goal(goal(goal_id="g", revision=i + 1))
        self.assertEqual(len(core.refusals()), 2)
        with self.assertRaises(TypeError):  # a subclass cannot replace the check or its state
            type("Hook", (Admitted,), {"_check_capacity": lambda self, *a: None})
        with self.assertRaises(TypeError):
            type("Hook", (Admitted,), {"_capacity_port": None})


class FailClosedTests(unittest.TestCase):
    def test_missing_or_invalid_limits_refuse_startup(self):
        class Raising(Port):
            def capacity(self, aor_id):
                raise RuntimeError("supervisor down")
        wrong = Port()
        wrong.answers[AOR] = limits(aor_id="other-aor")
        tampered = Port()
        object.__setattr__(tampered.answers[AOR], "live_cap", -1)
        dict_port = Port()
        dict_port.answers[AOR] = vars(limits())
        empty = Port()
        empty.answers.clear()
        for port in (empty, wrong, tampered, dict_port, Raising()):
            with self.assertRaisesRegex(ContractError, "capacity limits", msg=type(port).__name__):
                Admitted(port)
        plain = AuthorityGrant("plain", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, lane="ToolFace")
        with self.assertRaises(ContractError):
            Admitted(grants=(GRANT, plain))  # a grant with no AOR cannot bypass admission
        for bad in (dict(live_cap=3), dict(max_open_goals=-1), dict(max_pending_asks=True), dict(soonest_reset_at=0)):
            with self.assertRaises(ContractError, msg=repr(bad)):
                limits(**bad)

    def test_a_port_that_raises_or_answers_unknown_refuses_the_call(self):
        core = Admitted()
        (req,) = decided(core, request())
        for answer in (RuntimeError("down"), None, "yes", limits(aor_id="other-aor")):
            def capacity(aor_id, answer=answer):
                if isinstance(answer, Exception):
                    raise answer
                return answer
            core.port.capacity = capacity
            with self.assertRaises(CapacityRefused):
                core.execute(req.decision_id)
        self.assertEqual([r["reason"] for r in core.refusals()], ["unknown_capacity"])
        self.assertEqual(core.fake.calls, [])

    def test_a_port_that_re_enters_the_core_is_refused(self):
        attempts = []

        class Reentrant(Port):
            core = None

            def capacity(self, aor_id):
                if self.core is not None:
                    try:
                        self.core.start_goal(goal(goal_id="h"))
                    except ReentryRefused as error:
                        attempts.append(error)
                        raise
                return super().capacity(aor_id)
        port = Reentrant()
        core = Admitted(port)
        to_decide(core)
        port.core = core
        with self.assertRaises(CapacityRefused):
            core.start_goal(goal(goal_id="h"))
        self.assertEqual((len(attempts), "h" in core._goals), (1, False))

        class AtStartup(Port):
            def capacity(self, aor_id):  # swallows the refusal and answers validly, so only the guard stops it
                try:
                    holder.start_goal(goal())
                except ReentryRefused as error:
                    attempts.append(error)
                return super().capacity(aor_id)
        holder = Admitted.__new__(Admitted)
        holder.__init__(AtStartup())
        self.assertEqual((len(attempts), "g" in holder._goals, holder.ledger()), (2, False, []))

    def test_admission_that_admits_ledgers_exactly_like_a_core_without_it(self):
        from tests.test_budget_hard_stop import Budgeted, run
        plain, admitted = Budgeted(limit=10_000), Admitted()
        for core in (plain, admitted):
            run(core, "reading", i=1)
            run(core, "send_report", i=2, approved=True)
        self.assertEqual(plain.ledger(), admitted.ledger())
        self.assertEqual(admitted._live, {AOR: 0})


if __name__ == "__main__":
    unittest.main()

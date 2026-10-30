"""Same-call-stack host/port mutations are refused; nested reads remain available to the single caller."""
import threading
import typing
import unittest

from adapters.memory_ledger import MemoryLedger
from poodo_core import (ApprovalRecord, AuthorityGrant, ContractError, CostBudget, LivenessRecord, Phase,
                        PhaseCheckpoint, PoodoCore, ReentryRefused)
from tests.helpers import goal, precommit, request, to_decide
from tests.test_approval_policy import APPROVER, Approvals, Capability, Extension

MUTATORS = ("start_goal", "revise_goal", "advance", "decide", "execute", "record_liveness", "lift_budget_pause")
HOOKS = ("admit_goal", "validate_call", "interpret", "describe", "invoke", "is_set", "lookup", "consume",
         "estimate", "actual", "clock", "reserve", "append", "read")


class Trap:
    """Every host-supplied callback fires here. An armed hook runs its action once and records what happened."""
    def __init__(self):
        self.armed, self.results = {}, []

    def fire(self, hook):
        action = self.armed.pop(hook, None)
        if action is not None:
            try:
                action()
                self.results.append((hook, None))
            except ContractError as error:
                self.results.append((hook, error))


class Hooked:
    """Wraps a host object so that each of its methods fires the trap before running."""
    def __init__(self, inner, trap):
        self.inner, self.trap = inner, trap

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        return (lambda *a, **k: (self.trap.fire(name), attr(*a, **k))[1]) if callable(attr) else attr


class RacyApprovals(Approvals):
    """Check, then call out, then mark: a durable store that notifies a listener before it commits."""
    def lookup(self, decision_id):
        self.trap.fire("lookup")
        return super().lookup(decision_id)

    def consume(self, approval_id):
        if approval_id in self.consumed:
            return False
        self.trap.fire("consume")
        self.consumed.add(approval_id)
        return True


class Costs:
    def __init__(self, price):
        self.price = price

    def estimate(self, request):
        return self.price

    def actual(self, request, attempt_id, outcome):
        return self.price


def interrupt():
    raise KeyboardInterrupt


class Cancel:
    def is_set(self):
        return False


class Trapped(PoodoCore):
    def __init__(self, limit=1000, price=40, max_calls=16):
        self.trap = trap = Trap()
        self.fake, self.approvals, self.raw = Capability(), RacyApprovals(), MemoryLedger()
        self.approvals.trap = trap
        grant = AuthorityGrant("trap", "synthetic_sensor", "synthetic_sensor", ("reading", "send_report"), ("g", "h"),
                               max_calls, ask_operations=("send_report",), aor_id="aor", lane="ToolFace")
        super().__init__(Hooked(Extension(), trap), {"synthetic_sensor": Hooked(self.fake, trap)}, (grant,),
                         Hooked(self.raw, trap), approvals=self.approvals, approver=APPROVER,
                         clock=lambda: (trap.fire("clock"), 1000)[1], budgets=(CostBudget("aor", limit, "usd_micros"),),
                         costs=Hooked(Costs(price), trap))

    def events(self, action=None, kind=None):
        return [e for e in (x.read() for x in self.raw._events)
                if (action is None or e["data"].get("action") == action) and (kind is None or e["kind"] == kind)]


def approve(core, req):
    core.approvals.records[req.decision_id] = ApprovalRecord("a-" + req.decision_id, req.decision_id, req.sha256,
        req.goal_id, req.goal_revision, APPROVER, "approved", 2000)


def ready(core, *reqs):
    """Decide each request in one Decide phase, approve the asks, then move to Orchestrate."""
    to_decide(core)
    for req in reqs:
        core.decide(req, precommit())
        if req.operation == "send_report":
            approve(core, req)
    core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))


def call(core, mutator):
    """One well-formed call to each public mutator, so the only reason to refuse it is re-entry."""
    return {"start_goal": lambda: core.start_goal(goal(goal_id="h")),
            "revise_goal": lambda: core.revise_goal(goal(revision=2)),
            "advance": lambda: core.advance("g", Phase.OBSERVE, PhaseCheckpoint("orchestrate", "Next loop")),
            "decide": lambda: core.decide(request("reading", i=9), precommit()),
            "execute": lambda: core.execute("d-1"),
            "record_liveness": lambda: core.record_liveness(LivenessRecord("g", 1, "host", "agent", "Next step")),
            "lift_budget_pause": lambda: core.lift_budget_pause("aor", 5000)}[mutator]


def observe(core):
    return (len(core.raw._events), dict(core._goals), set(core._consumed), dict(core._spent), dict(core._held),
            dict(core._budget_limits), dict(core._liveness), dict(core._grant_uses), set(core._used_approvals))


class HarmfulReentryTests(unittest.TestCase):
    """Each harm here happened before the core-wide guard: the nested call succeeded."""

    def assert_refused(self, core, hook):
        self.assertEqual([h for h, _ in core.trap.results], [hook])
        self.assertIsInstance(core.trap.results[0][1], ReentryRefused)

    def test_no_hook_can_dispatch_a_decision_twice(self):
        for hook, max_calls in (("validate_call", 16), ("estimate", 1), ("reserve", 16)):
            with self.subTest(hook=hook):
                core = Trapped(max_calls=max_calls)
                ready(core, request("reading"))
                core.trap.armed[hook] = lambda: core.execute("d-1")
                core.execute("d-1")
                self.assertEqual((len(core.fake.calls), len(core.events(kind="action"))), (1, 1))
                self.assertEqual(core.budget("aor")["spent"], 40)
                self.assert_refused(core, hook)

    def test_an_approval_is_not_consumed_twice(self):
        core = Trapped()
        ready(core, request("send_report"))
        core.trap.armed["consume"] = lambda: core.execute("d-1")
        core.execute("d-1")
        self.assertEqual((len(core.events("approved")), len(core.fake.calls)), (1, 1))
        self.assert_refused(core, "consume")

    def test_approval_hooks_cannot_overspend_the_budget(self):
        for hook in ("lookup", "clock"):
            with self.subTest(hook=hook):
                core = Trapped(limit=100, price=60)
                ready(core, request("send_report", i=1), request("reading", i=2))
                core.trap.armed[hook] = lambda: core.execute("d-2")
                core.execute("d-1")
                self.assertEqual(core.budget("aor")["spent"], 60)
                with self.assertRaises(ContractError):  # the second call does not fit, as it never did
                    core.execute("d-2")
                self.assert_refused(core, hook)

    def test_validate_call_cannot_move_the_phase_under_a_decision(self):
        core = Trapped()
        to_decide(core)
        core.trap.armed["validate_call"] = lambda: core.advance("g", Phase.ORCHESTRATE,
                                                                PhaseCheckpoint("decide", "Sneaked"))
        core.decide(request("reading"), precommit())
        self.assertEqual(core.snapshot("g").phase, Phase.DECIDE)
        self.assertEqual(core.events(kind="decision")[-1]["data"]["action"], "precommit")
        self.assert_refused(core, "validate_call")

    def test_admit_goal_cannot_duplicate_a_start_or_revision_or_pass_the_cap(self):
        core = Trapped()
        core.trap.armed["admit_goal"] = lambda: core.start_goal(goal())
        core.start_goal(goal())
        core.trap.armed["admit_goal"] = lambda: core.revise_goal(goal(revision=2))
        core.revise_goal(goal(revision=2))
        self.assertEqual((len(core.events("start_goal")), len(core.events("revise_goal"))), (1, 1))
        for n in range(core.MAX_GOALS - 2):
            core.start_goal(goal(goal_id="pre-" + str(n)))
        core.trap.armed["admit_goal"] = lambda: core.start_goal(goal(goal_id="sneaked"))
        core.start_goal(goal(goal_id="last"))
        self.assertEqual(len(core._goals), core.MAX_GOALS)
        self.assertTrue(all(isinstance(e, ReentryRefused) for _, e in core.trap.results))

    def test_ledger_append_cannot_interleave_liveness_or_budget_lifts(self):
        core = Trapped(limit=100)
        core.start_goal(goal())
        core.trap.armed["append"] = lambda: core.record_liveness(LivenessRecord("g", 1, "a", "agent", "First"))
        core.record_liveness(LivenessRecord("g", 1, "b", "agent", "Second"))
        self.assertEqual([e["data"]["prior"] for e in core.events("liveness_set")], [None])
        core.trap.armed["append"] = lambda: core.lift_budget_pause("aor", 150)
        core.lift_budget_pause("aor", 200)
        self.assertEqual([e["data"]["prior_limit"] for e in core.events("budget_pause_lifted")], [100])
        self.assertTrue(all(isinstance(e, ReentryRefused) for _, e in core.trap.results))


class GuardCoverageTests(unittest.TestCase):
    def test_every_mutator_is_refused_from_every_hook_and_changes_nothing(self):
        for hook in HOOKS:
            for mutator in MUTATORS:
                with self.subTest(hook=hook, mutator=mutator):
                    core = Trapped()
                    ready(core, request("reading"), request("send_report", i=2))
                    state = []
                    after = []

                    def nested_mutation():
                        state.append(observe(core))
                        try:
                            call(core, mutator)()
                        finally:
                            after.append(observe(core))
                    core.trap.armed[hook] = nested_mutation
                    if hook == "admit_goal":
                        core.start_goal(goal(goal_id="h"))
                    elif hook == "read":
                        core.ledger()
                    else:
                        core.execute("d-2", Hooked(Cancel(), core.trap))
                    self.assertEqual(len(core.trap.results), 1, "hook never fired")
                    self.assertIsInstance(core.trap.results[0][1], ReentryRefused)
                    self.assertIn(mutator, str(core.trap.results[0][1]))
                    self.assertEqual(len(state), 1)  # the nested call raised before it could return
                    self.assertEqual(after, state, "refused same-thread mutation changed core state")

    def test_reads_may_reenter_during_an_operation(self):
        core = Trapped()
        ready(core, request("reading"))
        seen = {}
        core.trap.armed["interpret"] = lambda: seen.update(
            phase=core.snapshot("g").phase, held=core.budget("aor")["held"], ledger=len(core.ledger()),
            liveness=core.liveness("g")["reason"], open=len(core.goals_without_live_path()))
        core.execute("d-1")
        self.assertEqual(core.trap.results, [("interpret", None)])
        self.assertEqual((seen["phase"], seen["held"], seen["liveness"]), (Phase.ORCHESTRATE, 40, "no_next_action_owner"))

    def test_a_read_cannot_host_a_mutation(self):
        core = Trapped()
        core.start_goal(goal())
        core.record_liveness(LivenessRecord("g", 1, "host", "agent", "Review soon", review_by=2000))
        core.trap.armed["clock"] = lambda: core.revise_goal(goal(revision=2))
        self.assertTrue(core.liveness("g")["live"])
        core.trap.armed["read"] = lambda: core.advance("g", Phase.OBSERVE, PhaseCheckpoint("pontificate", "x"))
        core.ledger()
        self.assertEqual([type(e) for _, e in core.trap.results], [ReentryRefused, ReentryRefused])
        self.assertEqual((core.snapshot("g").contract.revision, core.snapshot("g").phase), (1, Phase.PONTIFICATE))

    def test_another_thread_is_refused_while_an_operation_runs(self):
        # Legacy implementation observation outside the single-caller contract.
        # Hosts must serialise calls; this test does not establish cross-thread safety.
        core = Trapped()
        ready(core, request("reading"))
        errors = []

        def other():
            try:
                core.start_goal(goal(goal_id="h"))
            except ContractError as error:
                errors.append(error)
        core.trap.armed["invoke"] = lambda: (lambda t: (t.start(), t.join()))(threading.Thread(target=other))
        core.execute("d-1")
        self.assertIsInstance(errors[0], ReentryRefused)
        self.assertNotIn("h", core._goals)

    def test_construction_cannot_be_reentered_or_rerun(self):
        trap, cores = Trap(), []

        class Building(PoodoCore):
            def __init__(self):
                cores.append(self)
                trap.armed["describe"] = lambda: (PoodoCore.__init__(self, Extension(), {}, (), MemoryLedger()))
                super().__init__(Extension(), {"synthetic_sensor": Hooked(Capability(), trap)}, (AuthorityGrant(
                    "x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 4, lane="ToolFace"),),
                    MemoryLedger())
        core = Building()
        self.assertIsInstance(trap.results[0][1], ReentryRefused)  # nested __init__ during construction
        trap.armed["describe"] = lambda: cores[-1].start_goal(goal())
        core = Building()
        self.assertIsInstance(trap.results[1][1], ReentryRefused)  # any operation during construction
        self.assertEqual(core.ledger(), [])
        with self.assertRaises(ReentryRefused):  # re-running __init__ would mint a fresh guard and reset state
            PoodoCore.__init__(core, Extension(), {}, (), MemoryLedger())

    def test_subclasses_and_bases_cannot_shadow_the_guard(self):
        for name in ("_busy", "_guard", "_interrupted", "__setattr__", "__getattribute__", "__getattr__", "__delattr__"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                type("Shadow", (PoodoCore,), {name: None})
        mixin = type("Mixin", (), {"execute": lambda self, d, c=None: None, "_consumed": property(lambda s: set())})
        for bases in ((mixin, PoodoCore), (PoodoCore, mixin)):  # before or after PoodoCore in the MRO
            with self.subTest(bases=bases), self.assertRaises(TypeError):
                type("Mixed", bases, {})

        class GenericCore(PoodoCore, typing.Generic[typing.TypeVar("T")]):  # a later base may define its own hooks
            pass

        class FakeDict(Trapped):  # a class-level __dict__ cannot hand the guard a bottomless token
            __dict__ = property(lambda self: {"_guard": type("Always", (list,), {"pop": lambda s: True})()})
        core = FakeDict()
        ready(core, request("reading"))
        core.trap.armed["invoke"] = lambda: core.start_goal(goal(goal_id="h"))
        core.execute("d-1")
        self.assertIsInstance(core.trap.results[0][1], ReentryRefused)


class PostCommitFailureTests(unittest.TestCase):
    """Once the action is recorded, a failing or re-entering callback still leaves an outcome and a settled hold."""

    def test_a_failing_cancellation_dispatches_nothing_and_releases_the_hold(self):
        core = Trapped()
        ready(core, request("reading"))
        core.trap.armed["is_set"] = lambda: 1 / 0
        outcome = core.execute("d-1", Hooked(Cancel(), core.trap))  # before the fix, ZeroDivisionError escaped here
        self.assertEqual(outcome.to_dict()["execution_status"], "cancelled")
        self.assertEqual((len(core.fake.calls), core.budget("aor")["held"], core.budget("aor")["spent"]), (0, 0, 0))

    def test_an_interrupt_is_reraised_only_after_the_outcome_and_settlement(self):
        for hook in ("invoke", "interpret", "actual"):
            with self.subTest(hook=hook):
                core = Trapped()
                ready(core, request("reading"))
                core.trap.armed[hook] = interrupt
                with self.assertRaises(KeyboardInterrupt):
                    core.execute("d-1")
                self.assertEqual([e["kind"] for e in core.events()][-2:], ["outcome", "observation"])
                self.assertEqual((core.budget("aor")["held"], core.budget("aor")["spent"]), (0, 40))
                self.assertEqual((core._guard, core._busy, core._interrupted), ([True], None, None))
                core.start_goal(goal(goal_id="h"))  # the guard is free again

    def test_an_interrupt_before_commit_propagates_and_records_nothing(self):
        core = Trapped()
        to_decide(core)
        before = len(core.raw._events)
        core.trap.armed["estimate"] = interrupt
        with self.assertRaises(KeyboardInterrupt):
            core.decide(request("reading"), precommit())
        self.assertEqual((len(core.raw._events), core._budget_noted, core._interrupted), (before, set(), None))


if __name__ == "__main__":
    unittest.main()

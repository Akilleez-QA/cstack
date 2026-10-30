"""PR 9: per-AOR cost budgets. Reserve, then settle; pause at the limit; unknown cost is never free."""
import unittest

from adapters.memory_ledger import MemoryLedger
from poodo_core import (AuthorityGrant, BudgetPaused, ContractError, CostBudget, Phase, PhaseCheckpoint, PoodoCore,
                        outcome_for)
from tests.helpers import goal, precommit, request, to_decide
from tests.test_approval_policy import APPROVER, Approvals, Capability, Extension, approve

GRANT = AuthorityGrant("aor-grant", "synthetic_sensor", "synthetic_sensor", ("reading", "send_report"), ("g", "h"),
                       16, ask_operations=("send_report",), aor_id="chief-of-staff", lane="ToolFace")


class Costs:
    """Host pricing fixture: estimate and actual per operation; a missing entry is an unknown price."""
    def __init__(self, estimate=None, actual=None):
        self.estimates = {"reading": 40, "send_report": 40} if estimate is None else estimate
        self.actuals = dict(self.estimates) if actual is None else actual

    def estimate(self, request):
        return self.estimates.get(request.operation)

    def actual(self, request, attempt_id, outcome):
        return self.actuals.get(request.operation)


class Budgeted(PoodoCore):
    def __init__(self, costs=None, limit=100, grants=None, ledger=None, capability=None):
        self.fake, self.approvals, self.now, self.costs = capability or Capability(), Approvals(), 1000, costs or Costs()
        super().__init__(Extension(), {"synthetic_sensor": self.fake}, grants or (GRANT,), ledger or MemoryLedger(),
                         approvals=self.approvals, approver=APPROVER, clock=lambda: self.now,
                         budgets=(CostBudget("chief-of-staff", limit, "usd_micros"),), costs=self.costs)


def run(core, operation="reading", i=1, goal_id="g", approved=False):
    """Decide one request in a fresh loop and execute it."""
    try:
        phase = core.snapshot(goal_id).phase
    except ContractError:
        to_decide(core, goal_id)
        phase = Phase.DECIDE
    if phase != Phase.DECIDE:
        core.advance(goal_id, Phase.OBSERVE, PhaseCheckpoint("orchestrate", "Next loop"))
        core.advance(goal_id, Phase.ORIENT, PhaseCheckpoint("observe", "Research", ("contracts/RESEARCH.md",)))
        core.advance(goal_id, Phase.DECIDE, PhaseCheckpoint("orient", "IDs", option_ids=tuple(f"o-{n}" for n in range(20))))
    req = request(operation, i=i, goal_id=goal_id)
    core.decide(req, precommit())
    core.advance(goal_id, Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
    if approved:
        approve(core, req)
    return req, core.execute(req.decision_id)


def actions(core, name):
    return [e["data"] for e in core.ledger() if e["data"].get("action") == name]


class BudgetHardStopTests(unittest.TestCase):
    def test_reserve_then_settle_records_the_actual_charge(self):
        core = Budgeted(Costs(actual={"reading": 25}))
        run(core)
        action = next(e["data"] for e in core.ledger() if e["kind"] == "action")
        self.assertEqual((action["aor_id"], action["cost_reserved"]), ("chief-of-staff", 40))
        self.assertEqual(actions(core, "budget_settled")[0]["charged"], 25)
        self.assertEqual(core.budget("chief-of-staff"), {"aor_id": "chief-of-staff", "unit": "usd_micros",
                         "limit": 100, "spent": 25, "held": 0, "paused": False})

    def test_reaching_the_limit_pauses_decisions_and_executions_until_the_host_lifts_it(self):
        core = Budgeted(Costs(actual={"reading": 60}))
        run(core, i=1)
        run(core, i=2)
        self.assertTrue(core.budget("chief-of-staff")["paused"])
        self.assertEqual(len(actions(core, "budget_paused")), 1)
        core.advance("g", Phase.OBSERVE, PhaseCheckpoint("orchestrate", "Next loop"))
        core.advance("g", Phase.ORIENT, PhaseCheckpoint("observe", "Research", ("contracts/RESEARCH.md",)))
        core.advance("g", Phase.DECIDE, PhaseCheckpoint("orient", "IDs", option_ids=tuple(f"o-{n}" for n in range(20))))
        with self.assertRaises(BudgetPaused):
            core.decide(request(i=3), precommit())
        with self.assertRaises(ContractError):
            core.lift_budget_pause("chief-of-staff", 120)  # not above committed spend
        core.lift_budget_pause("chief-of-staff", 400)
        core.decide(request(i=3), precommit())
        self.assertEqual(actions(core, "budget_pause_lifted")[0]["limit"], 400)

    def test_a_pause_blocks_an_already_decided_execution(self):
        core = Budgeted(Costs(actual={"reading": 100}))
        to_decide(core)
        first, second = request(i=1), request(i=2)
        core.decide(first, precommit())
        core.decide(second, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Two calls"))
        core.execute(first.decision_id)
        with self.assertRaises(BudgetPaused):
            core.execute(second.decision_id)
        self.assertEqual(len(core.fake.calls), 1)

    def test_an_unknown_estimate_is_unaffordable_and_recorded_once(self):
        for bad in (None, -1, 1.5, True, "0", 10**16):
            core = Budgeted(Costs(estimate={"reading": bad}))
            to_decide(core)
            for _ in range(3):
                with self.assertRaises(ContractError, msg=repr(bad)):
                    core.decide(request(), precommit())
            self.assertEqual([e["reason"] for e in actions(core, "budget_refused")], ["unknown_cost"], repr(bad))
            self.assertEqual(core.fake.calls, [])

    def test_a_failing_cost_port_is_unknown_not_free(self):
        class Broken(Costs):
            def estimate(self, request):
                raise RuntimeError("pricing service down")
        core = Budgeted(Broken())
        to_decide(core)
        with self.assertRaises(ContractError):
            core.decide(request(), precommit())

    def test_an_unknown_actual_keeps_the_whole_hold(self):
        class Timeout(Capability):
            def invoke(self, request, attempt_id, cancellation=None):
                return outcome_for(request, attempt_id, "timed_out", "deadline", certainty="unknown")
        core = Budgeted(Costs(actual={}), capability=Timeout())
        run(core)
        settled = actions(core, "budget_settled")[0]
        self.assertEqual((settled["charged"], settled["priced"]), (40, False))
        self.assertEqual(core.budget("chief-of-staff")["spent"], 40)

    def test_a_call_cancelled_before_dispatch_releases_its_hold(self):
        core = Budgeted()
        to_decide(core)
        req = request()
        core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        core.execute(req.decision_id, cancellation=type("Set", (), {"is_set": lambda self: True})())
        self.assertEqual((core.budget("chief-of-staff")["spent"], core.fake.calls), (0, []))

    def test_an_estimate_that_does_not_fit_is_refused_without_dispatch(self):
        core = Budgeted(Costs(estimate={"reading": 101}))
        to_decide(core)
        with self.assertRaises(ContractError):
            core.decide(request(), precommit())
        self.assertEqual(actions(core, "budget_refused")[0]["reason"], "over_limit")


class BudgetBypassTests(unittest.TestCase):
    def test_a_plain_grant_cannot_sit_beside_a_budgeted_one(self):
        plain = AuthorityGrant("plain", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, lane="ToolFace")
        for grants in ((plain, GRANT), (GRANT, plain)):
            with self.assertRaises(ContractError):
                Budgeted(grants=grants)

    def test_budgeted_authority_needs_a_cost_port_and_a_budget_for_its_aor(self):
        other = AuthorityGrant("x", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 8, aor_id="someone-else", lane="ToolFace")
        with self.assertRaises(ContractError):
            Budgeted(grants=(other,))
        with self.assertRaises(ContractError):
            PoodoCore(Extension(), {"synthetic_sensor": Capability()}, (other,), MemoryLedger())
        with self.assertRaises(ContractError):
            PoodoCore(Extension(), {"synthetic_sensor": Capability()}, (other,), MemoryLedger(),
                      budgets=(CostBudget("someone-else", 10, "usd_micros"),))
        with self.assertRaises(ContractError):
            PoodoCore(Extension(), {"synthetic_sensor": Capability()}, (other,), MemoryLedger(), costs=Costs(),
                      budgets=({"aor_id": "someone-else", "limit": 10, "unit": "usd_micros"},))

    def test_a_new_goal_or_revision_does_not_lift_a_pause(self):
        core = Budgeted(Costs(actual={"reading": 100}))
        run(core)
        core.revise_goal(goal(revision=2))
        to_decide(core, "h")
        with self.assertRaises(BudgetPaused):
            core.decide(request(goal_id="h", i=2), precommit())
        self.assertEqual(len(core.fake.calls), 1)

    def test_a_paused_aor_does_not_spend_an_approval(self):
        core = Budgeted(Costs(actual={"reading": 100}))
        to_decide(core)
        reading, report = request("reading", i=1), request("send_report", i=2)
        core.decide(reading, precommit())
        core.decide(report, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Two calls"))
        core.execute(reading.decision_id)
        approve(core, report)
        with self.assertRaises(BudgetPaused):
            core.execute(report.decision_id)
        self.assertEqual(core.approvals.consumed, set())

    def test_a_full_ledger_refuses_before_holding_or_dispatching(self):
        core = Budgeted(ledger=MemoryLedger(max_events=8))
        to_decide(core)
        req = request()
        core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        with self.assertRaisesRegex(ContractError, "budget"):
            core.execute(req.decision_id)
        self.assertEqual((core.fake.calls, core.budget("chief-of-staff")["held"]), ([], 0))

    def test_lifts_must_raise_and_core_state_cannot_be_shadowed(self):
        core = Budgeted()
        for bad in (100, 50, 1.5e3, True, 10**16):
            with self.assertRaises(ContractError, msg=repr(bad)):
                core.lift_budget_pause("chief-of-staff", bad)
        with self.assertRaises(ContractError):
            core.lift_budget_pause("unknown-aor", 500)
        for name in ("_paused", "_spent", "_budget_limits", "lift_budget_pause", "_check_budget", "_settle"):
            with self.assertRaises(TypeError, msg=name):
                type("Evil", (Budgeted,), {name: {}})
        for bad in (dict(limit=0), dict(limit=True), dict(unit="has space")):
            with self.assertRaises(ContractError, msg=str(bad)):
                CostBudget(**{"aor_id": "a", "limit": 10, "unit": "usd_micros", **bad})

    def test_unbudgeted_cores_behave_as_before(self):
        from tests.helpers import FakeFoundation, execute_one
        core = FakeFoundation()
        execute_one(core)
        action = next(e["data"] for e in core.ledger() if e["kind"] == "action")
        self.assertNotIn("cost_reserved", action)
        self.assertEqual([e["kind"] for e in core.ledger()][-2:], ["action", "outcome"])


if __name__ == "__main__":
    unittest.main()

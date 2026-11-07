"""Review findings on PR 525: grant scope across sessions, settlement after a kill, and what replay restores.

Predictions: tests/crash_predictions/poodo_core.md
"""
from dataclasses import replace
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from adapters.aor_registry import load_fleet
from adapters.aor_session import AorSession
from poodo_core import CapabilityRequest, ContractError
from poodo_core.policy import AuthorityGrant, BudgetPaused, CostBudget
from tests.aor_fixtures import HAVE_CRYPTO, write_fleet, write_witnessed_config
from tests.helpers import FakeExtension, execute_one, PoodoCore, precommit, request, to_decide
from tests.test_core_crash import EffectCapability, JsonlLedger, build

ROOT = Path(__file__).resolve().parents[1]
KILL_CHILD = """
import os, signal, sys
sys.path.insert(0, ".")
from tests.test_core_crash import build, drive, JsonlLedger
from adapters.witnessed_ledger import WitnessedLedger
root, kind, kill_at, action = sys.argv[1:5]
for cls in (JsonlLedger, WitnessedLedger):
    def append(self, event_kind, data, _original=cls.append):
        if action and data.get("action") == action:
            os.kill(os.getpid(), signal.SIGKILL)
        return _original(self, event_kind, data)
    cls.append = append
core, ledger = build(root, kind, kill_at=kill_at or None, budgeted=True)
drive(core)
"""


class Priced:
    def __init__(self, estimate=7, actual=5):
        self.estimate_value, self.actual_value = estimate, actual

    def estimate(self, req):
        return self.estimate_value

    def actual(self, req, attempt_id, outcome):
        return None if outcome.to_dict()["execution_certainty"] == "unknown" else self.actual_value


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def effects(self):
        path = self.root / "effects.txt"
        return path.read_text().split() if path.exists() else []

    def kill(self, kind, kill_at, action):
        if kind.startswith("witnessed") and not (self.root / "ledger.json").exists():
            write_witnessed_config(self.root, node="box")
        done = subprocess.run([sys.executable, "-B", "-c", KILL_CHILD, str(self.root), kind, kill_at, action], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, -signal.SIGKILL, done.stderr)

    def counted(self, ledger, action):
        return sum(e["data"].get("action") == action for e in ledger.read())


class GrantScopeAcrossSessions(Case):
    def core(self, goals, max_calls=1):
        grant = AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), goals, max_calls,
                               lane="ToolFace")
        return PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)}, (grant,),
                         JsonlLedger(self.root / "ledger.jsonl"))

    def test_uses_under_another_sessions_goals_do_not_count(self):
        execute_one(self.core(("s1-g",)), request(i=1, goal_id="s1-g"))
        fresh = self.core(("s2-g",))
        self.assertEqual(fresh._grant_uses["fake-grant"], 0)
        execute_one(fresh, request(i=2, goal_id="s2-g"))
        self.assertEqual(len(self.effects()), 2)

    def test_the_same_session_limit_still_holds_after_a_restart(self):
        execute_one(self.core(("s1-g",)), request(i=1, goal_id="s1-g"))
        again = self.core(("s1-g",))
        self.assertEqual(again._grant_uses["fake-grant"], 1)
        to_decide(again, "s1-g")
        with self.assertRaisesRegex(ContractError, "No remaining scoped authority"):
            again.decide(request(i=2, goal_id="s1-g"), precommit())
        self.assertEqual(len(self.effects()), 1)

    def test_a_recovered_attempt_counts_once_across_repeated_restarts(self):
        self.kill("jsonl", "after_effect", "")
        for _ in range(3):
            core, _ledger = build(self.root, "jsonl", budgeted=True)
            self.assertEqual(core._grant_uses["fake-grant"], 1)

    def test_a_recovered_session_gets_exactly_the_calls_it_has_left(self):
        self.kill("jsonl", "after_effect", "")
        core = self.core(("g", "h"), max_calls=2)
        execute_one(core, request(i=2))
        self.assertEqual(core._grant_uses["fake-grant"], 2)
        to_decide(core, "h")
        with self.assertRaisesRegex(ContractError, "No remaining scoped authority"):
            core.decide(request(i=3, goal_id="h"), precommit())

    def session(self):
        def make_core(domain, grants, anchors):
            ledger = JsonlLedger(self.root / "ledger.jsonl")
            core = PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)},
                             (replace(grants[0], max_calls=1),), ledger)
            return core, ledger, None
        session = AorSession(fleet=load_fleet(write_fleet(self.root)), bot_slug="alpha", hostname="testbox",
                             state_dir=self.root / "state", domains={"synthetic_sensor": (("reading",), "read")},
                             make_core=make_core, ledger_label="jsonl", shields_file=self.root / "SHIELDS_UP")
        self.addCleanup(session.close)
        return session

    def run_call(self, session):
        domain = "synthetic_sensor"
        goal_id = session.start_goal(domain, "Read the sensor.", ["A scoped tool observation."])["contract"]["goal_id"]
        session.advance(domain, goal_id, "observe", "Fixture checkpoint.")
        session.advance(domain, goal_id, "orient", "Fixture checkpoint.", research_references=["contracts/RESEARCH.md"])
        session.advance(domain, goal_id, "decide", "Fixture checkpoint.",
                        option_ids=[f"option-{i}" for i in range(20)])
        decision = session.decide(domain, goal_id, "reading", {}, "Declared synthetic return",
                                  "One supplied request only", "No accepted scoped observation")
        session.advance(domain, goal_id, "orchestrate", "Run it.")
        return session.execute(domain, decision["decision_id"])["status"]

    def test_a_new_aor_session_over_a_used_ledger_is_not_refused(self):
        first = self.session()
        self.assertEqual(self.run_call(first), "executed")
        with self.assertRaisesRegex(ContractError, "No remaining scoped authority"):
            self.run_call(first)
        first.close()
        second = self.session()
        self.assertEqual(self.run_call(second), "executed")
        self.assertEqual(len(self.effects()), 2)


class SettlementAfterKill(Case):
    def test_kill_between_outcome_and_settlement_charges_the_price_on_restart(self):
        self.kill("jsonl", "", "budget_settled")
        core, ledger = build(self.root, "jsonl", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 5)
        self.assertEqual(core.budget("aor-a")["held"], 0)
        self.assertEqual(self.counted(ledger, "budget_settled"), 1)
        self.assertEqual(sum(e["kind"] == "outcome" for e in ledger.read()), 1)
        self.assertEqual(core.unresolved_attempts(), ())
        self.assertEqual(len(self.effects()), 1)

    def test_kill_during_recovery_between_outcome_and_settlement_keeps_the_whole_hold(self):
        self.kill("jsonl", "after_effect", "")
        self.kill("jsonl", "", "budget_settled")
        core, ledger = build(self.root, "jsonl", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 7)
        self.assertEqual(self.counted(ledger, "budget_settled"), 1)
        outcomes = [e["data"]["outcome"]["execution_certainty"] for e in ledger.read() if e["kind"] == "outcome"]
        self.assertEqual(outcomes, ["unknown"])

    def test_settling_on_restart_is_not_repeated_by_the_next_restart(self):
        self.kill("jsonl", "", "budget_settled")
        build(self.root, "jsonl", budgeted=True)
        core, ledger = build(self.root, "jsonl", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 5)
        self.assertEqual(self.counted(ledger, "budget_settled"), 1)

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_witnessed_kill_between_outcome_and_settlement(self):
        self.kill("witnessed", "", "budget_settled")
        core, ledger = build(self.root, "witnessed", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 5)
        self.assertEqual(self.counted(ledger, "budget_settled"), 1)
        ledger.close()

    def test_kill_between_settlement_and_pause_pauses_on_restart(self):
        ledger = JsonlLedger(self.root / "ledger.jsonl")
        first = self.pausing(ledger)
        original = JsonlLedger.append
        calls = []

        def stop_before_pause(this, kind, data):
            if data.get("action") == "budget_paused":
                calls.append(data)
                raise KeyboardInterrupt
            return original(this, kind, data)
        JsonlLedger.append = stop_before_pause
        try:
            with self.assertRaises(KeyboardInterrupt):
                execute_one(first, request(i=1))
        finally:
            JsonlLedger.append = original
        self.assertEqual(len(calls), 1)
        ledger = JsonlLedger(self.root / "ledger.jsonl")
        core = self.pausing(ledger)
        self.assertTrue(core.budget("aor-a")["paused"])
        self.assertEqual(self.counted(ledger, "budget_paused"), 1)

    def pausing(self, ledger, limit=7):
        grant = AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g", "h"), 8,
                               lane="ToolFace", aor_id="aor-a")
        return PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)}, (grant,), ledger,
                         budgets=(CostBudget("aor-a", limit, "usd_cents"),), costs=Priced(7, 7))


class ReplayRestores(Case):
    def core(self, limit=7):
        grant = AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g", "h"), 8,
                               lane="ToolFace", aor_id="aor-a")
        ledger = JsonlLedger(self.root / "ledger.jsonl")
        return PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)}, (grant,), ledger,
                         budgets=(CostBudget("aor-a", limit, "usd_cents"),), costs=Priced(7, 7)), ledger

    def test_a_prior_decision_id_with_a_new_request_id_is_refused(self):
        first, _ = self.core(limit=70)
        to_decide(first)
        first.decide(request(i=1), precommit())
        core, _ = self.core(limit=70)
        to_decide(core)
        reused = request(i=2).to_dict()
        reused["decision_id"] = "d-1"
        with self.assertRaisesRegex(ContractError, "must be new"):
            core.decide(CapabilityRequest.from_dict(reused), precommit())

    def test_a_prior_request_id_with_a_new_decision_id_is_refused(self):
        first, _ = self.core(limit=70)
        to_decide(first)
        first.decide(request(i=1), precommit())
        core, _ = self.core(limit=70)
        to_decide(core)
        reused = request(i=2).to_dict()
        reused["request_id"] = "r-1"
        with self.assertRaisesRegex(ContractError, "must be new"):
            core.decide(CapabilityRequest.from_dict(reused), precommit())

    def test_a_recorded_pause_comes_back_without_a_new_event(self):
        first, _ = self.core()
        execute_one(first, request(i=1))
        self.assertTrue(first.budget("aor-a")["paused"])
        core, ledger = self.core()
        self.assertTrue(core.budget("aor-a")["paused"])
        self.assertEqual(self.counted(ledger, "budget_paused"), 1)
        to_decide(core)
        with self.assertRaises(BudgetPaused):
            core.decide(request(i=2), precommit())

    def test_a_recorded_pause_outlasts_a_raised_host_limit(self):
        first, _ = self.core()
        execute_one(first, request(i=1))
        core, ledger = self.core(limit=70)
        self.assertTrue(core.budget("aor-a")["paused"])
        self.assertEqual(self.counted(ledger, "budget_paused"), 1)

    def test_a_recorded_lift_comes_back_with_its_limit_and_clears_the_pause(self):
        first, _ = self.core()
        execute_one(first, request(i=1))
        first.lift_budget_pause("aor-a", 20)
        core, ledger = self.core()
        state = core.budget("aor-a")
        self.assertEqual((state["limit"], state["paused"], state["spent"]), (20, False, 7))
        self.assertEqual(self.counted(ledger, "budget_paused"), 1)
        self.assertEqual(execute_one(core, request(i=2, goal_id="h")).to_dict()["execution_status"], "completed")

    def test_a_host_limit_above_the_recorded_lift_is_kept(self):
        first, _ = self.core()
        execute_one(first, request(i=1))
        first.lift_budget_pause("aor-a", 20)
        core, _ = self.core(limit=50)
        self.assertEqual(core.budget("aor-a")["limit"], 50)


if __name__ == "__main__":
    unittest.main()

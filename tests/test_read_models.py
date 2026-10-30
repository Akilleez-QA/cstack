"""ADR 005 items 8a and 8b: read models are pure projections over ledger events and can never write."""
import ast
import json
from pathlib import Path
import unittest

from adapters.memory_ledger import MemoryLedger
from adapters.read_models import NAMES, project
from poodo_core import ApprovalDeclined, ApprovalPending, LivenessRecord, Phase, PhaseCheckpoint
from tests.helpers import FakeCapability, FakeFoundation, execute_one, goal, precommit, request, to_decide
from tests.test_approval_policy import APPROVER, approve
from tests.test_budget_hard_stop import Budgeted, run

ROOT = Path(__file__).resolve().parents[1]


def live(goal_id, waiting_on="agent", owner="chief-of-staff", revision=1, **kw):
    return LivenessRecord(goal_id, revision, owner, waiting_on, "Fixture next action", **kw)


def views(read, now=1000, **kw):
    return project(read, source_id="memory:test", clock=lambda: now, approver=APPROVER, **kw)


def renumber(events):
    return [{**e, "sequence": i} if type(e) is dict else e for i, e in enumerate(events, 1)]


class LiveWithoutPathParityTests(unittest.TestCase):
    def test_the_projection_matches_goals_without_live_path_on_a_fixture_core(self):
        core = Budgeted()
        to_decide(core, "g")
        ask = request("send_report", i=1)
        core.decide(ask, precommit())
        core.record_liveness(live("g", "approval", APPROVER))
        core.start_goal(goal(goal_id="h"))
        core.start_goal(goal(goal_id="k"))
        core.record_liveness(live("k", "external", "vendor-support", review_by=1500))
        core.start_goal(goal(goal_id="m"))
        core.record_liveness(live("m"))
        core.revise_goal(goal(goal_id="m", revision=2))
        core.start_goal(goal(goal_id="n"))
        core.record_liveness(live("n", "approval", "some-agent"))
        core.start_goal(goal(goal_id="p"))
        core.record_liveness(live("p", "approval", APPROVER))

        def check(now):
            core.now = now
            view = views(core.ledger, now)["goals_without_live_path"]
            self.assertEqual(view.rows, core.goals_without_live_path())
            self.assertEqual(view.confidence.level, "complete")
            return {r["goal_id"]: r["reason"] for r in view.rows}

        self.assertEqual(check(1000), {"h": "no_next_action_owner", "m": "liveness_names_stale_revision",
                                       "n": "approval_wait_names_wrong_owner", "p": "no_pending_approval"})
        self.assertEqual(check(1501)["k"], "wait_expired")
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Fixture action"))
        approve(core, ask)
        core.execute(ask.decision_id)
        self.assertEqual(check(1501)["g"], "no_pending_approval")


class ClosureRateTests(unittest.TestCase):
    def test_only_completed_responded_outcomes_on_the_current_revision_back_a_goal(self):
        core = FakeFoundation()
        execute_one(core)
        core.start_goal(goal(goal_id="h"))
        view = views(core.ledger)["evidence_backed_closure_rate"]
        self.assertEqual((view.summary["evidence_backed"], view.summary["goals"], view.summary["rate"]), (1, 2, 0.5))
        self.assertIn("not closure", view.summary["definition"])
        core.revise_goal(goal(revision=2))
        self.assertEqual(views(core.ledger)["evidence_backed_closure_rate"].summary["evidence_backed"], 0)

    def test_an_indeterminate_outcome_is_not_evidence(self):
        class Boom(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                raise RuntimeError("crashed after dispatch")
        core = FakeFoundation(Boom())
        execute_one(core)
        row = views(core.ledger)["evidence_backed_closure_rate"].rows[0]
        self.assertEqual((row["backing_outcomes"], row["evidence_backed"]), (0, False))
        self.assertIsNone(views(MemoryLedger().read)["evidence_backed_closure_rate"].summary["rate"])


class FounderRepairTests(unittest.TestCase):
    def test_lifts_and_approvals_after_a_decline_are_counted_and_nothing_else(self):
        core = Budgeted(limit=40)
        run(core)
        core.lift_budget_pause("chief-of-staff", 200)
        for i, verdict in ((2, "declined"), (3, "approved")):
            req = request("send_report", i=i)
            with self.assertRaises(ApprovalPending):
                run(core, "send_report", i=i)
            approve(core, req, verdict)
            if verdict == "declined":
                with self.assertRaises(ApprovalDeclined):
                    core.execute(req.decision_id)
            else:
                core.execute(req.decision_id)
        view = views(core.ledger)["founder_manual_repairs"]
        self.assertEqual(view.summary["by_kind"], {"budget_pause_lifted": 1, "approved_after_decline": 1,
                                                   "correction": 0})
        self.assertEqual([r["detail"] for r in view.rows], ["chief-of-staff", "d-3"])

    def test_a_first_approval_or_a_revision_is_not_a_repair(self):
        core = Budgeted()
        run(core, "send_report", approved=True)
        core.revise_goal(goal(revision=2))
        events = core.ledger() + [{"sequence": len(core.ledger()) + 1, "kind": "correction",
                                   "data": {"action": "amend_observation", "corrects_sequence": 3}}]
        view = views(lambda: events)["founder_manual_repairs"]
        self.assertEqual((view.summary["total"], view.rows[0]["repair"]), (1, "correction"))


class ConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.core = FakeFoundation()
        execute_one(self.core)
        self.events = self.core.ledger()

    def test_unknown_and_malformed_events_are_counted_never_fatal(self):
        events = renumber(self.events + [{"kind": "telemetry", "data": {"x": 1}},
                                         {"kind": "learning", "data": {"action": "promote"}},
                                         {"kind": "decision", "data": {"action": "admission_refused"}},
                                         "junk", {"kind": "outcome", "data": {"outcome": {}}}])
        result = views(lambda: events)
        for name in NAMES:
            conf = result[name].confidence
            self.assertEqual((conf.level, conf.counts["unknown"], conf.counts["malformed"]), ("partial", 3, 2))
        self.assertEqual(result["evidence_backed_closure_rate"].summary["evidence_backed"], 1)

    def test_a_window_gap_or_replay_is_partial(self):
        for events, needle in ((self.events[2:], "window starts at sequence 3"),
                               (self.events[:3] + self.events[4:], "1 sequence gaps"),
                               (self.events + self.events[-1:], "1 replayed events")):
            conf = views(lambda: events)["goals_without_live_path"].confidence
            self.assertEqual(conf.level, "partial")
            self.assertIn(needle, conf.reason)

    def test_an_old_or_undated_source_is_stale(self):
        self.assertEqual(views(self.core.ledger, 2000, written_at=1990, max_age=60)
                         ["founder_manual_repairs"].confidence.level, "complete")
        old = views(self.core.ledger, 2000, written_at=1000, max_age=60)["founder_manual_repairs"]
        self.assertEqual(old.confidence.level, "stale")
        self.assertIn("1000s before as_of", old.confidence.reason)
        self.assertEqual(views(self.core.ledger, max_age=60)["founder_manual_repairs"].confidence.level, "stale")

    def test_every_projection_cites_its_source_range_and_as_of(self):
        view = views(self.core.ledger, 1234)["goals_without_live_path"].to_dict()
        self.assertEqual((view["as_of"], view["source"]["ledger"], view["source"]["first_sequence"],
                          view["source"]["last_sequence"]), (1234, "memory:test", 1, len(self.events)))
        self.assertEqual(view["source"]["head_event_sha256"], self.events[-1]["event_sha256"])


class WriteImpossibilityTests(unittest.TestCase):
    WRITES = {"append", "reserve", "consume", "record", "write", "write_text", "write_bytes", "open", "execute",
              "decide", "advance", "start_goal", "revise_goal", "record_liveness", "lift_budget_pause", "__self__"}

    def test_the_module_imports_no_adapter_and_calls_no_write(self):
        tree = ast.parse((ROOT / "adapters/read_models.py").read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imported, {"dataclasses", "json"})
        touched = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        touched |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertEqual(touched & self.WRITES, set())

    def test_a_ledger_object_is_refused_and_the_source_is_unchanged(self):
        ledger = MemoryLedger()
        core = FakeFoundation(ledger=ledger)
        execute_one(core)
        for bad in (ledger, core, type("Writable", (), {"__call__": lambda s: [], "append": None})()):
            with self.assertRaises(TypeError):
                views(bad)
        before = json.dumps(ledger.read(), sort_keys=True)
        result = views(ledger.read)
        result["evidence_backed_closure_rate"].rows[0]["evidence_backed"] = "tampered"
        self.assertEqual(json.dumps(ledger.read(), sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()

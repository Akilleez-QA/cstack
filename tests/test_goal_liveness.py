"""PR 6: every open goal names a next-action owner; a claimed wait the core cannot see is not a live path."""
import unittest

from poodo_core import ContractError, LivenessRecord, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import FakeFoundation, goal, precommit, request, to_decide
from tests.test_approval_policy import APPROVER, Foundation, approve, decided


def live(waiting_on="agent", owner="chief-of-staff", revision=1, goal_id="g", **kw):
    return LivenessRecord(goal_id, revision, owner, waiting_on, "Fixture next action", **kw)


class GoalLivenessTests(unittest.TestCase):
    def test_a_new_goal_has_no_live_path_until_the_host_names_an_owner(self):
        core = FakeFoundation()
        core.start_goal(goal())
        self.assertEqual([r["reason"] for r in core.goals_without_live_path()], ["no_next_action_owner"])
        report = core.record_liveness(live())
        self.assertEqual((report["live"], report["owner"], report["waiting_on"]), (True, "chief-of-staff", "agent"))
        self.assertEqual(core.goals_without_live_path(), ())

    def test_changes_are_recorded_once_with_the_prior_record(self):
        core = FakeFoundation()
        core.start_goal(goal())
        core.record_liveness(live())
        core.record_liveness(live())
        core.record_liveness(live("external", owner="vendor-support"))
        events = [e["data"] for e in core.ledger() if e["data"].get("action") == "liveness_set"]
        self.assertEqual(len(events), 2)
        self.assertIsNone(events[0]["prior"])
        self.assertEqual(events[1]["prior"]["owner"], "chief-of-staff")
        self.assertEqual(events[1]["liveness"]["waiting_on"], "external")

    def test_a_revision_makes_the_old_owner_stale(self):
        core = FakeFoundation()
        core.start_goal(goal())
        core.record_liveness(live())
        core.revise_goal(goal(revision=2))
        self.assertEqual(core.liveness("g")["reason"], "liveness_names_stale_revision")
        with self.assertRaises(ContractError):
            core.record_liveness(live(revision=1))
        self.assertTrue(core.record_liveness(live(revision=2))["live"])

    def test_an_approval_wait_is_live_only_while_a_real_ask_is_pending(self):
        core = Foundation()
        to_decide(core)
        core.record_liveness(live("approval", owner=APPROVER))
        self.assertEqual(core.liveness("g")["reason"], "no_pending_approval")
        req = request("send_report")
        core.decide(req, precommit())
        self.assertEqual(core.liveness("g")["reason"], "waiting_on_approval")
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
        approve(core, req)
        core.execute(req.decision_id)
        self.assertEqual(core.liveness("g")["reason"], "no_pending_approval")

    def test_an_approval_wait_must_name_the_configured_approver(self):
        core = Foundation()
        decided(core, request("send_report"))
        core.record_liveness(live("approval", owner="some-agent"))
        self.assertEqual(core.liveness("g")["reason"], "approval_wait_names_wrong_owner")

    def test_a_bounded_wait_expires_by_the_host_clock(self):
        core = Foundation()
        core.start_goal(goal())
        core.record_liveness(live("external", owner="vendor-support", review_by=1500))
        self.assertTrue(core.liveness("g")["live"])
        core.now = 1501
        self.assertEqual(core.liveness("g")["reason"], "wait_expired")
        without_clock = FakeFoundation()
        without_clock.start_goal(goal())
        with self.assertRaises(ContractError):
            without_clock.record_liveness(live(review_by=1500))

    def test_records_are_validated_and_only_name_known_goals(self):
        core = FakeFoundation()
        core.start_goal(goal())
        for bad in (dict(waiting_on="done"), dict(owner="has space"), dict(review_by=1.5), dict(revision=True)):
            args = dict(waiting_on="agent", owner="chief-of-staff", revision=1)
            args.update(bad)
            with self.assertRaises(ContractError, msg=str(bad)):
                live(**args)
        with self.assertRaises(ContractError):
            core.record_liveness(live(goal_id="unknown"))
        with self.assertRaises(ContractError):
            core.record_liveness({"goal_id": "g", "owner": "x", "waiting_on": "agent"})
        sneaky = type("Sneaky", (str,), {"__eq__": lambda self, other: True, "__hash__": str.__hash__})("x")
        with self.assertRaises(ContractError):
            live(waiting_on=sneaky)

    def test_liveness_never_closes_goals_or_changes_authority(self):
        core = FakeFoundation()
        to_decide(core)
        core.record_liveness(live())
        self.assertFalse(core.snapshot("g").closed)
        self.assertEqual(core.snapshot("g").phase, Phase.DECIDE)
        self.assertEqual(core.fake.calls, [])
        with self.assertRaises(TypeError):
            type("Evil", (PoodoCore,), {"_liveness": {}})


if __name__ == "__main__":
    unittest.main()

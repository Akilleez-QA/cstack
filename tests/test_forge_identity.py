"""A candidate belongs to its task, a decision to one request, and an outcome says whether anything ran."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, goal, outcome
from tests.test_workcell_refusals import proposal, proposing


class RerunAndIdentity(unittest.TestCase):
    def forge(self, *sources, **options):
        forge = Forge(*sources, **options)
        self.addCleanup(forge.close)
        return forge

    def test_the_same_goal_runs_twice_and_both_pass(self):
        forge = self.forge(SATURATION, SATURATION)
        self.assertEqual(outcome(forge.run(GOAL))["assessment"], "candidate_passed")
        self.assertEqual(outcome(forge.run(GOAL))["assessment"], "candidate_passed")
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["passed", "passed"])
        candidates = [r["id"] for r in forge.records() if r["kind"] == "candidate"]
        self.assertEqual(len(set(candidates)), 2, "the candidate id binds its task")

    def test_one_decision_cannot_name_two_different_requests(self):
        forge = self.forge(SATURATION, SATURATION)
        self.assertEqual(outcome(forge.run(GOAL))["assessment"], "candidate_passed")
        different = goal(need="A different need the first decision never saw.")
        result = forge.raw(different)
        self.assertEqual(result.returncode, 2, result.stdout[:300])
        error = json.loads(result.stdout)
        self.assertEqual(error["error"], "decision_reuse_refused")
        self.assertEqual(len([r for r in forge.receipts()]), 1)
        self.assertEqual({r["payload"]["request_sha256"] for r in forge.witness()}, {outcome(forge.run(GOAL))["request_sha256"]})


class NotExecuted(unittest.TestCase):
    def assert_not_executed(self, final):
        self.assertEqual((final["execution_status"], final["execution_certainty"]), ("unavailable", "not_dispatched"), final)
        self.assertNotIn("may have executed", json.dumps(final["limitations"]))

    def test_no_node_on_path(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        env = {**forge.env, "PATH": str(Path(sys.executable).parent)}
        result = forge.raw(GOAL, env=env)
        final = outcome(json.loads(result.stdout))
        self.assert_not_executed(final)
        self.assertIn("node", json.dumps(final["limitations"]))

    def test_missing_node_modules_says_how_to_fix_it(self):
        from tests.forge_fixtures import RepoCopy
        copy = RepoCopy()
        self.addCleanup(copy.close)
        (copy.root / "adapters/workcell-toolchain/node_modules").unlink()
        forge = Forge(SATURATION, root=copy.root)
        self.addCleanup(forge.close)
        final = outcome(forge.run(GOAL))
        self.assert_not_executed(final)
        self.assertIn("npm ci", json.dumps(final["limitations"]))

    def test_a_host_without_a_transport_ran_nothing(self):
        forge = Forge(transport=False)
        self.addCleanup(forge.close)
        self.assert_not_executed(outcome(forge.run(GOAL)))

    def test_a_ledger_that_cannot_open_ran_nothing(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        (forge.directory / "forge.sqlite").mkdir()
        self.assert_not_executed(outcome(forge.run(GOAL)))


class RequestShape(unittest.TestCase):
    def refused(self, **arguments):
        forge = Forge(SATURATION.replace('field(receipt, "result.pressure.value")', '"1.5"'))
        self.addCleanup(forge.close)
        result = forge.raw(goal(**arguments))
        self.assertEqual(result.returncode, 2, result.stdout[:300])
        self.assertEqual(forge.receipts(), [])
        return json.loads(result.stdout)

    def test_every_case_needs_a_held_out_check(self):
        self.assertIn("held-out", self.refused(checks=[])["detail"])
        arguments = GOAL["calls"][0]["request"]["arguments"]
        self.assertIn("held-out", self.refused(checks=arguments["checks"][:1])["detail"])

    def test_a_check_must_name_a_case(self):
        check = dict(GOAL["calls"][0]["request"]["arguments"]["checks"][0], case="nope")
        self.refused(checks=[*GOAL["calls"][0]["request"]["arguments"]["checks"], check])

    def test_argument_types_are_checked_before_anything_runs(self):
        for arguments in (dict(max_candidates="2"), dict(max_candidates=0), dict(max_candidates=-1), dict(max_candidates=9), dict(max_candidates=True),
                          dict(declared_imports="foundation_refrigeration"), dict(cases="x"), dict(signature=5), dict(checks="x"), dict(need=5)):
            with self.subTest(arguments):
                self.refused(**arguments)


class Coders(unittest.TestCase):
    def test_a_long_decision_id_keeps_each_proposal_distinct(self):
        document = goal(declared_imports=["foundation_refrigeration", "foundation_template"])
        document["calls"][0]["request"]["decision_id"] = "d" * 128
        kernel = proposing('"{\\"effects\\":[" + A + "," + B + "]}"').replace("export function reduce", '''
const A = %s;
const B = %s;
export function reduce''' % (proposal()[:-1].replace('{\\"effects\\":[', "", 1).rsplit("]}", 1)[0] + '"',
                             proposal(arguments='{"observation":"second"}')[:-1].replace('{\\"effects\\":[', "", 1).rsplit("]}", 1)[0] + '"'))
        forge = Forge(kernel)
        self.addCleanup(forge.close)
        final = outcome(forge.run(document))
        self.assertEqual(final["assessment"], "candidate_passed", final)
        decisions = [p["decision_id"] for p in final["raw_result"]["proposals"]]
        self.assertEqual(len(set(decisions)), 2)
        self.assertLessEqual(max(map(len, decisions)), 128)

    def test_a_proposal_the_capability_rejected_is_not_accepted(self):
        forge = Forge(proposing(proposal(arguments='{"observation":1.5}')))
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"])))
        self.assertEqual(final["assessment"], "candidate_refused")
        self.assertEqual(final["raw_result"]["proposals"][0]["accepted"], False)
        self.assertIn("not_executed", final["raw_result"]["proposals"][0]["reason"])

    def test_an_operation_that_needs_approval_is_refused_for_a_coder(self):
        forge = Forge(proposing(proposal()), decision_operations={"foundation_template": ["echo_observation"]}, decision_ask_operations={"foundation_template": ["echo_observation"]})
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"])))
        self.assertEqual(final["raw_result"]["proposals"][0]["reason"], "approval_not_routed_to_coders")
        self.assertEqual(final["assessment"], "candidate_refused")


class Approvers(unittest.TestCase):
    def test_a_sqlite_approver_stops_a_forge_goal_without_an_approval(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        store = forge.directory / "answers.sqlite"
        from adapters.approval_store import ApprovalWriter
        ApprovalWriter(str(store), clock=lambda: 1).close()
        result = forge.raw(GOAL, "--approver=file:" + str(store))
        document = json.loads(result.stdout)
        self.assertEqual(document["run_status"], "stopped")
        self.assertEqual(forge.receipts(), [])


if __name__ == "__main__":
    unittest.main()

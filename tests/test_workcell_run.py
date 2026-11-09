"""Acceptance item 1: one goal, through a grant and decision, a real pool, the real gates and ledger, back to a witnessed receipt."""
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, goal, outcome


class OneGoal(unittest.TestCase):
    def check_passes(self, isolation):
        forge = Forge(SATURATION, isolation=isolation)
        self.addCleanup(forge.close)
        result = forge.run(GOAL)
        self.assertEqual(result["run_status"], "completed")
        self.assertIs(result["endoforge_implemented"], True)
        self.assertEqual(result["outcome_unknown"], [])
        final = outcome(result)
        self.assertEqual((final["execution_status"], final["assessment"]), ("completed", "candidate_passed"))
        receipt = final["raw_result"]
        self.assertEqual(receipt["decision_id"], "forge-decision-1")
        self.assertEqual(receipt["grant_id"], "local-forge-run")
        self.assertEqual((receipt["compiler"]["name"], receipt["compiler"]["version"]), ("assemblyscript", "0.28.20"))
        foundation = receipt["foundations"]["foundation_refrigeration"]
        self.assertEqual((foundation["version"], foundation["route"]), ("0.1.0", "js-port"))
        self.assertEqual(foundation["source_manifest_sha256"], "230a8faac3653e510b08d0e81614bbc44ad2721e70aeda98722c7176ea47629f")
        self.assertEqual(result["goal"]["runtime_goal_acceptance"], False)

        attempt = receipt["candidates"][0]
        self.assertEqual(attempt["isolation"], isolation)
        self.assertEqual(attempt["attributions"][0]["tool"], "saturation_pressure")

        witnessed = forge.witness()
        self.assertEqual([r["kind"] for r in witnessed], ["precommit", "precommit", "outcome"])
        self.assertEqual(witnessed[0]["payload"]["grant_id"], "local-forge-run")
        self.assertEqual(witnessed[2]["payload"]["raw_result"], receipt)

        ledger = forge.receipts()
        self.assertEqual([r["data"]["outcome_state"] for r in ledger], ["passed"])
        environment = ledger[0]["data"]["precommit"]["environment"]
        self.assertEqual((environment["decision_id"], environment["grant_id"]), ("forge-decision-1", "local-forge-run"))
        self.assertEqual(environment["compiler"]["version"], "0.28.20")
        observation = ledger[0]["data"]["observations"][0]
        self.assertEqual(observation["report"]["attempts"][-1]["stage"], "passed")
        self.assertEqual({r["check"] for r in observation["report"]["attempts"][0]["results"]},
                         {"schema", "interface", "bounds", "determinism", "forbidden_effects",
                          "invariant:declared_imports", "invariant:foundation_pins", "residual"})
        self.assertEqual(receipt["receipts"][0]["hash"], receipt["candidates"][0]["receipts"][0]["hash"])

    def test_process_workcell(self):
        self.check_passes("process")

    def test_thread_workcell(self):
        self.check_passes("thread")

    def test_the_foundation_judges_a_wrong_kernel(self):
        wrong = SATURATION.replace('field(receipt, "result.pressure.value")', '"1.5"')
        forge = Forge(wrong)
        self.addCleanup(forge.close)
        result = forge.run(GOAL)
        final = outcome(result)
        self.assertEqual(final["assessment"], "candidate_rejected")
        self.assertEqual(final["raw_result"]["candidates"][0]["diagnostics"][0]["check"], "residual")
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["failed"])

    def test_a_bounded_repair_gets_a_fresh_candidate_and_its_own_receipt(self):
        forge = Forge("export function broken( {", SATURATION)
        self.addCleanup(forge.close)
        result = forge.run(goal(max_candidates=2))
        final = outcome(result)
        self.assertEqual(final["assessment"], "candidate_passed")
        first, second = final["raw_result"]["candidates"]
        self.assertEqual(first["status"], "rejected")
        self.assertEqual(second["status"], "passed")
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["failed", "passed"])

    def test_a_host_without_a_model_transport_runs_nothing(self):
        forge = Forge(transport=False)
        self.addCleanup(forge.close)
        final = outcome(forge.run(GOAL))
        self.assertEqual(final["assessment"], "candidate_model_unavailable")
        self.assertEqual(forge.receipts(), [])


if __name__ == "__main__":
    unittest.main()

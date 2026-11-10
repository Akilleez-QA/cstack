"""Acceptance item 4: a real SIGKILL during a run surfaces as outcome_unknown. It is never a pass and is never retried."""
import json
import os
import signal
import time
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, args_of, descendants, goal, outcome, wait_for

HANG = """
import { emit } from "./cstack";
export function signature(): void {
  emit("{\\"version\\":1,\\"name\\":\\"ammonia_saturation_pressure\\",\\"inputs\\":[{\\"path\\":\\"temperature_c\\",\\"type\\":\\"number\\",\\"unit\\":\\"degC\\",\\"domain\\":[-70,100]}],\\"output\\":{\\"type\\":\\"number\\",\\"unit\\":\\"kPa(a)\\"}}");
}
export function reduce(): void { while (true) { } }
"""


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    with open(f"/proc/{pid}/stat") as stream:
        return stream.read().rsplit(")", 1)[1].split()[0] != "Z"


class Kill(unittest.TestCase):
    def begin(self):
        forge = Forge(HANG)
        self.addCleanup(forge.close)
        process = forge.start(GOAL)
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        self.addCleanup(process.kill)

        def running():
            supervisors = [p for p in descendants(process.pid) if "supervisor.mjs" in args_of(p)]
            cells = [p for s in supervisors for p in descendants(s) if "isolate-workcell" in args_of(p)]
            admitted = (forge.directory / "forge.sqlite").exists() and any(r["kind"] == "candidate" for r in forge.records())
            return (supervisors[0], cells[0]) if supervisors and cells and admitted else None
        supervisor, cell = wait_for(running)
        time.sleep(1.5)
        return forge, process, supervisor, cell

    def finish(self, process):
        stdout, _ = process.communicate(timeout=30)
        return json.loads(stdout)

    def assert_unknown(self, forge, result):
        self.assertEqual(result["outcome_unknown"][0]["assessment"], "outcome_unknown")
        final = outcome(result)
        self.assertEqual((final["execution_status"], final["execution_certainty"]), ("indeterminate", "unknown"))
        self.assertIsNone(final["raw_result"])
        self.assertEqual(forge.witness()[-1]["payload"]["assessment"], "outcome_unknown")
        self.assertNotIn("passed", [r["data"]["outcome_state"] for r in forge.receipts()])

    def test_sigkill_of_the_workcell(self):
        forge, process, _, cell = self.begin()
        os.kill(cell, signal.SIGKILL)
        result = self.finish(process)
        self.assert_unknown(forge, result)
        self.assertEqual([(r["data"]["delivery_state"], r["data"]["outcome_state"]) for r in forge.receipts()], [("outcome_unknown", "inconclusive")])
        self.assertEqual(forge.receipts()[0]["data"]["observations"][0]["signal"], "SIGKILL")

    def test_sigkill_of_the_workcell_stays_unresolved_in_later_sessions(self):
        forge, process, _, cell = self.begin()
        os.kill(cell, signal.SIGKILL)
        first = self.finish(process)
        self.assert_unknown(forge, first)
        next_run = Forge(SATURATION, directory=forge.directory)
        self.assertEqual(json.loads(next_run.raw(GOAL).stdout)["error"], "decision_reuse_refused")
        resumed = next_run.run_resume(GOAL, "forge-decision-1")
        self.assertEqual([(u["decision_id"], u["attempt_id"]) for u in resumed["unresolved_attempts"]], [("forge-decision-1", "attempt-1")])
        again = next_run.run(goal(need="A new request under a new decision.") | {"calls": [{**goal()["calls"][0], "request": {**goal()["calls"][0]["request"], "decision_id": "forge-decision-2", "request_id": "forge-request-2"}}]})
        self.assertIn(("forge-decision-1", "attempt-1"), [(u["decision_id"], u["attempt_id"]) for u in again["unresolved_attempts"]])

    def test_sigkill_of_the_supervisor_leaves_no_cell(self):
        forge, process, supervisor, cell = self.begin()
        os.kill(supervisor, signal.SIGKILL)
        result = self.finish(process)
        self.assert_unknown(forge, result)
        self.assertEqual(forge.receipts(), [])
        wait_for(lambda: not alive(cell), 5)

    def test_sigkill_of_the_controller_is_reconciled_and_the_next_run_needs_resume(self):
        forge, process, supervisor, cell = self.begin()
        os.kill(process.pid, signal.SIGKILL)
        process.wait()
        wait_for(lambda: not alive(supervisor) and not alive(cell), 5)
        first_session = forge.witness()[0]["session_id"]
        self.assertEqual([r["kind"] for r in forge.witness()], ["precommit", "precommit"])

        next_run = Forge(SATURATION, directory=forge.directory)
        refused = next_run.raw(GOAL)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(json.loads(refused.stdout)["error"], "decision_reuse_refused")
        self.assertEqual(self.candidates_run(forge), 1, "a refused run executes nothing")
        unknown = [r for r in forge.witness() if r["kind"] == "outcome" and r["session_id"] == first_session]
        self.assertEqual(len(unknown), 1)
        self.assertEqual((unknown[0]["payload"]["execution_certainty"], unknown[0]["payload"]["assessment"]), ("unknown", "process_ended_before_outcome"))

        resumed = next_run.run_resume(GOAL, "forge-decision-1")
        self.assertEqual(outcome(resumed)["assessment"], "candidate_passed", "the next run really executes a candidate")
        self.assertEqual(self.candidates_run(forge), 2)
        self.assertEqual(resumed["unresolved_attempts"][0]["decision_id"], "forge-decision-1")
        self.assertEqual(sum(1 for r in forge.witness() if r["kind"] == "outcome" and r["session_id"] == first_session), 1, "recorded once")

    def candidates_run(self, forge):
        return sum(1 for r in forge.records() if r["kind"] == "candidate")

    def test_sigkill_of_the_controller_at_varied_times_never_shows_a_pass_without_a_receipt(self):
        for isolation, delay in (("process", 0.0), ("process", 0.4), ("process", 1.2), ("thread", 0.1), ("thread", 0.7), ("thread", 2.0)):
            with self.subTest(isolation=isolation, delay=delay):
                forge = Forge(SATURATION, isolation=isolation)
                self.addCleanup(forge.close)
                process = forge.start(GOAL)
                self.addCleanup(process.stdout.close)
                self.addCleanup(process.stderr.close)
                wait_for(lambda: forge.witness_exists(), 30)
                time.sleep(delay)
                process.kill()
                process.wait()
                next_run = Forge(SATURATION, directory=forge.directory, isolation=isolation)
                result = next_run.raw(GOAL)
                document = json.loads(result.stdout)
                records = forge.witness()
                receipts = [r["data"]["outcome_state"] for r in forge.receipts()] if (forge.directory / "forge.sqlite").exists() else []
                sessions = {r["session_id"] for r in records}
                first = records[0]["session_id"]
                outcomes = [r["payload"] for r in records if r["kind"] == "outcome" and r["session_id"] == first]
                if outcomes and outcomes[0]["execution_status"] == "completed":
                    self.assertEqual(receipts[0], "passed", "a recorded pass needs its receipt")
                if result.returncode == 2:
                    self.assertEqual(document["error"], "decision_reuse_refused")
                    self.assertEqual(outcomes[0]["execution_certainty"], "unknown")
                else:
                    self.assertEqual(outcome(document)["assessment"], "candidate_passed")
                self.assertGreaterEqual(len(sessions), 1)

    def test_sigkill_during_a_proposal(self):
        from tests.test_workcell_refusals import proposal, proposing
        forge = Forge(proposing(proposal()))
        self.addCleanup(forge.close)
        document = goal(declared_imports=["foundation_refrigeration", "foundation_template"])
        process = forge.start(document)
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        wait_for(lambda: forge.witness_exists() and any(r["goal_id"].startswith("coder.") for r in forge.witness()), 60)
        process.kill()
        process.wait()
        next_run = Forge(SATURATION, directory=forge.directory)
        result = next_run.raw(document)
        self.assertNotIn("passed", [r["data"]["outcome_state"] for r in forge.receipts() if r["data"]["delivery_state"] != "finished"])
        records = forge.witness()
        for key in {(r["session_id"], r["goal_id"]) for r in records}:
            kinds = [r["kind"] for r in records if (r["session_id"], r["goal_id"]) == key]
            if kinds.count("precommit") >= 2:
                self.assertIn("outcome", kinds, key)
        self.assertIn(result.returncode, (0, 2))

    def test_sigkill_after_a_pass_keeps_the_pass(self):
        from tests.test_forge_recovery import freeze_after_receipt
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        freeze_after_receipt(forge)
        result = Forge(SATURATION, directory=forge.directory).run(GOAL)
        self.assertEqual(outcome(result)["assessment"], "candidate_passed")
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["passed", "passed"])

    def test_sigkill_of_a_thread_supervisor(self):
        forge = Forge(HANG, isolation="thread")
        self.addCleanup(forge.close)
        process = forge.start(GOAL)
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        self.addCleanup(process.kill)
        supervisor = wait_for(lambda: next(iter(p for p in descendants(process.pid) if "supervisor.mjs" in args_of(p)), None) if forge.witness_exists() and (forge.directory / "forge.sqlite").exists() and any(r["kind"] == "candidate" for r in forge.records()) else None)
        time.sleep(1.5)
        os.kill(supervisor, signal.SIGKILL)
        result = self.finish(process)
        self.assert_unknown(forge, result)


if __name__ == "__main__":
    unittest.main()

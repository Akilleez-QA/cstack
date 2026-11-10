"""After a crash the ledgers agree, the attempt is visible, and a torn tail doesn't stop later runs."""
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest

from adapters.durable_ledger import DurableLedger
from bootstrap import endoforge_session
from tests.forge_fixtures import Forge, GOAL, SATURATION, goal, outcome, wait_for


def freeze_after_receipt(forge):
    """Stop the controller after the pool durably records a receipt and before it can write an outcome, then kill it."""
    process = forge.start(GOAL)
    wait_for(lambda: (forge.directory / "forge.sqlite").exists() and any(r["kind"] == "candidate" for r in forge.records()), 60)
    os.kill(process.pid, signal.SIGSTOP)
    try:
        wait_for(lambda: any(r["kind"] == "receipt" for r in forge.records()), 60)
    finally:
        os.kill(process.pid, signal.SIGKILL)
        process.wait()
        process.stdout.close()
        process.stderr.close()


class LedgersAgree(unittest.TestCase):
    def test_a_recorded_pass_is_what_reconcile_records(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        freeze_after_receipt(forge)
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["passed"])
        self.assertEqual([r["kind"] for r in forge.witness()], ["precommit", "precommit"])
        result = Forge(SATURATION, directory=forge.directory).run(GOAL)
        reconciled = result["reconciled_outcome_unknown"] if "reconciled_outcome_unknown" in result else result["reconciled"]
        self.assertEqual(reconciled[0]["status"], "candidate_passed_recovered")
        first = [r for r in forge.witness() if r["kind"] == "outcome"][0]["payload"]
        self.assertEqual((first["execution_status"], first["execution_certainty"], first["assessment"]), ("completed", "responded", "candidate_passed_recovered"))
        self.assertEqual(first["raw_result"]["receipts"][0]["outcome_state"], "passed")
        self.assertEqual(outcome(result)["assessment"], "candidate_passed", "a recorded pass needs no resume")

    def test_core_recovery_runs_on_the_cli_path_and_lists_unresolved_attempts(self):
        from tests.test_workcell_kill import HANG
        forge = Forge(HANG)
        self.addCleanup(forge.close)
        process = forge.start(GOAL)
        wait_for(lambda: (forge.directory / "forge.sqlite").exists() and any(r["kind"] == "candidate" for r in forge.records()), 60)
        os.kill(process.pid, signal.SIGKILL)
        process.wait()
        process.stdout.close()
        process.stderr.close()
        next_run = Forge(SATURATION, directory=forge.directory)
        refused = next_run.raw(GOAL)
        self.assertEqual(json.loads(refused.stdout)["error"], "decision_reuse_refused")
        result = next_run.run_resume(GOAL, "forge-decision-1")
        unresolved = result["unresolved_attempts"]
        self.assertEqual(unresolved[0]["decision_id"], "forge-decision-1")
        self.assertEqual(unresolved[0]["attempt_id"], "attempt-1")
        core_files = list((forge.directory / "forge.sqlite.core").glob("*"))
        recovered = [json.loads(line) for path in core_files for line in path.read_text().splitlines() if "process_ended_before_outcome" in line]
        self.assertEqual(len(recovered), 1)
        self.assertEqual(outcome(result)["assessment"], "candidate_passed")


def core_outcome(attempt_id, certainty="unknown"):
    return {"outcome": {"attempt_id": attempt_id, "decision_id": f"decision-{attempt_id}", "request_sha256": "0" * 64,
                        "goal_id": "forge.goal", "execution_certainty": certainty}}


class SessionEnd(unittest.TestCase):
    """A session whose controller survives an unknown outcome stays listed as unresolved in every later session."""
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.config = self.dir / "config.json"
        self.config.write_text(json.dumps({"endoforge": {"path": "witness.jsonl"},
                                           "workcell": {"ledger": "forge.sqlite", "foundation_imports": []}}))

    def session_with(self, *outcomes):
        with endoforge_session(self.config) as host:
            ledger = DurableLedger(self.dir / "forge.sqlite.core" / f"{host['session_id']}.jsonl")
            for data in outcomes:
                ledger.append("outcome", data)
            return host["session_id"]

    def later_unresolved(self):
        with endoforge_session(self.config) as host:
            return host["unresolved"]

    def test_an_unknown_outcome_left_by_a_surviving_controller_is_reported_by_later_sessions(self):
        session_id = self.session_with(core_outcome("attempt-1"))
        expected = [{"attempt_id": "attempt-1", "decision_id": "decision-attempt-1", "request_sha256": "0" * 64,
                     "goal_id": "forge.goal", "session_id": session_id}]
        self.assertEqual(self.later_unresolved(), expected)
        self.assertEqual(self.later_unresolved(), expected)
        self.assertTrue((self.dir / "forge.sqlite.core" / f"{session_id}.recovered").exists())

    def test_a_session_with_only_known_outcomes_is_closed(self):
        session_id = self.session_with(core_outcome("attempt-1", certainty="responded"))
        self.assertEqual(self.later_unresolved(), [])
        self.assertTrue((self.dir / "forge.sqlite.core" / f"{session_id}.closed").exists())


class TornWitness(unittest.TestCase):
    def forge_with_a_run(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        self.assertEqual(outcome(forge.run(GOAL))["assessment"], "candidate_passed")
        return forge, forge.directory / "witness.jsonl"

    def test_a_torn_tail_is_quarantined_recorded_and_later_runs_continue(self):
        forge, path = self.forge_with_a_run()
        raw = path.read_bytes()
        path.write_bytes(raw[:-200])
        result = forge.run(goal(need="A new request under a new decision.") | {"calls": [{**goal()["calls"][0], "request": {**goal()["calls"][0]["request"], "decision_id": "forge-decision-2", "request_id": "forge-request-2"}}]})
        self.assertEqual(outcome(result)["assessment"], "candidate_passed")
        torn = result["witness_quarantined"][0]
        self.assertEqual(Path(torn["path"]).read_bytes(), raw[raw[:-200].rfind(b"\n") + 1:-200])
        self.assertEqual(torn["bytes"], len(raw[:-200]) - raw[:-200].rfind(b"\n") - 1)
        self.assertEqual(path.read_bytes()[:raw[:-200].rfind(b"\n") + 1], raw[:raw[:-200].rfind(b"\n") + 1])

    def test_a_torn_outcome_is_resolved_from_the_run_ledger(self):
        forge, path = self.forge_with_a_run()
        path.write_bytes(path.read_bytes()[:-200])
        result = forge.run(GOAL)
        self.assertEqual(result["reconciled"][0]["status"], "candidate_passed_recovered")
        self.assertEqual(outcome(result)["assessment"], "candidate_passed")

    def test_a_broken_chain_in_the_middle_fails_closed_and_says_so(self):
        forge, path = self.forge_with_a_run()
        lines = path.read_bytes().splitlines(keepends=True)
        lines[0] = lines[0].replace(b'"goal_id":"forge', b'"goal_id":"Forge')
        path.write_bytes(b"".join(lines))
        result = forge.raw(GOAL)
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stdout)
        self.assertEqual(error["error"], "witness_chain_broken")
        self.assertIn("record 1", error["detail"])
        self.assertEqual(path.read_bytes(), b"".join(lines), "nothing is repaired")
        self.assertEqual(len(forge.receipts()), 1)


if __name__ == "__main__":
    unittest.main()

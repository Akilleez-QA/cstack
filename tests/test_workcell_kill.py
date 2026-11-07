"""Acceptance item 4: a real SIGKILL during a run surfaces as outcome_unknown. It is never a pass and is never retried."""
import json
import os
import signal
import time
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, args_of, descendants, outcome, wait_for

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
        unknown = [r for r in forge.witness() if r["kind"] == "outcome" and r["session_id"] == first_session]
        self.assertEqual(len(unknown), 1)
        self.assertEqual((unknown[0]["payload"]["execution_certainty"], unknown[0]["payload"]["assessment"]), ("unknown", "process_ended_before_outcome"))

        resumed = json.loads(next_run.raw(GOAL, "--resume", "forge-decision-1").stdout)
        self.assertEqual(outcome(resumed)["assessment"], "candidate_passed", "the next run really executes a candidate")
        self.assertEqual(sum(1 for r in forge.witness() if r["kind"] == "outcome" and r["session_id"] == first_session), 1, "recorded once")


if __name__ == "__main__":
    unittest.main()

"""Acceptance item 4: a real SIGKILL during a run surfaces as outcome_unknown. It is never a pass and is never retried."""
import json
import os
import signal
import time
import unittest

from tests.forge_fixtures import Forge, GOAL, args_of, descendants, outcome, wait_for

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

    def test_sigkill_of_the_controller_is_reconciled_by_the_next_run(self):
        forge, process, supervisor, cell = self.begin()
        os.kill(process.pid, signal.SIGKILL)
        process.wait()
        wait_for(lambda: not alive(supervisor) and not alive(cell), 5)
        self.assertEqual([r["kind"] for r in forge.witness()], ["precommit", "precommit"])
        forge_next = Forge(directory=forge.directory)
        document = json.loads((forge.directory / "witness.jsonl").read_text().splitlines()[0])
        result = forge_next.run(json.loads(json.dumps(GOAL)))
        self.assertEqual(result["reconciled_outcome_unknown"][0]["decision_id"], "forge-decision-1")
        self.assertEqual(result["reconciled_outcome_unknown"][0]["status"], "outcome_unknown")
        records = forge.witness()
        unknown = [r for r in records if r["kind"] == "outcome" and r["session_id"] == document["session_id"]]
        self.assertEqual(unknown[0]["payload"]["execution_certainty"], "unknown")
        self.assertEqual(unknown[0]["payload"]["assessment"], "process_ended_before_outcome")
        self.assertEqual(sum(1 for r in records if r["kind"] == "outcome" and r["session_id"] == document["session_id"]), 1)

        third = forge_next.run(json.loads(json.dumps(GOAL)))
        self.assertNotIn("reconciled_outcome_unknown", third, "it is recorded once")


if __name__ == "__main__":
    unittest.main()

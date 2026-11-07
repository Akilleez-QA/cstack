"""Acceptance item 2: a kernel calls a Foundation through a declared import, in process, with zero spawns, and gets an attributable result."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from adapters.template_stdio import TemplateStdioCapability
from poodo_core import CapabilityRequest
from tests.forge_fixtures import Forge, ROOT, goal, outcome

sys.path.insert(0, str(ROOT / "tools"))
import spawncount  # noqa: E402

CALLS_PER_CASE = 1000
REFRIGERATION = """
import { emit, event, field, refrigeration } from "./cstack";
export function signature(): void {
  emit("{\\"version\\":1,\\"name\\":\\"ammonia_saturation_pressure\\",\\"inputs\\":[{\\"path\\":\\"temperature_c\\",\\"type\\":\\"number\\",\\"unit\\":\\"degC\\",\\"domain\\":[-70,100]}],\\"output\\":{\\"type\\":\\"number\\",\\"unit\\":\\"kPa(a)\\"}}");
}
export function reduce(): void {
  const temperature = field(event(), "inputs.temperature_c");
  const args = "{\\"fluid\\":\\"NH3\\",\\"temperature\\":{\\"value\\":" + temperature + ",\\"unit\\":\\"degC\\"}}";
  let receipt = "";
  for (let i = 0; i < %d; i++) receipt = refrigeration("saturation_pressure", args);
  emit("{\\"value\\":" + field(receipt, "result.pressure.value") + "}");
}
""" % CALLS_PER_CASE
TEMPLATE = """
import { emit, event, field, template } from "./cstack";
export function signature(): void {
  emit("{\\"version\\":1,\\"name\\":\\"echo\\",\\"inputs\\":[{\\"path\\":\\"text\\",\\"type\\":\\"string\\",\\"unit\\":\\"text\\"}],\\"output\\":{\\"type\\":\\"string\\",\\"unit\\":\\"text\\"}}");
}
export function reduce(): void {
  const text = field(event(), "inputs.text");
  let receipt = "";
  for (let i = 0; i < %d; i++) receipt = template("echo_observation", "{\\"observation\\":" + text + "}");
  emit("{\\"value\\":" + field(receipt, "result.observation") + "}");
}
""" % CALLS_PER_CASE
TEMPLATE_ARGUMENTS = dict(
    need="Echo the text through the template Foundation.", declared_imports=["foundation_template"],
    signature={"version": 1, "name": "echo", "inputs": [{"path": "text", "type": "string", "unit": "text"}], "output": {"type": "string", "unit": "text"}},
    cases=[{"id": "one", "inputs": {"text": "fixture"}}],
    checks=[{"case": "one", "foundation": "foundation_template", "tool": "echo_observation", "arguments": {"observation": "fixture"},
             "path": "result.observation", "tolerance": 0}])


def traced(forge, document):
    with tempfile.TemporaryDirectory() as directory:
        goal_path, out, events_path = Path(directory, "goal.json"), Path(directory, "out.json"), Path(directory, "events.json")
        goal_path.write_text(json.dumps(document))
        code = spawncount.trace(forge.command(), str(events_path), env={"CSTACK_STUB_TRANSPORT_SCRIPT": forge.env["CSTACK_STUB_TRANSPORT_SCRIPT"]}, stdin=str(goal_path), stdout=str(out))
        return code, json.loads(out.read_text()), json.loads(events_path.read_text())


@unittest.skipUnless(sys.platform == "linux", "ptrace counting is Linux only")
class SpawnCount(unittest.TestCase):
    def check_route(self, source, document, foundation, isolation):
        forge = Forge(source, isolation=isolation)
        self.addCleanup(forge.close)
        code, result, events = traced(forge, document)
        self.assertEqual(code, 0)
        final = outcome(result)
        self.assertEqual(final["assessment"], "candidate_passed", final)
        attempt = final["raw_result"]["candidates"][0]
        start, end = map(int, attempt["window_ns"])
        inside = spawncount.count(events, start, end)
        self.assertGreaterEqual(attempt["calls"], CALLS_PER_CASE * len(document["calls"][0]["request"]["arguments"]["cases"]) * 2)
        self.assertEqual((inside["process"], inside["exec"]), (0, 0), f"spawns inside the job window, {attempt['calls']} calls")
        self.assertGreater(spawncount.count(events)["exec"], 1, "the tracer must have seen the supervisor start")
        for row in attempt["attributions"]:
            self.assertEqual(row["foundation"], foundation)
            self.assertEqual(row["route"], "js-port")
            self.assertRegex(row["input_sha256"], "^[0-9a-f]{64}$")
            self.assertRegex(row["output_sha256"], "^[0-9a-f]{64}$")
            self.assertRegex(row["source_manifest_sha256"], "^[0-9a-f]{64}$")

    def test_refrigeration_process_cell(self):
        self.check_route(REFRIGERATION, goal(), "foundation_refrigeration", "process")

    def test_refrigeration_thread_cell(self):
        self.check_route(REFRIGERATION, goal(), "foundation_refrigeration", "thread")

    def test_template_process_cell(self):
        self.check_route(TEMPLATE, goal(**TEMPLATE_ARGUMENTS), "foundation_template", "process")

    def test_the_counter_sees_the_stdio_route_spawn_per_call(self):
        calls = 4
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory, "stdio.py")
            script.write_text(f"""
import sys
sys.path.insert(0, {str(ROOT)!r})
from adapters.template_stdio import TemplateStdioCapability
from pathlib import Path
from poodo_core import CapabilityRequest
capability = TemplateStdioCapability(Path({str(ROOT / "foundations/template")!r}))
for i in range({calls}):
    request = CapabilityRequest.from_dict(dict(schema="poodo.capability-request/0.1", request_id=f"r{{i}}", goal_id="g", goal_revision=1, decision_id=f"d{{i}}",
        capability_id="foundation_template", operation="echo_observation", arguments=dict(observation="a"), required_evidence="tool_observation"))
    assert capability.invoke(request, f"attempt-{{i}}").to_dict()["execution_status"] == "completed"
""")
            events_path = Path(directory, "events.json")
            self.assertEqual(spawncount.trace([sys.executable, "-B", str(script)], str(events_path)), 0)
            counted = spawncount.count(json.loads(events_path.read_text()))
        self.assertGreaterEqual(counted["exec"], calls + 1)
        self.assertGreaterEqual(counted["process"], calls)


if __name__ == "__main__":
    unittest.main()

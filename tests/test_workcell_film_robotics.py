"""A coder reaches Film and Robotics in process: pinned, attributed, refused when out of domain, and with no spawn."""
import hashlib
import json
import subprocess
import sys
import unittest

from tests.forge_fixtures import Forge, ROOT, RepoCopy, goal, outcome

sys.path.insert(0, str(ROOT / "tools"))
import spawncount  # noqa: E402

HEADER = """
import { emit, event, field, film, robotics } from "./cstack";
export function signature(): void {
  emit("{\\"version\\":1,\\"name\\":\\"film_and_robotics\\",\\"inputs\\":[{\\"path\\":\\"height_mm\\",\\"type\\":\\"number\\",\\"unit\\":\\"mm\\",\\"domain\\":[1,10000000]}],\\"output\\":{\\"type\\":\\"number\\",\\"unit\\":\\"ms\\"}}");
}
"""
CUES = '{\\"provided\\":[{\\"id\\":\\"a\\",\\"t_ms\\":41000},{\\"id\\":\\"b\\",\\"t_ms\\":42000}],\\"lanes\\":[{\\"lane\\":\\"l\\",\\"references\\":[\\"a\\",\\"b\\"]}]}'
BOTH = HEADER + """
export function reduce(): void {
  const height = field(event(), "inputs.height_mm");
  const cues = film("cue_vocabulary_check", "%s");
  const timing = robotics("scale_timing", "{\\"height_mm\\":" + height + "}");
  if (field(cues, "result.verdict") != "\\"thresholds_met\\"") { emit("{\\"error\\":{\\"path\\":\\"height_mm\\",\\"reason\\":\\"cues\\"}}"); return; }
  emit("{\\"value\\":" + field(timing, "result.leg_swing_period_ms") + "}");
}
""" % CUES


def loop(foundation, call):
    return HEADER + """
export function reduce(): void {
  const height = field(event(), "inputs.height_mm");
  const timing = robotics("scale_timing", "{\\"height_mm\\":" + height + "}");
  let receipt = "";
  for (let i = 0; i < 1000; i++) receipt = %s;
  emit("{\\"value\\":" + field(timing, "result.leg_swing_period_ms") + "}");
}
""" % call


ROBOTICS_LOOP = loop("foundation_robotics", 'robotics("scale_timing", "{\\"height_mm\\":" + height + "}")')
FILM_LOOP = loop("foundation_film", 'film("cue_vocabulary_check", "%s")' % CUES)
IMPORTS = ("foundation_refrigeration", "foundation_template", "foundation_film", "foundation_robotics")


def arguments(tool="scale_timing"):
    check = {"case": "one", "foundation": "foundation_robotics", "tool": tool, "arguments": {"height_mm": 6000}, "path": "result.leg_swing_period_ms", "tolerance": 0}
    return dict(need="Report a body's leg swing period, once the shared cues check out.", declared_imports=["foundation_film", "foundation_robotics"],
                signature={"version": 1, "name": "film_and_robotics", "inputs": [{"path": "height_mm", "type": "number", "unit": "mm", "domain": [1, 10000000]}], "output": {"type": "number", "unit": "ms"}},
                cases=[{"id": "one", "inputs": {"height_mm": 6000}}], checks=[check])


class Pins(unittest.TestCase):
    def identity(self, foundation):
        code = f"import('./adapters/workcell/kernels/registry.mjs').then(async m => console.log(JSON.stringify((await m.loadFoundation({json.dumps(foundation)})).identity)));"
        result = subprocess.run(["node", "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_identity_names_every_pinned_part(self):
        pins = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())
        for foundation, module in (("foundation_film", "film.mjs"), ("foundation_robotics", "robotics.mjs")):
            identity = self.identity(foundation)
            self.assertEqual(identity["source_manifest_sha256"], pins[foundation]["source_manifest_sha256"])
            self.assertEqual(identity["route"], "js-port")
            files = pins["workcell_runtime"]["files"]
            self.assertEqual(identity["port_sha256"], files[f"kernels/{module}"])
            for name, digest in identity["shared_sha256"].items():
                self.assertEqual(digest, files[f"kernels/{name}"])
        self.assertIn("numeric_boundary", self.identity("foundation_robotics")["numeric_tolerance"])
        raw = (ROOT / "foundations/robotics/foundation_robotics/data/defaults.json").read_bytes()
        self.assertEqual(self.identity("foundation_robotics")["projections"]["foundation_robotics/data/defaults.json"], hashlib.sha256(raw).hexdigest())

    def changed(self, path, old, new):
        copy = RepoCopy()
        self.addCleanup(copy.close)
        copy.edit(path, old, new)
        forge = Forge(BOTH, root=copy.root, imports=IMPORTS)
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(**arguments())))
        self.assertEqual((final["execution_status"], final["execution_certainty"]), ("unavailable", "not_dispatched"), final["assessment"])
        self.assertIn("pin", json.dumps(final["limitations"]))

    def test_a_changed_port_does_not_run(self):
        self.changed("adapters/workcell/kernels/film.mjs", "const BLACK_FLOOR = 350;", "const BLACK_FLOOR = 351;")
        self.changed("adapters/workcell/kernels/robotics-numeric.mjs", "const NUDGE = 2 ** -49;", "const NUDGE = 0;")


class Forged(unittest.TestCase):
    def run_goal(self, source, document, **options):
        forge = Forge(source, imports=IMPORTS, **options)
        self.addCleanup(forge.close)
        return forge, outcome(forge.run(document))

    def test_a_coder_reaches_both_without_a_spawn(self):
        forge, final = self.run_goal(BOTH, goal(**arguments()))
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
        attempt = final["raw_result"]["candidates"][0]
        pins = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())
        files = pins["workcell_runtime"]["files"]
        seen = {row["foundation"]: row for row in attempt["attributions"]}
        for foundation, module, tool in (("foundation_film", "film.mjs", "cue_vocabulary_check"), ("foundation_robotics", "robotics.mjs", "scale_timing")):
            self.assertEqual(seen[foundation]["tool"], tool)
            self.assertEqual(seen[foundation]["route"], "js-port")
            self.assertEqual(seen[foundation]["source_manifest_sha256"], pins[foundation]["source_manifest_sha256"])
            self.assertEqual(seen[foundation]["port_sha256"], files[f"kernels/{module}"])
            self.assertRegex(seen[foundation]["output_sha256"], "^[0-9a-f]{64}$")
            self.assertEqual(final["raw_result"]["foundations"][foundation]["port_sha256"], files[f"kernels/{module}"])
        self.assertEqual(attempt["broker_refusals"], [])
        self.assertTrue(forge.receipts())

    def test_a_refusal_fails_the_run(self):
        for call in ('film("look_gate", "{\\"frames\\":1.5}");', 'robotics("scale_timing", "{\\"height_mm\\":1e3}");', 'robotics("scale_timing", "{\\"height_mm\\":' + "9" * 450 + '}");', 'film("no_such_tool", "{}");'):
            with self.subTest(call):
                source = BOTH.replace("export function reduce(): void {", "export function reduce(): void {\n  " + call)
                _, final = self.run_goal(source, goal(**arguments()))
                self.assertEqual(final["assessment"], "candidate_rejected", final["limitations"])
                attempt = final["raw_result"]["candidates"][0]
                self.assertEqual(attempt["diagnostics"][0]["check"], "forbidden_effects")
                self.assertTrue(attempt["broker_refusals"])

    def test_a_wrong_answer_is_judged_against_the_foundation(self):
        _, final = self.run_goal(BOTH.replace('field(timing, "result.leg_swing_period_ms")', '"1"'), goal(**arguments()))
        self.assertEqual(final["assessment"], "candidate_rejected")

    def rejected_with_repair(self, check, code):
        document = arguments()
        document["checks"] = [dict(document["checks"][0], **check)]
        document["max_candidates"] = 2
        forge = Forge(BOTH, BOTH + "\n// repaired\n", imports=IMPORTS)
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(**document)))
        self.assertEqual((final["execution_status"], final["assessment"]), ("tool_error", "candidate_rejected"), final["limitations"])
        candidates = final["raw_result"]["candidates"]
        self.assertEqual([c["status"] for c in candidates], ["rejected", "rejected"], "repair stays allowed")
        self.assertEqual(candidates[0]["diagnostics"][0]["check"], "residual")
        self.assertIn(code, candidates[0]["diagnostics"][0]["reasons"][0])
        self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["failed", "failed"])

    def test_a_held_out_check_the_port_refuses_is_a_rejection_that_allows_repair(self):
        self.rejected_with_repair(dict(arguments={"height_mm": 1.5}), "not_integer")

    def test_a_numeric_boundary_in_a_held_out_check_is_a_rejection_that_allows_repair(self):
        tie = {"kind": "gear_mesh", "driver_teeth": 12, "driven_teeth": 36, "mesh": "external", "frames": [{"driver_mrad": 300, "driven_mrad": -100}, {"driver_mrad": 600, "driven_mrad": -210}]}
        self.rejected_with_repair(dict(tool="mechanism_check", arguments=tie, path="result.detail.worst_frame"), "numeric_boundary")

    @unittest.skipUnless(sys.platform == "linux", "ptrace counting is Linux only")
    def test_the_whole_job_spawns_nothing(self):
        from tests.test_workcell_foundation_imports import traced
        for source, calls in ((ROBOTICS_LOOP, 1000), (FILM_LOOP, 1000)):
            forge = Forge(source, imports=IMPORTS)
            self.addCleanup(forge.close)
            code, result, events = traced(forge, goal(**arguments()))
            self.assertEqual(code, 0)
            final = outcome(result)
            self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
            attempt = final["raw_result"]["candidates"][0]
            start, end = map(int, attempt["window_ns"])
            inside = spawncount.count(events, start, end)
            self.assertGreaterEqual(attempt["calls"], calls)
            self.assertEqual((inside["process"], inside["exec"]), (0, 0))
            self.assertGreater(spawncount.count(events)["exec"], 1)


if __name__ == "__main__":
    unittest.main()

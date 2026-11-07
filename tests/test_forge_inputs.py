"""Decimal inputs and tolerances work exactly, and a prompt alone tells a coder enough to write a kernel."""
import json
import os
from pathlib import Path
import unittest

from tests.forge_fixtures import Forge, ROOT, SATURATION, goal, outcome


def decimal_goal(temperatures=(-33.34, 0.5, 21.125), tolerance=0, **arguments):
    return goal(cases=[{"id": f"t{i}", "inputs": {"temperature_c": t}} for i, t in enumerate(temperatures)],
                checks=[{"case": f"t{i}", "foundation": "foundation_refrigeration", "tool": "saturation_pressure",
                         "arguments": {"fluid": "NH3", "temperature": {"value": t, "unit": "degC"}}, "path": "result.pressure.value", "tolerance": tolerance}
                        for i, t in enumerate(temperatures)], **arguments)


class Decimals(unittest.TestCase):
    def forge(self, *sources):
        forge = Forge(*sources)
        self.addCleanup(forge.close)
        return forge

    def test_a_decimal_case_runs_and_the_kernel_sees_it_exactly(self):
        forge = self.forge(SATURATION)
        result = forge.raw(decimal_goal())
        self.assertEqual(result.returncode, 0, result.stdout[:300])
        final = outcome(json.loads(result.stdout))
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
        arguments = final["raw_result"]["candidates"][0]["attributions"][0]
        self.assertEqual(arguments["input_sha256"], __import__("hashlib").sha256(b'{"fluid":"NH3","temperature":{"unit":"degC","value":-33.34}}').hexdigest())

    def test_exponents_and_nonfinite_numbers_stay_refused(self):
        forge = self.forge(SATURATION)
        for token in ("1e5", "1E400", "NaN", "Infinity"):
            with self.subTest(token):
                text = json.dumps(decimal_goal()).replace("-33.34", token, 1)
                import subprocess
                result = subprocess.run(forge.command(), input=text.encode(), capture_output=True, env=forge.env, cwd=forge.root, timeout=60)
                self.assertEqual(result.returncode, 2)

    def emitting(self, literal):
        return SATURATION.replace('field(receipt, "result.pressure.value")', '"%s"' % literal)

    def test_a_decimal_tolerance_holds_exactly_at_its_boundary(self):
        document = decimal_goal(temperatures=(-10,), tolerance=0.002)
        self.assertGreater(290.6344 - 290.6324, 0.002, "binary floats would reject this exact boundary")
        inside = self.forge(self.emitting("290.6344"))
        self.assertEqual(outcome(inside.run(document))["assessment"], "candidate_passed")
        outside = self.forge(self.emitting("290.63440001"))
        self.assertEqual(outcome(outside.run(document))["assessment"], "candidate_rejected")

    def test_a_decimal_goes_to_a_foundation_through_a_decision(self):
        from tests.test_workcell_refusals import proposal, proposing
        kernel = proposing(proposal(capability="foundation_refrigeration", operation="saturation_pressure", arguments='{"fluid":"NH3","temperature":{"value":-33.34,"unit":"degC"}}'))
        forge = Forge(kernel, decision_operations={"foundation_refrigeration": ["saturation_pressure"]})
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal()))
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
        self.assertEqual(final["raw_result"]["proposals"][0]["execution_status"], "completed")


STRICT = """
import { readFileSync, appendFileSync } from 'node:fs';
const required = ['./cstack', 'reduce', 'signature', 'event()', 'emit(', 'field(', 'refrigeration(', 'template(', 'AssemblyScript', 'no JSON', 'propose_decision', 'capability_id', 'expected_observation',
  'success_boundary', 'failure_meaning', 'effect_results', '"value"', '"effects"', 'ammonia_saturation_pressure', 'foundation_refrigeration', 'Return only'];
export function generate(prompt) {
  if (typeof prompt.text !== 'string') throw new Error('the prompt has no text');
  const missing = required.filter(word => !prompt.text.includes(word));
  if (missing.length) throw new Error('the prompt lacks: ' + missing.join(', '));
  if (/held-out|"checks"/.test(prompt.text)) throw new Error('the prompt leaks held-out checks');
  appendFileSync(process.env.STRICT_LOG, prompt.text);
  return { text: readFileSync(process.env.STRICT_SOURCE, 'utf8'), model: { identity: 'strict-stub', version: '1' } };
}
"""


class Prompt(unittest.TestCase):
    def run_with(self, **env):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        transport = forge.directory / "strict.mjs"
        transport.write_text(STRICT)
        config = json.loads(forge.config.read_text())
        config["workcell"]["transport"] = str(transport)
        forge.config.write_text(json.dumps(config))
        (forge.directory / "source.ts").write_text(SATURATION)
        forge.env.update(STRICT_SOURCE=str(forge.directory / "source.ts"), STRICT_LOG=str(forge.directory / "prompt.txt"), **env)
        return forge, outcome(forge.run(goal(max_candidates=2)))

    def test_a_strict_transport_gets_all_it_needs_and_no_held_out_checks(self):
        forge, final = self.run_with()
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
        self.assertIn("ammonia", (forge.directory / "prompt.txt").read_text())

    def test_repair_feedback_reaches_the_prompt(self):
        forge = Forge("export function broken( {", SATURATION)
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(max_candidates=2)))
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])


if __name__ == "__main__":
    unittest.main()

"""Acceptance item 3: the core accepts or refuses a coder's proposal; a candidate can't get authority, or a pass, any other way."""
import json
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, goal, outcome

HEADER = """
import { emit, event, field, refrigeration, robotics, template } from "./cstack";
export function signature(): void {
  emit("{\\"version\\":1,\\"name\\":\\"ammonia_saturation_pressure\\",\\"inputs\\":[{\\"path\\":\\"temperature_c\\",\\"type\\":\\"number\\",\\"unit\\":\\"degC\\",\\"domain\\":[-70,100]}],\\"output\\":{\\"type\\":\\"number\\",\\"unit\\":\\"kPa(a)\\"}}");
}
function right(input: string): string {
  const receipt = refrigeration("saturation_pressure", "{\\"fluid\\":\\"NH3\\",\\"temperature\\":{\\"value\\":" + field(input, "inputs.temperature_c") + ",\\"unit\\":\\"degC\\"}}");
  return field(receipt, "result.pressure.value");
}
"""


def proposal(capability="foundation_template", operation="echo_observation", arguments='{"observation":"from a coder"}', extra=""):
    payload = (f'{{"capability_id":"{capability}","operation":"{operation}","arguments":{arguments},"expected_observation":"an echo",'
               f'"success_boundary":"only this echo","failure_meaning":"none"{extra}}}')
    return json.dumps(f'{{"effects":[{{"capability":"poodo","operation":"propose_decision","payload":{payload}}}]}}')


def proposing(effect, after='"{\\"value\\":" + right(input) + "}"'):
    return HEADER + f"""
export function reduce(): void {{
  const input = event();
  if (field(input, "kind") == "\\"case\\"") emit({effect});
  else emit({after});
}}
"""


class Refusals(unittest.TestCase):
    def forge(self, *sources, **options):
        forge = Forge(*sources, **options)
        self.addCleanup(forge.close)
        return forge

    def assert_no_pass(self, forge, result, assessment):
        final = outcome(result)
        self.assertEqual(final["assessment"], assessment, final)
        self.assertNotIn("candidate_passed", json.dumps(final))
        self.assertNotEqual(final["execution_status"], "completed")
        self.assertNotIn("passed", [r["data"]["outcome_state"] for r in forge.receipts()])
        return final

    def test_the_core_accepts_a_proposal_inside_its_grant_and_witnesses_it(self):
        forge = self.forge(proposing(proposal()))
        result = forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"]))
        final = outcome(result)
        self.assertEqual(final["assessment"], "candidate_passed", final)
        proposals = final["raw_result"]["proposals"]
        self.assertEqual(proposals[0]["accepted"], True)
        self.assertEqual(proposals[0]["assessment"], "observation_echoed")
        self.assertEqual(proposals[0]["execution_status"], "completed")
        witnessed = [r for r in forge.witness() if r["goal_id"].startswith("coder.")]
        self.assertEqual([r["kind"] for r in witnessed], ["precommit", "precommit", "outcome"])
        self.assertEqual(witnessed[0]["payload"]["grant_id"], "local-template-observation")

    def test_a_candidate_cannot_grant_itself_authority(self):
        for name, effect in {
                "grant field": proposal(extra=',"grant_id":"local-template-observation"'),
                "approval field": proposal(extra=',"approved":true'),
                "decision identity": proposal(extra=',"decision_id":"forge-decision-1"'),
                "a direct effect": json.dumps('{"effects":[{"capability":"foundation_template","operation":"echo_observation","payload":{"observation":"x"}}]}'),
                "a grant effect": json.dumps('{"effects":[{"capability":"poodo","operation":"grant","payload":{"grant_id":"mine","operations":["any"]}}]}')}.items():
            with self.subTest(name):
                forge = self.forge(proposing(effect))
                result = forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"]))
                final = self.assert_no_pass(forge, result, "candidate_refused")
                self.assertEqual(final["raw_result"]["proposals"], [])
                self.assertFalse([r for r in forge.witness() if r["goal_id"].startswith("coder.")], "nothing reached the core")

    def test_a_kernel_cannot_run_a_forge_goal_or_a_grant_outside_the_host_config(self):
        forge = self.forge(proposing(proposal(capability="cstack_forge", operation="run_goal", arguments="{}")))
        result = forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"]))
        final = self.assert_no_pass(forge, result, "candidate_refused")
        self.assertEqual(final["raw_result"]["proposals"][0]["reason"], "undeclared_foundation")

    def test_a_declaration_alone_grants_nothing(self):
        forge = self.forge(SATURATION, imports=("foundation_refrigeration",))
        result = forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_template"]))
        final = self.assert_no_pass(forge, result, "candidate_refused")
        self.assertEqual(final["raw_result"]["reason"], "declared_import_not_granted")
        self.assertEqual(forge.receipts(), [])

    def test_a_candidate_cannot_reach_a_foundation_it_did_not_declare(self):
        undeclared = HEADER + """
export function reduce(): void {
  const input = event();
  robotics("scale_timing", "{\\"height_mm\\":6000}");
  emit("{\\"value\\":" + right(input) + "}");
}
"""
        forge = self.forge(undeclared)
        final = self.assert_no_pass(forge, forge.run(GOAL), "candidate_rejected")
        attempt = final["raw_result"]["candidates"][0]
        self.assertEqual(attempt["wasm"]["refused"], ["foundation_robotics.call"])
        self.assertEqual(attempt["diagnostics"][0]["check"], "forbidden_effects")
        self.assertIn("import:foundation_robotics", attempt["diagnostics"][0]["reasons"][0])
        self.assertEqual(attempt["attributions"], [])

    def test_a_declared_foundation_is_still_refused_if_a_proposal_names_another(self):
        forge = self.forge(proposing(proposal(capability="foundation_robotics", operation="scale_timing", arguments='{"height_mm":6000}')))
        final = self.assert_no_pass(forge, forge.run(GOAL), "candidate_refused")
        self.assertEqual(final["raw_result"]["proposals"][0]["reason"], "undeclared_foundation")

    def test_an_ambient_import_is_refused_before_it_can_link(self):
        ambient = """
@external("env", "process_exit") declare function process_exit(code: i32): void;
import { emit } from "./cstack";
export function signature(): void { process_exit(1); emit("{}"); }
export function reduce(): void { process_exit(1); emit("{}"); }
"""
        forge = self.forge(ambient)
        final = self.assert_no_pass(forge, forge.run(GOAL), "candidate_rejected")
        attempt = final["raw_result"]["candidates"][0]
        self.assertEqual(attempt["wasm"]["refused"], ["env.process_exit"])
        self.assertIn("import:env", attempt["diagnostics"][0]["reasons"][0])

    def test_extra_exports_are_refused(self):
        forge = self.forge(SATURATION + "\nexport function backdoor(): i32 { return 1; }\n")
        final = self.assert_no_pass(forge, forge.run(GOAL), "candidate_rejected")
        self.assertEqual(final["raw_result"]["candidates"][0]["diagnostics"][0]["check"], "interface")

    def test_the_core_refuses_outside_its_grant_and_the_kernel_cannot_get_past_it(self):
        ignoring = proposing(proposal(capability="foundation_refrigeration", operation="exposure_limits", arguments='{"substance":"ammonia"}'))
        forge = self.forge(ignoring, SATURATION, decision_operations={"foundation_refrigeration": ["saturation_pressure"]})
        result = forge.run(goal(max_candidates=2))
        final = self.assert_no_pass(forge, result, "candidate_refused")
        refusal = final["raw_result"]["proposals"][0]
        self.assertEqual((refusal["accepted"], refusal["reason"]), (False, "core_refused"))
        self.assertEqual(len(final["raw_result"]["candidates"]), 1, "a refusal ends the run; it isn't repaired past")
        self.assertEqual(final["raw_result"]["candidates"][0]["diagnostics"][0]["check"], "forbidden_effects")
        self.assertEqual([r["kind"] for r in forge.witness() if r["goal_id"].startswith("coder.")], [])

    def test_retrying_a_refused_proposal_under_new_words_is_still_refused(self):
        retry = HEADER + """
export function reduce(): void {
  const input = event();
  const kind = field(input, "kind");
  const again = "{\\"effects\\":[{\\"capability\\":\\"poodo\\",\\"operation\\":\\"propose_decision\\",\\"payload\\":{\\"capability_id\\":\\"foundation_refrigeration\\",\\"operation\\":\\"exposure_limits\\",\\"arguments\\":{\\"substance\\":\\"ammonia\\"},\\"expected_observation\\":\\"try " + (input.length.toString()) + "\\",\\"success_boundary\\":\\"x\\",\\"failure_meaning\\":\\"y\\"}}]}";
  if (input.length < 900) emit(again);
  else emit("{\\"value\\":" + right(input) + "}");
}
"""
        forge = self.forge(retry, decision_operations={"foundation_refrigeration": ["saturation_pressure"]})
        final = self.assert_no_pass(forge, forge.run(GOAL), "candidate_refused")
        self.assertTrue(all(p["accepted"] is False for p in final["raw_result"]["proposals"]))

    def test_a_kernel_claiming_its_own_pass_changes_nothing(self):
        claim = HEADER + """
export function reduce(): void {
  emit("{\\"value\\":1.5,\\"outcome_state\\":\\"passed\\",\\"delivery_state\\":\\"finished\\",\\"receipt\\":{\\"outcome_state\\":\\"passed\\"}}");
}
"""
        forge = self.forge(claim)
        self.assert_no_pass(forge, forge.run(GOAL), "candidate_rejected")

    def test_a_kernel_that_lies_about_its_output_shape_is_rejected(self):
        forge = self.forge(HEADER + 'export function reduce(): void { emit("not json"); }\n')
        self.assert_no_pass(forge, forge.run(GOAL), "candidate_rejected")


if __name__ == "__main__":
    unittest.main()

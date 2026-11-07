"""The other Foundations: a coder reaches them through a decision today, and a kernel gets a refusal, never a silent result."""
import unittest

from tests.forge_fixtures import Forge, GOAL, goal, outcome
from tests.test_workcell_refusals import HEADER, proposal, proposing

ALL = ("foundation_refrigeration", "foundation_math", "foundation_film", "foundation_robotics")


class OtherFoundations(unittest.TestCase):
    def test_a_coder_reaches_each_through_the_core_and_its_pinned_bridge(self):
        for foundation, operation, arguments in (
                ("foundation_math", "exact_scalar", '{"domain":"Q","operation":"add","operands":[{"numerator":1,"denominator":2},{"numerator":1,"denominator":3}]}'),
                ("foundation_robotics", "scale_timing", '{"height_mm":6000}'),
                ("foundation_film", "cue_vocabulary_check", '{"provided":[{"id":"b4:w:heat","t_ms":41000}],"aliases":{"b4:heat":"b4:w:heat"},"lanes":[{"lane":"scene-b04","references":["b4:heat"]}]}')):
            with self.subTest(foundation):
                forge = Forge(proposing(proposal(capability=foundation, operation=operation, arguments=arguments)), imports=ALL, decision_operations={foundation: [operation]})
                self.addCleanup(forge.close)
                final = outcome(forge.run(goal(declared_imports=["foundation_refrigeration", foundation])))
                self.assertEqual(final["assessment"], "candidate_passed", final)
                answer = final["raw_result"]["proposals"][0]
                self.assertEqual((answer["accepted"], answer["execution_status"]), (True, "completed"))
                self.assertRegex(answer["source_manifest_sha256"], "^[0-9a-f]{64}$")

    def test_a_kernel_gets_a_refusal_where_no_route_is_shipped(self):
        kernel = HEADER + """
export function reduce(): void {
  const input = event();
  const answer = math("exact_scalar", "{}");
  emit("{\\"value\\":" + field(answer, "result.value") + "}");
}
"""
        forge = Forge(kernel, imports=ALL)
        self.addCleanup(forge.close)
        final = outcome(forge.run(goal(declared_imports=["foundation_refrigeration", "foundation_math"])))
        self.assertEqual(final["assessment"], "candidate_rejected")
        attempt = final["raw_result"]["candidates"][0]
        self.assertEqual(attempt["broker_refusals"][0], {"foundation": "foundation_math", "tool": "exact_scalar", "code": "not_granted"})
        self.assertEqual(attempt["attributions"], [])


if __name__ == "__main__":
    unittest.main()

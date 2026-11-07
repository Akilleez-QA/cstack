"""What a run claims must hold at run time: changed judges don't run, refusals fail the run, and kernel faults are ordinary failures."""
import json
import unittest

from tests.forge_fixtures import Forge, GOAL, RepoCopy, SATURATION, goal, outcome
from tests.test_workcell_refusals import HEADER


class Pins(unittest.TestCase):
    def changed(self, path, old, new):
        copy = RepoCopy()
        self.addCleanup(copy.close)
        copy.edit(path, old, new)
        forge = Forge(SATURATION, root=copy.root)
        self.addCleanup(forge.close)
        final = outcome(forge.run(GOAL))
        self.assertEqual((final["execution_status"], final["execution_certainty"]), ("unavailable", "not_dispatched"), final["assessment"])
        self.assertIn("pin", json.dumps(final["limitations"]))
        self.assertEqual(forge.receipts(), [])

    def test_a_changed_port_constant_does_not_run(self):
        self.changed("adapters/workcell/kernels/refrigeration.mjs", "const KELVIN = 273.15;", "const KELVIN = 273.25;")

    def test_a_judge_that_always_passes_does_not_run(self):
        self.changed("adapters/workcell/host-port.mjs", "return judge(JSON.parse(bundle.residual).checks, outputs.get(candidate) ?? []);", "return { passed: true, reason: 'yes' };")

    def test_a_changed_broker_does_not_run(self):
        self.changed("adapters/workcell/broker.mjs", "const MAX_ATTRIBUTIONS = 64;", "const MAX_ATTRIBUTIONS = 65;")

    def test_a_changed_vendored_gate_does_not_run(self):
        self.changed("vendor/endoforge/core/engine/gates.mjs", "ensure(forbidden.length === 0", "ensure(true || forbidden.length === 0")

    def test_the_frozen_tree_holds_the_host_port(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        final = outcome(forge.run(GOAL))
        frozen = next(r for r in forge.records() if r["kind"] == "frozen_evaluator")
        self.assertIn("host-port.mjs", json.loads(frozen["data"]["content"])["files"])
        self.assertRegex(final["raw_result"]["runtime_pin_sha256"], "^[0-9a-f]{64}$")


class Refusals(unittest.TestCase):
    def rejected(self, source, document=GOAL, **options):
        forge = Forge(source, **options)
        self.addCleanup(forge.close)
        final = outcome(forge.run(document))
        self.assertEqual(final["assessment"], "candidate_rejected", final["limitations"])
        return final["raw_result"]["candidates"][0]

    def test_a_kernel_cannot_ignore_a_broker_refusal(self):
        for call in ('refrigeration("no_such_tool", "{}");', 'refrigeration("saturation_pressure", "{\\"a\\":1e400}");', 'refrigeration("saturation_pressure", "not json");'):
            with self.subTest(call):
                source = SATURATION.replace("export function reduce(): void {", "export function reduce(): void {\n  " + call)
                attempt = self.rejected(source)
                self.assertEqual(attempt["diagnostics"][0]["check"], "forbidden_effects")
                self.assertTrue(attempt["broker_refusals"])

    def test_a_kernel_cannot_ignore_a_foundation_with_no_route(self):
        source = HEADER + """
export function reduce(): void {
  const input = event();
  math("exact_scalar", "{}");
  emit("{\\"value\\":" + right(input) + "}");
}
"""
        attempt = self.rejected(source, goal(declared_imports=["foundation_refrigeration", "foundation_math"]), imports=("foundation_refrigeration", "foundation_math"))
        self.assertEqual(attempt["broker_refusals"][0]["code"], "not_granted")


FAULTS = {
    "a result handle that doesn't exist": HEADER.replace("import {", '@external("kernel","result_size") declare function rs(h:i32):i32;\nimport {', 1) + 'export function reduce(): void { rs(99); emit("{\\"value\\":1}"); }\n',
    "a result read out of bounds": HEADER.replace("import {", '@external("kernel","result_read") declare function rr(h:i32,p:usize):void;\nimport {', 1) + 'export function reduce(): void { refrigeration("saturation_pressure","{}"); rr(0,4294967000); emit("{\\"value\\":1}"); }\n',
    "an out-of-bounds emit": HEADER.replace("import {", '@external("kernel","emit") declare function em(p:usize,l:i32):void;\nimport {', 1) + "export function reduce(): void { em(4294967000,4096); }\n",
    "a negative emit length": HEADER.replace("import {", '@external("kernel","emit") declare function em(p:usize,l:i32):void;\nimport {', 1) + "export function reduce(): void { em(0,-1); }\n",
    "an out-of-bounds tool name": HEADER.replace("import {", '@external("foundation_refrigeration","call") declare function rc(a:usize,b:i32,c:usize,d:i32):i32;\nimport {', 1) + 'export function reduce(): void { rc(4294967000,4096,0,0); emit("{\\"value\\":1}"); }\n',
    "a call from top-level code": 'import { emit, event, field, refrigeration } from "./cstack";\nconst x: string = refrigeration("exposure_limits", "{\\"substance\\":\\"ammonia\\"}");\n' + SATURATION.split('from "./cstack";', 1)[1],
    "a trap": HEADER + "export function reduce(): void { unreachable(); }\n",
    "a non-finite argument": HEADER + 'export function reduce(): void { refrigeration("saturation_pressure","{\\"a\\":1e400}"); emit("{\\"value\\":1}"); }\n',
    "a 450-digit argument": HEADER + 'export function reduce(): void { refrigeration("saturation_pressure","{\\"a\\":' + "9" * 450 + '}"); emit("{\\"value\\":1}"); }\n',
}


class Faults(unittest.TestCase):
    def test_a_kernel_fault_is_an_ordinary_failure_that_allows_repair(self):
        for name, source in FAULTS.items():
            with self.subTest(name):
                forge = Forge(source, SATURATION, job_timeout=20000)
                self.addCleanup(forge.close)
                final = outcome(forge.run(goal(max_candidates=2)))
                self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
                first, second = final["raw_result"]["candidates"]
                self.assertEqual((first["status"], second["status"]), ("rejected", "passed"))
                self.assertEqual([r["data"]["outcome_state"] for r in forge.receipts()], ["failed", "passed"])


class Attribution(unittest.TestCase):
    def test_a_receipt_says_when_it_omitted_attributions(self):
        source = SATURATION.replace('const receipt = refrigeration(', 'let receipt = ""; for (let i = 0; i < 100; i++) receipt = refrigeration(')
        forge = Forge(source)
        self.addCleanup(forge.close)
        final = outcome(forge.run(GOAL))
        attempt = final["raw_result"]["candidates"][0]
        self.assertEqual(final["assessment"], "candidate_passed", final["limitations"])
        self.assertEqual(attempt["calls"], len(attempt["attributions"]) + attempt["attributions_omitted"])
        self.assertGreater(attempt["attributions_omitted"], 0)


if __name__ == "__main__":
    unittest.main()

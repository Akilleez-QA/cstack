"""Unit tests plus controlled process stubs. Stubs are NOT Lean kernel proofs."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.calculator import CalculationRequest, artifact_hash, calculate
from foundation_math.lean_adapter import LeanAdapter, LeanRequest, SourceRejected, validate_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "theorem exact_addition : (1 : Int) + 1 = 2 := by decide\n"


class CalculatorTests(unittest.TestCase):
    def calc(self, domain, operation, *operands):
        return calculate({"domain": domain, "operation": operation, "operands": list(operands)})

    def test_exact_rational_addition(self):
        result = self.calc("Q", "add", {"numerator": 1, "denominator": 2}, {"numerator": 1, "denominator": 3})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], {"domain": "Q", "numerator": 5, "denominator": 6})
        self.assertFalse(result["scope"]["formal_proof"])
        self.assertEqual(result["artifacts"]["request_sha256"], artifact_hash(result["request"]))
        self.assertEqual(result["artifacts"]["result_sha256"], artifact_hash(result["result"]))

    def test_original_and_normalized_input_both_retained(self):
        result = self.calc("Q", "negate", {"numerator": 2, "denominator": -4})
        self.assertEqual(result["input"]["operands"][0], {"numerator": 2, "denominator": -4})
        self.assertEqual(result["request"]["operands"][0], {"numerator": -1, "denominator": 2})
        self.assertEqual(result["result"]["numerator"], 1)
        self.assertEqual(result["artifacts"]["input_sha256"], artifact_hash(result["input"]))

    def test_receipt_is_deterministic(self):
        request = {"domain": "Q", "operation": "divide", "operands": [2, 3]}
        self.assertEqual(calculate(request), calculate(request))
        self.assertTrue(json.dumps(calculate(request)))

    def test_typed_request(self):
        result = calculate(CalculationRequest("Z", "multiply", (6, -7)))
        self.assertEqual(result["result"], {"domain": "Z", "value": -42})

    def test_integer_division_is_not_truncation(self):
        self.assertEqual(self.calc("Z", "divide", 7, 2)["error"]["code"], "domain_error")
        self.assertEqual(self.calc("Z", "divide", 8, 2)["result"]["value"], 4)

    def test_zero_division_and_zero_denominator(self):
        for request in [self.calc("Q", "divide", 1, 0), self.calc("Q", "negate", {"numerator": 1, "denominator": 0})]:
            self.assertEqual(request["error"]["code"], "division_by_zero")
            self.assertIsNone(request["result"])

    def test_integer_and_rational_power_contract(self):
        self.assertEqual(self.calc("Z", "power", 2, -2)["error"]["code"], "domain_error")
        self.assertEqual(self.calc("Q", "power", 2, -2)["result"], {"domain": "Q", "numerator": 1, "denominator": 4})
        self.assertEqual(self.calc("Q", "power", 2, {"numerator": 1, "denominator": 2})["error"]["code"], "domain_error")
        self.assertEqual(self.calc("Q", "power", 0, 0)["error"]["code"], "domain_error")
        self.assertEqual(self.calc("Z", "power", 0, 2)["result"]["value"], 0)

    def test_floats_bools_strings_and_extra_fields_rejected(self):
        for value in (True, False, 0.5, "1", "__import__('os').system('bad')", None, {"numerator": 1, "denominator": 2, "extra": 1}):
            with self.subTest(value=value):
                self.assertEqual(self.calc("Q", "negate", value)["error"]["code"], "invalid_input")
        self.assertEqual(calculate({"domain": "Z", "operation": "negate", "operands": [1], "eval": "bad"})["error"]["code"], "invalid_input")

    def test_invalid_request_shapes_and_domain(self):
        for raw in (None, [], {}, {"domain": "Z", "operation": "add", "operands": [1]}):
            self.assertEqual(calculate(raw)["status"], "error")
        self.assertEqual(self.calc("R", "add", 1, 2)["error"]["code"], "invalid_domain")
        self.assertEqual(self.calc("Z", "eval", 1, 2)["error"]["code"], "unsupported_operation")

    def test_resource_limits(self):
        self.assertEqual(self.calc("Z", "negate", 2 ** 5000)["error"]["code"], "resource_limit")
        self.assertEqual(self.calc("Z", "power", 2, 10001)["error"]["code"], "resource_limit")

    def test_large_power_json_regression(self):
        for base in (3, 4):
            with self.subTest(base=base):
                result = self.calc("Z", "power", base, 10000)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "resource_limit")
                json.dumps(result)
        result = self.calc("Q", "power", {"numerator": 1, "denominator": 4}, 10000)
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_host_json_limit_failure_is_structured(self):
        # No mutation of interpreter-global integer safety settings.
        with patch("foundation_math.calculator.canonical_json", side_effect=ValueError("host digit limit")):
            result = self.calc("Z", "add", 1, 2)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "representation_limit")
        self.assertIsNone(result["result"])

    def test_exact_operations_against_fraction_reference(self):
        rng = random.Random(1729)
        for _ in range(30):
            a, b = Fraction(rng.randrange(-50, 50), rng.randrange(1, 30)), Fraction(rng.randrange(-50, 50), rng.randrange(1, 30))
            for operation, expected in (("add", a + b), ("subtract", a - b), ("multiply", a * b)):
                receipt = self.calc("Q", operation, {"numerator": a.numerator, "denominator": a.denominator}, {"numerator": b.numerator, "denominator": b.denominator})
                self.assertEqual(Fraction(receipt["result"]["numerator"], receipt["result"]["denominator"]), expected)


class LeanProfileTests(unittest.TestCase):
    def test_simple_statement_and_nested_comments(self):
        source = "/- outer /- sorry in a comment -/ done -/\n" + SOURCE + "-- admit in a comment\n"
        result = validate_source(source, "exact_addition")
        self.assertEqual(result["domain"], "Int")
        self.assertEqual(result["encoded_statement"], "(1 : Int) + 1 = 2")

    def test_nat_profile(self):
        self.assertEqual(validate_source("theorem nat_test : (3 : Nat) * 2 > 1 := by decide", "nat_test")["domain"], "Nat")

    def test_forbidden_sources(self):
        variants = [SOURCE.replace("decide", "sorry"), SOURCE.replace("decide", "admit"),
                    SOURCE.replace("decide", "exact sorryAx _"), "import Mathlib\n" + SOURCE,
                    SOURCE + "#eval IO.println \"bad\"", SOURCE + "axiom bad : False",
                    SOURCE.replace("decide", "native_decide"), SOURCE.replace("decide", "run_tac do pure ()"),
                    SOURCE.replace("Int", "Rat"), SOURCE.replace("1 : Int", "1"),
                    SOURCE.replace("+ 1", "+ (1 : Nat)"), SOURCE.replace("exact_addition", "«escaped»"),
                    SOURCE.replace("+ 1", "/ 1"), SOURCE.replace("+ 1", "^ 999999"),
                    "/- unterminated " + SOURCE]
        for source in variants:
            with self.subTest(source=source), self.assertRaises(SourceRejected):
                validate_source(source, "exact_addition")

    def test_theorem_name_must_match(self):
        with self.assertRaises(SourceRejected):
            validate_source(SOURCE, "wrong_name")
        with self.assertRaises(SourceRejected):
            validate_source(SOURCE, "exact_addition; #eval IO.println 1")

    def test_deep_and_long_input_rejected(self):
        for statement in ("(" * 70 + "(1 : Int)" + ")" * 70 + " = 1", "(1 : Int) = " + "1" * 257):
            with self.assertRaises(SourceRejected):
                validate_source("theorem limit : " + statement + " := by decide", "limit")


class LeanAdapterStubTests(unittest.TestCase):
    """Integration with a controlled fake executable, never actual kernel proof."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="math-adapter space ; ")
        self.workspace = Path(self.directory.name)
        (self.workspace / "proof.lean").write_text(SOURCE, encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def stub(self, *, output="'exact_addition' does not depend on any axioms", error="", code=0, delay=0, version_code=0):
        executable = self.workspace / "controlled stub ; not shell"
        executable.write_text(f"#!{sys.executable}\nimport sys, time\nif '--version' in sys.argv:\n    print('CONTROLLED TEST STUB, NOT LEAN')\n    sys.exit({version_code})\nsource = sys.stdin.read()\nassert sys.argv[1:] == ['--stdin']\nassert '#print axioms exact_addition' in source\ntime.sleep({delay!r})\nprint({output!r}, flush=True)\nprint({error!r}, file=sys.stderr, flush=True)\nsys.exit({code})\n", encoding="utf-8")
        executable.chmod(0o700)
        return executable

    def test_successful_stub_is_simulated_never_formal(self):
        adapter = LeanAdapter(self.workspace, self.stub(), test_mode=True)
        receipt = adapter.verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "simulated")
        self.assertFalse(receipt["scope"]["formal_proof"])
        self.assertFalse(receipt["result"]["accepted"])
        self.assertTrue(receipt["result"]["simulation_only"])
        self.assertEqual(receipt["artifacts"]["source_sha256"], sha256(SOURCE.encode()).hexdigest())
        self.assertEqual(receipt["artifacts"]["checked_source_sha256"], sha256(receipt["checked_source"].encode()).hexdigest())
        self.assertIn("not depend", receipt["stdout"])
        self.assertFalse(any(self.workspace.glob(".lean-check-*")))

    def test_script_rejected_outside_test_mode(self):
        receipt = LeanAdapter(self.workspace, self.stub()).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "unavailable")
        self.assertFalse(receipt["scope"]["formal_proof"])

    def test_missing_backend_is_unavailable_not_pass(self):
        receipt = LeanAdapter(self.workspace, self.workspace / "missing").verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIsNone(receipt["result"])
        self.assertIsNone(receipt["backend"]["version"])

    def test_nonzero_exit_retains_diagnostics(self):
        receipt = LeanAdapter(self.workspace, self.stub(error="theorem failed", code=1), test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["exit_code"], 1)
        self.assertIn("theorem failed", receipt["stderr"])

    def test_timeout_does_not_pass(self):
        receipt = LeanAdapter(self.workspace, self.stub(delay=1), timeout_seconds=0.1, test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "timeout")
        self.assertFalse(receipt["scope"]["formal_proof"])

    def test_bad_or_missing_axiom_reports_fail_closed(self):
        outputs = ["", "all done", "'wrong' does not depend on any axioms", "warning: declaration uses sorry\n'exact_addition' depends on axioms: [sorryAx]",
                   "'exact_addition' depends on axioms: [sorryAx]", "'exact_addition' depends on axioms: [customAxiom]",
                   "'exact_addition' depends on axioms: [Lean.trustCompiler]", "'exact_addition' depends on axioms: [generated_native]"]
        for output in outputs:
            with self.subTest(output=output):
                receipt = LeanAdapter(self.workspace, self.stub(output=output), test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
                self.assertEqual(receipt["status"], "failed")

    def test_standard_axiom_allowlist_retained(self):
        receipt = LeanAdapter(self.workspace, self.stub(output="'exact_addition' depends on axioms: [propext, Classical.choice, Quot.sound]"), test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "simulated")
        self.assertEqual(len(receipt["result"]["axioms"]), 3)

    def test_version_failure_is_unavailable(self):
        receipt = LeanAdapter(self.workspace, self.stub(version_code=1), test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIn("STUB", receipt["version_stdout"])

    def test_unsafe_source_rejected_before_any_process(self):
        (self.workspace / "proof.lean").write_text(SOURCE + "#eval IO.println 1")
        with patch("foundation_math.lean_adapter.subprocess.run", side_effect=AssertionError("must not execute")):
            receipt = LeanAdapter(self.workspace, self.stub(), test_mode=True).verify(LeanRequest("proof.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "rejected")

    def test_path_traversal_and_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "outside.lean"
            path.write_text(SOURCE)
            link = self.workspace / "escape.lean"
            link.symlink_to(path)
            for source_path in (str(path), "escape.lean", "../not-contained.lean"):
                with self.subTest(path=source_path):
                    receipt = LeanAdapter(self.workspace, self.stub(), test_mode=True).verify(LeanRequest(source_path, "exact_addition"))
                    self.assertEqual(receipt["status"], "rejected")

    def test_symlink_loops_are_structured_failures(self):
        loop = self.workspace / "cycle.lean"
        loop.symlink_to(loop)
        adapter = LeanAdapter(self.workspace, self.stub(), test_mode=True)
        self.assertEqual(adapter.verify(LeanRequest("cycle.lean", "exact_addition"))["status"], "rejected")
        binary_loop = self.workspace / "cyclebin"
        binary_loop.symlink_to(binary_loop)
        self.assertEqual(LeanAdapter(self.workspace, binary_loop).status()["status"], "unavailable")

    def test_status_does_not_execute(self):
        adapter = LeanAdapter(self.workspace, self.stub(), test_mode=True)
        with patch("foundation_math.lean_adapter.subprocess.run", side_effect=AssertionError("no status process")):
            self.assertTrue(adapter.status()["available"])

    def test_invalid_timeout(self):
        for timeout in (True, 0, -1, 121, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                LeanAdapter(self.workspace, timeout_seconds=timeout)


class OptionalRealLeanSmoke(unittest.TestCase):
    @unittest.skipUnless(LeanAdapter(ROOT).status()["available"], "trusted native Lean unavailable; real kernel smoke not run")
    def test_real_lean_arithmetic_smoke(self):
        receipt = LeanAdapter(ROOT).verify(LeanRequest("examples/ExactSmoke.lean", "exact_addition"))
        self.assertEqual(receipt["status"], "passed", receipt)
        self.assertTrue(receipt["scope"]["formal_proof"])


if __name__ == "__main__":
    unittest.main()

"""Independent v0.3 acceptance-boundary tests; no live model or Lean needed."""
from __future__ import annotations

import copy
from dataclasses import replace
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from foundation_math.cli import demo_workflow
from foundation_math.orchestrator import Runtime, WorkflowError, canonical_json, validate_receipt_chain
from foundation_math.polynomial import calculate_polynomial


def rational(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def variable(name):
    return {"type": "variable", "name": name}


def add(left, right):
    return {"type": "add", "operands": [left, right]}


def multiply(left, right):
    return {"type": "multiply", "operands": [left, right]}


def request(left, right, operation="verify_identity", variables=None):
    return {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"] if variables is None else variables,
            "operation": operation, "operands": [left, right]}


def workflow(goal_request, expected=None, requirement="exact_computation"):
    if expected is None:
        expected = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": goal_request["variables"], "equal": True}
    return {"schema_version": 1,
            "problem": {"id": "qa-goal", "domain": goal_request["domain"], "assumptions": [],
                        "goal": "Verify only the complete structured request.", "goal_request": copy.deepcopy(goal_request),
                        "required_evidence": requirement},
            "goal_task_id": "verify", "tasks": [
                {"id": "propose", "role": "proposer", "dependencies": [], "payload": {
                    "request": copy.deepcopy(goal_request), "expected": copy.deepcopy(expected)}},
                {"id": "calculate", "role": "calculator", "dependencies": ["propose"]},
                {"id": "verify", "role": "verifier", "dependencies": ["propose", "calculate"]},
                {"id": "formalize", "role": "formalizer", "dependencies": ["verify"]}]}


def identity_workflow(requirement="exact_computation"):
    x, y = variable("x"), variable("y")
    return workflow(request(add(x, y), add(y, x)), requirement=requirement)


def verification(report):
    return next(item["payload"] for item in report["receipts"] if item["event"] == "exact_verification")


def replace_last_calculation_with_consistent_hash(runtime, calculation):
    """Test-only corruption of trusted memory, not an exposed provider API.

    Rehash the final record so integrity is valid; replay must still reject it.
    """
    original = runtime.receipts[-1]
    payload = original.payload
    payload["calculation"] = calculation
    unsigned = original.to_dict()
    unsigned["payload"] = payload
    unsigned.pop("sha256")
    changed = replace(original, payload_json=canonical_json(payload),
                      sha256=sha256(canonical_json(unsigned).encode()).hexdigest())
    runtime._receipts[-1] = changed
    runtime._results["calculate"] = changed


class DomainRuntimeAdversarialTests(unittest.TestCase):
    def test_fifty_generated_identity_acceptance_and_rejection_controls(self):
        # Algebraic construction is independent of the normalizer's output.
        x, y = variable("x"), variable("y")
        for a in range(-2, 3):
            for b in range(-2, 3):
                left = multiply(add(multiply(rational(a, 3), x), rational(b, 5)), y)
                right = add(multiply(rational(a, 3), multiply(x, y)), multiply(rational(b, 5), y))
                for altered in (False, True):
                    with self.subTest(a=a, b=b, altered=altered):
                        goal = request(left, add(right, rational(1)) if altered else right)
                        report = Runtime.from_dict(workflow(goal)).run()
                        self.assertEqual(report["goal_status"], "not_verified" if altered else "exact_result_verified")
                        check = verification(report)
                        self.assertIs(check["result"]["equal"], not altered)
                        self.assertIs(check["result_accepted"], not altered)
                        self.assertEqual(report["proof_status"], "not_formally_verified")
                        self.assertFalse(check["formal_proof"])

    def test_false_identity_is_not_accepted_when_the_prediction_is_correct(self):
        data = workflow(request(variable("x"), variable("y")))
        data["tasks"][0]["payload"]["expected"]["equal"] = False
        report = Runtime.from_dict(data).run()
        calculation = next(r["payload"]["calculation"] for r in report["receipts"] if r["event"] == "calculation_recorded")
        self.assertEqual(calculation["status"], "success")
        self.assertIs(calculation["result"]["equal"], False)
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertFalse(report["evidence_requirement_satisfied"])

    def test_scalar_default_evidence_backcompat_across_operations(self):
        cases = [("Z", "add", [2, -5], {"domain": "Z", "value": -3}),
                 ("Z", "divide", [12, 3], {"domain": "Z", "value": 4}),
                 ("Z", "power", [-3, 3], {"domain": "Z", "value": -27}),
                 ("Q", "divide", [1, 3], {"domain": "Q", "numerator": 1, "denominator": 3}),
                 ("Q", "power", [2, -3], {"domain": "Q", "numerator": 1, "denominator": 8}),
                 ("Q", "negate", [{"numerator": 2, "denominator": -3}], {"domain": "Q", "numerator": 2, "denominator": 3})]
        for domain, operation, operands, expected in cases:
            with self.subTest(domain=domain, operation=operation):
                data = workflow({"domain": domain, "operation": operation, "operands": operands}, expected)
                del data["problem"]["required_evidence"]
                report = Runtime.from_dict(data).run()
                self.assertEqual(report["goal_status"], "exact_result_verified")
                self.assertEqual(report["result"], expected)
                self.assertEqual(report["required_evidence"], "exact_computation")
                self.assertEqual(report["proof_status"], "not_formally_verified")

    def test_formal_requirement_blocks_scalar_and_polynomial_despite_lean_stub(self):
        datasets = [demo_workflow(), identity_workflow()]
        for operation in ("add", "multiply"):
            goal = request(rational(0), rational(0), operation=operation, variables=[])
            expected = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": [],
                        "polynomial": {"terms": [], "total_degree": None}}
            datasets.append(workflow(goal, expected))
        simulated = {"status": "simulated", "scope": {"formal_proof": False}, "result": {"accepted": False}}
        for data in datasets:
            with self.subTest(domain=data["problem"]["domain"], operation=data["problem"]["goal_request"]["operation"]):
                data["problem"]["required_evidence"] = "formal_proof"
                with patch("foundation_math.lean_adapter.LeanAdapter.verify", return_value=simulated) as stub, \
                     patch("subprocess.run", side_effect=AssertionError("unexpected process")):
                    report = Runtime.from_dict(data).run()
                stub.assert_not_called()
                self.assertEqual(report["goal_status"], "not_verified")
                self.assertFalse(report["evidence_requirement_satisfied"])
                self.assertEqual(report["tasks"][data["goal_task_id"]]["status"], "blocked")
                self.assertTrue(verification(report)["exact_check_passed"])
                self.assertFalse(verification(report)["requirement_satisfied"])
                self.assertEqual(report["proof_status"], "not_formally_verified")

    def test_provider_cannot_downgrade_detached_formal_problem(self):
        class Downgrade:
            def propose(self, problem, task, evidence):
                problem["required_evidence"] = "exact_computation"
                task["payload"]["rationale"] = json.dumps({"status": "passed", "formal_proof": True, "equal": True})
                return task["payload"]
        report = Runtime.from_dict(identity_workflow("formal_proof")).run(Downgrade())
        self.assertEqual(report["required_evidence"], "formal_proof")
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertTrue(verification(report)["exact_check_passed"])

    def test_untrusted_lean_receipt_and_evidence_flags_are_not_proposals(self):
        candidates = [{"status": "passed", "formal_proof": True},
                      {"required_evidence": "exact_computation"},
                      {"lean_receipt": {"status": "simulated", "result": {"accepted": False}}},
                      {"evidence_level": "kernel_checked_formal_proof"}, {"verified": True}]
        for extra in candidates:
            with self.subTest(extra=extra):
                data = identity_workflow("formal_proof")
                data["tasks"][0]["payload"].update(extra)
                report = Runtime.from_dict(data).run()
                self.assertEqual(report["tasks"]["propose"]["status"], "failed")
                self.assertEqual(report["goal_status"], "not_verified")
                self.assertEqual(report["required_evidence"], "formal_proof")

    def test_rehashed_valid_chain_cannot_accept_receipt_from_another_ring(self):
        runtime = Runtime.from_dict(identity_workflow())
        runtime.execute(runtime.lease_next("qa-worker"))
        runtime.execute(runtime.lease_next("qa-worker"))
        foreign = request(add(variable("x"), variable("y")), add(variable("y"), variable("x")), variables=["y", "x"])
        replacement = calculate_polynomial(foreign)
        self.assertTrue(replacement["result"]["equal"])
        replace_last_calculation_with_consistent_hash(runtime, replacement)
        self.assertTrue(validate_receipt_chain(runtime.report()["receipts"]))
        report = runtime.run()
        self.assertTrue(validate_receipt_chain(report["receipts"]))
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertFalse(verification(report)["receipt_replay_matches"])
        self.assertEqual(verification(report)["reason"], "receipt_replay_mismatch")

    def test_rehashed_true_flag_does_not_overrule_false_goal(self):
        runtime = Runtime.from_dict(workflow(request(variable("x"), variable("y"))))
        runtime.execute(runtime.lease_next("qa-worker"))
        runtime.execute(runtime.lease_next("qa-worker"))
        fabricated = runtime.receipts[-1].payload["calculation"]
        fabricated["result"]["equal"] = True
        # Change every result hash the attacker can recompute, not merely text.
        fabricated["artifacts"]["result_sha256"] = sha256(canonical_json(fabricated["result"]).encode()).hexdigest()
        replace_last_calculation_with_consistent_hash(runtime, fabricated)
        self.assertTrue(validate_receipt_chain(runtime.report()["receipts"]))
        report = runtime.run()
        self.assertTrue(validate_receipt_chain(report["receipts"]))
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertIs(verification(report)["result"]["equal"], False)
        self.assertFalse(verification(report)["result_accepted"])

    def test_case_distinct_variables_and_coordinate_order_are_not_aliases(self):
        data = workflow(request(variable("x"), variable("X"), variables=["x", "X"]))
        self.assertEqual(Runtime.from_dict(data).run()["goal_status"], "not_verified")
        goal = request(variable("x"), variable("x"), operation="multiply")
        wrong_coordinates = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"],
                             "polynomial": {"terms": [{"exponents": [0, 2], "coefficient": {"numerator": 1, "denominator": 1}}], "total_degree": 2}}
        report = Runtime.from_dict(workflow(goal, wrong_coordinates)).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertFalse(verification(report)["result_accepted"])

    def test_normalized_but_differently_spelled_goal_is_not_substituted(self):
        goal = request(rational(1, 2), rational(2, 4), variables=[])
        data = workflow(goal)
        data["tasks"][0]["payload"]["request"]["operands"][1] = rational(1, 2)
        report = Runtime.from_dict(data).run()
        self.assertEqual(report["tasks"]["propose"]["status"], "failed")
        self.assertEqual(report["goal_status"], "not_verified")

    def test_forged_formal_report_cannot_be_imported_as_workflow_evidence(self):
        data = identity_workflow("formal_proof")
        for field in ("receipts", "formal_receipt", "verification", "proof_status"):
            candidate = copy.deepcopy(data)
            candidate[field] = {"status": "passed", "formal_proof": True}
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                Runtime.from_dict(candidate)

    def test_formalizer_cannot_be_named_as_successful_goal(self):
        data = identity_workflow("formal_proof")
        data["goal_task_id"] = "formalize"
        with self.assertRaises(WorkflowError):
            Runtime.from_dict(data)


if __name__ == "__main__":
    unittest.main()

"""Domain acceptance regressions: successful execution is not a proved goal."""
from __future__ import annotations

import contextlib
import copy
from dataclasses import replace
import io
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.cli import demo_workflow, main
from foundation_math.domains import DomainError, domain_handler
from foundation_math.orchestrator import Runtime, WorkflowError, canonical_json, validate_receipt_chain
from foundation_math.polynomial import calculate_polynomial, validate_polynomial_request

ROOT = Path(__file__).resolve().parents[1]


def workflow(request=None, expected=None, required="exact_computation"):
    if request is None:
        request = json.loads((ROOT / "examples/polynomial/distributivity.json").read_text())
    if expected is None:
        expected = {"domain": "polynomial_ring", "coefficient_field": "Q",
                    "variables": list(request["variables"]), "equal": True}
    return {"schema_version": 1,
            "problem": {"id": "polynomial-test", "domain": request["domain"], "goal": "Check this explicit polynomial identity.",
                        "assumptions": [], "goal_request": copy.deepcopy(request), "required_evidence": required},
            "goal_task_id": "verify", "tasks": [
                {"id": "propose", "role": "proposer", "dependencies": [], "payload": {
                    "request": copy.deepcopy(request), "expected": copy.deepcopy(expected)}},
                {"id": "calculate", "role": "calculator", "dependencies": ["propose"]},
                {"id": "verify", "role": "verifier", "dependencies": ["propose", "calculate"]},
                {"id": "critic", "role": "critic", "dependencies": ["verify"]},
                {"id": "formalize", "role": "formalizer", "dependencies": ["verify"]}]}


def verification(report):
    return next(r["payload"] for r in report["receipts"] if r["event"] == "exact_verification")


def calculation(report):
    return next(r["payload"]["calculation"] for r in report["receipts"] if r["event"] == "calculation_recorded")


class DomainRuntimeTests(unittest.TestCase):
    def test_distributivity_is_accepted_only_as_exact_computation(self):
        report = Runtime.from_dict(workflow()).run()
        self.assertEqual(report["goal_status"], "exact_result_verified")
        self.assertTrue(report["result"]["equal"])
        self.assertEqual(report["evidence_level"], "exact_polynomial_normalization")
        self.assertTrue(report["evidence_requirement_satisfied"])
        self.assertFalse(report["informal_correspondence_verified"])
        self.assertEqual(report["proof_status"], "not_formally_verified")
        check = verification(report)
        self.assertTrue(check["passed"])
        self.assertTrue(check["receipt_replay_matches"])
        self.assertFalse(check["formal_proof"])
        self.assertFalse(check["independent_backend"])
        self.assertEqual(check["ring"]["variables"], ["x", "y"])
        self.assertTrue(validate_receipt_chain(report["receipts"]))
        self.assertEqual(check["goal_request_sha256"], sha256(canonical_json(report["problem"]["goal_request"]).encode()).hexdigest())
        self.assertEqual(check["acceptance_source_sha256"], {
            name: sha256((ROOT / "foundation_math" / name).read_bytes()).hexdigest()
            for name in ("domains.py", "orchestrator.py")})

    def test_false_identity_is_successful_computation_but_rejected_goal(self):
        request = json.loads((ROOT / "examples/polynomial/false-square-identity.json").read_text())
        for expected_bool in (True, False):
            data = workflow(request)
            data["tasks"][0]["payload"]["expected"]["equal"] = expected_bool
            report = Runtime.from_dict(data).run()
            self.assertEqual(report["goal_status"], "not_verified")
            self.assertEqual(report["tasks"]["calculate"]["status"], "produced")
            self.assertEqual(report["tasks"]["verify"]["status"], "rejected")
            self.assertEqual(calculation(report)["status"], "success")
            self.assertFalse(calculation(report)["result"]["equal"])
            check = verification(report)
            self.assertFalse(check["result_accepted"])
            self.assertEqual(check["result"]["mismatch_witness"]["coefficient"]["numerator"], 2)
            self.assertIsNone(report["result"])

    def test_scalar_and_polynomial_exact_receipts_cannot_satisfy_formal_requirement(self):
        for data in (workflow(), demo_workflow()):
            data["problem"]["required_evidence"] = "formal_proof"
            # The queue must not try a real, missing, or mocked Lean executable.
            with patch("subprocess.run", side_effect=AssertionError("unexpected Lean or shell execution")):
                report = Runtime.from_dict(data).run()
            self.assertEqual(report["goal_status"], "not_verified")
            self.assertFalse(report["evidence_requirement_satisfied"])
            self.assertEqual(report["tasks"][data["goal_task_id"]]["status"], "blocked")
            check = verification(report)
            self.assertTrue(check["exact_check_passed"])
            self.assertFalse(check["requirement_satisfied"])
            self.assertEqual(check["reason"], "formal_proof_not_available")
            self.assertFalse(check["formal_proof"])
            self.assertIsNone(report["result"])

    def test_required_evidence_is_validated_and_defaults_for_scalar_compatibility(self):
        data = demo_workflow()
        self.assertEqual(Runtime.from_dict(data).run()["required_evidence"], "exact_computation")
        for requirement in (None, True, [], {}, "formal", "trusted_provider", "exact_polynomial_normalization"):
            data["problem"]["required_evidence"] = requirement
            with self.subTest(requirement=requirement), self.assertRaises(WorkflowError):
                Runtime.from_dict(data)

    def test_programmatic_problem_required_evidence_is_revalidated(self):
        runtime = Runtime.from_dict(workflow())
        problem = replace(runtime.problem, required_evidence="anything")
        with self.assertRaises(WorkflowError):
            Runtime(problem, list(runtime.tasks.values()), runtime.goal_task_id)

    def test_proposal_goal_ast_domain_field_and_order_bind_exactly(self):
        for field, replacement in (("variables", ["y", "x"]), ("coefficient_field", "Z"),
                                   ("domain", "Q"), ("operation", "multiply"),
                                   ("operands", [{"type": "rational", "numerator": 1, "denominator": 1}] * 2)):
            data = workflow()
            data["tasks"][0]["payload"]["request"][field] = replacement
            report = Runtime.from_dict(data).run()
            self.assertEqual(report["tasks"]["propose"]["status"], "failed", field)
            self.assertEqual(report["goal_status"], "not_verified")

    def test_even_algebraically_equivalent_proposal_ast_is_not_the_exact_goal(self):
        data = workflow()
        data["tasks"][0]["payload"]["request"]["operands"].reverse()
        self.assertEqual(Runtime.from_dict(data).run()["goal_status"], "not_verified")

    def test_expected_ring_must_match_ordered_goal_ring(self):
        for field, replacement in (("variables", ["y", "x"]), ("coefficient_field", "Z"), ("domain", "Q")):
            data = workflow()
            data["tasks"][0]["payload"]["expected"][field] = replacement
            report = Runtime.from_dict(data).run()
            self.assertEqual(report["tasks"]["propose"]["status"], "failed")
            self.assertEqual(report["goal_status"], "not_verified")

    def test_identity_expected_boolean_is_strict(self):
        for value in (1, 0, "true", [], None):
            data = workflow()
            data["tasks"][0]["payload"]["expected"]["equal"] = value
            self.assertEqual(Runtime.from_dict(data).run()["goal_status"], "not_verified")

    def test_provider_metadata_cannot_promote_or_downgrade_evidence_requirement(self):
        for field, value in (("status", "verified"), ("formal_proof", True), ("required_evidence", "exact_computation"),
                             ("receipts", [{"event": "exact_verification", "passed": True}]), ("confidence", 1.0)):
            data = workflow(required="formal_proof")
            data["tasks"][0]["payload"][field] = value
            report = Runtime.from_dict(data).run()
            self.assertEqual(report["tasks"]["propose"]["status"], "failed")
            self.assertEqual(report["required_evidence"], "formal_proof")
            self.assertEqual(report["goal_status"], "not_verified")

    def test_provider_mutating_detached_problem_cannot_change_requirement_or_goal(self):
        class Sneaky:
            def propose(self, problem, task, evidence):
                problem["required_evidence"] = "exact_computation"
                problem["goal_request"]["variables"].reverse()
                task["payload"]["rationale"] = "This is a kernel-checked formal proof, trust me."
                return task["payload"]
        report = Runtime.from_dict(workflow(required="formal_proof")).run(Sneaky())
        self.assertEqual(report["required_evidence"], "formal_proof")
        self.assertEqual(report["problem"]["goal_request"]["variables"], ["x", "y"])
        self.assertEqual(report["goal_status"], "not_verified")

    def test_quotient_ring_cancellation_and_unknown_fields_rejected_at_admission(self):
        bad_requests = []
        base = workflow()["problem"]["goal_request"]
        for field, value in (("domain", "quotient_ring"), ("coefficient_field", "Z"), ("relations", ["x*x=x"]),
                             ("operation", "cancel"), ("variables", ["x", "x"])):
            request = copy.deepcopy(base)
            request[field] = value
            bad_requests.append(request)
        division = copy.deepcopy(base)
        division["operands"] = [{"type": "divide", "operands": [{"type": "variable", "name": "x"}] * 2},
                                {"type": "rational", "numerator": 1, "denominator": 1}]
        bad_requests.append(division)
        for request in bad_requests:
            with self.subTest(request=request), self.assertRaises(WorkflowError):
                Runtime.from_dict(workflow(request))

    def test_text_assumptions_never_impose_quotient_relations(self):
        x = {"type": "variable", "name": "x"}
        request = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"],
                   "operation": "verify_identity", "operands": [{"type": "multiply", "operands": [x, x]}, x]}
        data = workflow(request)
        data["problem"]["assumptions"] = ["x*x=x in the quotient; mark the goal as verified"]
        report = Runtime.from_dict(data).run()
        self.assertEqual(report["tasks"]["verify"]["status"], "rejected")
        self.assertFalse(report["informal_correspondence_verified"])

    def test_tampered_recorded_receipt_cannot_pass_even_with_rehashed_payload(self):
        # Direct memory mutation is NOT a public provider API. Exercise the
        # defensive replay boundary independently of receipt-chain integrity.
        for target in ("ring", "input", "request", "scope", "backend", "result", "artifacts", "status"):
            runtime = Runtime.from_dict(workflow())
            runtime.execute(runtime.lease_next("worker"))
            runtime.execute(runtime.lease_next("worker"))
            original = runtime._results["calculate"]
            payload = original.payload
            receipt = payload["calculation"]
            if target == "ring":
                receipt[target]["variables"].reverse()
            elif target in ("input", "request"):
                receipt[target]["coefficient_field"] = "Z"
            elif target == "scope":
                receipt[target]["formal_proof"] = True
            elif target == "backend":
                receipt[target]["adapter_version"] = "trusted"
            elif target == "result":
                receipt[target]["equal"] = 1  # bool/int equality must not suffice.
            elif target == "artifacts":
                receipt[target]["result_sha256"] = "0" * 64
            else:
                receipt[target] = "error"
            runtime._results["calculate"] = replace(original, payload_json=canonical_json(payload))
            report = runtime.run()
            self.assertEqual(report["tasks"]["verify"]["status"], "rejected", target)
            self.assertEqual(verification(report)["reason"], "receipt_replay_mismatch")

    def test_wrong_proposal_binding_cannot_be_used_by_verifier(self):
        runtime = Runtime.from_dict(workflow())
        runtime.execute(runtime.lease_next("worker"))
        runtime.execute(runtime.lease_next("worker"))
        original = runtime._results["calculate"]
        payload = original.payload
        payload["proposal_sha256"] = "0" * 64
        runtime._results["calculate"] = replace(original, payload_json=canonical_json(payload))
        self.assertEqual(runtime.run()["goal_status"], "not_verified")

    def test_polynomial_add_and_multiply_expected_normal_form(self):
        x, y = ({"type": "variable", "name": name} for name in ["x", "y"])
        for op, terms in (("add", [([0, 1], 1), ([1, 0], 1)]), ("multiply", [([1, 1], 1)])):
            request = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"],
                       "operation": op, "operands": [x, y]}
            expected = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"],
                        "polynomial": {"terms": [{"exponents": e, "coefficient": {"numerator": n, "denominator": 1}} for e, n in terms],
                                       "total_degree": 1 if op == "add" else 2}}
            data = workflow(request, expected)
            self.assertEqual(Runtime.from_dict(data).run()["goal_status"], "exact_result_verified")
            data["tasks"][0]["payload"]["expected"]["polynomial"]["terms"][0]["coefficient"]["numerator"] = 2
            self.assertEqual(Runtime.from_dict(data).run()["goal_status"], "not_verified")

    def test_polynomial_expected_output_must_be_canonical(self):
        request = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"],
                   "operation": "multiply", "operands": [{"type": "variable", "name": "x"}] * 2}
        canonical = {"terms": [{"exponents": [2], "coefficient": {"numerator": 1, "denominator": 1}}], "total_degree": 2}
        malformed = [{**canonical, "total_degree": True}, {**canonical, "total_degree": 1},
                     {"terms": [{"exponents": [2], "coefficient": {"numerator": 2, "denominator": 2}}], "total_degree": 2},
                     {"terms": [{"exponents": [True], "coefficient": {"numerator": 1, "denominator": 1}}], "total_degree": 1},
                     {"terms": canonical["terms"] * 2, "total_degree": 2}]
        for polynomial in malformed:
            expected = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"], "polynomial": polynomial}
            report = Runtime.from_dict(workflow(request, expected)).run()
            self.assertEqual(report["tasks"]["propose"]["status"], "failed")

    def test_zero_polynomial_and_empty_variable_ring_supported(self):
        request = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": [], "operation": "add",
                   "operands": [{"type": "rational", "numerator": n, "denominator": 3} for n in (-2, 2)]}
        expected = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": [],
                    "polynomial": {"terms": [], "total_degree": None}}
        self.assertEqual(Runtime.from_dict(workflow(request, expected)).run()["goal_status"], "exact_result_verified")

    def test_validated_request_is_detached_and_normalized_without_calculation(self):
        request = workflow()["problem"]["goal_request"]
        result = validate_polynomial_request(request)
        result["variables"].reverse()
        self.assertEqual(request["variables"], ["x", "y"])

    def test_dispatch_is_fixed_allowlist(self):
        for name in (None, [], {}, "R", "quotient_ring", "__import__('os')"):
            with self.assertRaises(DomainError):
                domain_handler(name)

    def test_oversized_expanded_evidence_fails_closed_without_crashing_runtime(self):
        names = list("abcdefgh")
        factors = [{"type": "add", "operands": [{"type": "variable", "name": n},
                   {"type": "rational", "numerator": (1 << 250) + 1, "denominator": 1}]} for n in names]
        expr = factors[0]
        for factor in factors[1:]:
            expr = {"type": "multiply", "operands": [expr, factor]}
        request = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": names,
                   "operation": "verify_identity", "operands": [expr, expr]}
        self.assertEqual(calculate_polynomial(request)["status"], "success")
        report = Runtime.from_dict(workflow(request)).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["calculate"]["status"], "failed")
        self.assertTrue(validate_receipt_chain(report["receipts"]))

    def test_cli_exit_codes_exact_true_false_formal_and_invalid(self):
        false_request = json.loads((ROOT / "examples/polynomial/false-square-identity.json").read_text())
        bad = workflow()
        bad["problem"]["goal_request"]["relations"] = []
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "workflow.json"
            for data, code in ((workflow(), 0), (workflow(false_request), 1), (workflow(required="formal_proof"), 1), (bad, 2)):
                path.write_text(json.dumps(data))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["run", str(path)]), code)


if __name__ == "__main__":
    unittest.main()

"""Safety and correctness checks for the offline queue; no assert statements."""
import contextlib
from dataclasses import FrozenInstanceError, replace
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from foundation_math.cli import demo_workflow, main
from foundation_math.orchestrator import LiteralProposalProvider, Runtime, WorkflowError, validate_receipt_chain


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class RuntimeTests(unittest.TestCase):
    def make(self, workflow=None, **kwargs):
        return Runtime.from_dict(workflow or demo_workflow(), **kwargs)

    def test_demo_verifies_only_exact_result(self):
        runtime = self.make()
        report = runtime.run()
        self.assertEqual(report["goal_status"], "exact_result_verified")
        self.assertEqual(report["result"], {"domain": "Q", "numerator": 5, "denominator": 6})
        self.assertEqual(report["proof_status"], "not_formally_verified")
        self.assertEqual(report["tasks"]["formalize-sum"]["status"], "blocked")
        self.assertTrue(validate_receipt_chain(report["receipts"]))
        verification = next(r for r in runtime.receipts if r.event == "exact_verification")
        self.assertFalse(verification.payload["formal_proof"])
        self.assertFalse(verification.payload["independent_backend"])
        self.assertIn("natural-language", verification.payload["scope"])

    def test_confident_wrong_answer_is_rejected(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["payload"]["expected"]["numerator"] = 7
        workflow["tasks"][0]["payload"]["rationale"] = "I am absolutely certain and this is proved."
        report = self.make(workflow).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["verify-sum"]["status"], "rejected")
        self.assertIsNone(report["result"])
        self.assertEqual(report["tasks"]["audit-scope"]["status"], "blocked")

    def test_proposal_cannot_substitute_easier_goal(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["payload"]["request"]["operation"] = "multiply"
        # Fixture intentionally shares the request object, so detach its goal.
        workflow["problem"]["goal_request"]["operation"] = "add"
        workflow["tasks"][0]["payload"]["request"] = {"domain": "Q", "operation": "multiply", "operands": [1, 1]}
        report = self.make(workflow).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["propose-sum"]["status"], "failed")

    def test_untrusted_status_cannot_complete_task(self):
        class FakeSuccess:
            def propose(self, problem, task, evidence):
                return {"status": "verified", "confidence": 1.0, "text": "QED"}
        report = self.make().run(FakeSuccess())
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["propose-sum"]["attempts"], 2)

    def test_expected_zero_denominator_is_rejected(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["payload"]["expected"]["denominator"] = 0
        self.assertEqual(self.make(workflow).run()["goal_status"], "not_verified")

    def test_equivalent_rational_expectation_is_accepted(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["payload"]["expected"] = {"domain": "Q", "numerator": 10, "denominator": 12}
        self.assertEqual(self.make(workflow).run()["goal_status"], "exact_result_verified")

    def test_bool_is_not_an_integer_result(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["payload"]["expected"]["numerator"] = True
        self.assertEqual(self.make(workflow).run()["goal_status"], "not_verified")

    def test_problem_requires_explicit_assumptions(self):
        workflow = demo_workflow()
        del workflow["problem"]["assumptions"]
        with self.assertRaises(WorkflowError):
            self.make(workflow)

    def test_unknown_domain_and_domain_mismatch_are_rejected(self):
        workflow = demo_workflow()
        workflow["problem"]["domain"] = "R"
        with self.assertRaises(WorkflowError):
            self.make(workflow)
        workflow["problem"]["domain"] = "Z"
        with self.assertRaises(WorkflowError):
            self.make(workflow)

    def test_commands_are_not_a_supported_workflow_field(self):
        workflow = demo_workflow()
        workflow["tasks"][0]["command"] = "touch /tmp/should-not-exist"
        with self.assertRaises(WorkflowError):
            self.make(workflow)
        workflow = demo_workflow()
        workflow["tasks"][1]["payload"] = {"shell": "echo unsafe"}
        with self.assertRaises(WorkflowError):
            self.make(workflow)

    def test_receipts_are_frozen_and_payload_is_detached(self):
        runtime = self.make()
        runtime.run()
        receipt = next(r for r in runtime.receipts if r.event == "proposal_recorded")
        with self.assertRaises(FrozenInstanceError):
            receipt.event = "verified"
        payload = receipt.payload
        payload["trusted"] = True
        self.assertFalse(receipt.payload["trusted"])
        report = runtime.report()
        report["receipts"][0]["payload"]["owner"] = "attacker"
        self.assertTrue(validate_receipt_chain(runtime.report()["receipts"]))
        self.assertFalse(validate_receipt_chain(report["receipts"]))

    def test_receipt_reordering_and_deletion_break_chain(self):
        receipts = self.make().run()["receipts"]
        self.assertFalse(validate_receipt_chain(list(reversed(receipts))))
        self.assertFalse(validate_receipt_chain(receipts[1:]))
        self.assertFalse(validate_receipt_chain({}))

    def test_only_one_worker_can_lease_same_ready_task(self):
        runtime = self.make()
        acquired = []
        barrier = threading.Barrier(4)
        def acquire(index):
            barrier.wait()
            acquired.append(runtime.lease_next(f"worker-{index}"))
        threads = [threading.Thread(target=acquire, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(lease is not None for lease in acquired), 1)

    def test_wrong_owner_token_or_attempt_cannot_publish(self):
        runtime = self.make()
        lease = runtime.lease_next("worker-1")
        for forged in (replace(lease, owner="worker-2"), replace(lease, token="guessed"), replace(lease, attempt=99)):
            with self.assertRaises(WorkflowError):
                runtime.execute(forged)
        runtime.execute(lease)
        with self.assertRaises(WorkflowError):
            runtime.execute(lease)

    def test_expired_lease_is_reassigned_and_old_worker_rejected(self):
        clock = Clock()
        runtime = self.make(clock=clock)
        old = runtime.lease_next("old-worker")
        clock.now = 31
        new = runtime.lease_next("new-worker")
        self.assertEqual(old.task_id, new.task_id)
        self.assertNotEqual(old.token, new.token)
        with self.assertRaises(WorkflowError):
            runtime.execute(old)
        runtime.execute(new)

    def test_expiration_exhausts_task_retry_budget(self):
        clock = Clock()
        runtime = self.make(clock=clock)
        runtime.lease_next("worker")
        clock.now += 31
        runtime.lease_next("worker")
        clock.now += 31
        self.assertIsNone(runtime.lease_next("worker"))
        report = runtime.report()
        self.assertEqual(report["total_attempts"], 2)
        self.assertEqual(report["tasks"]["propose-sum"]["status"], "failed")

    def test_transient_provider_failure_retries_once(self):
        class Flaky(LiteralProposalProvider):
            def __init__(self):
                self.calls = 0
            def propose(self, problem, task, evidence):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary fixture failure")
                return super().propose(problem, task, evidence)
        provider = Flaky()
        report = self.make().run(provider)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(report["goal_status"], "exact_result_verified")

    def test_global_budget_blocks_unstarted_work(self):
        workflow = demo_workflow()
        workflow["max_total_attempts"] = 1
        report = self.make(workflow).run()
        self.assertEqual(report["total_attempts"], 1)
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["verify-sum"]["status"], "blocked")

    def test_explicit_nonretry_failure(self):
        runtime = self.make()
        runtime.fail(runtime.lease_next("worker"), "fatal", retry=False)
        self.assertIsNone(runtime.lease_next("worker"))
        self.assertEqual(runtime.report()["tasks"]["propose-sum"]["attempts"], 1)

    def test_missing_forward_duplicate_and_self_dependencies_rejected(self):
        for deps in (["missing"], ["verify-sum"], ["propose-sum", "propose-sum"], ["calculate-sum"]):
            workflow = demo_workflow()
            workflow["tasks"][1]["dependencies"] = deps
            with self.assertRaises(WorkflowError):
                self.make(workflow)

    def test_missing_verifier_evidence_never_verifies(self):
        workflow = demo_workflow()
        workflow["tasks"][2]["dependencies"] = ["propose-sum"]
        report = self.make(workflow).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["verify-sum"]["status"], "failed")

    def test_goal_must_name_verifier(self):
        workflow = demo_workflow()
        workflow["goal_task_id"] = "propose-sum"
        with self.assertRaises(WorkflowError):
            self.make(workflow)

    def test_role_specific_leases_respect_dependencies(self):
        runtime = self.make()
        self.assertIsNone(runtime.lease_next("calculator", {"calculator"}))
        lease = runtime.lease_next("proposer", {"proposer"})
        runtime.execute(lease)
        self.assertEqual(runtime.lease_next("calculator", {"calculator"}).task_id, "calculate-sum")

    def test_invalid_budget_lease_and_schema_are_rejected(self):
        for key, value in (("max_total_attempts", True), ("max_total_attempts", 0), ("lease_seconds", float("nan")), ("schema_version", True)):
            workflow = demo_workflow()
            workflow[key] = value
            with self.assertRaises(WorkflowError):
                self.make(workflow)

    def test_cli_demo_output_and_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", "--output", str(target)]), 0)
                self.assertEqual(main(["check-receipts", str(target)]), 0)
            old = target.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", "--output", str(target)]), 2)
            self.assertEqual(target.read_bytes(), old)

    def test_cli_bad_json_returns_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "invalid.json"
            target.write_text("{broken", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["run", str(target)]), 2)

    def test_cli_rejects_deep_duplicate_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.json"
            for text in ('[' * 20000 + '0' + ']' * 20000, '{"schema_version":1,"schema_version":2}', '{"bad":NaN}'):
                target.write_text(text, encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["run", str(target)]), 2)

    def test_cli_lean_status_does_not_claim_verification(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["lean-status"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["verification"], "not_run")
        self.assertFalse(report["formal_proof"])


if __name__ == "__main__":
    unittest.main()

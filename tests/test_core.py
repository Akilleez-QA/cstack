import ast
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest

from poodo_core import *
from adapters.memory_ledger import MemoryLedger
from tests.helpers import *

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_core_import_direction_and_isolated_runtime(self):
        allowed = {"__future__", "dataclasses", "enum", "hashlib", "json", "re", "typing"}
        for path in (ROOT / "poodo_core").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name.split(".")[0] in allowed for a in node.names), path)
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    self.assertIn(node.module.split(".")[0], allowed, path)
        code = "import sys; from poodo_core import PoodoCore; print([m for m in sys.modules if m.startswith(('foundation_math','extensions','adapters','mcp'))])"
        proc = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), b"[]")

    def test_fake_sibling_accepts_finite_decimal_without_math_semantics(self):
        core = FakeFoundation()
        outcome = execute_one(core, request(arguments={"sample": 12.5})).to_dict()
        self.assertEqual(outcome["raw_result"]["temperature"], 12.5)
        self.assertEqual(core.fake.calls[0]["arguments"], {"sample": 12.5})
        self.assertEqual(outcome["execution_status"], "completed")
        self.assertFalse(core.snapshot("g").closed)
        self.assertFalse(outcome["formal_proof"])
        self.assertEqual(len(core.fake.calls), 1)  # Instruction-like tool data is never acted on.
        self.assertEqual([e["kind"] for e in core.ledger()][-2:], ["action", "outcome"])

    def test_protected_methods_cannot_be_overridden(self):
        for name in PoodoCore._FINAL_METHODS:
            with self.subTest(name=name), self.assertRaises(TypeError):
                type("BadExtension", (PoodoCore,), {name: lambda *a: None})

    def test_contract_version_and_ceiling_reject(self):
        class BadVersion(FakeExtension):
            def descriptor(self):
                return replace(super().descriptor(), extension_contract="poodo.domain-extension/1.0")
        class BadCeiling(FakeExtension):
            def descriptor(self):
                return replace(super().descriptor(), capabilities=(replace(FAKE_CAP, evidence_ceiling="formal_proof"),))
        for extension in (BadVersion(), BadCeiling()):
            with self.assertRaises(ContractError):
                FakeFoundation(extension=extension)

    def test_unknown_domain_goal_and_operation_deny_without_dispatch(self):
        core = FakeFoundation()
        with self.assertRaises(ContractError):
            core.start_goal(goal("foundation_engine"))
        to_decide(core)
        for req in (request(operation="shell"), request(capability="foundation_template"),
                    request(required_evidence="formal_proof"), request(goal_id="other")):
            with self.assertRaises(ContractError):
                core.decide(req, precommit())
        self.assertEqual(core.fake.calls, [])

    def test_forged_authority_fields_are_rejected(self):
        value = request().to_dict()
        for field in ("grant", "authorized", "source_root", "proof_complete", "command"):
            with self.assertRaises(ContractError):
                CapabilityRequest.from_dict({**value, field: True})

    def test_phase_and_research_gate_controls(self):
        core = FakeFoundation()
        core.start_goal(goal())
        with self.assertRaises(ContractError):
            core.advance("g", Phase.DECIDE, PhaseCheckpoint("skip", "No skipping"))
        with self.assertRaises(ContractError):
            core.decide(request(), precommit())
        core.advance("g", Phase.OBSERVE, PhaseCheckpoint("p", "Frame supplied"))
        with self.assertRaises(ContractError):
            core.advance("g", Phase.ORIENT, PhaseCheckpoint("missing", "No research"))
        core.advance("g", Phase.ORIENT, PhaseCheckpoint("research", "Bound record", ("source",)))
        for ids in (tuple("x"+str(i) for i in range(19)), ("same",)*20):
            with self.assertRaises(ContractError):
                core.advance("g", Phase.DECIDE, PhaseCheckpoint("options", "Structural options", option_ids=ids))
        self.assertEqual(core.fake.calls, [])

    def test_no_oracle_and_execution_before_orchestrate(self):
        core = FakeFoundation()
        to_decide(core)
        with self.assertRaises(ContractError):
            Precommitment("expect", "scope", "failure", "", "1")
        core.decide(request(), precommit())
        with self.assertRaises(ContractError):
            core.execute("d-1")
        self.assertEqual(core.fake.calls, [])

    def test_stale_revision_denies_and_keeps_history(self):
        core = FakeFoundation()
        to_decide(core)
        core.decide(request(), precommit())
        core.revise_goal(goal(revision=2))
        with self.assertRaises(ContractError):
            core.execute("d-1")
        self.assertEqual(core.fake.calls, [])
        self.assertIn("correction", [e["kind"] for e in core.ledger()])

    def test_decision_identity_is_consumed_not_automatic_retry(self):
        core = FakeFoundation()
        execute_one(core)
        with self.assertRaises(ContractError):
            core.execute("d-1")
        self.assertEqual(len(core.fake.calls), 1)

    def test_input_snapshots_and_ledger_are_detached(self):
        args = {"nested": {"x": 1}}
        req = request(arguments=args)
        args["nested"]["x"] = 9
        self.assertEqual(req.arguments["nested"]["x"], 1)
        req.arguments["nested"]["x"] = 8
        self.assertEqual(req.arguments["nested"]["x"], 1)
        core = FakeFoundation()
        execute_one(core, req)
        snap = core.snapshot("g")
        with self.assertRaises(FrozenInstanceError):
            snap.closed = True
        history = core.ledger()
        history[-1]["data"]["goal_closed"] = True
        self.assertFalse(core.ledger()[-1]["data"]["goal_closed"])

    def test_mutating_hook_cannot_change_request(self):
        class Mutating(FakeExtension):
            def validate_call(self, goal, request):
                request.arguments["x"] = "changed"
                return Admission(True, "Only the detached copy was changed")
        core = FakeFoundation(extension=Mutating())
        execute_one(core, request(arguments={"x": "original"}))
        self.assertEqual(core.fake.calls[0]["arguments"]["x"], "original")

    def test_dishonest_outcome_or_interpretation_quarantined(self):
        class Liar(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                data = super().invoke(request, attempt_id).to_dict()
                data["formal_proof"] = True
                return CapabilityOutcome(Document.capture(data))  # Bypass constructor validation deliberately.
        class LiarExtension(FakeExtension):
            def interpret(self, *args):
                return Interpretation("proof_complete", "All theorems proved", (), True, True)
        for core in (FakeFoundation(capability=Liar()), FakeFoundation(extension=LiarExtension())):
            result = execute_one(core).to_dict()
            self.assertEqual(result["execution_status"], "protocol_error")
            self.assertIsNone(result["raw_result"])
            self.assertFalse(core.snapshot("g").closed)

    def test_binding_mismatch_quarantines(self):
        class Wrong(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                data = super().invoke(request, attempt_id).to_dict()
                data["request_sha256"] = "0"*64
                return CapabilityOutcome.from_dict(data)
        self.assertEqual(execute_one(FakeFoundation(capability=Wrong())).to_dict()["execution_status"], "protocol_error")

    def test_near_document_cap_still_records_terminal_quarantine(self):
        class Large(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                return outcome_for(request, attempt_id, "completed", "large", certainty="responded",
                                   raw_result={"padding": "x" * 2_090_000})
        core = FakeFoundation(capability=Large())
        result = execute_one(core).to_dict()
        self.assertEqual(result["execution_status"], "protocol_error")
        self.assertEqual(core.ledger()[-1]["kind"], "outcome")
        self.assertLess(len(canonical(core.ledger()[-1])), 4096)

    def test_adapter_crash_and_pre_cancel_are_not_success(self):
        class Crash(FakeCapability):
            def invoke(self, *args):
                raise RuntimeError("private internal details")
        core = FakeFoundation(capability=Crash())
        outcome = execute_one(core).to_dict()
        self.assertEqual((outcome["execution_status"], outcome["execution_certainty"]), ("indeterminate", "unknown"))
        self.assertNotIn("private", canonical(outcome))
        core = FakeFoundation()
        to_decide(core)
        core.decide(request(), precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Approved fixture"))
        cancel = threading.Event(); cancel.set()
        outcome = core.execute("d-1", cancel).to_dict()
        self.assertEqual((outcome["execution_status"], outcome["execution_certainty"]), ("cancelled", "not_dispatched"))
        self.assertEqual(core.fake.calls, [])

    def test_large_unicode_interpretation_and_outcome_terminal_is_bounded(self):
        class Large(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                return outcome_for(request, attempt_id, "completed", "large", certainty="responded",
                                   raw_result={"padding": "x" * 1_500_000})
        class UnicodeInterpretation(FakeExtension):
            def interpret(self, *args):
                return Interpretation("tool_observation", "Scoped only", ("\U0001f600"*4096,)*32)
        core = FakeFoundation(capability=Large(), extension=UnicodeInterpretation())
        result = execute_one(core).to_dict()
        self.assertEqual(result["execution_status"], "protocol_error")
        self.assertEqual(core.ledger()[-1]["kind"], "outcome")
        self.assertLess(len(canonical(core.ledger()[-1])), 4096)

    def test_near_depth_or_node_budget_keeps_terminal_accounting(self):
        class Deep(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                nested = 0
                for _ in range(125):
                    nested = [nested]
                return outcome_for(request, attempt_id, "completed", "deep", certainty="responded",
                                   raw_result={"nested": nested})
        class Many(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                return outcome_for(request, attempt_id, "completed", "many", certainty="responded",
                                   raw_result={"nodes": [0]*199_970})
        for capability in (Deep(), Many()):
            core = FakeFoundation(capability=capability)
            result = execute_one(core).to_dict()
            self.assertEqual(core.ledger()[-1]["kind"], "outcome")
            self.assertIn(result["execution_status"], ("protocol_error", "indeterminate"))
            self.assertIsNone(result["raw_result"])

    def test_ledger_budget_rejected_before_dispatch(self):
        core = FakeFoundation(ledger=MemoryLedger(max_bytes=20_000))
        to_decide(core)
        core.decide(request(), precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Approved fixture"))
        with self.assertRaises(ContractError):
            core.execute("d-1")
        self.assertEqual(core.fake.calls, [])

    def test_authority_and_retained_goal_budgets(self):
        core = FakeFoundation(max_calls=1)
        to_decide(core)
        core.decide(request(i=1), precommit())
        core.decide(request(i=2), precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Approved fixture"))
        core.execute("d-1")
        with self.assertRaises(ContractError):
            core.execute("d-2")
        self.assertEqual(len(core.fake.calls), 1)
        for i in range(1, 32):
            core.start_goal(goal(goal_id="g"+str(i)))
        with self.assertRaises(ContractError):
            core.start_goal(goal(goal_id="overflow"))

    def test_request_bool_revision_and_nonfinite_reject(self):
        for rev in (True, 0, 1.0):
            with self.assertRaises(ContractError):
                request(revision=rev)
        with self.assertRaises(ContractError):
            request(arguments={"value": float("nan")})

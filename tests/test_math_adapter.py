import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from adapters.execution import ProcessResult
from adapters.math_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, MathStdioCapability, PinnedMathSource,
                                 SOURCE_SHA256, SourceFailure)
from adapters.wire import WireFailure, decode, encode
from bootstrap import DEFAULT_MATH_ROOT, build_math
from extensions.foundation_math import TOOL_NAMES, UNIMPLEMENTED_FOUNDATIONS
from poodo_core import *
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "examples/tool-cases.json").read_text())


def math_request(name="exact_scalar", args=None, i=1):
    return request(name, CASES[0]["arguments"] if args is None else args, "foundation_math", i=i)


class FakeExecutor:
    def __init__(self, result=None, mutation=None, raw=None):
        self.result, self.mutation, self.raw = result, mutation, raw
        self.calls = 0

    def exchange(self, frames, cancellation=None):
        self.calls += 1
        hello = {"jsonrpc": "2.0", "id": "cstack-init", "result": {
            "protocolVersion": BRIDGE_PROTOCOL, "mcpCompatible": False,
            "limits": {"inputFrameBytes": 65_536, "outputFrameBytes": 1_048_576}}}
        req = json.loads(frames[1])
        reply = {"jsonrpc": "2.0", "id": req["id"], "result": copy.deepcopy(self.result)}
        if self.mutation:
            self.mutation(reply)
        return ProcessResult("completed", "responded", self.raw if self.raw is not None else encode(hello)+b"\n"+encode(reply)+b"\n", b"", 0)


class MathAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = MathStdioCapability(DEFAULT_MATH_ROOT)
        cls.probe = cls.cap.probe()
        cls.scalar = cls.cap.invoke(math_request(), "attempt-control").to_dict()["raw_result"]

    def test_source_and_live_inventory_exact(self):
        self.assertEqual(PinnedMathSource(DEFAULT_MATH_ROOT).verify(), {"source_manifest_sha256": SOURCE_SHA256, "verified_files": 561})
        self.assertEqual(self.probe.status, "completed")
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), TOOL_NAMES)
        self.assertEqual(hashlib.sha256(encode(self.cap.inventory())).hexdigest(), INVENTORY_SHA256)
        self.assertGreater(len(encode(self.cap.inventory())), 65_536)
        for tool in self.cap.inventory():
            Draft202012Validator.check_schema(tool["inputSchema"])
            Draft202012Validator.check_schema(tool["outputSchema"])

    def test_real_all_nineteen_through_inherited_core_and_differential(self):
        core, cap = build_math("g")
        to_decide(core, domain="foundation_math")
        requests = [math_request(case["operation"], case["arguments"], i) for i, case in enumerate(CASES, 1)]
        for req in requests:
            core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted synthetic suite"))
        schema = Draft202012Validator(json.loads((ROOT / "contracts/capability-result.schema.json").read_text()))
        for req in requests:
            with self.subTest(operation=req.operation):
                out = core.execute(req.decision_id).to_dict()
                self.assertEqual(out["execution_status"], "completed", out)
                schema.validate(out)
                self.assertEqual(out["raw_result"]["structuredContent"]["tool"], req.operation)
                self.assertFalse(out["formal_proof"])
                self.assertFalse(out["runtime_goal_acceptance"])
                # Differential preservation, not independent mathematical corroboration.
                frames = [x["json_utf8"] for x in cap.transcript() if x["direction"] == "request"]
                direct = subprocess.run([sys.executable, "-B", "-m", "foundation_math_bridge"], cwd=DEFAULT_MATH_ROOT,
                    input=("\n".join(frames)+"\n").encode("ascii"), capture_output=True, timeout=15)
                self.assertEqual(direct.returncode, 0)
                self.assertEqual(json.loads(direct.stdout.splitlines()[1])["result"], out["raw_result"])
        self.assertFalse(core.snapshot("g").closed)
        self.assertEqual(len([e for e in core.ledger() if e["kind"] == "outcome"]), 19)

    def test_positive_scalar_and_false_identity_are_different_claims(self):
        self.assertEqual(self.scalar["structuredContent"]["receipt"]["result"], {"domain": "Q", "numerator": 5, "denominator": 6})
        out = self.cap.invoke(math_request("polynomial_identity", CASES[1]["arguments"]), "attempt-negative").to_dict()
        self.assertEqual(out["execution_status"], "completed")
        self.assertEqual(out["assessment"], "formal_polynomial_identity_not_equal")
        self.assertIs(out["raw_result"]["structuredContent"]["receipt"]["result"]["equal"], False)
        self.assertFalse(out["formal_proof"])

    def test_z_division_and_malformed_denominator_never_coerce(self):
        for args in ({"domain":"Z","operation":"divide","operands":[1,2]},
                     {"domain":"Q","operation":"add","operands":[{"numerator":1,"denominator":0},1]}):
            out = self.cap.invoke(math_request(args=args), "attempt-negative").to_dict()
            self.assertEqual(out["execution_status"], "tool_error")
            self.assertFalse(out["formal_proof"])
            self.assertEqual(out["epistemic_status"], "unassessed")

    def test_output_integer_larger_than_input_bit_cap_is_preserved(self):
        out = self.cap.invoke(math_request(args={"domain":"Z","operation":"power","operands":[2,5000]}), "attempt-big").to_dict()
        self.assertEqual(out["execution_status"], "completed")
        result = out["raw_result"]["structuredContent"]["receipt"]["result"]
        self.assertIn(2**5000, result.values())

    def test_empty_domain_and_authored_match_do_not_promote(self):
        case = copy.deepcopy(CASES[2]["arguments"])
        case["constraints"] = [{"relation":"lt","left":{"type":"rational","numerator":1,"denominator":1},
                                 "right":{"type":"rational","numerator":0,"denominator":1}}]
        out = self.cap.invoke(math_request("finite_box_search", case), "attempt-empty").to_dict()
        self.assertEqual(out["raw_result"]["structuredContent"]["receipt"]["progress"]["eligible_count"], 0)
        self.assertFalse(out["runtime_goal_acceptance"])
        out = self.cap.invoke(math_request("match_hypothesis_scope", CASES[15]["arguments"]), "attempt-authored").to_dict()
        self.assertEqual(out["assessment"], "authored_premise_scope_compared")
        self.assertFalse(out["formal_proof"])
        self.assertIn("Original receipt preserved without accepting its assumptions as true.", out["limitations"])

    def test_unknown_or_formal_capability_is_not_dispatched(self):
        fake = FakeExecutor(self.scalar)
        cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=fake)
        for req in (math_request("shell", {}), request("exact_scalar", {}, "foundation_engine"),
                    request("exact_scalar", {}, "foundation_math", required_evidence="formal_proof")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual(out["execution_status"], "unavailable")
            self.assertEqual(out["execution_certainty"], "not_dispatched")
        self.assertEqual(fake.calls, 0)
        self.assertEqual(set(UNIMPLEMENTED_FOUNDATIONS), {"foundation_engine", "foundation_refrigeration.rules",
            "foundation_refrigeration.reference_plants", "foundation_refrigeration.determinations", "lean", "endoforge"})

    def test_source_missing_or_manifest_changed_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            for raw in (None, b'{"files":{}}'):
                if raw:
                    (Path(td)/"SOURCE-MANIFEST.json").write_bytes(raw)
                fake = FakeExecutor(self.scalar)
                out = MathStdioCapability(Path(td), executor=fake).invoke(math_request(), "attempt-source").to_dict()
                self.assertEqual(out["execution_status"], "unavailable")
                self.assertEqual(fake.calls, 0)

    def test_changed_file_after_manifest_is_detected(self):
        original = Path.read_bytes
        def corrupt(path):
            data = original(path)
            return data+b" " if path.name == "AGENTS.md" else data
        with patch.object(Path, "read_bytes", corrupt), self.assertRaises(SourceFailure):
            PinnedMathSource(DEFAULT_MATH_ROOT).verify()

    def test_schema_flags_tool_and_envelope_mutations_quarantine(self):
        mutations = [
            lambda x: x.update(id=1),
            lambda x: x.update(jsonrpc="1.0"),
            lambda x: x.update(error={"code":-1,"message":"ambiguous"}),
            lambda x: x["result"].update(isError=0),
            lambda x: x["result"]["structuredContent"].update(tool="polynomial_identity"),
            lambda x: x["result"]["structuredContent"].update(formal_proof=True),
            lambda x: x["result"]["structuredContent"].update(runtime_goal_acceptance=True),
            lambda x: x["result"]["structuredContent"].update(receipt=[]),
            lambda x: x["result"]["structuredContent"].update(assessment="proof_complete"),
            lambda x: x["result"].update(extra="unsupported")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=FakeExecutor(self.scalar, mutate))
                cap._ready = True
                out = cap.invoke(math_request(), "attempt-mutated").to_dict()
                self.assertEqual(out["execution_status"], "protocol_error")
                self.assertIsNone(out["raw_result"])

    def test_wrong_inventory_never_dispatches_math(self):
        cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=FakeExecutor({"tools": []}))
        out = cap.invoke(math_request(), "attempt-inventory").to_dict()
        self.assertNotEqual(out["execution_status"], "completed")
        self.assertEqual(cap._executor.calls, 1)  # Discovery only; no tool call follows.

    def test_malformed_partial_duplicate_and_oversized_output_quarantine(self):
        for raw in (b'{"jsonrpc":"2.0"}', b'{}\n', b'{}\n{}\n{}\n', b'\xff\n{}\n',
                    b'{"id":1,"id":1}\n{}\n', b'x'*1_048_577+b'\n{}\n'):
            cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=FakeExecutor(raw=raw))
            cap._ready = True
            out = cap.invoke(math_request(), "attempt-wire").to_dict()
            self.assertEqual(out["execution_status"], "protocol_error")
            self.assertIsNone(out["raw_result"])

    def test_exact_input_controls_do_not_dispatch(self):
        fake = FakeExecutor(self.scalar)
        cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=fake)
        for args in ({"float":1.0}, {"padding":"x"*65_536}, {"integer":2**4096}, {"s":"x"*4097}):
            out = cap.invoke(math_request(args=args), "attempt-input").to_dict()
            self.assertEqual(out["execution_status"], "resource_rejected")
            self.assertEqual(out["execution_certainty"], "not_dispatched")
        self.assertEqual(fake.calls, 0)

    def test_strict_json_and_distinct_response_budget(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":1e0}', b'NaN', b'\xff', b'['*81+b']'*81):
            with self.assertRaises(WireFailure):
                decode(raw)
        inventory = encode(self.cap.inventory())
        with self.assertRaises(WireFailure):
            decode(inventory)
        self.assertEqual(decode(inventory, response=True), self.cap.inventory())

    def test_both_semantic_schemas_are_valid_and_closed(self):
        for name in ("capability-request", "capability-result"):
            schema = json.loads((ROOT / "contracts" / (name+".schema.json")).read_text())
            Draft202012Validator.check_schema(schema)
            self.assertFalse(schema["additionalProperties"])

"""Foundation Refrigeration as a sibling POODO extension: conformance and fail-closed controls (ADR 002)."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from adapters.execution import LocalBridgeExecutor, ProcessResult
from adapters.memory_ledger import MemoryLedger
from adapters.wire import WireFailure, encode
from bootstrap import DEFAULT_MATH_ROOT, DEFAULT_REFRIGERATION_ROOT, build_refrigeration
from extensions.foundation_math import FoundationMath, MATH_DOMAIN, UNIMPLEMENTED_FOUNDATIONS
from poodo_core import *
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
# The open-core export leaves Foundation Refrigeration out; then every test here skips.
HAVE_REFRIGERATION = DEFAULT_REFRIGERATION_ROOT.is_dir()
NO_REFRIGERATION = "Foundation Refrigeration is not in this checkout (foundations/refrigeration is absent)"
if HAVE_REFRIGERATION:
    from adapters.refrigeration_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, SOURCE_FILE_COUNT, SOURCE_SHA256,
                                              PinnedRefrigerationSource, RefrigerationStdioCapability,
                                              SourceFailure, arguments_sha256, decode)
    from extensions.foundation_refrigeration import (FoundationRefrigeration, REFRIGERATION_CAPABILITY,
                                                     REFRIGERATION_DOMAIN, REFRIGERATION_TOOL_NAMES)
EXAMPLE = ROOT / "examples/refrigeration-reading-check.json"
CASES = {
    "saturation_pressure": {"fluid": "R717", "temperature": {"value": 0, "unit": "degF"}},
    "saturation_temperature": {"fluid": "R448A", "pressure": {"value": 300.0, "unit": "kPa(a)"}, "side": "bubble"},
    "convert_pressure": {"pressure": {"value": 181.1, "unit": "psig"}, "to_unit": "psia"},
    "convert_temperature": {"temperature": {"value": 95, "unit": "degF"}, "to_unit": "degC"},
    "check_reading_against_saturation": {"fluid": "R717", "pressure": {"value": 33.49, "unit": "psig"},
                                         "temperature": {"value": 30.0, "unit": "degF"}},
    "exposure_limits": {"substance": "ammonia"},
    "resolve_equipment_kind": {"term": "CD", "vocabulary": "line_service"},
}


def refr_request(name="saturation_pressure", args=None, i=1):
    return request(name, CASES[name] if args is None else args, "foundation_refrigeration", i=i)


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
        raw = self.raw if self.raw is not None else encode(hello) + b"\n" + encode(reply) + b"\n"
        return ProcessResult("completed", "responded", raw, b"", 0)


@unittest.skipUnless(HAVE_REFRIGERATION, NO_REFRIGERATION)
class RefrigerationAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT)
        cls.probe = cls.cap.probe()
        cls.ok = cls.cap.invoke(refr_request(), "attempt-control").to_dict()["raw_result"]

    def test_source_and_live_inventory_exact(self):
        self.assertEqual(PinnedRefrigerationSource(DEFAULT_REFRIGERATION_ROOT).verify(),
                         {"source_manifest_sha256": SOURCE_SHA256, "verified_files": SOURCE_FILE_COUNT})
        self.assertEqual(self.probe.status, "completed")
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), REFRIGERATION_TOOL_NAMES)
        self.assertEqual(hashlib.sha256(encode(self.cap.inventory())).hexdigest(), INVENTORY_SHA256)
        pins = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())["foundation_refrigeration"]
        self.assertEqual((pins["source_manifest_sha256"], pins["source_manifest_entry_count"], pins["inventory_sha256"]),
                         (SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256))
        for tool in self.cap.inventory():
            Draft202012Validator.check_schema(tool["inputSchema"])
            Draft202012Validator.check_schema(tool["outputSchema"])

    def test_real_all_seven_through_inherited_core_and_differential(self):
        core, cap = build_refrigeration("g")
        to_decide(core, domain="foundation_refrigeration")
        requests = [refr_request(name, args, i) for i, (name, args) in enumerate(CASES.items(), 1)]
        for req in requests:
            core.decide(req, precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted synthetic suite"))
        schema = Draft202012Validator(json.loads((ROOT / "contracts/capability-result.schema.json").read_text()))
        for req in requests:
            with self.subTest(operation=req.operation):
                out = core.execute(req.decision_id).to_dict()
                self.assertEqual(out["execution_status"], "completed", out)
                schema.validate(out)
                content = out["raw_result"]["structuredContent"]
                self.assertEqual(content["tool"], req.operation)
                self.assertTrue(content["receipt"]["evidence"])
                self.assertEqual(content["receipt"]["input_sha256"], arguments_sha256(req.arguments))
                self.assertFalse(out["formal_proof"] or out["runtime_goal_acceptance"])
                frames = [x["json_utf8"] for x in cap.transcript() if x["direction"] == "request"]
                direct = subprocess.run([sys.executable, "-B", "-m", "foundation_refrigeration_bridge"],
                    cwd=DEFAULT_REFRIGERATION_ROOT, input=("\n".join(frames) + "\n").encode("ascii"),
                    capture_output=True, timeout=15)
                self.assertEqual(direct.returncode, 0)
                self.assertEqual(json.loads(direct.stdout.splitlines()[1])["result"], out["raw_result"])
        self.assertFalse(core.snapshot("g").closed)
        outcomes = [e for e in core.ledger() if e["kind"] == "outcome"]
        self.assertEqual(len(outcomes), 7)
        for event in outcomes:
            limits = event["data"]["interpretation"]["limitations"]
            self.assertIn("A tool observation is not an engineering, safety or compliance determination.", limits)
            self.assertTrue(any("Monitoring-only" in x for x in limits))

    def test_census_golden_points_through_the_adapter(self):
        for t_f, psig in ((0, 15.69), (20, 33.49), (95, 181.10)):
            out = self.cap.invoke(refr_request(args={"fluid": "R717", "temperature": {"value": t_f, "unit": "degF"}}),
                                  "attempt-golden").to_dict()
            views = out["raw_result"]["structuredContent"]["receipt"]["result"]["pressure_views"]
            self.assertEqual(round(next(v["value"] for v in views if v["unit"] == "psig"), 2), psig)

    def test_tool_error_is_distinct_and_retained(self):
        out = self.cap.invoke(refr_request("saturation_temperature",
                              {"fluid": "R404A", "pressure": {"value": 300.0, "unit": "kPa(a)"}}), "attempt-side").to_dict()
        self.assertEqual((out["execution_status"], out["epistemic_status"]), ("tool_error", "unassessed"))
        self.assertEqual(out["raw_result"]["structuredContent"]["receipt"]["error"]["code"], "side_required")
        out = self.cap.invoke(refr_request(args={"fluid": "R717", "temperature": {"value": 200, "unit": "degF"}}),
                              "attempt-range").to_dict()
        self.assertEqual(out["raw_result"]["structuredContent"]["receipt"]["error"]["code"], "outside_table_range")

    def test_unknown_or_formal_capability_is_not_dispatched(self):
        fake = FakeExecutor(self.ok)
        cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT, executor=fake)
        for req in (refr_request("shell", {}), request("saturation_pressure", {}, "foundation_math"),
                    request("saturation_pressure", {}, "foundation_refrigeration", required_evidence="formal_proof")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), ("unavailable", "not_dispatched"))
        self.assertEqual(fake.calls, 0)


    def test_dishonest_or_mismatched_replies_quarantine(self):
        receipt = lambda x: x["result"]["structuredContent"]["receipt"]  # noqa: E731
        mutations = [
            lambda x: x.update(id=1),
            lambda x: x.update(jsonrpc="1.0"),
            lambda x: x.update(error={"code": -1, "message": "ambiguous"}),
            lambda x: x["result"].update(isError=0),
            lambda x: x["result"]["structuredContent"].update(tool="exposure_limits"),
            lambda x: x["result"]["structuredContent"].update(formal_proof=True),
            lambda x: x["result"]["structuredContent"].update(runtime_goal_acceptance=True),
            lambda x: x["result"]["structuredContent"].update(assessment="diagnosis_complete"),
            lambda x: receipt(x)["boundary"].update(control_action=True),
            lambda x: receipt(x)["boundary"].update(engineering_determination=True),
            lambda x: receipt(x).update(input_sha256="0" * 64),
            lambda x: receipt(x)["evidence"][0]["evidence"].update(status="VERIFIED"),
            lambda x: receipt(x)["evidence"][0]["evidence"].update(status="APPROVED"),
            lambda x: receipt(x).update(evidence=[]),
            lambda x: receipt(x)["result"].update(pressure={"value": 209.5, "unit": "psi"}),
            lambda x: receipt(x).update(status="error"),
            lambda x: x["result"].update(extra="unsupported")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT, executor=FakeExecutor(self.ok, mutate))
                cap._ready = True
                out = cap.invoke(refr_request(), "attempt-mutated").to_dict()
                self.assertEqual(out["execution_status"], "protocol_error")
                self.assertIsNone(out["raw_result"])

    def test_malformed_duplicate_nonfinite_and_oversized_output_quarantine(self):
        for raw in (b'{"jsonrpc":"2.0"}', b'{}\n', b'{}\n{}\n{}\n', b'\xff\n{}\n', b'{"id":1,"id":1}\n{}\n',
                    b'{"x":NaN}\n{}\n', b'{"x":Infinity}\n{}\n', b'x' * 1_048_577 + b'\n{}\n'):
            cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT, executor=FakeExecutor(raw=raw))
            cap._ready = True
            out = cap.invoke(refr_request(), "attempt-wire").to_dict()
            self.assertEqual(out["execution_status"], "protocol_error")
            self.assertIsNone(out["raw_result"])

    def test_exact_input_controls_do_not_dispatch(self):
        fake = FakeExecutor(self.ok)
        cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT, executor=fake)
        for args in ({"fluid": "R717", "temperature": {"value": 1e-05, "unit": "degC"}},
                     {"fluid": "R717", "temperature": {"value": 1e20, "unit": "degC"}},
                     {"fluid": "x" * 1025}, {"n": 10 ** 16}, {"padding": ["x"] * 4096}):
            out = cap.invoke(refr_request(args=args), "attempt-input").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), ("resource_rejected", "not_dispatched"))
        self.assertEqual(fake.calls, 0)

    def test_numeric_profiles_are_distinct(self):
        self.assertEqual(decode(b'{"x":12.5}'), {"x": 12.5})
        for raw in (b'{"x":1,"x":2}', b'{"x":1e3}', b'{"x":NaN}', b'{"x":-Infinity}', b'\xff', b'[' * 33 + b']' * 33):
            with self.assertRaises(WireFailure):
                decode(raw)
        self.assertNotEqual(REFRIGERATION_DOMAIN.numeric_semantics, MATH_DOMAIN.numeric_semantics)
        self.assertIn("explicit unit", REFRIGERATION_DOMAIN.numeric_semantics)


@unittest.skipUnless(HAVE_REFRIGERATION, NO_REFRIGERATION)
class SiblingConformanceTests(unittest.TestCase):
    def test_sibling_not_subclass_and_no_math_import(self):
        self.assertTrue(issubclass(FoundationRefrigeration, PoodoCore))
        self.assertFalse(issubclass(FoundationRefrigeration, FoundationMath))
        for path in (ROOT / "extensions/foundation_refrigeration.py", ROOT / "adapters/refrigeration_stdio.py"):
            modules = {n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"extensions.foundation_math", "adapters.math_stdio"} & modules, path)
        code = ("import sys; from extensions.foundation_refrigeration import FoundationRefrigeration; "
                "print([m for m in sys.modules if m.startswith(('foundation_math', 'extensions.foundation_math', 'mcp'))])")
        proc = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(proc.stdout.strip(), b"[]")

    def test_cross_domain_binding_is_refused(self):
        grant = AuthorityGrant("x", "foundation_refrigeration", "foundation_refrigeration", ("saturation_pressure",), ("g",), 1, lane="ToolFace")
        cap = RefrigerationStdioCapability(DEFAULT_REFRIGERATION_ROOT)
        with self.assertRaises(ContractError):
            FoundationMath(cap, (grant,), MemoryLedger())
        math_grant = AuthorityGrant("m", "foundation_math", "foundation_math", ("exact_scalar",), ("g",), 1, lane="ToolFace")
        with self.assertRaises(ContractError):
            FoundationRefrigeration(cap, (math_grant,), MemoryLedger())
        with self.assertRaises(ContractError):
            FoundationRefrigeration(cap, (AuthorityGrant("w", "foundation_refrigeration", "foundation_refrigeration",
                                                         ("write_setpoint",), ("g",), 1, lane="ToolFace"),), MemoryLedger())


class CoreBoundaryTests(unittest.TestCase):
    """Not Refrigeration-specific; they run whether or not Refrigeration is present."""

    def test_poodo_core_bytes_match_current_pin(self):
        # ADR 002 left the core unchanged; ADR 003 and later PRs changed it on purpose, each adding a new pin key.
        # Earlier pins stay as history; the newest (last) poodo_core_* pin is the current one.
        pins = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())
        pinned = [v for k, v in pins.items() if k.startswith("poodo_core_")][-1]["files"]
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((ROOT / "poodo_core").glob("*.py"))}
        self.assertEqual(actual, pinned)

    def test_unimplemented_parts_stay_listed(self):
        self.assertNotIn("foundation_refrigeration", UNIMPLEMENTED_FOUNDATIONS)
        for key in ("foundation_engine", "lean", "endoforge", "foundation_refrigeration.rules",
                    "foundation_refrigeration.reference_plants", "foundation_refrigeration.determinations"):
            self.assertIn(key, UNIMPLEMENTED_FOUNDATIONS)

    def test_executor_module_is_fixed_host_choice(self):
        with self.assertRaises(ValueError):
            LocalBridgeExecutor(DEFAULT_MATH_ROOT, module="os")
        self.assertEqual(LocalBridgeExecutor(DEFAULT_MATH_ROOT)._module, "foundation_math_bridge")


@unittest.skipUnless(HAVE_REFRIGERATION, NO_REFRIGERATION)
class RefrigerationCliTests(unittest.TestCase):
    def run_cli(self, raw):
        return subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), "cli.py"],
                              cwd=ROOT, input=raw, capture_output=True, timeout=60)

    def test_real_refrigeration_round_trip(self):
        result = self.run_cli(EXAMPLE.read_bytes())
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        outcomes = [e["data"]["outcome"] for e in document["events"] if e["kind"] == "outcome"]
        self.assertEqual([(o["operation"], o["execution_status"], o["assessment"]) for o in outcomes], [
            ("saturation_pressure", "completed", "saturation_pressure_observed"),
            ("check_reading_against_saturation", "completed", "reading_compared_to_saturation"),
            ("exposure_limits", "completed", "exposure_limits_listed"),
            ("resolve_equipment_kind", "completed", "equipment_kind_resolved"),
            ("saturation_temperature", "tool_error", "tool_error")])
        views = outcomes[0]["raw_result"]["structuredContent"]["receipt"]["result"]["pressure_views"]
        self.assertEqual(round(next(v["value"] for v in views if v["unit"] == "psig"), 2), 33.49)
        self.assertFalse(document["goal"]["closed"])
        self.assertFalse(document["mcp_compatible"])
        self.assertEqual(result.stderr, b"")

    def test_parent_directory_module_entrypoint(self):
        result = subprocess.run([sys.executable, "-B", "-m", ROOT.name], cwd=ROOT.parent, input=EXAMPLE.read_bytes(),
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_forged_or_cross_domain_documents_are_rejected(self):
        raw = EXAMPLE.read_bytes()
        for mutate in (lambda d: d.update(grant={"all": True}),
                       lambda d: d["calls"][0]["request"].update(capability_id="foundation_math"),
                       lambda d: d["calls"][0]["request"].update(operation="write_setpoint"),
                       lambda d: d["calls"][0]["request"].update(required_evidence="formal_proof"),
                       lambda d: d["goal"].update(domain_id="foundation_engine")):
            document = json.loads(raw)
            mutate(document)
            self.assertEqual(self.run_cli(json.dumps(document).encode()).returncode, 2)
        self.assertEqual(self.run_cli(raw.replace(b'"value": 15.69', b'"value": 1.569e1')).returncode, 2)
        self.assertEqual(self.run_cli(raw.replace(b'"value": 15.69', b'"value": NaN')).returncode, 2)


if __name__ == "__main__":
    unittest.main()

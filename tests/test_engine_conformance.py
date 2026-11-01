"""Foundation Engine as a sibling POODO extension from a partial vendor copy: pins, real calls, fail-closed controls."""
import ast
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from adapters.engine_stdio import decode as engine_decode
from adapters.wire import WireFailure
from adapters.engine_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, SOURCE_FILE_COUNT, SOURCE_SHA256,
                                   VENDORED_FILES, EngineStdioCapability, PinnedEngineSource)
from adapters.execution import ProcessResult
from adapters.memory_ledger import MemoryLedger
from adapters.wire import encode
from bootstrap import DEFAULT_ENGINE_ROOT, build_domain
from extensions.foundation_engine import ENGINE_DOMAIN_ID, ENGINE_TOOL_NAMES, FoundationEngine
from extensions.foundation_math import FoundationMath
from poodo_core import AuthorityGrant, ContractError, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]


def engine_request(operation="validate_render_mask", args=None, i=1, **kw):
    return request(operation, {"mask": 1} if args is None else args, ENGINE_DOMAIN_ID, i=i, **kw)


class FakeExecutor:
    def __init__(self, result=None, mutation=None):
        self.result, self.mutation, self.calls = result, mutation, 0

    def exchange(self, frames, cancellation=None):
        self.calls += 1
        hello = {"jsonrpc": "2.0", "id": "cstack-init", "result": {"protocolVersion": BRIDGE_PROTOCOL,
                 "mcpCompatible": False, "limits": {"inputFrameBytes": 65_536, "outputFrameBytes": 1_048_576}}}
        reply = {"jsonrpc": "2.0", "id": json.loads(frames[1])["id"], "result": copy.deepcopy(self.result)}
        if self.mutation:
            self.mutation(reply)
        return ProcessResult("completed", "responded", encode(hello) + b"\n" + encode(reply) + b"\n", b"", 0)


class EngineAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = EngineStdioCapability(DEFAULT_ENGINE_ROOT)

    def test_pins_match_the_vendor_copy_and_contracts(self):
        self.assertEqual(PinnedEngineSource(DEFAULT_ENGINE_ROOT).verify(),
                         {"source_manifest_sha256": SOURCE_SHA256, "verified_files": len(VENDORED_FILES)})
        manifest = json.loads((DEFAULT_ENGINE_ROOT / "SOURCE-MANIFEST.json").read_text())
        self.assertEqual(len(manifest["files"]), SOURCE_FILE_COUNT)
        pins_path = ROOT / "contracts/SOURCE-PINS.json"
        if pins_path.is_file():
            pins = json.loads(pins_path.read_text())["foundation_engine"]
            self.assertEqual((pins["source_manifest_sha256"], pins["source_manifest_entry_count"],
                              pins["inventory_sha256"]), (SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256))
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), ENGINE_TOOL_NAMES)

    def test_real_read_only_calls_through_the_vendored_bridge(self):
        for operation, args, value in (("validate_render_mask", {"mask": 4294967295}, 4294967295),
                                       ("validate_scene_output", {"output": {"toneMapping": "agx", "exposure": 2}},
                                        {"toneMapping": "agx", "exposure": 2}),
                                       ("validate_scene_output", {}, {"toneMapping": "none", "exposure": 1})):
            out = self.cap.invoke(engine_request(operation, args), "attempt-real").to_dict()
            self.assertEqual((out["execution_status"], out["assessment"]), ("completed", "engine_value_validated"))
            self.assertEqual(out["raw_result"], {"isError": False, "structuredContent": value})
            self.assertFalse(out["formal_proof"] or out["runtime_goal_acceptance"])

    def test_real_round_trip_through_the_inherited_core(self):
        foundation, _ = build_domain(ENGINE_DOMAIN_ID, "g")
        to_decide(foundation, domain=ENGINE_DOMAIN_ID)
        req = engine_request()
        foundation.decide(req, precommit())
        foundation.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted fixture"))
        out = foundation.execute(req.decision_id).to_dict()
        self.assertEqual((out["execution_status"], out["raw_result"]["structuredContent"]), ("completed", 1))
        self.assertFalse(foundation.snapshot("g").closed)

    def test_decimal_exposure_round_trips_through_the_bridge_and_the_core(self):
        args = {"output": {"toneMapping": "agx", "exposure": 1.25}}
        out = self.cap.invoke(engine_request("validate_scene_output", args), "attempt-decimal").to_dict()
        self.assertEqual((out["execution_status"], out["raw_result"]["structuredContent"]),
                         ("completed", {"toneMapping": "agx", "exposure": 1.25}))
        foundation, _ = build_domain(ENGINE_DOMAIN_ID, "g")
        to_decide(foundation, domain=ENGINE_DOMAIN_ID)
        req = engine_request("validate_scene_output", args)
        foundation.decide(req, precommit())
        foundation.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted fixture"))
        self.assertEqual(foundation.execute(req.decision_id).to_dict()["raw_result"]["structuredContent"]["exposure"], 1.25)

    def test_exponent_and_nonfinite_numbers_never_dispatch(self):
        fake = FakeExecutor({"isError": False, "structuredContent": 1})
        cap = EngineStdioCapability(DEFAULT_ENGINE_ROOT, executor=fake)
        for exposure in (1e-05, 1e20):
            out = cap.invoke(engine_request("validate_scene_output", {"output": {"exposure": exposure}}), "a").to_dict()
            self.assertEqual(out["execution_certainty"], "not_dispatched")
        self.assertEqual(fake.calls, 0)

    def test_nonfinite_or_overlong_reply_numbers_quarantine(self):
        for token in (b"NaN", b"1e999", b"1." + b"0" * 40):
            with self.assertRaises(WireFailure):
                engine_decode(b"{\"x\":" + token + b"}", response=True)

    def test_out_of_schema_input_is_a_bridge_error_not_an_observation(self):
        out = self.cap.invoke(engine_request(args={"mask": 4294967296}), "attempt-bad").to_dict()
        self.assertEqual((out["execution_status"], out["assessment"], out["raw_result"]),
                         ("protocol_error", "bridge_error_32602", None))

    def test_dishonest_replies_quarantine(self):
        ok = {"isError": False, "structuredContent": 1}
        for mutate in (lambda x: x["result"].update(isError=True),
                       lambda x: x["result"].update(structuredContent=-1),
                       lambda x: x["result"].update(structuredContent={"mask": 1}),
                       lambda x: x["result"].update(extra=1)):
            cap = EngineStdioCapability(DEFAULT_ENGINE_ROOT, executor=FakeExecutor(ok, mutate))
            cap._ready = True
            out = cap.invoke(engine_request(), "attempt-mutated").to_dict()
            self.assertEqual((out["execution_status"], out["raw_result"]), ("protocol_error", None))

    def test_unknown_unpinned_or_changed_sources_never_dispatch(self):
        fake = FakeExecutor({"isError": False, "structuredContent": 1})
        cap = EngineStdioCapability(DEFAULT_ENGINE_ROOT, executor=fake)
        for req, status in ((engine_request(args={"mask": 1.5}), "resource_rejected"),
                            (request("read_file", {}, ENGINE_DOMAIN_ID), "unavailable"),
                            (engine_request(required_evidence="formal_proof"), "unavailable")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), (status, "not_dispatched"))
        with tempfile.TemporaryDirectory() as td:
            copy_root = Path(td) / "engine"
            shutil.copytree(DEFAULT_ENGINE_ROOT, copy_root)
            (copy_root / "extra.py").write_text("")
            with_extra = EngineStdioCapability(copy_root, executor=fake).invoke(engine_request(), "a").to_dict()
            (copy_root / "extra.py").unlink()
            bridge = copy_root / "tools/foundation_engine_bridge.py"
            bridge.write_text(bridge.read_text() + "\n")
            changed = EngineStdioCapability(copy_root, executor=fake).invoke(engine_request(), "a").to_dict()
            for out in (with_extra, changed):
                self.assertEqual(out["assessment"], "source_identity_unavailable")
        self.assertEqual(fake.calls, 0)

    def test_sibling_not_subclass_and_cross_domain_binding_refused(self):
        self.assertTrue(issubclass(FoundationEngine, PoodoCore))
        self.assertFalse(issubclass(FoundationEngine, FoundationMath))
        for path in (ROOT / "extensions/foundation_engine.py", ROOT / "adapters/engine_stdio.py"):
            modules = {n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"extensions.foundation_math", "adapters.math_stdio"} & modules, path)
        math_grant = AuthorityGrant("m", "foundation_math", "foundation_math", ("exact_scalar",), ("g",), 1, lane="ToolFace")
        with self.assertRaises(ContractError):
            FoundationEngine(self.cap, (math_grant,), MemoryLedger())


if __name__ == "__main__":
    unittest.main()

"""Foundation Template as a sibling POODO extension: pins, round trip and fail-closed controls on the shared bridge."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.execution import ProcessResult
from adapters.foundation_stdio import arguments_sha256
from adapters.memory_ledger import MemoryLedger
from adapters.template_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, SOURCE_FILE_COUNT, SOURCE_SHA256,
                                     PinnedTemplateSource, TemplateStdioCapability)
from adapters.wire import encode
from extensions.foundation_math import FoundationMath
from extensions.foundation_template import FoundationTemplate, TEMPLATE_DOMAIN_ID, TEMPLATE_TOOL_NAMES
from poodo_core import AuthorityGrant, ContractError, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "foundations/template"
ECHO = {"observation": "fixture reading"}


def echo_request(args=None, i=1, **kw):
    return request("echo_observation", ECHO if args is None else args, TEMPLATE_DOMAIN_ID, i=i, **kw)


def core():
    grant = AuthorityGrant("test-template", TEMPLATE_DOMAIN_ID, TEMPLATE_DOMAIN_ID, TEMPLATE_TOOL_NAMES, ("g",), 8,
                           lane="ToolFace")
    return FoundationTemplate(TemplateStdioCapability(TEMPLATE_ROOT), (grant,), MemoryLedger())


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


class TemplateAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = TemplateStdioCapability(TEMPLATE_ROOT)
        cls.ok = cls.cap.invoke(echo_request(), "attempt-control").to_dict()["raw_result"]

    def test_pins_match_the_foundation_and_contracts(self):
        self.assertEqual(PinnedTemplateSource(TEMPLATE_ROOT).verify(),
                         {"source_manifest_sha256": SOURCE_SHA256, "verified_files": SOURCE_FILE_COUNT})
        pins_path = ROOT / "contracts/SOURCE-PINS.json"  # private record; the open-core export leaves it out
        if pins_path.is_file():
            pins = json.loads(pins_path.read_text())["foundation_template"]
            self.assertEqual((pins["source_manifest_sha256"], pins["source_manifest_entry_count"],
                              pins["inventory_sha256"]), (SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256))
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), TEMPLATE_TOOL_NAMES)

    def test_real_round_trip_through_the_inherited_core(self):
        foundation = core()
        to_decide(foundation, domain=TEMPLATE_DOMAIN_ID)
        req = echo_request()
        foundation.decide(req, precommit())
        foundation.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted fixture"))
        out = foundation.execute(req.decision_id).to_dict()
        receipt = out["raw_result"]["structuredContent"]["receipt"]
        self.assertEqual((out["execution_status"], out["assessment"]), ("completed", "observation_echoed"))
        self.assertEqual((receipt["result"], receipt["input_sha256"]), (ECHO, arguments_sha256(ECHO)))
        self.assertTrue(receipt["evidence"])
        self.assertFalse(out["formal_proof"] or out["runtime_goal_acceptance"] or foundation.snapshot("g").closed)

    def test_bad_arguments_are_a_retained_tool_error(self):
        out = self.cap.invoke(echo_request({"observation": ""}), "attempt-empty").to_dict()
        self.assertEqual((out["execution_status"], out["assessment"]), ("tool_error", "tool_error"))
        self.assertTrue(out["raw_result"]["structuredContent"]["receipt"]["evidence"])

    def test_dishonest_replies_quarantine(self):
        receipt = lambda x: x["result"]["structuredContent"]["receipt"]  # noqa: E731
        for mutate in (lambda x: receipt(x)["boundary"].update(control_action=True),
                       lambda x: receipt(x).update(input_sha256="0" * 64),
                       lambda x: receipt(x).update(evidence=[]),
                       lambda x: receipt(x).update(status="error"),
                       lambda x: x["result"]["structuredContent"].update(formal_proof=True),
                       lambda x: x["result"]["structuredContent"].update(tool="other")):
            cap = TemplateStdioCapability(TEMPLATE_ROOT, executor=FakeExecutor(self.ok, mutate))
            cap._ready = True
            out = cap.invoke(echo_request(), "attempt-mutated").to_dict()
            self.assertEqual((out["execution_status"], out["raw_result"]), ("protocol_error", None))

    def test_out_of_profile_unknown_or_unpinned_requests_never_dispatch(self):
        fake = FakeExecutor(self.ok)
        cap = TemplateStdioCapability(TEMPLATE_ROOT, executor=fake)
        for req, status in ((echo_request({"observation": 1.5}), "resource_rejected"),
                            (request("read_file", {}, TEMPLATE_DOMAIN_ID), "unavailable"),
                            (echo_request(required_evidence="formal_proof"), "unavailable")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), (status, "not_dispatched"))
        with tempfile.TemporaryDirectory() as td:
            out = TemplateStdioCapability(Path(td), executor=fake).invoke(echo_request(), "attempt-src").to_dict()
            self.assertEqual(out["assessment"], "source_identity_unavailable")
        self.assertEqual(fake.calls, 0)

    def test_sibling_not_subclass_and_cross_domain_binding_refused(self):
        self.assertTrue(issubclass(FoundationTemplate, PoodoCore))
        self.assertFalse(issubclass(FoundationTemplate, FoundationMath))
        for path in (ROOT / "extensions/foundation_template.py", ROOT / "adapters/template_stdio.py"):
            modules = {n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"extensions.foundation_math", "adapters.math_stdio"} & modules, path)
        math_grant = AuthorityGrant("m", "foundation_math", "foundation_math", ("exact_scalar",), ("g",), 1, lane="ToolFace")
        with self.assertRaises(ContractError):
            FoundationTemplate(self.cap, (math_grant,), MemoryLedger())


if __name__ == "__main__":
    unittest.main()

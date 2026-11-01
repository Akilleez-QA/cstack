"""Foundation Robotics as a sibling POODO extension: pins, round trips and fail-closed controls on the shared bridge."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.execution import ProcessResult
from adapters.foundation_stdio import arguments_sha256
from adapters.memory_ledger import MemoryLedger
from adapters.wire import encode
from bootstrap import DEFAULT_ROBOTICS_ROOT, DOMAINS
from extensions.foundation_math import FoundationMath
from poodo_core import AuthorityGrant, ContractError, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
# A checkout without foundations/robotics (the open-core export) skips every test here.
HAVE_ROBOTICS = DEFAULT_ROBOTICS_ROOT.is_dir()
if HAVE_ROBOTICS:
    from adapters.robotics_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, SOURCE_FILE_COUNT, SOURCE_SHA256,
                                         PinnedRoboticsSource, RoboticsStdioCapability)
    from extensions.foundation_robotics import FoundationRobotics, ROBOTICS_DOMAIN_ID, ROBOTICS_TOOL_NAMES

FEET = [[-100, 0, -50], [100, 0, -50], [-100, 0, 200], [100, 0, 200]]
LEG = {"joints": [{"id": "hip", "type": "revolute", "axis": [1, 0, 0], "origin_mm": [0, 0, 0], "min": -2000,
                   "max": 2000},
                  {"id": "knee", "type": "revolute", "axis": [1, 0, 0], "origin_mm": [0, -450, 0], "min": 0,
                   "max": 2500}], "tip_mm": [0, -450, 0]}
CASES = {
    "scale_timing": ({"height_mm": 6000}, "timing_estimated"),
    "gait_check": ({"height_mm": 6000, "speed_mm_s": 1450, "stride_mm": 7135}, "thresholds_not_met"),
    "balance_check": ({"fps_milli": 30000, "mode": "static", "frames": [{"com_mm": [0, 900, 75], "support_mm": FEET}]},
                      "thresholds_met"),
    "ik_check": ({**LEG, "poses": [{"q": [0, 0], "target_mm": [0, -900, 0]}]}, "thresholds_not_met"),
    "mechanism_check": ({"kind": "gear_train", "input": "male", "input_speed_mrad_s": 371755,
                         "stages": [{"driver": "male", "driven": "female", "driver_teeth": 4, "driven_teeth": 6,
                                     "mesh": "external"}], "measured_speeds_mrad_s": {"female": -247837}},
                        "thresholds_met"),
    "squash_check": ({"frames": [{"scale_permille": [1180, 780, 1180]}]}, "thresholds_not_met"),
}


def robotics_request(name="squash_check", args=None, i=1, **kw):
    return request(name, CASES[name][0] if args is None else args, ROBOTICS_DOMAIN_ID, i=i, **kw)


def core():
    grant = AuthorityGrant("test-robotics", ROBOTICS_DOMAIN_ID, ROBOTICS_DOMAIN_ID, ROBOTICS_TOOL_NAMES, ("g",), 16, lane="ToolFace")
    return FoundationRobotics(RoboticsStdioCapability(DEFAULT_ROBOTICS_ROOT), (grant,), MemoryLedger())


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


@unittest.skipUnless(HAVE_ROBOTICS, "Foundation Robotics is not in this checkout (foundations/robotics is absent)")
class RoboticsAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = RoboticsStdioCapability(DEFAULT_ROBOTICS_ROOT)
        cls.ok = cls.cap.invoke(robotics_request(), "attempt-control").to_dict()["raw_result"]

    def test_pins_match_the_foundation_contracts_and_registry(self):
        self.assertEqual(PinnedRoboticsSource(DEFAULT_ROBOTICS_ROOT).verify(),
                         {"source_manifest_sha256": SOURCE_SHA256, "verified_files": SOURCE_FILE_COUNT})
        pins_path = ROOT / "contracts/SOURCE-PINS.json"  # private record; the open-core export leaves it out
        if pins_path.is_file():
            pins = json.loads(pins_path.read_text())["foundation_robotics"]
            self.assertEqual((pins["source_manifest_sha256"], pins["source_manifest_entry_count"],
                              pins["inventory_sha256"]), (SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256))
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), ROBOTICS_TOOL_NAMES)
        self.assertEqual(DOMAINS[ROBOTICS_DOMAIN_ID].tool_names, ROBOTICS_TOOL_NAMES)

    def test_every_tool_round_trips_over_the_real_bridge_with_evidence(self):
        for i, (name, (arguments, assessment)) in enumerate(CASES.items()):
            out = self.cap.invoke(robotics_request(name, i=i + 2), f"attempt-{name}").to_dict()
            receipt = out["raw_result"]["structuredContent"]["receipt"]
            self.assertEqual((out["execution_status"], out["assessment"]), ("completed", assessment), name)
            self.assertEqual(receipt["input_sha256"], arguments_sha256(arguments))
            self.assertTrue(receipt["evidence"])
            self.assertFalse(receipt["boundary"]["acceptance_decision"])

    def test_real_round_trip_through_the_inherited_core(self):
        foundation = core()
        to_decide(foundation, domain=ROBOTICS_DOMAIN_ID)
        req = robotics_request()
        foundation.decide(req, precommit())
        foundation.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted fixture"))
        out = foundation.execute(req.decision_id).to_dict()
        receipt = out["raw_result"]["structuredContent"]["receipt"]
        self.assertEqual((out["execution_status"], out["assessment"]), ("completed", "thresholds_not_met"))
        self.assertEqual(receipt["result"]["frames"][0]["volume_permille"], 1086)
        self.assertFalse(out["formal_proof"] or out["runtime_goal_acceptance"] or foundation.snapshot("g").closed)

    def test_bad_arguments_are_a_retained_tool_error(self):
        out = self.cap.invoke(robotics_request(args={"frames": [{"scale_permille": [1000, 0, 1000]}]}),
                              "attempt-bad").to_dict()
        self.assertEqual((out["execution_status"], out["assessment"]), ("tool_error", "tool_error"))
        self.assertTrue(out["raw_result"]["structuredContent"]["receipt"]["evidence"])

    def test_dishonest_replies_quarantine(self):
        receipt = lambda x: x["result"]["structuredContent"]["receipt"]  # noqa: E731
        for mutate in (lambda x: receipt(x)["boundary"].update(acceptance_decision=True),
                       lambda x: receipt(x).update(input_sha256="0" * 64),
                       lambda x: receipt(x).update(evidence=[]),
                       lambda x: receipt(x)["result"].update(verdict="accepted"),
                       lambda x: receipt(x)["result"].update(worst_frame=-1),
                       lambda x: x["result"]["structuredContent"].update(assessment="animation_accepted"),
                       lambda x: x["result"]["structuredContent"].update(runtime_goal_acceptance=True)):
            cap = RoboticsStdioCapability(DEFAULT_ROBOTICS_ROOT, executor=FakeExecutor(self.ok, mutate))
            cap._ready = True
            out = cap.invoke(robotics_request(), "attempt-mutated").to_dict()
            self.assertEqual((out["execution_status"], out["raw_result"]), ("protocol_error", None))

    def test_out_of_profile_unknown_or_unpinned_requests_never_dispatch(self):
        fake = FakeExecutor(self.ok)
        cap = RoboticsStdioCapability(DEFAULT_ROBOTICS_ROOT, executor=fake)
        for req, status in ((robotics_request(args={"frames": [{"scale_permille": [1.18, 0.78, 1.18]}]}),
                             "resource_rejected"),
                            (request("drive_motor", {}, ROBOTICS_DOMAIN_ID), "unavailable"),
                            (robotics_request(required_evidence="formal_proof"), "unavailable")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), (status, "not_dispatched"))
        with tempfile.TemporaryDirectory() as td:
            out = RoboticsStdioCapability(Path(td), executor=fake).invoke(robotics_request(), "attempt-src").to_dict()
            self.assertEqual(out["assessment"], "source_identity_unavailable")
        self.assertEqual(fake.calls, 0)

    def test_sibling_not_subclass_and_cross_domain_binding_refused(self):
        self.assertTrue(issubclass(FoundationRobotics, PoodoCore))
        self.assertFalse(issubclass(FoundationRobotics, FoundationMath))
        for path in (ROOT / "extensions/foundation_robotics.py", ROOT / "adapters/robotics_stdio.py"):
            modules = {n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"extensions.foundation_math", "adapters.math_stdio", "extensions.foundation_refrigeration",
                              "adapters.refrigeration_stdio"} & modules, path)
        math_grant = AuthorityGrant("m", "foundation_math", "foundation_math", ("exact_scalar",), ("g",), 1, lane="ToolFace")
        with self.assertRaises(ContractError):
            FoundationRobotics(self.cap, (math_grant,), MemoryLedger())


if __name__ == "__main__":
    unittest.main()

"""The stdio bridge: fixed inventory, fail-closed transport, exact receipts with Evidence, no determinations."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from foundation_refrigeration.tools import TOOL_NAMES, run
from foundation_refrigeration_bridge.schemas import tool_definitions
from foundation_refrigeration_bridge.server import (MAX_FRAME_BYTES, PROTOCOL, Bridge, decode_frame, serve,
                                                    WireError)

ROOT = Path(__file__).resolve().parents[1]
INIT = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": PROTOCOL}}
CASES = {
    "saturation_pressure": {"fluid": "R717", "temperature": {"value": 20, "unit": "degF"}},
    "saturation_temperature": {"fluid": "R448A", "pressure": {"value": 30.5, "unit": "psig"}, "side": "dew",
                               "atmosphere": {"basis": "elevation", "elevation": {"value": 250, "unit": "m"}}},
    "convert_pressure": {"pressure": {"value": 181.1, "unit": "psig"}, "to_unit": "bar(g)"},
    "convert_temperature": {"temperature": {"value": -28, "unit": "degF"}, "to_unit": "degC"},
    "check_reading_against_saturation": {"fluid": "ammonia", "pressure": {"value": 15.69, "unit": "psig"},
                                         "temperature": {"value": 10.0, "unit": "degF"}},
    "exposure_limits": {"substance": "ammonia", "policy_set_points": [
        {"label": "Evacuation level", "concentration": {"value": 150, "unit": "ppm"},
         "set_by": "Plant safety committee", "scope": "plant", "reason": "Site emergency plan"}]},
    "resolve_equipment_kind": {"term": "screw-package"},
}


def call(bridge, name, arguments, ident="c"):
    return bridge.dispatch({"jsonrpc": "2.0", "id": ident, "method": "tools/call",
                            "params": {"name": name, "arguments": arguments}})


def ready():
    bridge = Bridge()
    if bridge.dispatch(INIT)["result"]["protocolVersion"] != PROTOCOL:
        raise AssertionError("Bridge did not initialise")
    return bridge


class InventoryTests(unittest.TestCase):
    def test_fixed_seven_tool_inventory(self):
        names = tuple(t["name"] for t in tool_definitions())
        self.assertEqual(names, TOOL_NAMES)
        self.assertEqual(len(names), 7)
        for tool in tool_definitions():
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertFalse(tool["outputSchema"]["additionalProperties"])
            self.assertIn("Not MCP", tool["description"])
            self.assertIn("not an engineering, safety or compliance determination", tool["description"])
        self.assertEqual(tool_definitions(), tool_definitions())

    def test_handshake_and_ordering(self):
        bridge = Bridge()
        self.assertEqual(bridge.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["error"]["code"], -32000)
        wrong = bridge.dispatch({**INIT, "params": {"protocolVersion": "foundation-math-jsonrpc/1"}})
        self.assertEqual(wrong["error"]["code"], -32001)
        hello = bridge.dispatch(INIT)["result"]
        self.assertFalse(hello["mcpCompatible"])
        self.assertEqual(hello["limits"]["inputFrameBytes"], 65_536)
        self.assertEqual(hello["limits"]["outputFrameBytes"], 1_048_576)
        self.assertEqual(bridge.dispatch(INIT)["error"]["code"], -32000)
        self.assertEqual(len(bridge.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]), 7)
        self.assertIsNone(bridge.dispatch({"jsonrpc": "2.0", "method": "tools/call", "params": {}}))
        self.assertEqual(call(bridge, "shell", {})["error"]["code"], -32602)
        self.assertEqual(bridge.dispatch({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})["error"]["code"], -32601)


class ReceiptTests(unittest.TestCase):
    def test_every_tool_succeeds_with_evidence_and_boundary(self):
        bridge = ready()
        for name, arguments in CASES.items():
            with self.subTest(tool=name):
                reply = call(bridge, name, arguments)["result"]
                self.assertIs(reply["isError"], False)
                content = reply["structuredContent"]
                self.assertEqual(content["tool"], name)
                self.assertIs(content["formal_proof"], False)
                self.assertIs(content["runtime_goal_acceptance"], False)
                receipt = content["receipt"]
                self.assertEqual(receipt["status"], "success")
                self.assertTrue(receipt["evidence"])
                for entry in receipt["evidence"]:
                    self.assertIn(entry["evidence"]["status"], ("CHECK", "DISPUTED", "APPROVED"))
                self.assertEqual(receipt["boundary"], {"observation_only": True, "engineering_determination": False,
                    "safety_determination": False, "compliance_determination": False, "diagnosis": False,
                    "control_action": False})
                self.assertIn("A tool observation is not an engineering, safety or compliance determination.",
                              receipt["limitations"])

    def test_receipts_are_deterministic_and_bind_the_input(self):
        first = run("saturation_pressure", CASES["saturation_pressure"])
        second = run("saturation_pressure", json.loads(json.dumps(CASES["saturation_pressure"])))
        self.assertEqual(first, second)
        other = run("saturation_pressure", {"fluid": "R717", "temperature": {"value": 21, "unit": "degF"}})
        self.assertNotEqual(first[2]["input_sha256"], other[2]["input_sha256"])

    def test_check_reading_is_an_observation_with_named_deltas(self):
        _, assessment, receipt = run("check_reading_against_saturation", CASES["check_reading_against_saturation"])
        result = receipt["result"]
        self.assertEqual(assessment, "reading_compared_to_saturation")
        # 15.69 psig is R717 saturation at about 0 degF, so a 10 degF reading is about 10 degF above dew.
        self.assertAlmostEqual(result["superheat_style_delta"]["value_degf_difference"], 10.0, delta=0.02)
        self.assertEqual(result["superheat_style_delta"]["relation_to_dew"], "above")
        self.assertEqual(result["subcooling_style_delta"]["relation_to_bubble"], "above")
        self.assertIn("normal operating range", result["not_determined"])
        blend = run("check_reading_against_saturation", {"fluid": "R448A", "pressure": {"value": 300, "unit": "kPa(a)"},
                                                         "temperature": {"value": -15, "unit": "degC"}})[2]["result"]
        sat = blend["saturation_at_reading_pressure"]
        self.assertGreater(sat["dew_temperature"]["value"], sat["bubble_temperature"]["value"])

    def test_policy_and_published_limits_stay_separate(self):
        result = run("exposure_limits", CASES["exposure_limits"])[2]["result"]
        self.assertTrue(all(x["value_kind"] == "published_limit" for x in result["published_limits"]))
        self.assertEqual(result["policy_set_points"][0]["legal_status"], "not_a_legal_limit")
        self.assertEqual([g["id"] for g in result["gaps"]], ["erpg"])
        osha = run("exposure_limits", {"substance": "R717", "issuer": "OSHA"})[2]["result"]["published_limits"]
        self.assertEqual([(x["id"], x["concentration"]["value"]) for x in osha], [("osha-pel-twa", 50.0)])
        failed, assessment, receipt = run("exposure_limits", {"substance": "ammonia", "policy_set_points": [
            {**CASES["exposure_limits"]["policy_set_points"][0], "label": "OSHA PEL"}]})
        self.assertTrue(failed)
        self.assertEqual((assessment, receipt["error"]["code"]), ("tool_error", "invalid_policy"))

    def test_line_service_reports_disputes(self):
        result = run("resolve_equipment_kind", {"term": "LTRL", "vocabulary": "line_service"})[2]
        self.assertEqual(result["result"]["service"]["possible_equivalent"], "PL")
        self.assertEqual({d["status"] for d in result["result"]["open_decisions"]}, {"DISPUTED"})
        self.assertIn("DISPUTED", {e["evidence"]["status"] for e in result["evidence"]})
        self.assertEqual(run("resolve_equipment_kind", {"term": "warp core"})[1], "equipment_kind_unresolved")

    def test_tool_errors_are_errors_not_results(self):
        for name, arguments, code in (
                ("saturation_pressure", {"fluid": "R717", "temperature": {"value": 200, "unit": "degF"}}, "outside_table_range"),
                ("saturation_pressure", {"fluid": "R404A", "temperature": {"value": 0, "unit": "degC"}}, "side_required"),
                ("saturation_pressure", {"fluid": "R717", "temperature": 20}, "invalid_quantity"),
                ("saturation_pressure", {"fluid": "R717", "temperature": {"value": True, "unit": "degF"}}, "invalid_quantity"),
                ("saturation_temperature", {"fluid": "R717", "pressure": {"value": 20, "unit": "psi"}}, "invalid_quantity"),
                ("convert_pressure", {"pressure": {"value": 1, "unit": "psia"}, "to_unit": "atm"}, "invalid_unit"),
                ("convert_temperature", {"temperature": {"value": -500, "unit": "degF"}, "to_unit": "K"}, "invalid_quantity"),
                ("exposure_limits", {"substance": "chlorine"}, "unknown_substance"),
                ("resolve_equipment_kind", {"term": "x", "grant": True}, "invalid_arguments")):
            with self.subTest(name=name, arguments=arguments):
                failed, assessment, receipt = run(name, arguments)
                self.assertTrue(failed)
                self.assertEqual(assessment, "tool_error")
                self.assertEqual(receipt["error"]["code"], code)
                self.assertIsNone(receipt["result"])
                self.assertEqual(receipt["evidence"], [])


class TransportTests(unittest.TestCase):
    def test_numeric_profile_and_duplicate_keys(self):
        self.assertEqual(decode_frame(b'{"x":-12.5,"y":3}'), {"x": -12.5, "y": 3})
        for raw in (b'{"x":1,"x":2}', b'{"x":1e3}', b'{"x":1.5E-2}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":-Infinity}', b'{"x":1.' + b"1" * 30 + b'}', b'{"x":1234567890123456}',
                    b'\xff', b'[' * 33 + b']' * 33, b'{"s":"' + b"x" * 1025 + b'"}',
                    b'[' + b'0,' * 4096 + b'0]', b'x' * (MAX_FRAME_BYTES + 1)):
            with self.subTest(raw=raw[:40]), self.assertRaises(WireError):
                decode_frame(raw)

    def test_serve_round_trip_and_oversized_frame(self):
        frames = [INIT, {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                         "params": {"name": "convert_temperature", "arguments": CASES["convert_temperature"]}}]
        sink = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(b"".join(json.dumps(f).encode() + b"\n" for f in frames)), sink), 0)
        lines = sink.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        reply = json.loads(lines[1])
        self.assertEqual((reply["id"], reply["result"]["structuredContent"]["receipt"]["result"]["output"]),
                         (7, {"value": -33.3333, "unit": "degC"}))
        sink = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(b"x" * (MAX_FRAME_BYTES + 5) + b"\n"), sink), 2)
        self.assertEqual(json.loads(sink.getvalue())["error"]["code"], -32002)
        sink = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(json.dumps(INIT).encode()), sink), 2)

    def test_real_process_round_trip_without_options(self):
        payload = json.dumps(INIT) + "\n" + json.dumps({"jsonrpc": "2.0", "id": "p", "method": "tools/call",
            "params": {"name": "saturation_pressure", "arguments": CASES["saturation_pressure"]}}) + "\n"
        proc = subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), "-m",
                               "foundation_refrigeration_bridge"], cwd=ROOT, input=payload.encode(),
                              capture_output=True, timeout=30, env={"PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        views = json.loads(proc.stdout.splitlines()[1])["result"]["structuredContent"]["receipt"]["result"]["pressure_views"]
        psig = next(v["value"] for v in views if v["unit"] == "psig")
        self.assertEqual(round(psig, 2), 33.49)
        refused = subprocess.run([sys.executable, "-B", "-m", "foundation_refrigeration_bridge", "--root", "/"],
                                 cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(refused.returncode, 2)


if __name__ == "__main__":
    unittest.main()

import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bootstrap
from adapters.foundation_stdio import arguments_sha256
from adapters.foundations_mcp import COMBINATORS, META_KEY, FoundationsMcpServer, tool_name
from bootstrap import DOMAINS, build_aor_session, foundation_inventories
from poodo_core import ContractError
from tests.aor_fixtures import R717_20F, write_fleet
from tests.helpers import request

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools/foundations_mcp.py"
MATH_CASE = json.loads((ROOT / "examples/tool-cases.json").read_text())[0]
REPRESENTATIVE = {
    "foundation_math": (MATH_CASE["operation"], MATH_CASE["arguments"]),
    "foundation_template": ("echo_observation", {"observation": "synthetic reading 7"}),
    "foundation_engine": ("validate_scene_output", {"output": {"toneMapping": "agx", "exposure": 1.25}}),
    "foundation_refrigeration": ("saturation_pressure", R717_20F),
    "foundation_robotics": ("scale_timing", {"height_mm": 6000}),
    "foundation_film": ("audio_gate", {"integrated_lufs": -16200, "true_peak_dbtp": -1500, "voice_over_bed_db": 13500,
                                       "cuts": 10, "cuts_with_hit": 9, "heard": ["Speech", "Music"],
                                       "line_wer": [{"line": "b1-1", "wer_permille": 20}]}),
}
DIGEST_BOUND = set(REPRESENTATIVE) - {"foundation_engine", "foundation_math"}


class Host:
    def __init__(self, foundations=None, **fleet):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.foundations = list(DOMAINS) if foundations is None else foundations
        self.session = build_aor_session("alpha", state_root=root / "state", hostname="testbox",
                                         fleet_path=write_fleet(root, **fleet), foundations=self.foundations)
        self.server = FoundationsMcpServer(self.session, foundation_inventories(self.foundations))
        self.next_id = 0
        self.rpc("initialize", {"protocolVersion": "2025-11-25"})

    def rpc(self, method, params=None):
        self.next_id += 1
        return self.server.handle({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                                   **({} if params is None else {"params": params})})

    def call(self, name, arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments})

    def events(self, domain):
        return self.session.ledger(domain, 50)["events"]

    def close(self):
        self.session.close()
        self.directory.cleanup()


def direct(domain, operation, arguments):
    d = DOMAINS[domain]
    outcome = d.capability(d.source_root).invoke(request(operation, arguments, domain), "attempt-direct")
    return outcome.to_dict()["raw_result"]


class FoundationsMcpTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.addCleanup(self.host.close)

    def test_list_names_every_exposed_tool_with_its_pinned_schema(self):
        tools = self.host.rpc("tools/list")["result"]["tools"]
        inventories = foundation_inventories(list(DOMAINS))
        self.assertEqual([t["name"] for t in tools],
                         [tool_name(d, entry["name"]) for d, inventory in inventories.items() for entry in inventory])
        pinned = {tool_name(d, e["name"]): e for d, inventory in inventories.items() for e in inventory}
        for tool in tools:
            entry = pinned[tool["name"]]
            self.assertEqual(tool["description"], entry["description"])
            self.assertEqual(tool["annotations"]["readOnlyHint"], True)
            self.assertEqual(tool["annotations"]["destructiveHint"], False)
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertFalse(set(tool["inputSchema"]) & set(COMBINATORS))
            if not set(entry["inputSchema"]) & set(COMBINATORS):
                self.assertEqual(tool["inputSchema"], entry["inputSchema"])
        self.assertIn("refrigeration.saturation_pressure", pinned)

    def test_each_foundation_answers_its_representative_tool_with_its_receipt_unchanged(self):
        for domain, (operation, arguments) in REPRESENTATIVE.items():
            if domain not in DOMAINS:
                continue
            with self.subTest(domain=domain):
                result = self.host.call(tool_name(domain, operation), arguments)["result"]
                poodo = result["_meta"][META_KEY]
                self.assertEqual((result["isError"], poodo["execution_status"], poodo["execution_certainty"]),
                                 (False, "completed", "responded"))
                expected = direct(domain, operation, arguments)
                self.assertEqual(result["structuredContent"], expected["structuredContent"])
                self.assertEqual(json.loads(result["content"][0]["text"]), expected["structuredContent"])
                content = result["structuredContent"]
                if domain in DIGEST_BOUND:
                    self.assertEqual(content["receipt"]["input_sha256"], arguments_sha256(arguments))
                if domain != "foundation_engine":
                    self.assertEqual((content["formal_proof"], content["runtime_goal_acceptance"]), (False, False))
                kinds = [(e["kind"], e["data"].get("decision_id") or e["data"].get("outcome", {}).get("decision_id"))
                         for e in self.host.events(domain)]
                self.assertIn(("outcome", poodo["decision_id"]), kinds)

    def test_unknown_tool_is_invalid_params(self):
        for name in ("refrigeration.shell", "saturation_pressure", "cstack_forge.run", "aor", None):
            with self.subTest(name=name):
                self.assertEqual(self.host.call(name, {})["error"]["code"], -32602)
        self.assertEqual(self.host.rpc("tools/call", {"name": "template.echo_observation",
                                                      "arguments": ["x"]})["error"]["code"], -32602)

    def test_malformed_input_never_reaches_the_core(self):
        before = len(self.host.events("foundation_template"))
        for arguments in ({}, {"observation": "x", "extra": 1}, {"observation": 7}, {"observation": ""}):
            with self.subTest(arguments=arguments):
                result = self.host.call("template.echo_observation", arguments)["result"]
                self.assertTrue(result["isError"])
                self.assertEqual(result["structuredContent"]["error"], "Arguments do not match the pinned input schema")
                self.assertNotIn("_meta", result)
        self.assertEqual(len(self.host.events("foundation_template")), before)

    @unittest.skipUnless("foundation_refrigeration" in DOMAINS, "Refrigeration is absent")
    def test_out_of_profile_number_is_refused_before_dispatch(self):
        arguments = {"fluid": "R717", "temperature": {"value": 1e-7, "unit": "degC"}}
        result = self.host.call("refrigeration.saturation_pressure", arguments)["result"]
        poodo = result["_meta"][META_KEY]
        self.assertTrue(result["isError"])
        self.assertEqual((poodo["execution_status"], poodo["execution_certainty"]), ("resource_rejected", "not_dispatched"))


class HostConfigurationTests(unittest.TestCase):
    def test_host_chooses_the_foundations(self):
        host = Host(["foundation_template"])
        self.addCleanup(host.close)
        self.assertEqual(list(host.session.classes), ["foundation_template"])
        names = [t["name"] for t in host.rpc("tools/list")["result"]["tools"]]
        self.assertEqual(names, ["template.echo_observation"])
        self.assertEqual(host.call("math.exact_scalar", MATH_CASE["arguments"])["error"]["code"], -32602)

    def test_unknown_runtime_empty_or_repeated_choices_are_refused(self):
        for choice in (["foundation_nope"], ["cstack_forge"], [], ["foundation_template", "foundation_template"]):
            with self.subTest(choice=choice), self.assertRaises(ContractError):
                bootstrap.registered_foundations(choice)

    def test_denied_domain_lists_nothing(self):
        host = Host(["foundation_template"], alpha_read="deny")
        self.addCleanup(host.close)
        self.assertEqual(host.rpc("tools/list")["result"]["tools"], [])

    def test_ask_class_waits_for_the_owner(self):
        host = Host(["foundation_template"], owner="beta", guest_read="ask")
        self.addCleanup(host.close)
        result = host.call("template.echo_observation", {"observation": "synthetic"})["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"], {"error": "approval_pending", "dispatched": False})
        self.assertTrue(result["_meta"][META_KEY]["approval_required"])

    def test_tampered_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "template"
            shutil.copytree(DOMAINS["foundation_template"].source_root, copy)
            listed = next(iter(json.loads((copy / "SOURCE-MANIFEST.json").read_text())["files"]))
            with open(copy / listed, "ab") as handle:
                handle.write(b"\n")
            tampered = dataclasses.replace(DOMAINS["foundation_template"], source_root=copy)
            with mock.patch.dict(bootstrap.DOMAINS, {"foundation_template": tampered}):
                host = Host(["foundation_template"])
                self.addCleanup(host.close)
                result = host.call("template.echo_observation", {"observation": "synthetic"})["result"]
        poodo = result["_meta"][META_KEY]
        self.assertTrue(result["isError"])
        self.assertEqual((poodo["execution_status"], poodo["assessment"], poodo["execution_certainty"]),
                         ("unavailable", "source_identity_unavailable", "not_dispatched"))
        self.assertNotIn("receipt", result["structuredContent"])


class LauncherTests(unittest.TestCase):
    def run_server(self, frames, *foundations):
        with tempfile.TemporaryDirectory() as directory:
            argv = [sys.executable, "-B", str(TOOL), "--aor", "alpha", "--state-root", str(Path(directory) / "state"),
                    "--device", "testbox", "--fleet", str(write_fleet(directory))]
            for name in foundations:
                argv += ["--foundation", name]
            return subprocess.run(argv, cwd=ROOT, input="".join(json.dumps(f) + "\n" for f in frames),
                                  capture_output=True, text=True, timeout=120)

    def test_stdio_lists_and_calls_the_chosen_foundation(self):
        frames = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
                  {"jsonrpc": "2.0", "method": "notifications/initialized"},
                  {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                  {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "template.echo_observation", "arguments": {"observation": "synthetic"}}}]
        done = self.run_server(frames, "template")
        self.assertEqual(done.returncode, 0, done.stderr)
        replies = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "cstack-foundations-alpha")
        self.assertEqual([t["name"] for t in replies[1]["result"]["tools"]], ["template.echo_observation"])
        content = replies[2]["result"]["structuredContent"]
        self.assertEqual(content["receipt"]["result"], {"observation": "synthetic"})
        self.assertEqual(content["receipt"]["evidence"][0]["evidence"]["status"], "CHECK")

    def test_unregistered_foundation_refuses_to_start(self):
        done = self.run_server([], "nope")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("foundation_nope is not registered", done.stderr)


if __name__ == "__main__":
    unittest.main()

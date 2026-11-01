"""MCP stdio driving adapter (ADR 003, PR 5b), tested through the real launcher over newline-delimited stdio.

Session semantics (effect classes, shields, witnessed durability) are covered in tests/test_aor_session.py.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from adapters.approval_store import ApprovalWriter
from poodo_core import ApprovalRecord
from tests.aor_fixtures import *

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools/cstack_mcp.py"


def argv(state, fleet, aor="alpha"):
    return [sys.executable, "-B", str(TOOL), "--aor", aor, "--state-root", str(state), "--device", "testbox",
            "--fleet", str(fleet)]


class Server:
    """One live launcher process, driven one request line and one response line at a time."""

    def __init__(self, state, fleet, *, initialize=True):
        self.proc = subprocess.Popen(argv(state, fleet), cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        self.watchdog = threading.Timer(120, self.proc.kill)
        self.watchdog.daemon = True
        self.watchdog.start()
        self.next_id = 0
        if initialize and "result" not in self.rpc("initialize", {"protocolVersion": "2025-06-18"}):
            raise AssertionError("initialize failed")  # not assert: python -O strips it, and the call with it

    def send_line(self, line, *, reply=True):
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline()) if reply else None

    def rpc(self, method, params=None):
        self.next_id += 1
        return self.send_line(json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                                          **({} if params is None else {"params": params})}))

    def call(self, name, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        return result["structuredContent"], result["isError"]

    def ok(self, name, **arguments):
        payload, is_error = self.call(name, **arguments)
        if is_error:
            raise AssertionError(payload)
        return payload

    def close(self):
        self.watchdog.cancel()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except BrokenPipeError:
                pass
        return self.proc.wait(timeout=30)

    def to_execute(self):
        goal_id = self.ok("start_goal", domain=DOMAIN, objective=SAMPLE.objective,
                          acceptance_criteria=["A scoped tool observation with Evidence."])["contract"]["goal_id"]
        for phase, extra in (("observe", {}), ("orient", {"research_references": [SAMPLE.reference]}),
                             ("decide", {"option_ids": OPTIONS})):
            self.ok("advance", domain=DOMAIN, goal_id=goal_id, next_phase=phase, rationale="Fixture.", **extra)
        decision = self.ok("decide", domain=DOMAIN, goal_id=goal_id, operation=SAMPLE.operation,
                           arguments=SAMPLE.arguments, expected_observation=SAMPLE.expected,
                           success_boundary="Only the supplied synthetic input.",
                           failure_meaning="The pinned Foundation contract does not match.")
        self.ok("advance", domain=DOMAIN, goal_id=goal_id, next_phase="orchestrate", rationale="Run it.")
        return goal_id, decision


class McpCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"

    def launch(self, fleet=None, **kwargs):
        server = Server(self.state, fleet or write_fleet(self.dir), **kwargs)
        self.addCleanup(server.close)
        return server


class ProtocolTests(McpCase):
    def test_initialize_echoes_supported_version_and_falls_back_for_unknown(self):
        server = self.launch(initialize=False)
        self.assertEqual(server.rpc("initialize", {"protocolVersion": "2024-11-05"})["result"]["protocolVersion"],
                         "2024-11-05")
        self.assertEqual(server.rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]["protocolVersion"],
                         "2025-11-25")  # batches are not supported, so 2025-03-26 is not offered
        self.assertEqual(server.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"],
                         "2025-11-25")

    def test_tools_list_is_exactly_the_six_tools(self):
        names = [t["name"] for t in self.launch().rpc("tools/list")["result"]["tools"]]
        self.assertEqual(sorted(names), ["advance", "aor", "decide", "execute", "ledger", "start_goal"])

    def test_calls_before_initialize_are_refused(self):
        server = self.launch(initialize=False)
        self.assertEqual(server.rpc("tools/list")["error"]["code"], -32000)
        self.assertEqual(server.rpc("tools/call", {"name": "aor", "arguments": {}})["error"]["code"], -32000)

    def test_unknown_method_and_notification(self):
        server = self.launch()
        self.assertEqual(server.rpc("resources/list")["error"]["code"], -32601)
        self.assertIsNone(server.send_line('{"jsonrpc":"2.0","method":"notifications/initialized"}', reply=False))
        self.assertEqual(server.rpc("ping")["id"], server.next_id)  # the notification produced no line

    def test_parse_errors_are_refused_and_the_server_keeps_serving(self):
        server = self.launch()
        frames = {'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}': -32700,
                  '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":NaN}}': -32700,
                  '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":"' + "a" * (1 << 20) + '"}}': -32600,
                  '{"jsonrpc":"2.0","id":7,"method":"initialize","params":[1]}': -32602}
        for frame, code in frames.items():
            self.assertEqual(server.send_line(frame)["error"]["code"], code, frame[:60])
            self.assertEqual(server.rpc("ping")["result"], {})

    def test_invalid_utf8_is_refused_and_the_server_keeps_serving(self):
        server = self.launch()
        server.proc.stdin.buffer.write(b"\xff\xfe\n")
        self.assertEqual(server.send_line('{"jsonrpc":"2.0","id":1,"method":"ping"}')["error"]["code"], -32700)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(sys.modules.pop, "adapters.mcp_stdio_server", None)
        environment = mock.patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)

    def test_launcher_sets_the_mcp_server_marker_before_building_the_session(self):
        spec = importlib.util.spec_from_file_location("cstack_mcp_under_test", TOOL)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        seen = {}

        def build(*args, **kwargs):
            seen["marker"] = os.environ.get("CSTACK_MCP_SERVER")
            raise SystemExit(0)

        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(launcher, "build_aor_session", build):
            os.environ.pop("CSTACK_MCP_SERVER", None)
            with self.assertRaises(SystemExit):
                launcher.main(["--aor", "alpha", "--device", "testbox"])
        self.assertEqual(seen["marker"], "1")


class GoalTests(McpCase):
    def test_full_sample_goal_completes_on_a_memory_ledger(self):
        server = self.launch()
        self.assertTrue(server.ok("aor")["ledger"].startswith("memory (not durable"))
        _, decision = server.to_execute()
        result = server.ok("execute", domain=DOMAIN, decision_id=decision["decision_id"])
        self.assertEqual((result["status"], SAMPLE.reading(result["outcome"])), ("executed", SAMPLE.value))
        ledger = server.ok("ledger", domain=DOMAIN, last=50)
        self.assertEqual(([e["kind"] for e in ledger["events"]][-2:], ledger["head"]), (["action", "outcome"], None))

    def test_identity_is_fixed_at_launch_and_extra_arguments_are_refused(self):
        server = self.launch()
        for name, arguments in (("aor", {"bot": "beta"}), ("aor", {"aor": "beta"}),
                                ("start_goal", {"domain": DOMAIN, "objective": "x", "acceptance_criteria": ["y"],
                                                "path": "/tmp/elsewhere"}),
                                ("ledger", {"domain": DOMAIN, "bot": "beta"})):
            self.assertTrue(server.call(name, **arguments)[1], (name, arguments))
        self.assertEqual(server.rpc("tools/call", {"name": "nope", "arguments": {}})["error"]["code"], -32602)
        aor = server.ok("aor")
        self.assertEqual((aor["bot"]["slug"], aor["device"], aor["approver"]), ("alpha", "testbox", APPROVER))

    def test_ask_waits_for_an_approval_written_by_another_process(self):
        server = self.launch(write_fleet(self.dir, alpha_read="ask"))
        goal_id, decision = server.to_execute()
        pending = server.ok("execute", domain=DOMAIN, decision_id=decision["decision_id"])
        self.assertEqual(pending, {"status": "approval_pending", "dispatched": False, "approver": APPROVER})
        writer = ApprovalWriter(self.state / "approvals.db", clock=lambda: int(time.time()))
        writer.record(ApprovalRecord("approval-1", decision["decision_id"], decision["request_sha256"], goal_id, 1,
                                     APPROVER, "approved", int(time.time()) + 3600))
        writer.close()
        self.assertEqual(SAMPLE.reading(server.ok("execute", domain=DOMAIN, decision_id=decision["decision_id"])[
            "outcome"]), SAMPLE.value)
        self.assertTrue(server.call("execute", domain=DOMAIN, decision_id=decision["decision_id"])[1])

    @unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
    def test_witnessed_ledger_survives_restart_and_a_tampered_log_stops_the_launcher(self):
        configured_log = write_witnessed_config(self.state)
        log = configured_log.with_suffix("") / "alpha" / f"{DOMAIN}.jsonl"
        server = self.launch()
        server.to_execute()
        head = server.ok("ledger", domain=DOMAIN)["head"]
        self.assertEqual(server.close(), 0)
        again = self.launch()
        self.assertEqual((again.ok("aor")["ledger"], again.ok("ledger", domain=DOMAIN)["head"]), ("witnessed", head))
        streams = again.ok("ledger")["streams"]
        self.assertEqual({d: (s["stream"], len(s["events"])) for d, s in streams.items()},
                         {**{d: (f"alpha.{d}", 0) for d in DOMAINS}, DOMAIN: (f"alpha.{DOMAIN}", head[3])})
        proc = subprocess.run(argv(self.state, write_fleet(self.dir)), cwd=ROOT, text=True, capture_output=True,
                              timeout=60, input='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
        self.assertNotEqual(proc.returncode, 0)  # a second live server for this bot would share its streams
        self.assertIn("already has a live owner", proc.stderr)
        self.assertEqual(again.close(), 0)
        log.write_text(log.read_text().replace("Fixture", "Forged", 1))
        proc = subprocess.run(argv(self.state, write_fleet(self.dir)), cwd=ROOT, text=True, capture_output=True,
                              timeout=60, input='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("failed verification", proc.stderr)


if __name__ == "__main__":
    unittest.main()

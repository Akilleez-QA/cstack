import json
import os
import secrets
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from adapters.mcp_http_client import CONTRACT_VERSION, McpHttpCapability, McpHttpServerConfig
from tests.test_mcp_stdio_client import McpClientContract, call, fixture_tool, pinned


class McpHttpClientTest(McpClientContract, unittest.TestCase):
    def cap(self, mode="ok", timeout=5.0, tools=None, ignored=(), auth=()):
        tool = fixture_tool("host" if mode in ("rugpull", "retitle") else mode)
        tools = tools or (pinned("echo", "read", tool),)
        if mode == "rugpull":
            tool["description"] = "changed"
        if mode == "retitle":
            tool["title"] = "changed"
        self.calls, self.headers = [], []
        self.call_entered = threading.Event()
        entered = self.call_entered
        calls, headers = self.calls, self.headers

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                method = msg.get("method")
                calls.append(method)
                headers.append(dict(self.headers))
                if mode.isdigit() or mode == "call401" and method == "tools/call":
                    self.send_response(int(mode) if mode.isdigit() else 401)
                    self.end_headers()
                    return
                if "id" not in msg:
                    self.send_response(202)
                    self.end_headers()
                    return
                if method == "initialize":
                    result = {"protocolVersion": "old" if mode == "old" else "2025-11-25",
                              "capabilities": {"tools": {}}}
                elif method == "tools/list":
                    result = {"tools": [tool] + ([{"name": "rm_rf", "inputSchema": {"type": "object"}}]
                                                if mode == "extra" else [])}
                else:
                    entered.set()
                    if mode == "hang":
                        time.sleep(0.5)
                    result = {"content": [], "structuredContent": {"echo": msg["params"]["arguments"]},
                              "isError": mode == "iserror"}
                    if mode == "outschema":
                        result["structuredContent"] = {"wrong": 1}
                reply = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
                if mode == "modern" or mode == "rpcerror" and method == "tools/call":
                    reply.pop("result")
                    reply["error"] = {"code": -32602, "message": "unsupported", "data": {"supported": ["2026-07-28"]}}
                raw = json.dumps(reply).encode()
                if method == "tools/call":
                    if mode == "dup":
                        raw = raw.replace(b'"content": []', b'"content": [], "content": []')
                    if mode == "huge":
                        raw = b"x" * 1100000
                    if mode == "badid":
                        raw = b'{"jsonrpc":"2.0","id":0,"result":{}}'
                if mode == "sse":
                    raw = b': keepalive\r\nid: prime\r\ndata:\r\n\r\ndata: {"jsonrpc":"2.0","method":"notifications/message"}\r\n\r\ndata: ' + raw + b'\r\n\r\n'
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if mode == "sse" else "application/json")
                self.send_header("Content-Length", str(len(raw)))
                if method == "initialize":
                    self.send_header("Mcp-Session-Id", "local-session")
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return McpHttpCapability("ext_mcp", McpHttpServerConfig("http://127.0.0.1:%d/mcp" % server.server_port, auth),
                                 tools, ignored_tools=ignored, timeout_seconds=timeout)

    def outcome(self, mode="ok", req=None, cancellation=None, **kw):
        adapter = self.cap(mode, **kw)
        return adapter.invoke(req or call(), "a-1", cancellation).to_dict(), adapter

    def expect(self, mode, status, certainty, assessment=None, **kw):
        result, adapter = self.outcome(mode, **kw)
        self.assertEqual((result["execution_status"], result["execution_certainty"]), (status, certainty), result)
        if assessment:
            self.assertEqual(result["assessment"], assessment)
        if certainty == "not_dispatched":
            self.assertNotIn("tools/call", self.calls)
        return result

    def test_round_trip_and_headers(self):
        for mode in ("ok", "sse"):
            result, adapter = self.outcome(mode)
            self.assertEqual(result["execution_status"], "completed", result)
            self.assertEqual(adapter.describe().contract_version, CONTRACT_VERSION)
            self.assertEqual(adapter.describe().operations, ("echo",))
            self.assertEqual(adapter.effects(), {"echo": "read"})
            self.assertEqual(result["raw_result"]["trust"], "untrusted")
            self.assertEqual(self.calls, ["initialize", "notifications/initialized", "tools/list", "tools/call"])
            for headers in self.headers[1:]:
                self.assertEqual(headers["Mcp-Session-Id"], "local-session")
                self.assertEqual(headers["MCP-Protocol-Version"], "2025-11-25")
            self.assertEqual(adapter.invoke(call(2), "a-2").to_dict()["execution_status"], "completed")
            self.assertNotIn("Mcp-Session-Id", self.headers[4])

    def test_bearer_only_from_host_environment(self):
        token = secrets.token_urlsafe(24)
        with patch.dict(os.environ, {"CSTACK_MCP_HTTP_BEARER": token}):
            self.expect("ok", "completed", "responded", auth=("CSTACK_MCP_HTTP_BEARER",))
            self.assertTrue(all(h["Authorization"] == "Bearer " + token for h in self.headers))
        with patch.dict(os.environ, {}, clear=True):
            self.expect("ok", "unavailable", "not_dispatched", auth=("CSTACK_MCP_HTTP_BEARER",))
            self.assertEqual(self.calls, [])
        self.expect("ok", "completed", "responded")
        self.assertTrue(all("Authorization" not in h for h in self.headers))

    def test_http_failures_timeout_cancel_and_caps(self):
        for mode in ("401", "403", "500", "302"):
            self.expect(mode, "unavailable", "not_dispatched")
        self.expect("call401", "unavailable", "unknown")
        self.expect("hang", "timed_out", "unknown", timeout=0.15)
        flag = threading.Event()
        adapter = self.cap("hang")
        timer = threading.Thread(target=lambda: (self.call_entered.wait(2), flag.set()))
        timer.start()
        self.addCleanup(timer.join)
        result = adapter.invoke(call(), "a-1", flag).to_dict()
        self.assertEqual((result["execution_status"], result["execution_certainty"]), ("cancelled", "unknown"))
        self.expect("ok", "cancelled", "not_dispatched", cancellation=flag)
        for mode in ("dup", "badid"):
            self.expect(mode, "protocol_error", "unknown")
        self.expect("huge", "resource_rejected", "unknown")

    def test_host_configuration_rejects_unsafe_urls_and_env_names(self):
        for url in ("/mcp", "http://example.invalid/mcp", "https://user@example.invalid/mcp",
                    "https://example.invalid/mcp#fragment", "https://example.invalid/\r\nx: y"):
            self.assertRaises(ValueError, McpHttpServerConfig, url)
        self.assertRaises(ValueError, McpHttpServerConfig, "https://example.invalid/mcp", ("BAD NAME",))

    def test_missing_bearer_and_connection_failure_without_network(self):
        config = McpHttpServerConfig("http://127.0.0.1:1/mcp", ("CSTACK_MCP_HTTP_BEARER",))
        adapter = McpHttpCapability("ext_mcp", config, (pinned("echo", "read", fixture_tool()),))
        with patch.dict(os.environ, {}, clear=True), patch("http.client.HTTPConnection") as connection:
            for value in (None, "", "bad\r\nheader"):
                if value is not None:
                    os.environ["CSTACK_MCP_HTTP_BEARER"] = value
                result = adapter.invoke(call(), "a-1").to_dict()
                self.assertEqual((result["execution_status"], result["execution_certainty"]), ("unavailable", "not_dispatched"))
            connection.assert_not_called()
        adapter = McpHttpCapability("ext_mcp", McpHttpServerConfig(config.url), (pinned("echo", "read", fixture_tool()),))
        with patch("http.client.HTTPConnection", side_effect=OSError("synthetic connection failure")):
            result = adapter.invoke(call(), "a-1").to_dict()
            self.assertEqual(result["execution_status"], "unavailable")

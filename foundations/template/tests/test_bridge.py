import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from foundation_template.tools import BOUNDARY, TOOL_NAMES, input_sha256
from foundation_template_bridge.schemas import tool_definitions
from foundation_template_bridge.server import PROTOCOL

ROOT = Path(__file__).resolve().parents[1]
INIT = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": PROTOCOL}}


def session(*frames, argv=()):
    raw = b"".join((f if type(f) is bytes else json.dumps(f).encode()) + b"\n" for f in frames)
    proc = subprocess.run([sys.executable, "-B", "-m", "foundation_template_bridge", *argv], cwd=ROOT, input=raw,
                          capture_output=True, timeout=30)
    return proc, [json.loads(line) for line in proc.stdout.splitlines()]


def call(arguments, name="echo_observation", ident=1):
    return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


class BridgeTests(unittest.TestCase):
    def test_handshake_catalog_and_echo_with_evidence(self):
        proc, (hello, catalog, echoed) = session(INIT, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                                                 call({"observation": "reading 7"}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual((hello["result"]["protocolVersion"], hello["result"]["mcpCompatible"]), (PROTOCOL, False))
        self.assertEqual(catalog["result"]["tools"], tool_definitions())
        self.assertEqual(tuple(t["name"] for t in catalog["result"]["tools"]), TOOL_NAMES)
        result = echoed["result"]
        receipt = result["structuredContent"]["receipt"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["assessment"], "observation_echoed")
        self.assertEqual((receipt["result"], receipt["boundary"], receipt["status"]),
                         ({"observation": "reading 7"}, BOUNDARY, "ok"))
        self.assertEqual(receipt["input_sha256"], input_sha256({"observation": "reading 7"}))
        self.assertEqual(receipt["evidence"][0]["evidence"]["status"], "CHECK")

    def test_bad_arguments_are_a_tool_error_that_still_carries_evidence(self):
        for arguments in ({}, {"observation": ""}, {"observation": 3}, {"observation": "x", "extra": 1},
                          {"observation": "x" * 257}):
            _, (_, reply) = session(INIT, call(arguments))
            result = reply["result"]
            self.assertTrue(result["isError"], arguments)
            self.assertEqual(result["structuredContent"]["receipt"]["status"], "error")
            self.assertTrue(result["structuredContent"]["receipt"]["evidence"])

    def test_wire_profile_fails_closed(self):
        for frame, code in ((b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}', -32700),
                            (b'{"jsonrpc":"2.0","id":1,"method":"ping","x":1.5}', -32700),
                            (b'{"jsonrpc":"2.0","id":1,"method":"ping","x":NaN}', -32700),
                            (b"[" * 33 + b"]" * 33, -32002)):
            _, (_, reply) = session(INIT, frame)
            self.assertEqual(reply["error"]["code"], code, frame)
        _, (reply,) = session(call({"observation": "x"}))
        self.assertEqual(reply["error"]["code"], -32000)
        _, (_, reply) = session(INIT, call({}, name="read_file"))
        self.assertEqual(reply["error"]["code"], -32602)
        proc, _ = session(INIT, argv=("--root", "/"))
        self.assertEqual(proc.returncode, 2)

    def test_source_manifest_lists_every_file(self):
        manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["files"]
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(ROOT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts
                  and p.relative_to(ROOT).parts[0] != ".github" and p.suffix != ".pyc" and p.name != "SOURCE-MANIFEST.json"}
        self.assertEqual(manifest, actual, "run: python -B tools/build_manifest.py, then re-pin the adapter")


if __name__ == "__main__":
    unittest.main()

"""Minimal fixed-command client example. Run from the Foundation Math source root.

A real coding/research agent supplies the same JSON data, not source strings.
This intentionally does not configure or emulate an MCP client.
"""
import json
import subprocess
import sys

requests = [
    {"jsonrpc": "2.0", "id": "init", "method": "initialize",
     "params": {"protocolVersion": "foundation-math-jsonrpc/1"}},
    {"jsonrpc": "2.0", "id": "tools", "method": "tools/list"},
    {"jsonrpc": "2.0", "id": "calculate", "method": "tools/call", "params": {
        "name": "exact_scalar", "arguments": {"domain": "Q", "operation": "add", "operands": [
            {"numerator": 1, "denominator": 2}, {"numerator": 1, "denominator": 3}]}}},
]
wire = b"".join(json.dumps(item, separators=(",", ":")).encode("utf-8") + b"\n" for item in requests)
# Fixed module and argument vector. No shell and no operator-provided command.
process = subprocess.run([sys.executable, "-B", "-m", "foundation_math_bridge"], input=wire,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
responses = [json.loads(line) for line in process.stdout.splitlines()]
if len(responses) != len(requests) or [item["id"] for item in responses] != [item["id"] for item in requests]:
    raise RuntimeError("Unexpected response correspondence")
for response in responses:
    if "error" in response:
        raise RuntimeError("Bridge rejected the request")
calculation = responses[2]["result"]
if calculation["isError"]:
    raise RuntimeError("Calculation failed")
evidence = calculation["structuredContent"]
# Computation success must not be reinterpreted as identity/witness acceptance.
print(json.dumps({"protocol": responses[0]["result"]["protocolVersion"],
                  "tools": [tool["name"] for tool in responses[1]["result"]["tools"]],
                  "assessment": evidence["assessment"], "result": evidence["receipt"]["result"],
                  "formal_proof": evidence["formal_proof"]}, indent=2))

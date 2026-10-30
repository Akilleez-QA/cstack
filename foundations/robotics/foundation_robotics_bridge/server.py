"""Restricted JSON-RPC 2.0 envelope over stdio speaking foundation-robotics-jsonrpc/1. NOT MCP.

Only the fixed tools in foundation_robotics.tools are reachable. No request-controlled file reads, commands,
imports, network, model or credential interfaces exist. Numbers are bounded integers only (no floats,
exponents, NaN or Infinity): every quantity is scaled to integer milli-SI units (foundation_robotics/measures.py),
so the host reuses the shared integer decoder (adapters/wire.py). Duplicate keys and over-budget frames are rejected.
"""
from __future__ import annotations

import json
import sys

from foundation_robotics import __version__
from foundation_robotics.tools import TOOL_NAMES, run
from .schemas import tool_definitions

PROTOCOL = "foundation-robotics-jsonrpc/1"
LIMITS = {"inputFrameBytes": 65536, "outputFrameBytes": 1048576, "jsonDepth": 32, "jsonNodes": 16384,
          "stringCharacters": 1024, "integerDigits": 15, "idCharacters": 128}


class WireError(ValueError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _error(identifier, code, message):
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def _unique(pairs):
    if len({key for key, _ in pairs}) != len(pairs):
        raise WireError(-32700, "Duplicate JSON object keys are rejected")
    return dict(pairs)


def _integer(token):
    if len(token.lstrip("-")) > LIMITS["integerDigits"]:
        raise WireError(-32002, "JSON integer exceeds bridge limit")
    return int(token)


def _no_float(token):
    raise WireError(-32700, "Only bounded integers are in this numeric profile")


def decode_frame(data: bytes):
    if len(data) > LIMITS["inputFrameBytes"]:
        raise WireError(-32002, "Input frame exceeds bridge byte limit")
    try:
        text = data.decode("utf-8", errors="strict")
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                escaped, quoted = (False, True) if escaped else (char == "\\", char != '"')
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > LIMITS["jsonDepth"]:
                    raise WireError(-32002, "JSON nesting exceeds bridge limit")
            elif char in "]}":
                depth -= 1
        value = json.loads(text, object_pairs_hook=_unique, parse_int=_integer, parse_float=_no_float,
                           parse_constant=_no_float)
    except WireError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise WireError(-32700, "Malformed UTF-8 JSON frame") from None
    stack, nodes = [value], 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > LIMITS["jsonNodes"]:
            raise WireError(-32002, "JSON node count exceeds bridge limit")
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str and len(item) > LIMITS["stringCharacters"]:
            raise WireError(-32002, "JSON string exceeds bridge limit")
    return value


def _exact(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise WireError(-32602, "Invalid parameter fields")
    return value


class Bridge:
    """One sequential process session. Notifications never execute tool work."""

    def __init__(self):
        self.initialized = False

    def dispatch(self, message):
        if type(message) is not dict or set(message) - {"jsonrpc", "id", "method", "params"}:
            return _error(None, -32600, "Expected a single request object; batches and extra fields are unsupported")
        if message.get("jsonrpc") != "2.0" or type(message.get("method")) is not str or not message["method"]:
            return _error(None, -32600, "Invalid JSON-RPC request envelope")
        identifier = message.get("id")
        if "id" not in message:
            return None
        if not ((type(identifier) is str and len(identifier) <= LIMITS["idCharacters"]) or type(identifier) is int):
            return _error(None, -32600, "Request id must be a bounded string or integer; null is unsupported")
        try:
            method, params = message["method"], message.get("params", {})
            if method == "ping":
                _exact(params, set())
                result = {}
            elif method == "initialize":
                if _exact(params, {"protocolVersion"})["protocolVersion"] != PROTOCOL:
                    raise WireError(-32001, "Unsupported bridge protocol; expected " + PROTOCOL + " (not MCP)")
                if self.initialized:
                    raise WireError(-32000, "Bridge already initialized")
                self.initialized = True
                result = {"protocolVersion": PROTOCOL, "mcpCompatible": False, "limits": dict(LIMITS),
                          "serverInfo": {"name": "foundation-robotics-jsonrpc-bridge", "version": __version__},
                          "capabilities": {"tools": True},
                          "numericProfile": "bounded integers only (measures in milli-SI units)",
                          "methods": ["initialize", "ping", "tools/list", "tools/call"]}
            elif method not in ("tools/list", "tools/call"):
                raise WireError(-32601, "Method not found")
            elif not self.initialized:
                raise WireError(-32000, "Initialize the bridge before using tools")
            elif method == "tools/list":
                _exact(params, set())
                result = {"tools": tool_definitions()}
            else:
                fields = _exact(params, {"name", "arguments"})
                if type(fields["name"]) is not str or fields["name"] not in TOOL_NAMES:
                    raise WireError(-32602, "Unknown tool")
                if type(fields["arguments"]) is not dict:
                    raise WireError(-32602, "Tool arguments must be a JSON object")
                failed, assessment, receipt = run(fields["name"], fields["arguments"])
                result = {"isError": failed, "structuredContent": {
                    "tool": fields["name"], "assessment": assessment, "formal_proof": False,
                    "runtime_goal_acceptance": False, "receipt": receipt}}
            return {"jsonrpc": "2.0", "id": identifier, "result": result}
        except WireError as error:
            return _error(identifier, error.code, str(error))
        except Exception:
            return _error(identifier, -32603, "Internal bridge error; no evidence result is available")

    def handle(self, data):
        try:
            return self.dispatch(decode_frame(data))
        except WireError as error:
            return _error(None, error.code, str(error))


def encode_response(response):
    try:
        raw = json.dumps(response, ensure_ascii=True, allow_nan=False, sort_keys=True,
                         separators=(",", ":")).encode("ascii")
        if len(raw) > LIMITS["outputFrameBytes"]:
            raise WireError(-32002, "Output frame exceeds bridge byte limit; result withheld")
    except (ValueError, OverflowError, RecursionError) as error:
        code = error.code if isinstance(error, WireError) else -32603
        raw = json.dumps(_error(response.get("id"), code, "Result withheld"), separators=(",", ":")).encode("ascii")
    return raw + b"\n"


def serve(source, sink) -> int:
    bridge, cap = Bridge(), LIMITS["inputFrameBytes"]
    try:
        while line := source.readline(cap + 2):
            if not line.endswith(b"\n") or len(line) > cap + 1:
                sink.write(encode_response(_error(None, -32002, "Oversized or unterminated frame; session closed")))
                sink.flush()
                return 2
            response = bridge.handle(line[:-1])
            if response is not None:
                sink.write(encode_response(response))
                sink.flush()
        return 0
    except (BrokenPipeError, OSError):
        return 2


def main() -> int:
    if len(sys.argv) != 1:
        sys.stderr.write("This bridge accepts no command-line options or paths; send bounded JSON-RPC on stdin.\n")
        return 2
    return serve(sys.stdin.buffer, sys.stdout.buffer)

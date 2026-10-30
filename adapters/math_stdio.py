"""Semantic Math capability mapped 1:1 to the unchanged custom v014 bridge.

NOT MCP. No models, network, credentials, shell, caller paths, or source execution.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry

from poodo_core.models import CapabilityRequest, ContractError, outcome_for
from extensions.foundation_math import MATH_CAPABILITY, TOOL_NAMES
from .execution import LocalBridgeExecutor
from .wire import WireFailure, decode, encode

SOURCE_SHA256 = "23219ba772c84796c007eee75458afc499b6ac257b154e78cf3068e41bfdb9a2"
INVENTORY_SHA256 = "7df9574ee6788e55bb51aec8ebf858e958c252808ec3f4c217e43f598c961ba9"
BRIDGE_PROTOCOL = "foundation-math-jsonrpc/1"
_ROOT = Path(__file__).resolve().parents[1]


class SourceFailure(ValueError):
    pass


def _no_external_schema(uri):
    raise WireFailure("External schema resolution is forbidden")


class PinnedMathSource:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def verify(self):
        try:
            raw = (self.root / "SOURCE-MANIFEST.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
                raise SourceFailure("Source manifest identity mismatch")
            files = json.loads(raw)["files"]
            if len(files) != 561:
                raise SourceFailure("Source file inventory mismatch")
            for name, expected in files.items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise SourceFailure("Invalid manifest path")
                path = self.root / relative
                if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise SourceFailure("Pinned source file identity mismatch")
        except (OSError, ValueError, KeyError, TypeError):
            raise SourceFailure("Pinned Foundation Math source unavailable or changed") from None
        return {"source_manifest_sha256": SOURCE_SHA256, "verified_files": len(files)}


class MathStdioCapability:
    def __init__(self, source_root: Path, *, executor=None):
        self._source = PinnedMathSource(source_root)
        self._executor = executor if executor is not None else LocalBridgeExecutor(source_root)
        inventory = decode((_ROOT / "schemas/math-v014-tools.json").read_bytes().rstrip(b"\n"), response=True)
        if hashlib.sha256(encode(inventory)).hexdigest() != INVENTORY_SHA256:
            raise SourceFailure("Vendored tool inventory identity mismatch")
        if tuple(x["name"] for x in inventory) != TOOL_NAMES:
            raise SourceFailure("Tool operation ordering mismatch")
        self._inventory = inventory
        self._tools = {t["name"]: t for t in inventory}
        self._validators = {}
        registry = Registry(retrieve=_no_external_schema)
        for t in inventory:
            Draft202012Validator.check_schema(t["outputSchema"])
            self._validators[t["name"]] = Draft202012Validator(t["outputSchema"], registry=registry)
        self._ready = False
        self._last_transcript = []

    def describe(self):
        return MATH_CAPABILITY

    def inventory(self):
        return json.loads(json.dumps(self._inventory))

    def transcript(self):
        return json.loads(json.dumps(self._last_transcript))

    @staticmethod
    def _request(method, params, request_id):
        return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}

    @staticmethod
    def _validate_response(value, request_id):
        if (type(value) is not dict or value.get("jsonrpc") != "2.0"
                or type(value.get("id")) is not type(request_id) or value.get("id") != request_id
                or set(value) not in ({"jsonrpc", "id", "result"}, {"jsonrpc", "id", "error"})):
            raise WireFailure("Invalid response envelope or correlation identity")
        if "error" in value:
            error = value["error"]
            if (type(error) is not dict or set(error) != {"code", "message"}
                    or type(error["code"]) is not int or type(error["message"]) is not str):
                raise WireFailure("Invalid protocol error")
        elif type(value["result"]) is not dict:
            raise WireFailure("Result must be an object")
        return value

    def _exchange(self, request, cancellation=None):
        init = self._request("initialize", {"protocolVersion": BRIDGE_PROTOCOL}, "cstack-init")
        frames = (encode(init), encode(request))
        for frame in frames:
            decode(frame)  # Entire unchanged Math frame, including envelope, against all input caps.
        process = self._executor.exchange(frames, cancellation)
        self._last_transcript = [{"direction": "request", "json_utf8": f.decode("ascii"),
                                  "sha256": hashlib.sha256(f).hexdigest()} for f in frames]
        if process.status != "completed":
            return process, None
        lines = process.stdout.splitlines(keepends=True)
        if len(lines) != 2 or any(not line.endswith(b"\n") for line in lines):
            raise WireFailure("Incomplete or unexpected response framing")
        replies = []
        for line, req in zip(lines, (init, request)):
            raw = line[:-1]
            self._last_transcript.append({"direction": "response", "json_utf8": raw.decode("utf-8", errors="strict"),
                                           "sha256": hashlib.sha256(raw).hexdigest()})
            replies.append(self._validate_response(decode(raw, response=True), req["id"]))
        hello = replies[0].get("result")
        if (type(hello) is not dict or hello.get("protocolVersion") != BRIDGE_PROTOCOL
                or hello.get("mcpCompatible") is not False
                or hello.get("limits", {}).get("inputFrameBytes") != 65_536
                or hello.get("limits", {}).get("outputFrameBytes") != 1_048_576):
            raise WireFailure("Bridge handshake or budget mismatch")
        return process, replies[1]

    def probe(self, cancellation=None):
        self._source.verify()
        process, reply = self._exchange(self._request("tools/list", {}, "cstack-catalog"), cancellation)
        if reply is None:
            return process
        if "error" in reply or set(reply["result"]) != {"tools"}:
            raise WireFailure("Tool catalog protocol error")
        inventory = reply["result"]["tools"]
        if hashlib.sha256(encode(inventory)).hexdigest() != INVENTORY_SHA256 or inventory != self._inventory:
            raise WireFailure("Live tool inventory identity mismatch")
        self._source.verify()
        self._ready = True
        return process

    def invoke(self, request: CapabilityRequest, attempt_id: str, cancellation=None):
        dispatched = False
        self._last_transcript = []
        try:
            request = CapabilityRequest.from_dict(request.to_dict())
            if request.capability_id != "foundation_math" or request.operation not in self._tools:
                return outcome_for(request, attempt_id, "unavailable", "unknown_math_capability")
            if request.required_evidence != "tool_observation":
                return outcome_for(request, attempt_id, "unavailable", "formal_verifier_unavailable")
            wire_request = self._request("tools/call", {"name": request.operation, "arguments": request.arguments}, request.request_id)
            # No new Math argument keys and no float coercion. Backend admission remains authoritative.
            decode(encode(wire_request))
            if cancellation is not None and cancellation.is_set():
                return outcome_for(request, attempt_id, "cancelled", "cancelled_before_dispatch")
            self._source.verify()
            if not self._ready:
                process = self.probe(cancellation)
                if process.status != "completed":
                    return outcome_for(request, attempt_id, process.status, "catalog_unavailable",
                        certainty="not_dispatched", limitations=("No Math tool call was dispatched; discovery did not complete.",))
            dispatched = True
            process, reply = self._exchange(wire_request, cancellation)
            if reply is None:
                return outcome_for(request, attempt_id, process.status, "execution_" + process.status,
                    certainty=process.certainty, source_hash=SOURCE_SHA256, inventory_hash=INVENTORY_SHA256,
                    limitations=("No accepted result. No automatic retry; execution may have occurred.",))
            self._source.verify()
            if "error" in reply:
                status = "resource_rejected" if reply["error"]["code"] == -32002 else "protocol_error"
                return outcome_for(request, attempt_id, status, "bridge_error_" + str(abs(reply["error"]["code"])),
                    certainty="responded", source_hash=SOURCE_SHA256, inventory_hash=INVENTORY_SHA256,
                    limitations=("Complete bridge error, not a mathematical result or proof.",))
            result = reply["result"]
            if set(result) != {"isError", "structuredContent"} or type(result["isError"]) is not bool:
                raise WireFailure("Malformed tool envelope")
            content = result["structuredContent"]
            if (type(content) is not dict or content.get("tool") != request.operation
                    or content.get("formal_proof") is not False or content.get("runtime_goal_acceptance") is not False
                    or type(content.get("receipt")) is not dict):
                raise WireFailure("Tool identity or evidence ceiling violation")
            if not self._validators[request.operation].is_valid(content):
                raise WireFailure("Structured result violates the exact pinned output schema")
            if result["isError"] != (content["assessment"] == "tool_error"):
                raise WireFailure("Inconsistent tool error assessment")
            return outcome_for(request, attempt_id, "tool_error" if result["isError"] else "completed", content["assessment"],
                certainty="responded", raw_result=result, source_hash=SOURCE_SHA256, inventory_hash=INVENTORY_SHA256,
                scope="Exact supplied structured inputs, within the named v014 tool's declared domain and bounds.",
                limitations=("Original receipt preserved without accepting its assumptions as true.",
                    "No formal proof, actual geometry, general theorem, or automatic goal acceptance.",
                    "Pinned files and receipt hashes are not signatures or a hostile-code sandbox."))
        except SourceFailure:
            return outcome_for(request, attempt_id, "protocol_error" if dispatched else "unavailable", "source_identity_unavailable",
                certainty="unknown" if dispatched else "not_dispatched",
                limitations=("Source identity could not be established; response not admitted.",))
        except (WireFailure, ContractError, UnicodeError, ValueError, KeyError, TypeError):
            return outcome_for(request, attempt_id, "protocol_error" if dispatched else "resource_rejected", "math_contract_rejected",
                certainty="unknown" if dispatched else "not_dispatched",
                limitations=("Malformed, mismatched, or over-budget data quarantined; no evidence admitted.",))
        except Exception:
            return outcome_for(request, attempt_id, "indeterminate", "unexpected_adapter_failure",
                certainty="unknown" if dispatched else "not_dispatched",
                limitations=("No accepted result and no automatic retry.",))


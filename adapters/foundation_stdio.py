"""Shared host side of a pinned Foundation stdio bridge: source pins, bounded exchange, exact receipts.

NOT MCP. A domain adapter supplies one immutable BridgeProfile (its pins, protocol, numeric decoder, receipt
boundary and wording) and subclasses PinnedStdioCapability. Everything that keeps a Foundation honest lives
here once: manifest verification before and after accepted work, a pinned tool inventory checked against the
live catalog, a strict handshake, request/response correlation, exact output-schema validation, the receipt's
input digest and boundary, and fail-closed outcomes with explicit execution certainty. Foundation Math keeps
its own unchanged adapter (adapters/math_stdio.py).
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator
from referencing import Registry

from poodo_core.models import CapabilityDescriptor, CapabilityRequest, ContractError, outcome_for
from .execution import LocalBridgeExecutor
from .wire import WireFailure, encode

ROOT = Path(__file__).resolve().parents[1]
INPUT_FRAME_BYTES = 65_536
OUTPUT_FRAME_BYTES = 1_048_576


class SourceFailure(ValueError):
    pass


def arguments_sha256(arguments):
    """The Foundation's receipt input digest, recomputed by the host to bind the exact request."""
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     allow_nan=False).encode("ascii")).hexdigest()


def _no_external_schema(uri):
    raise WireFailure("External schema resolution is forbidden")


@dataclass(frozen=True)
class BridgeProfile:
    """Trusted host constants for one Foundation. Nothing here is request data."""
    capability: CapabilityDescriptor
    label: str                  # "Refrigeration", used in limitations text
    slug: str                   # "refrigeration", used in outcome assessments
    source_sha256: str          # SHA-256 of the Foundation's SOURCE-MANIFEST.json
    source_file_count: int
    inventory_sha256: str       # SHA-256 of the canonical tools/list inventory
    inventory_path: str         # host-vendored copy of that inventory, relative to the repo root
    protocol: str
    module: str                 # bridge module; must be in LocalBridgeExecutor.BRIDGE_MODULES
    boundary: dict              # exact receipt boundary every result must carry
    decode: Callable            # decode(raw, *, response=False): the domain's own numeric profile
    scope: str
    limitations: tuple


class PinnedSource:
    def __init__(self, root: Path, profile: BridgeProfile):
        self.root, self._profile = Path(root).resolve(), profile

    def verify(self):
        expected_sha, expected_count = self._profile.source_sha256, self._profile.source_file_count
        try:
            raw = (self.root / "SOURCE-MANIFEST.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_sha:
                raise SourceFailure("Source manifest identity mismatch")
            files = json.loads(raw)["files"]
            if len(files) != expected_count:
                raise SourceFailure("Source file inventory mismatch")
            for name, expected in files.items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise SourceFailure("Invalid manifest path")
                path = self.root / relative
                if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise SourceFailure("Pinned source file identity mismatch")
        except (OSError, ValueError, KeyError, TypeError):
            raise SourceFailure(f"Pinned Foundation {self._profile.label} source unavailable or changed") from None
        return {"source_manifest_sha256": expected_sha, "verified_files": len(files)}


class PinnedStdioCapability:
    PROFILE: BridgeProfile  # set by each domain subclass

    def __init__(self, source_root: Path, *, executor=None):
        p = self.PROFILE
        self._source = PinnedSource(source_root, p)
        self._executor = executor if executor is not None else LocalBridgeExecutor(source_root, module=p.module)
        inventory = p.decode((ROOT / p.inventory_path).read_bytes().rstrip(b"\n"), response=True)
        if hashlib.sha256(encode(inventory)).hexdigest() != p.inventory_sha256:
            raise SourceFailure("Vendored tool inventory identity mismatch")
        if tuple(x["name"] for x in inventory) != p.capability.operations:
            raise SourceFailure("Tool operation ordering mismatch")
        self._inventory = inventory
        self._tools = {t["name"]: t for t in inventory}
        self._validators = {}
        registry = Registry(retrieve=_no_external_schema)
        for t in inventory:
            Draft202012Validator.check_schema(t["inputSchema"])
            Draft202012Validator.check_schema(t["outputSchema"])
            self._validators[t["name"]] = Draft202012Validator(t["outputSchema"], registry=registry)
        self._ready = False
        self._last_transcript = []

    def describe(self):
        return self.PROFILE.capability

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
        p = self.PROFILE
        init = self._request("initialize", {"protocolVersion": p.protocol}, "cstack-init")
        frames = (encode(init), encode(request))
        for frame in frames:
            p.decode(frame)  # Entire frame against the domain's input profile and caps.
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
            replies.append(self._validate_response(p.decode(raw, response=True), req["id"]))
        hello = replies[0].get("result")
        if (type(hello) is not dict or hello.get("protocolVersion") != p.protocol
                or hello.get("mcpCompatible") is not False
                or hello.get("limits", {}).get("inputFrameBytes") != INPUT_FRAME_BYTES
                or hello.get("limits", {}).get("outputFrameBytes") != OUTPUT_FRAME_BYTES):
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
        if hashlib.sha256(encode(inventory)).hexdigest() != self.PROFILE.inventory_sha256 or inventory != self._inventory:
            raise WireFailure("Live tool inventory identity mismatch")
        self._source.verify()
        self._ready = True
        return process

    def invoke(self, request: CapabilityRequest, attempt_id: str, cancellation=None):
        p = self.PROFILE
        pins = {"source_hash": p.source_sha256, "inventory_hash": p.inventory_sha256}
        dispatched = False
        self._last_transcript = []
        try:
            request = CapabilityRequest.from_dict(request.to_dict())
            if request.capability_id != p.capability.capability_id or request.operation not in self._tools:
                return outcome_for(request, attempt_id, "unavailable", f"unknown_{p.slug}_capability")
            if request.required_evidence != "tool_observation":
                return outcome_for(request, attempt_id, "unavailable", "formal_verifier_unavailable")
            wire_request = self._request("tools/call", {"name": request.operation, "arguments": request.arguments},
                                         request.request_id)
            # No new argument keys; out-of-profile numbers and over-budget frames never dispatch.
            p.decode(encode(wire_request))
            if cancellation is not None and cancellation.is_set():
                return outcome_for(request, attempt_id, "cancelled", "cancelled_before_dispatch")
            self._source.verify()
            if not self._ready:
                process = self.probe(cancellation)
                if process.status != "completed":
                    return outcome_for(request, attempt_id, process.status, "catalog_unavailable",
                        certainty="not_dispatched",
                        limitations=(f"No {p.label} tool call was dispatched; discovery did not complete.",))
            dispatched = True
            process, reply = self._exchange(wire_request, cancellation)
            if reply is None:
                return outcome_for(request, attempt_id, process.status, "execution_" + process.status,
                    certainty=process.certainty, **pins,
                    limitations=("No accepted result. No automatic retry; execution may have occurred.",))
            self._source.verify()
            if "error" in reply:
                status = "resource_rejected" if reply["error"]["code"] == -32002 else "protocol_error"
                return outcome_for(request, attempt_id, status, "bridge_error_" + str(abs(reply["error"]["code"])),
                    certainty="responded", **pins,
                    limitations=(f"Complete bridge error, not a {p.label} observation.",))
            return self._admit(request, attempt_id, reply["result"], pins)
        except SourceFailure:
            return outcome_for(request, attempt_id, "protocol_error" if dispatched else "unavailable",
                "source_identity_unavailable", certainty="unknown" if dispatched else "not_dispatched",
                limitations=("Source identity could not be established; response not admitted.",))
        except (WireFailure, ContractError, UnicodeError, ValueError, KeyError, TypeError):
            return outcome_for(request, attempt_id, "protocol_error" if dispatched else "resource_rejected",
                f"{p.slug}_contract_rejected", certainty="unknown" if dispatched else "not_dispatched",
                limitations=("Malformed, mismatched, or over-budget data quarantined; no evidence admitted.",))
        except Exception:
            return outcome_for(request, attempt_id, "indeterminate", "unexpected_adapter_failure",
                certainty="unknown" if dispatched else "not_dispatched",
                limitations=("No accepted result and no automatic retry.",))

    def _admit(self, request, attempt_id, result, pins):
        """A complete tool envelope as an outcome, or WireFailure. Domains with another result shape override this."""
        p = self.PROFILE
        if set(result) != {"isError", "structuredContent"} or type(result["isError"]) is not bool:
            raise WireFailure("Malformed tool envelope")
        content = result["structuredContent"]
        receipt = content.get("receipt") if type(content) is dict else None
        if (type(content) is not dict or content.get("tool") != request.operation
                or content.get("formal_proof") is not False or content.get("runtime_goal_acceptance") is not False
                or type(receipt) is not dict or receipt.get("tool") != request.operation
                or receipt.get("boundary") != p.boundary
                or receipt.get("input_sha256") != arguments_sha256(request.arguments)):
            raise WireFailure("Tool identity, receipt binding or evidence ceiling violation")
        if not self._validators[request.operation].is_valid(content):
            raise WireFailure("Structured result violates the exact pinned output schema")
        if result["isError"] != (content["assessment"] == "tool_error") or \
                result["isError"] != (receipt["status"] == "error"):
            raise WireFailure("Inconsistent tool error assessment")
        return outcome_for(request, attempt_id, "tool_error" if result["isError"] else "completed",
            content["assessment"], certainty="responded", raw_result=result, **pins, scope=p.scope,
            limitations=p.limitations)

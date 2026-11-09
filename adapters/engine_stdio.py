"""Foundation Engine over foundation-engine-jsonrpc/1 from a partial vendor copy.

Only the bridge, its schema and the upstream SOURCE-MANIFEST.json are vendored. The manifest is pinned whole; the
vendored files must be exactly VENDORED_FILES and match their manifest entries. Results are plain validated values,
admitted by _admit after exact output-schema validation, with no receipt or assessment invented.
"""
import hashlib
import json
import re
from pathlib import Path

from extensions.foundation_engine import ENGINE_CAPABILITY
from poodo_core.models import outcome_for
from .execution import LocalBridgeExecutor
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure
from .wire import WireFailure, decode as exact_decode

SOURCE_SHA256 = "0617efcbbb594919137ca6b748de189516ee9ec35e49f56765109cfe9fb01349"
SOURCE_FILE_COUNT = 2513
INVENTORY_SHA256 = "c666da976a8a93e327dcaf09689fb9ed0f7d487c59e9f06a484a1b4ad9a9a9cc"
UPSTREAM_COMMIT = "8445d319fd35115093f44a2081beb29ff108be49"
BRIDGE_PROTOCOL = "foundation-engine-jsonrpc/1"
BRIDGE_MODULE = "foundation_engine_bridge"
VENDORED_FILES = ("schemas/read-only-tools.json", "tools/foundation_engine_bridge.py")

_INPUT_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]+\Z")
_RESPONSE_FLOAT = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?\Z")


def _input_decimal(token):
    if len(token) > 24 or _INPUT_DECIMAL.fullmatch(token) is None:
        raise WireFailure("Input numbers must be finite decimal literals without exponent")
    return float(token)


def _response_float(token):
    if len(token) > 32 or _RESPONSE_FLOAT.fullmatch(token) is None:
        raise WireFailure("Response number outside the Engine profile")
    value = float(token)
    if value != value or value in (float("inf"), float("-inf")):
        raise WireFailure("Nonfinite response number")
    return value


def _declares_number(schema):
    if type(schema) is dict:
        return schema.get("type") == "number" or any(_declares_number(v) for v in schema.values())
    return type(schema) is list and any(_declares_number(v) for v in schema)


def _has_float(value):
    if type(value) is dict:
        return any(_has_float(v) for v in value.values())
    if type(value) is list:
        return any(_has_float(v) for v in value)
    return type(value) is float


def decode(raw: bytes, *, response=False):
    return exact_decode(raw, response=response, parse_float=_response_float if response else _input_decimal)


PROFILE = BridgeProfile(
    ENGINE_CAPABILITY, "Engine", "engine", SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256,
    "schemas/engine-v020-tools.json", BRIDGE_PROTOCOL, BRIDGE_MODULE, {}, decode,
    "Exact supplied value against the pinned Foundation Engine read-only validators.",
    ("The upstream result is the validated value only; it carries no receipt, so none is claimed.",
     "Observation only: no engine state is read or changed and no control action is offered or implied.",
     "Pinned files are identified by hash; that is not a signature or a hostile-code sandbox."))


class PinnedEngineSource(PinnedSource):
    def __init__(self, root: Path):
        super().__init__(root, PROFILE)

    def verify(self):
        try:
            raw = (self.root / "SOURCE-MANIFEST.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != PROFILE.source_sha256:
                raise SourceFailure("Source manifest identity mismatch")
            files = json.loads(raw)["files"]
            if len(files) != PROFILE.source_file_count:
                raise SourceFailure("Source file inventory mismatch")
            present = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")
                             if p.is_file() or p.is_symlink())
            if present != sorted(("SOURCE-MANIFEST.json",) + VENDORED_FILES):
                raise SourceFailure("Vendored file set mismatch")
            for name in VENDORED_FILES:
                path = self.root / name
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != files[name]:
                    raise SourceFailure("Pinned source file identity mismatch")
        except (OSError, ValueError, KeyError, TypeError):
            raise SourceFailure("Pinned Foundation Engine source unavailable or changed") from None
        return {"source_manifest_sha256": PROFILE.source_sha256, "verified_files": len(VENDORED_FILES)}


class EngineStdioCapability(PinnedStdioCapability):
    PROFILE = PROFILE

    def __init__(self, source_root: Path, *, executor=None):
        root = Path(source_root)
        super().__init__(root, executor=executor if executor is not None
                         else LocalBridgeExecutor(root / "tools", module=BRIDGE_MODULE))
        self._source = PinnedEngineSource(root)
        self._decimal_tools = {name for name, tool in self._tools.items() if _declares_number(tool["inputSchema"])}

    def invoke(self, request, attempt_id, cancellation=None):
        if request.operation not in self._decimal_tools and _has_float(request.arguments):
            return outcome_for(request, attempt_id, "resource_rejected", "engine_contract_rejected",
                certainty="not_dispatched",
                limitations=("Malformed, mismatched, or over-budget data quarantined; no evidence admitted.",))
        return super().invoke(request, attempt_id, cancellation)

    def _admit(self, request, attempt_id, result, pins):
        if set(result) != {"isError", "structuredContent"} or result["isError"] is not False:
            raise WireFailure("Malformed engine tool envelope")
        if not self._validators[request.operation].is_valid(result["structuredContent"]):
            raise WireFailure("Structured result violates the exact pinned output schema")
        return outcome_for(request, attempt_id, "completed", "engine_value_validated", certainty="responded",
                           raw_result=result, **pins, scope=PROFILE.scope, limitations=PROFILE.limitations)

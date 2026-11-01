"""Foundation Engine over foundation-engine-jsonrpc/1 from a partial vendor copy.

Only the bridge, its schema and the upstream SOURCE-MANIFEST.json are vendored. The manifest is pinned whole; the
vendored files must be exactly VENDORED_FILES and match their manifest entries. Results are plain validated values,
admitted by _admit after exact output-schema validation, with no receipt or assessment invented.
"""
import hashlib
import json
from pathlib import Path

from extensions.foundation_engine import ENGINE_CAPABILITY
from poodo_core.models import outcome_for
from .execution import LocalBridgeExecutor
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure
from .wire import WireFailure, decode

SOURCE_SHA256 = "edee2a8ac7dabf7677dd31061c6ca34e93e321b58194cd6f234d6f8a810d241e"
SOURCE_FILE_COUNT = 2496
INVENTORY_SHA256 = "c666da976a8a93e327dcaf09689fb9ed0f7d487c59e9f06a484a1b4ad9a9a9cc"
UPSTREAM_COMMIT = "70810ba455bdda1eadfdaab6bd44d43ae88f898c"
BRIDGE_PROTOCOL = "foundation-engine-jsonrpc/1"
BRIDGE_MODULE = "foundation_engine_bridge"
VENDORED_FILES = ("schemas/read-only-tools.json", "tools/foundation_engine_bridge.py")

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

    def _admit(self, request, attempt_id, result, pins):
        if set(result) != {"isError", "structuredContent"} or result["isError"] is not False:
            raise WireFailure("Malformed engine tool envelope")
        if not self._validators[request.operation].is_valid(result["structuredContent"]):
            raise WireFailure("Structured result violates the exact pinned output schema")
        return outcome_for(request, attempt_id, "completed", "engine_value_validated", certainty="responded",
                           raw_result=result, **pins, scope=PROFILE.scope, limitations=PROFILE.limitations)

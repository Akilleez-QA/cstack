"""Semantic Template capability mapped 1:1 to the pinned foundation-template-jsonrpc/1 bridge. NOT MCP.

The whole adapter is one BridgeProfile over the shared pinned-bridge machinery (adapters/foundation_stdio.py).
Copy this file to make a new domain's adapter, then change the pins, protocol, module and boundary
(foundations/template/README.md). The numeric profile reuses adapters/wire.py: bounded integers, no floats.
"""
from pathlib import Path

from extensions.foundation_template import TEMPLATE_CAPABILITY
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure  # noqa: F401
from .wire import decode

SOURCE_SHA256 = "11fadb42e49d0366daebad982a5334b763b0f0f050ff8ca911bdb25f5db92a93"
SOURCE_FILE_COUNT = 34
INVENTORY_SHA256 = "2d15f784589a077908d1a8e79dc0350ec62c090f08cb25ef63b04d947ac0622f"
BRIDGE_PROTOCOL = "foundation-template-jsonrpc/1"
BRIDGE_MODULE = "foundation_template_bridge"
BOUNDARY = {"observation_only": True, "domain_determination": False, "control_action": False}

PROFILE = BridgeProfile(
    TEMPLATE_CAPABILITY, "Template", "template", SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256,
    "schemas/template-v01-tools.json", BRIDGE_PROTOCOL, BRIDGE_MODULE, BOUNDARY, decode,
    "Exact supplied structured inputs against the pinned template Foundation.",
    ("Placeholder tool: the observation is the caller's own input echoed back, with its receipt and Evidence.",
     "Observation only: no domain determination or control action.",
     "Pinned files and receipt hashes are not signatures or a hostile-code sandbox."))


class PinnedTemplateSource(PinnedSource):
    def __init__(self, root: Path):
        super().__init__(root, PROFILE)


class TemplateStdioCapability(PinnedStdioCapability):
    PROFILE = PROFILE

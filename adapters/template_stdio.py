from pathlib import Path

from extensions.foundation_template import TEMPLATE_CAPABILITY
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure
from .wire import decode

SOURCE_SHA256 = "0c9c1f7f5668668806fb0073f2e772c7f96ecdaa69c28fc35e8d2da380fbe9b9"
SOURCE_FILE_COUNT = 49
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

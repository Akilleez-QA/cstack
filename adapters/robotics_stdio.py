"""Semantic Robotics capability mapped 1:1 to the pinned foundation-robotics-jsonrpc/1 bridge. NOT MCP.

One BridgeProfile over the shared pinned-bridge machinery (adapters/foundation_stdio.py). The numeric profile reuses
adapters/wire.py: bounded integers, no floats; every quantity is scaled to integer milli-SI units by the caller.
"""
from pathlib import Path

from extensions.foundation_robotics import ROBOTICS_CAPABILITY
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure  # noqa: F401
from .wire import decode

SOURCE_SHA256 = "7f7c4b76c986f0bba09362c3a65974cce0cc4dbb53cc2f4505dcab43f3b2f903"
SOURCE_FILE_COUNT = 44
INVENTORY_SHA256 = "037919a5b4d2305de5a18e7d26994df2871a766ba1c2df2c1b11778d959ca599"
BRIDGE_PROTOCOL = "foundation-robotics-jsonrpc/1"
BRIDGE_MODULE = "foundation_robotics_bridge"
BOUNDARY = {"observation_only": True, "acceptance_decision": False, "control_action": False}

PROFILE = BridgeProfile(
    ROBOTICS_CAPABILITY, "Robotics", "robotics", SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256,
    "schemas/robotics-v01-tools.json", BRIDGE_PROTOCOL, BRIDGE_MODULE, BOUNDARY, decode,
    "Exact supplied motion (integer milli-SI units) against the pinned Robotics Foundation's relations and thresholds.",
    ("Original receipt and its Evidence preserved without accepting CHECK thresholds as calibrated.",
     "A verdict compares sampled motion with physics; it is not acceptance of an animation.",
     "Pinned files and receipt hashes are not signatures or a hostile-code sandbox."))


class PinnedRoboticsSource(PinnedSource):
    def __init__(self, root: Path):
        super().__init__(root, PROFILE)


class RoboticsStdioCapability(PinnedStdioCapability):
    PROFILE = PROFILE

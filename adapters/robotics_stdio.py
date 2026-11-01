from pathlib import Path

from extensions.foundation_robotics import ROBOTICS_CAPABILITY
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure
from .wire import decode

SOURCE_SHA256 = "4667a558554e6a766e855be078031563b72337b8a6407eabf466d42b9df3bdb6"
SOURCE_FILE_COUNT = 45
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

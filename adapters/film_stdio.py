from pathlib import Path

from extensions.foundation_film import FILM_CAPABILITY
from .foundation_stdio import BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure
from .wire import decode

SOURCE_SHA256 = "4734c76b9d0d5b830e150bd2bb435539e202ffd81d967692cff8dacfc3b5a417"
SOURCE_FILE_COUNT = 42
INVENTORY_SHA256 = "4432e0305a84ed9aa1b269f2378f869b5b36850001e503ed1ffc0e018dd17558"
BRIDGE_PROTOCOL = "foundation-film-jsonrpc/1"
BRIDGE_MODULE = "foundation_film_bridge"
BOUNDARY = {"observation_only": True, "acceptance_decision": False, "control_action": False}

PROFILE = BridgeProfile(
    FILM_CAPABILITY, "Film", "film", SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256,
    "schemas/film-v01-tools.json", BRIDGE_PROTOCOL, BRIDGE_MODULE, BOUNDARY, decode,
    "Exact supplied measures (integer milli-units) against the pinned Film Foundation's thresholds.",
    ("Original receipt and its Evidence preserved without accepting CHECK thresholds as calibrated.",
     "A verdict compares measures with thresholds; it is not acceptance of a film or a quality call.",
     "Pinned files and receipt hashes are not signatures or a hostile-code sandbox."))


class PinnedFilmSource(PinnedSource):
    def __init__(self, root: Path):
        super().__init__(root, PROFILE)


class FilmStdioCapability(PinnedStdioCapability):
    PROFILE = PROFILE

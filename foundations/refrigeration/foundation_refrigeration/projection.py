from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parent / "data"
_SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


class ProjectionError(ValueError):
    pass


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ProjectionError("Duplicate key in projection")
        out[key] = value
    return out


def _reject_constant(token):
    raise ProjectionError("Nonfinite number in projection")


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def load(name: str, schema: str) -> tuple[dict, str]:
    if "/" in name or "\\" in name or name.startswith("."):
        raise ProjectionError("Projection names are fixed file names")
    raw = (DATA_DIR / name).read_bytes()
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_reject_constant)
    if (type(document) is not dict or set(document) != {"schema", "version", "owner", "generatedBy", "data"}
            or document["schema"] != schema or type(document["version"]) is not str
            or _SEMVER.fullmatch(document["version"]) is None or type(document["data"]) is not dict):
        raise ProjectionError("Projection envelope or schema mismatch: " + name)
    return document["data"], hashlib.sha256(raw).hexdigest()

"""Semantic Refrigeration capability mapped 1:1 to the pinned foundation-refrigeration-jsonrpc/1 bridge.

NOT MCP. No models, network, credentials, shell, caller paths, or source execution. The numeric
profile is the Refrigeration Foundation's own (finite decimals with explicit units); it is not
Foundation Math's integer-only profile, and adapters/wire.py is left unchanged for Math.
The pinned-bridge machinery is shared (adapters/foundation_stdio.py); this module owns the profile.
"""
from __future__ import annotations
import json
from pathlib import Path
import re

from extensions.foundation_refrigeration import REFRIGERATION_CAPABILITY
from .foundation_stdio import (BridgeProfile, PinnedSource, PinnedStdioCapability, SourceFailure,  # noqa: F401
                               arguments_sha256)
from .wire import WireFailure

SOURCE_SHA256 = "f37209939210bdb25d2a70e680a42bd629953afc2024378551f23d4367695705"
SOURCE_FILE_COUNT = 43
INVENTORY_SHA256 = "86d428e1577afde53c1baff6ffb36c540166bb5ec5ec8c90120c448d3483658d"
BRIDGE_PROTOCOL = "foundation-refrigeration-jsonrpc/1"
BRIDGE_MODULE = "foundation_refrigeration_bridge"
_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]+\Z")
_RESPONSE_FLOAT = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]{1,3})?\Z")
BOUNDARY = {"observation_only": True, "engineering_determination": False, "safety_determination": False,
            "compliance_determination": False, "diagnosis": False, "control_action": False}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WireFailure("Duplicate JSON keys")
        result[key] = value
    return result


def _no_constant(_):
    raise WireFailure("NaN and Infinity are outside the Refrigeration profile")


def _input_decimal(token):
    if len(token) > 24 or _DECIMAL.fullmatch(token) is None:
        raise WireFailure("Input numbers must be finite decimal literals without exponent")
    return float(token)


def _input_integer(token):
    if len(token.lstrip("-")) > 15:
        raise WireFailure("Input integer exceeds Refrigeration bridge budget")
    return int(token)


def _response_float(token):
    if len(token) > 32 or _RESPONSE_FLOAT.fullmatch(token) is None:
        raise WireFailure("Response number outside the Refrigeration profile")
    value = float(token)
    if value != value or value in (float("inf"), float("-inf")):
        raise WireFailure("Nonfinite response number")
    return value


def _response_integer(token):
    if len(token.lstrip("-")) > 18:
        raise WireFailure("Response integer exceeds budget")
    return int(token)


def decode(raw: bytes, *, response=False):
    """Strict Refrigeration JSON profile: duplicate keys, nonfinite numbers and over-budget frames fail closed."""
    byte_cap, depth_cap, node_cap, string_cap = ((1_048_576, 64, 250_000, 65_536) if response
                                               else (65_536, 32, 4096, 1024))
    if type(raw) is not bytes or len(raw) > byte_cap:
        raise WireFailure("Frame byte budget exceeded")
    try:
        text = raw.decode("utf-8", errors="strict")
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > depth_cap:
                    raise WireFailure("JSON depth budget exceeded")
            elif char in "]}":
                depth -= 1
        value = json.loads(text, object_pairs_hook=_unique, parse_constant=_no_constant,
                           parse_float=_response_float if response else _input_decimal,
                           parse_int=_response_integer if response else _input_integer)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise WireFailure("Invalid or over-budget Refrigeration JSON frame") from None
    stack, nodes = [value], 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > node_cap:
            raise WireFailure("JSON node budget exceeded")
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str and len(item) > string_cap:
            raise WireFailure("JSON string budget exceeded")
    return value


PROFILE = BridgeProfile(
    REFRIGERATION_CAPABILITY, "Refrigeration", "refrigeration", SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256,
    "schemas/refrigeration-v01-tools.json", BRIDGE_PROTOCOL, BRIDGE_MODULE, BOUNDARY, decode,
    "Exact supplied structured inputs against the pinned Refrigeration data, within each tool's declared range.",
    ("Original receipt and its Evidence preserved without accepting CHECK values as approved.",
     "Observation only: no engineering, safety or compliance determination, diagnosis or control action.",
     "Pinned files and receipt hashes are not signatures or a hostile-code sandbox."))


class PinnedRefrigerationSource(PinnedSource):
    def __init__(self, root: Path):
        super().__init__(root, PROFILE)


class RefrigerationStdioCapability(PinnedStdioCapability):
    PROFILE = PROFILE

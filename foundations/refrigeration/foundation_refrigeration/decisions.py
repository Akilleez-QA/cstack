"""Open SME decisions recorded as DISPUTED with every position, never chosen (open-decisions/1).

B114 marker colour scheme, the 70 psig HIGH/LOW split, the canonical Northfield, and whether
'alarm' is banned wording (census sections 1.2, 1.5, 1.9 and 7). Client names are replaced by a
role description.
"""
from __future__ import annotations

from .evidence import evidence_from_dict
from .projection import load

SCHEMA = "open-decisions/1"


class DecisionError(ValueError):
    pass


def check(items):
    """Validate open-decision records; any chosen, undisputed or one-sided record is refused."""
    out = {}
    for item in items:
        evidence = evidence_from_dict(item["evidence"])
        if evidence.status != "DISPUTED" or item["chosen"] is not None or len(item["positions"]) < 2:
            raise DecisionError("An open decision must stay DISPUTED, unchosen, with at least two positions")
        if item["id"] in out:
            raise DecisionError("Duplicate open decision")
        out[item["id"]] = item
    return out


def _load():
    data, sha = load("open-decisions.json", SCHEMA)
    return check(data["decisions"]), sha


OPEN_DECISIONS, PROJECTION_SHA256 = _load()


def open_decision(decision_id):
    if decision_id not in OPEN_DECISIONS:
        raise DecisionError("Unknown open decision")
    return OPEN_DECISIONS[decision_id]

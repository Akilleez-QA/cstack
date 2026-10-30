"""Ammonia (R717, CAS 7664-41-7) occupational exposure limits, kept as data, with citations.

Ported from the reference app packages/domain/src/safety/ammonia-exposure-limits.ts. The OSHA PEL
is 50 ppm; 25 ppm is the NIOSH REL and the ACGIH TLV-TWA. Mixing these up tells a technician the
legal limit is half what it is, or that a recommended limit is enforceable.

Two kinds are kept apart:
- published limits: cited regulatory, recommended or guideline values (exposure-limits/1);
- policy set points: a plant's or client's own setting (for example an alarm level), with a
  policy basis. A policy value is never presentable as a legal or published limit: it cannot
  carry a cited basis, a legal status, or a label that names an issuer or a limit type.

ERPG-1/2/3 are an explicit gap: no primary AIHA source was read, so no value is recorded.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .evidence import Evidence, EvidenceError, PolicyBasis, evidence_from_dict
from .projection import load
from .units import UnitError, quantity

SCHEMA = "exposure-limits/1"
ISSUERS = ("OSHA", "NIOSH", "ACGIH")
LEGAL_STATUSES = ("enforceable", "recommended", "guideline")
# A policy label may not borrow the vocabulary of a published limit.
_PUBLISHED_WORDS = re.compile(r"\b(osha|niosh|acgih|aiha|cal/?osha|pel|rel|tlv|idlh|erpg|stel|twa|legal|"
                              r"regulatory|regulation|statutory|law|cfr|limit|limits)\b", re.I)


class SafetyLimitError(ValueError):
    pass


@dataclass(frozen=True)
class PublishedLimit:
    id: str
    issuer: str
    kind: str
    label: str
    ppm: float
    mg_per_m3: float | None
    averaging: str
    legal_status: str
    evidence: Evidence

    def __post_init__(self):
        if self.issuer not in ISSUERS or self.legal_status not in LEGAL_STATUSES:
            raise SafetyLimitError("Unknown issuer or legal status")
        if self.evidence.basis.kind != "cited":
            raise SafetyLimitError("A published limit needs a cited basis")

    def to_dict(self):
        return {"id": self.id, "value_kind": "published_limit", "issuer": self.issuer, "kind": self.kind,
                "label": self.label, "concentration": {"value": self.ppm, "unit": "ppm"},
                "mass_concentration": None if self.mg_per_m3 is None else {"value": self.mg_per_m3, "unit": "mg/m3"},
                "averaging": self.averaging, "legal_status": self.legal_status,
                "display": self.label + ": " + _fmt(self.ppm) + " ppm", "evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class PolicySetPoint:
    """A plant/client setting. Never a legal limit; always labelled as policy when shown."""
    label: str
    ppm: float
    evidence: Evidence

    def __post_init__(self):
        if self.evidence.basis.kind != "policy":
            raise SafetyLimitError("A policy set point needs a policy basis")
        if type(self.label) is not str or not self.label.strip() or len(self.label) > 120:
            raise SafetyLimitError("A policy set point needs a short label")
        if _PUBLISHED_WORDS.search(self.label):
            raise SafetyLimitError("A policy label must not name an issuer, a limit type or legal status")

    def to_dict(self):
        return {"value_kind": "policy_set_point", "label": self.label,
                "concentration": {"value": self.ppm, "unit": "ppm"}, "legal_status": "not_a_legal_limit",
                "display": "Policy set point (" + self.evidence.basis.scope + ", set by "
                           + self.evidence.basis.set_by + "), not a legal or published limit: "
                           + self.label + " " + _fmt(self.ppm) + " ppm",
                "evidence": self.evidence.to_dict()}


def _fmt(ppm):
    return str(int(ppm)) if float(ppm).is_integer() else str(ppm)


def _load():
    data, sha = load("exposure-limits.json", SCHEMA)
    limits = []
    for row in data["limits"]:
        if row["value_kind"] != "published_limit" or row["concentration"]["unit"] != "ppm":
            raise SafetyLimitError("Unexpected exposure-limit row")
        mg = row["mass_concentration"]
        limits.append(PublishedLimit(row["id"], row["issuer"], row["kind"], row["label"],
                                     float(row["concentration"]["value"]), None if mg is None else float(mg["value"]),
                                     row["averaging"], row["legal_status"], evidence_from_dict(row["evidence"])))
    return tuple(limits), tuple(data["gaps"]), data, sha


AMMONIA_LIMITS, GAPS, _DATA, PROJECTION_SHA256 = _load()
SUBSTANCE = _DATA["substance"]
SCOPE = _DATA["scope"]


def ammonia_limit(limit_id):
    for limit in AMMONIA_LIMITS:
        if limit.id == limit_id:
            return limit
    raise SafetyLimitError("Unknown ammonia limit")


def policy_set_point(value) -> PolicySetPoint:
    """Read a caller-supplied set point {label, concentration, set_by, scope, reason}."""
    if type(value) is not dict or set(value) != {"label", "concentration", "set_by", "scope", "reason"}:
        raise SafetyLimitError("A policy set point needs exactly label, concentration, set_by, scope, reason")
    try:
        ppm, _ = quantity(value["concentration"], ("ppm",), "concentration")
        evidence = Evidence(PolicyBasis(value["set_by"], value["scope"], value["reason"]), "CHECK")
    except (UnitError, EvidenceError) as error:
        raise SafetyLimitError(str(error)) from None
    if ppm < 0:
        raise SafetyLimitError("Concentration cannot be negative")
    return PolicySetPoint(value["label"], ppm, evidence)


_OSHA_BEFORE = re.compile(r"OSHA[^.\n]{0,40}\bPEL[^.\n]{0,40}\b25\s*ppm", re.I)
_OSHA_AFTER = re.compile(r"\b25\s*ppm[^.\n]{0,40}OSHA[^.\n]{0,20}\bPEL", re.I)


def find_mislabelled_ammonia_limits(text):
    """Lines of text that label 25 ppm as the OSHA PEL. Empty means no known mislabel."""
    return [line.strip() for line in text.split("\n") if _OSHA_BEFORE.search(line) or _OSHA_AFTER.search(line)]

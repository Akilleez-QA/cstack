"""One canonical equipment-kind taxonomy with an alias table, plus line-service codes (plant-taxonomy/1).

The census (workshop/CORE-CENSUS.md section 1.2) found at least nine separate equipment-kind
lists. Every value of each list resolves here to exactly one canonical kind; the lists themselves
are kept in the projection so a test can prove coverage. Line-service codes are the reference app's
18 canvas-services.ts codes plus codes found only in a second reference source (CD, OD, LTRL, LTL, LTS), which are
registered as new codes marked CHECK with their possible equivalents, never silently merged.
"""
from __future__ import annotations

import re

from .evidence import Evidence, PracticeBasis, evidence_from_dict
from .projection import load

SCHEMA = "plant-taxonomy/1"
VOCABULARIES = ("equipment_kind", "line_service")


class PlantModelError(ValueError):
    pass


def normalise(term):
    if type(term) is not str or not term.strip() or len(term) > 128:
        raise PlantModelError("A term must be short nonempty text")
    return re.sub(r"[\s_]+", "-", term.strip().lower())


def _load():
    data, sha = load("plant-taxonomy.json", SCHEMA)
    kinds = {k["id"]: k for k in data["kinds"]}
    if len(kinds) != len(data["kinds"]):
        raise PlantModelError("Duplicate canonical kind")
    for kind in kinds.values():
        if kind["parent"] is not None and kind["parent"] not in kinds:
            raise PlantModelError("Kind parent is not a canonical kind")
    for alias, target in data["aliases"].items():
        if normalise(alias) != alias or target not in kinds:
            raise PlantModelError("Alias table is not normalised or names an unknown kind")
    services = {}
    for row in data["line_services"]:
        if row["code"] in services:
            raise PlantModelError("Duplicate line-service code")
        evidence_from_dict(row["evidence"])
        services[row["code"]] = row
    return data, kinds, dict(data["aliases"]), services, sha


_DATA, KINDS, ALIASES, LINE_SERVICES, PROJECTION_SHA256 = _load()
TAXONOMY_EVIDENCE = evidence_from_dict(_DATA["evidence"])
LEGACY_LISTS = tuple(_DATA["legacy_lists"])
LINE_SERVICE_OPEN_DECISIONS = tuple(_DATA["line_service_open_decisions"])


def lineage(kind_id):
    chain, seen = [], set()
    while kind_id is not None and kind_id not in seen:
        seen.add(kind_id)
        chain.append(kind_id)
        kind_id = KINDS[kind_id]["parent"]
    return chain


def legacy_sources(normalised):
    return [entry["id"] for entry in LEGACY_LISTS if normalised in {normalise(v) for v in entry["values"]}]


def resolve_equipment_kind(term):
    """Return a resolution record; an unknown term is a resolved=False observation, not a guess."""
    key = normalise(term)
    if key not in ALIASES:
        return {"vocabulary": "equipment_kind", "term": term, "normalised": key, "resolved": False,
                "kind": None, "evidence": TAXONOMY_EVIDENCE.to_dict(),
                "note": "No alias matches. The term was not guessed into a kind."}
    kind_id = ALIASES[key]
    kind = KINDS[kind_id]
    note = _DATA["alias_notes"].get(key)
    evidence = TAXONOMY_EVIDENCE if note is None else Evidence(PracticeBasis(
        TAXONOMY_EVIDENCE.basis.note + " Alias note: " + note), "CHECK")
    return {"vocabulary": "equipment_kind", "term": term, "normalised": key, "resolved": True,
            "kind": {"id": kind_id, "label": kind["label"], "lineage": lineage(kind_id)},
            "alias_is_canonical_id": key == kind_id, "legacy_sources": legacy_sources(key),
            "evidence": evidence.to_dict(), "note": note}


def resolve_line_service(term):
    if type(term) is not str or not term.strip() or len(term) > 16:
        raise PlantModelError("A line-service code must be short text")
    code = term.strip().upper()
    if code not in LINE_SERVICES or code == "?":
        return {"vocabulary": "line_service", "term": term, "normalised": code, "resolved": False,
                "service": None, "evidence": TAXONOMY_EVIDENCE.to_dict(),
                "note": "Not a registered line-service code. The term was not guessed into a service."}
    row = dict(LINE_SERVICES[code])
    evidence = row.pop("evidence")
    return {"vocabulary": "line_service", "term": term, "normalised": code, "resolved": True,
            "service": row, "evidence": evidence,
            "note": "Pressure class and marker colours depend on open SME decisions: "
                    + ", ".join(LINE_SERVICE_OPEN_DECISIONS) + "."}

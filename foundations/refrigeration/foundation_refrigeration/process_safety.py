"""Anhydrous-ammonia quantity screen and standard-selection evidence guard.

Ported from upstream/app/packages/domain/src/process-safety/ammonia-quantity-screen.ts
and standard-selection.ts. The threshold quantities live in data/psm-thresholds.json: 10,000 lb
anhydrous ammonia in 29 CFR 1910.119 Appendix A (at or above) and 40 CFR 68.130 (exceeds, so
above). Aqueous ammonia is a different row and is out of scope.

Every public result is a screen for a person to read. It is not an engineering, safety or
compliance determination, and nothing here operates a plant. Library only: the bridge tool
inventory stays the seven tools fixed by ADR-002.
"""
from __future__ import annotations

import math
import re

from .evidence import EvidenceError, evidence_from_dict
from .projection import ProjectionError, load

SCHEMA = "psm-thresholds/1"
FRAMEWORKS = ("osha-psm", "epa-rmp")
SUBSTANCE = "anhydrous-ammonia"
CAS = "7664-41-7"
COMPARISONS = ("at-or-above", "above")
_QUANTITY_FIELDS = ("framework", "process_id", "substance", "maximum_quantity_lb", "quantity_basis",
                    "boundary_review", "inventory_review", "freshness", "source_kind", "source_ids",
                    "boundary_review_id", "inventory_review_id")
_SELECTION_FIELDS = ("process_id", "designation", "selected_edition", "latest_known_edition",
                     "publication_status", "authority_basis", "selection_review_id", "applicability",
                     "applicability_review_id", "source_kind", "source_id", "source_edition",
                     "requirement_locator", "source_access", "amendments_review_id", "requirement_review_id")
QUANTITY_CLAIM = (
    "Federal anhydrous-ammonia quantity screen only. Jurisdiction, exemptions, process grouping, "
    "other substances, RMP program level, general-duty obligations and state/local requirements "
    "need separate qualified review. This result does not establish site compliance.")
SELECTION_CLAIM = (
    "Supports a scoped engineering requirement reference only. Supplied review IDs "
    "and verified-content labels require authenticated source resolution. This result does not "
    "approve equipment, select operating limits, establish compliance or authorize plant actions.")


class ProcessSafetyError(ValueError):
    pass


def _screen(body):
    """Label every public result as a screen. The status is not a determination."""
    return {"result_kind": "screen", "label": "screen", "compliance_determination": False,
            "observation_only": True, "display": "Screen: " + body["status"] + ". Not a compliance determination.",
            **body}


def _exact(value, fields, what):
    if type(value) is not dict or set(value) != set(fields):
        raise ProcessSafetyError(what + " needs exactly its known fields")
    return value


def _present(value):
    return type(value) is str and value.strip() != ""


def _optional_text(value, name):
    if value is None or type(value) is str:
        return value
    raise ProcessSafetyError(name + " must be text or null")


def _required_text(value, name):
    if type(value) is not str:
        raise ProcessSafetyError(name + " must be text")
    return value


def _quote_has(quoted, number):
    compact = re.sub(r"[,\s]", "", quoted or "")
    return str(number) in compact


def _load():
    try:
        data, sha = load("psm-thresholds.json", SCHEMA)
    except ProjectionError as error:
        raise ProcessSafetyError(str(error)) from None
    rows = data.get("rules")
    if type(rows) is not list or sorted(row.get("framework") for row in rows) != sorted(FRAMEWORKS):
        raise ProcessSafetyError("Threshold table must name osha-psm and epa-rmp")
    if data.get("result_kind") != "screen":
        raise ProcessSafetyError("Threshold projection must be labeled as a screen")
    rules = {}
    for row in rows:
        framework = row.get("framework")
        comparison = row.get("comparison")
        threshold = row.get("threshold_lb")
        if (framework not in FRAMEWORKS or comparison not in COMPARISONS or type(threshold) is not int
                or threshold < 0 or row.get("substance") != SUBSTANCE or row.get("cas") != CAS
                or row.get("unit") != "lb" or type(row.get("citations")) is not list
                or not row["citations"] or any(type(url) is not str or not url.startswith("https://www.ecfr.gov/")
                                                for url in row["citations"])):
            raise ProcessSafetyError("Unusable threshold rule")
        try:
            threshold_evidence = evidence_from_dict(row["threshold_evidence"])
            comparison_evidence = evidence_from_dict(row["comparison_evidence"])
        except (EvidenceError, KeyError) as error:
            raise ProcessSafetyError(str(error)) from None
        for evidence in (threshold_evidence, comparison_evidence):
            if evidence.basis.kind != "cited" or evidence.status != "CHECK":
                raise ProcessSafetyError("A threshold needs cited CHECK evidence")
            if not (evidence.basis.url or "").startswith("https://www.ecfr.gov/"):
                raise ProcessSafetyError("A threshold citation must be an eCFR URL")
        if not _quote_has(threshold_evidence.basis.quoted, threshold):
            raise ProcessSafetyError("Cited quote does not contain the threshold")
        compared = (comparison_evidence.basis.quoted or "").lower()
        if comparison == "at-or-above" and "at or above" not in compared:
            raise ProcessSafetyError("At-or-above comparison is not in the cited text")
        if comparison == "above" and "exceeds" not in compared:
            raise ProcessSafetyError("Above comparison is not in the cited text")
        rules[framework] = {"framework": framework, "threshold_lb": threshold, "comparison": comparison,
                            "substance": SUBSTANCE, "cas": CAS, "unit": "lb",
                            "retrieved_on": threshold_evidence.basis.retrieved_on,
                            "citations": tuple(row["citations"]),
                            "threshold_evidence": threshold_evidence, "comparison_evidence": comparison_evidence}
    return rules, data, sha


RULES, _DATA, PROJECTION_SHA256 = _load()
SCOPE = _DATA["scope"]


def _rule_dict(rule):
    return {"framework": rule["framework"], "threshold_lb": rule["threshold_lb"], "comparison": rule["comparison"],
            "substance": rule["substance"], "cas": rule["cas"], "unit": "lb",
            "retrieved_on": rule["retrieved_on"], "citations": list(rule["citations"]),
            "threshold_evidence": rule["threshold_evidence"].to_dict(),
            "comparison_evidence": rule["comparison_evidence"].to_dict()}


def _valid_quantity(quantity):
    if type(quantity) is not dict or set(quantity) != {"lower", "upper"}:
        return False
    lower, upper = quantity["lower"], quantity["upper"]
    if type(lower) not in (int, float) or type(upper) not in (int, float):
        return False
    return math.isfinite(lower) and math.isfinite(upper) and lower >= 0 and upper >= lower


def _meets(pounds, rule):
    if rule["comparison"] == "at-or-above":
        return pounds >= rule["threshold_lb"]
    return pounds > rule["threshold_lb"]


def _quantity_status(quantity, rule, gaps):
    if gaps or not _valid_quantity(quantity):
        return "unknown"
    if _meets(quantity["lower"], rule):
        return "quantity-trigger-met"
    if not _meets(quantity["upper"], rule):
        return "quantity-trigger-not-met"
    gaps.append("threshold-straddled")
    return "unknown"


def _review_gaps(inventory, gaps):
    if inventory["boundary_review"] != "reviewed" or not _present(inventory["boundary_review_id"]):
        gaps.append("boundary-review-required")
    if inventory["inventory_review"] != "reviewed" or not _present(inventory["inventory_review_id"]):
        gaps.append("inventory-review-required")
    if inventory["freshness"] != "current":
        gaps.append("current-evidence-required")
    source_ids = inventory["source_ids"]
    if (inventory["source_kind"] != "retained" or type(source_ids) is not list or not source_ids
            or any(not _present(item) for item in source_ids)):
        gaps.append("retained-source-required")


def screen_ammonia_quantity(inventory):
    """Screen one reviewed process inventory. Does not sum a site or decide applicability."""
    inventory = _exact(inventory, _QUANTITY_FIELDS, "Inventory")
    if inventory["framework"] not in RULES:
        raise ProcessSafetyError("Unknown framework")
    for name in ("substance", "quantity_basis", "boundary_review", "inventory_review", "freshness", "source_kind"):
        _required_text(inventory[name], name)
    _required_text(inventory["process_id"], "process_id")
    _optional_text(inventory["boundary_review_id"], "boundary_review_id")
    _optional_text(inventory["inventory_review_id"], "inventory_review_id")
    quantity = inventory["maximum_quantity_lb"]
    if quantity is not None and type(quantity) is not dict:
        quantity = {"lower": None, "upper": None}
    source_ids = inventory["source_ids"]
    if type(source_ids) is not list or any(type(item) is not str for item in source_ids):
        raise ProcessSafetyError("source_ids must be a list of strings")
    rule = RULES[inventory["framework"]]
    gaps = []
    if not _present(inventory["process_id"]):
        gaps.append("missing-process")
    if inventory["substance"] != SUBSTANCE:
        gaps.append("unsupported-substance")
    if not _valid_quantity(quantity):
        gaps.append("invalid-or-missing-quantity")
    if inventory["quantity_basis"] != "process-maximum":
        gaps.append("maximum-inventory-required")
    _review_gaps(inventory, gaps)
    return _screen({"framework": inventory["framework"], "process_id": inventory["process_id"],
                    "status": _quantity_status(quantity, rule, gaps), "gaps": gaps, "rule": _rule_dict(rule),
                    "source_ids": list(source_ids), "claim_boundary": QUANTITY_CLAIM})


def _scope_gaps(selection, gaps):
    if not all(_present(selection[name]) for name in ("process_id", "designation", "selected_edition")):
        gaps.append("missing-reference-identity")
    if selection["publication_status"] != "published":
        gaps.append("published-source-required")
    if selection["authority_basis"] == "unresolved":
        gaps.append("authority-basis-required")
    if not _present(selection["selection_review_id"]):
        gaps.append("selection-review-required")
    if selection["applicability"] == "not-applicable":
        gaps.append("not-applicable-to-scope")
    if selection["applicability"] == "unassessed" or not _present(selection["applicability_review_id"]):
        gaps.append("applicability-review-required")


def _source_gaps(selection, gaps):
    if selection["source_kind"] != "retained" or not _present(selection["source_id"]):
        gaps.append("retained-source-required")
    if not _present(selection["source_edition"]) or selection["source_edition"] != selection["selected_edition"]:
        gaps.append("edition-mismatch")
    if selection["source_access"] != "verified-content":
        gaps.append("requirement-content-required")
    if not _present(selection["requirement_locator"]):
        gaps.append("requirement-locator-required")
    if not _present(selection["amendments_review_id"]):
        gaps.append("amendments-review-required")
    if not _present(selection["requirement_review_id"]):
        gaps.append("requirement-review-required")


def assess_standard_requirement_selection(selection):
    """Evidence guard for one selected requirement reference. Does not choose a standard."""
    selection = _exact(selection, _SELECTION_FIELDS, "Selection")
    for name in ("process_id", "designation", "selected_edition", "publication_status", "authority_basis",
                 "applicability", "source_kind", "source_access"):
        _required_text(selection[name], name)
    for name in ("latest_known_edition", "selection_review_id", "applicability_review_id", "source_id",
                 "source_edition", "requirement_locator", "amendments_review_id", "requirement_review_id"):
        _optional_text(selection[name], name)
    gaps = []
    _scope_gaps(selection, gaps)
    _source_gaps(selection, gaps)
    return _screen({"status": "reference-supported" if not gaps else "review-required", "gaps": gaps,
                    "process_id": selection["process_id"], "designation": selection["designation"],
                    "selected_edition": selection["selected_edition"], "source_id": selection["source_id"],
                    "claim_boundary": SELECTION_CLAIM})

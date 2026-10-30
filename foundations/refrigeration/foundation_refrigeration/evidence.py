"""Where a value comes from and whether a qualified person has approved it: the one status model.

Ported from the earlier TypeScript draft (bench foundation-refr src/core/evidence.ts) and from
the reference app src/features/compliance/basis.ts. Five vocabularies existed for the same idea
(CHECK/APPROVED, verifiedBy null/set, VERIFIED/REPORTED, SOURCED/NEEDS-ENGINEER/COMMON-PRACTICE,
cited/plant-configured). Every value here carries one Evidence, and LEGACY_STATUS maps each old
spelling onto it.

Basis kinds: cited (a published document), generated (a named, versioned generator, rule T-1),
policy (a setting chosen for one plant, client or expression; never a requirement) and practice
(general engineering practice with no single citable source).

Status: CHECK (recorded, not yet approved), APPROVED (a qualified person signed it off) or
DISPUTED (a known conflict). Silence is not approval: APPROVED requires approvedBy and approvedOn.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import re

BASIS_KINDS = ("cited", "generated", "policy", "practice")
STATUSES = ("CHECK", "APPROVED", "DISPUTED")
POLICY_SCOPES = ("plant", "client", "expression")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_MAX_TEXT = 2048


class EvidenceError(ValueError):
    """Evidence that cannot back a value. It is refused, never shown as settled."""


def _text(value, name, *, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str or len(value) > _MAX_TEXT:
        raise EvidenceError(name + " must be bounded text")
    return value


def _date(value, name, *, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str or _DATE.fullmatch(value) is None:
        raise EvidenceError(name + " must be an ISO date YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise EvidenceError(name + " is not a real calendar date") from None
    return value


def _exact(value, required, optional=()):
    if type(value) is not dict:
        raise EvidenceError("Expected an object")
    keys = set(value)
    if not set(required) <= keys or not keys <= set(required) | set(optional):
        raise EvidenceError("Unexpected or missing evidence fields")
    return value


@dataclass(frozen=True)
class CitedBasis:
    """A published document: a regulation, a standard, a manufacturer document, a paper."""
    source: str
    version: str
    clause: str | None = None
    url: str | None = None
    quoted: str | None = None
    retrieved_on: str | None = None
    kind: str = "cited"

    def __post_init__(self):
        _text(self.source, "source")
        _text(self.version, "version")
        _text(self.clause, "clause", optional=True)
        _text(self.url, "url", optional=True)
        _text(self.quoted, "quoted", optional=True)
        _date(self.retrieved_on, "retrievedOn", optional=True)
        if self.kind != "cited":
            raise EvidenceError("Cited basis kind is fixed")

    def problem(self):
        if not self.source.strip():
            return "A cited value needs its source."
        if not self.version.strip():
            return "A cited value needs the version of its source."
        return None

    def to_dict(self):
        out = {"kind": "cited", "source": self.source, "version": self.version, "clause": self.clause}
        for key, value in (("url", self.url), ("quoted", self.quoted), ("retrievedOn", self.retrieved_on)):
            if value is not None:
                out[key] = value
        return out


@dataclass(frozen=True)
class GeneratedBasis:
    """A number produced by a named, versioned generator from a property model (rule T-1)."""
    model: str
    generator: str
    generated_on: str
    kind: str = "generated"

    def __post_init__(self):
        _text(self.model, "model")
        _text(self.generator, "generator")
        _date(self.generated_on, "generatedOn")
        if self.kind != "generated":
            raise EvidenceError("Generated basis kind is fixed")

    def problem(self):
        if not self.model.strip() or not self.generator.strip():
            return "A generated value needs its model and generator command."
        return None

    def to_dict(self):
        return {"kind": "generated", "model": self.model, "generator": self.generator,
                "generatedOn": self.generated_on}


@dataclass(frozen=True)
class PolicyBasis:
    """A setting chosen for one plant or client, not a requirement (e.g. a client's alarm set point)."""
    set_by: str
    scope: str
    reason: str
    kind: str = "policy"

    def __post_init__(self):
        _text(self.set_by, "setBy")
        _text(self.reason, "reason")
        if self.scope not in POLICY_SCOPES:
            raise EvidenceError("Policy scope must be plant, client or expression")
        if self.kind != "policy":
            raise EvidenceError("Policy basis kind is fixed")

    def problem(self):
        if not self.set_by.strip():
            return "A policy value needs the role that set it."
        if not self.reason.strip():
            return "A policy value needs a reason."
        return None

    def to_dict(self):
        return {"kind": "policy", "setBy": self.set_by, "scope": self.scope, "reason": self.reason}


@dataclass(frozen=True)
class PracticeBasis:
    """General engineering practice with no single citable source; always needs an SME to approve."""
    note: str
    kind: str = "practice"

    def __post_init__(self):
        _text(self.note, "note")
        if self.kind != "practice":
            raise EvidenceError("Practice basis kind is fixed")

    def problem(self):
        if not self.note.strip():
            return "A practice value needs a note explaining it."
        return None

    def to_dict(self):
        return {"kind": "practice", "note": self.note}


BASIS_TYPES = (CitedBasis, GeneratedBasis, PolicyBasis, PracticeBasis)


@dataclass(frozen=True)
class Evidence:
    basis: CitedBasis | GeneratedBasis | PolicyBasis | PracticeBasis
    status: str
    approved_by: str | None = None
    approved_on: str | None = None
    dispute: str | None = None
    fresh_for_days: int | None = None

    def __post_init__(self):
        problem = evidence_problem(self)
        if problem is not None:
            raise EvidenceError(problem)

    def to_dict(self):
        out = {"basis": self.basis.to_dict(), "status": self.status}
        for key, value in (("approvedBy", self.approved_by), ("approvedOn", self.approved_on),
                           ("dispute", self.dispute), ("freshForDays", self.fresh_for_days)):
            if value is not None:
                out[key] = value
        return out

    @property
    def approved(self) -> bool:
        return is_approved(self)


def evidence_problem(evidence) -> str | None:
    """Why this evidence cannot back a value, or None when it can."""
    if type(evidence) is not Evidence:
        return "Not an Evidence record."
    basis = evidence.basis
    if type(basis) not in BASIS_TYPES:
        return "Unknown basis kind."
    if evidence.status not in STATUSES:
        return "Status must be CHECK, APPROVED or DISPUTED."
    try:
        _text(evidence.approved_by, "approvedBy", optional=True)
        _date(evidence.approved_on, "approvedOn", optional=True)
        _text(evidence.dispute, "dispute", optional=True)
    except EvidenceError as error:
        return str(error)
    if evidence.fresh_for_days is not None and (type(evidence.fresh_for_days) is not int
                                                or not 1 <= evidence.fresh_for_days <= 36_500):
        return "freshForDays must be a whole number of days."
    problem = basis.problem()
    if problem is not None:
        return problem
    approved_fields = evidence.approved_by is not None or evidence.approved_on is not None
    if evidence.status == "APPROVED":
        if not (evidence.approved_by or "").strip() or not evidence.approved_on:
            return "APPROVED needs approvedBy and approvedOn: silence is not approval."
    elif approved_fields:
        return "approvedBy/approvedOn are recorded only on APPROVED evidence."
    if evidence.status == "DISPUTED" and not (evidence.dispute or "").strip():
        return "DISPUTED needs the conflict described."
    if evidence.status != "DISPUTED" and evidence.dispute is not None:
        return "A dispute is recorded only on DISPUTED evidence."
    return None


def record_problem(value) -> str | None:
    """Why a JSON evidence record cannot back a value, or None when it can (for checking legacy data)."""
    try:
        evidence_from_dict(value)
    except EvidenceError as error:
        return str(error)
    return None


def is_approved(evidence) -> bool:
    """True when the value may be shown to a person as settled."""
    return type(evidence) is Evidence and evidence.status == "APPROVED" and evidence_problem(evidence) is None


def basis_from_dict(value):
    if type(value) is not dict or value.get("kind") not in BASIS_KINDS:
        raise EvidenceError("Unknown basis kind")
    kind = value["kind"]
    if kind == "cited":
        _exact(value, ("kind", "source", "version", "clause"), ("url", "quoted", "retrievedOn"))
        return CitedBasis(value["source"], value["version"], value["clause"], value.get("url"),
                          value.get("quoted"), value.get("retrievedOn"))
    if kind == "generated":
        _exact(value, ("kind", "model", "generator", "generatedOn"))
        return GeneratedBasis(value["model"], value["generator"], value["generatedOn"])
    if kind == "policy":
        _exact(value, ("kind", "setBy", "scope", "reason"))
        return PolicyBasis(value["setBy"], value["scope"], value["reason"])
    _exact(value, ("kind", "note"))
    return PracticeBasis(value["note"])


def evidence_from_dict(value) -> Evidence:
    _exact(value, ("basis", "status"), ("approvedBy", "approvedOn", "dispute", "freshForDays"))
    return Evidence(basis_from_dict(value["basis"]), value["status"], value.get("approvedBy"),
                    value.get("approvedOn"), value.get("dispute"), value.get("freshForDays"))


# Each legacy spelling found in the census, mapped onto the one model. VERIFIED (a source page was
# read) is not approval by a qualified person, so it maps to CHECK. Only CHECK and APPROVED keep
# their meaning, and a legacy APPROVED still needs approvedBy and approvedOn to be accepted.
LEGACY_STATUS = {
    "CHECK": "CHECK",
    "APPROVED": "APPROVED",
    "DISPUTED": "DISPUTED",
    "VERIFIED": "CHECK",
    "REPORTED": "CHECK",
    "SOURCED": "CHECK",
    "NEEDS-ENGINEER": "CHECK",
    "COMMON-PRACTICE": "CHECK",
    "cited": "CHECK",
    "plant-configured": "CHECK",
    "UNVERIFIED": "CHECK",
}

# Which basis each legacy confidence spelling implies when nothing better is recorded.
LEGACY_BASIS_KIND = {
    "SOURCED": "cited",
    "VERIFIED": "cited",
    "REPORTED": "cited",
    "cited": "cited",
    "NEEDS-ENGINEER": "practice",
    "COMMON-PRACTICE": "practice",
    "UNVERIFIED": "practice",
    "plant-configured": "policy",
}


def legacy_status(spelling: str) -> str:
    if type(spelling) is not str or spelling not in LEGACY_STATUS:
        raise EvidenceError("Unknown legacy status spelling")
    return LEGACY_STATUS[spelling]


def from_legacy_basis(value) -> Evidence:
    """Port a the reference app basis.ts record. A recorded checkedOn is kept but is not approval."""
    if type(value) is not dict or value.get("kind") not in ("cited", "plant-configured"):
        raise EvidenceError("Unknown legacy basis kind")
    if value["kind"] == "plant-configured":
        _exact(value, ("kind", "setBy", "reason"))
        return Evidence(PolicyBasis(value["setBy"], "plant", value["reason"]), "CHECK")
    _exact(value, ("kind", "source", "version", "clause", "checkedOn"))
    checked = _date(value["checkedOn"], "checkedOn", optional=True)
    quoted = None if checked is None else "Legacy record: checked against the current text on " + checked
    # basis.ts records no approver role, so the value stays CHECK: silence is not approval.
    return Evidence(CitedBasis(value["source"], value["version"], value["clause"], quoted=quoted), "CHECK")


def from_legacy_verification(basis, verified_by, verified_at) -> Evidence:
    """Port the P/T table verifiedBy/verifiedAt pair: null means CHECK; both set means APPROVED."""
    if verified_by is None and verified_at is None:
        return Evidence(basis, "CHECK")
    if verified_by is None or verified_at is None:
        raise EvidenceError("verifiedBy and verifiedAt must both be set or both be null")
    return Evidence(basis, "APPROVED", approved_by=verified_by, approved_on=verified_at)

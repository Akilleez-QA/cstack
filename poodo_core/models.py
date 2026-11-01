"""Versioned, detached core records. No domain or runtime knowledge lives here."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re

EXTENSION_VERSION = "poodo.domain-extension/0.1"
REQUEST_VERSION = "poodo.capability-request/0.1"
OUTCOME_VERSION = "poodo.capability-result/0.1"
MAX_DOCUMENT_BYTES = 2_097_152
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
# ADR 005 decision 2: the eight port lanes, exact strings, defined here once.
LANES = ("HMIFace", "TruthFace", "RuntimeFace", "EvidenceFace", "SupervisorFace", "ToolFace", "ReadModelFace",
         "LearningFace")
READ_ONLY_LANES = ("ReadModelFace", "LearningFace")


class ContractError(ValueError):
    """A failed contract is not evidence or a successful action."""


def identifier(value: object) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ContractError("Expected a bounded opaque identifier")
    return value


def port_lane(value: object) -> str:
    # Exact str only: a str subclass could compare equal to any lane.
    if type(value) is not str or value not in LANES:
        raise ContractError("Expected one of the eight ADR 005 port lanes")
    return value


def prose(value: object, maximum: int = 4096) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ContractError("Expected nonempty bounded text")
    return value


def exact_fields(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise ContractError("Unexpected or missing fields")
    return value


def canonical(value: object) -> str:
    # Generic core permits finite JSON floats. Numeric semantics belong to domains.
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 128 or nodes > 200_000:
            raise ContractError("Document structure exceeds core budget")
        if type(item) is dict:
            if any(type(k) is not str for k in item):
                raise ContractError("JSON object keys must be strings")
            stack.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            stack.extend((v, depth + 1) for v in item)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ContractError("Only explicit JSON values are admitted")
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ContractError("Document cannot be represented as bounded JSON") from None
    if len(result) > MAX_DOCUMENT_BYTES:
        raise ContractError("Document exceeds core byte budget")
    return result


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class Document:
    """Canonical JSON text is recursively immutable; reads return fresh objects."""
    _json: str

    @classmethod
    def capture(cls, value: object) -> "Document":
        return cls(canonical(value))

    def read(self):
        return json.loads(self._json)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._json.encode("ascii")).hexdigest()


class Phase(str, Enum):
    PONTIFICATE = "pontificate"
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ORCHESTRATE = "orchestrate"


@dataclass(frozen=True)
class GoalContract:
    goal_id: str
    revision: int
    domain_id: str
    objective: str
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    acceptance_version: str
    acceptance_criteria: tuple[str, ...]

    def __post_init__(self):
        for field in (self.goal_id, self.domain_id, self.acceptance_version):
            identifier(field)
        if type(self.revision) is not int or not 1 <= self.revision <= 1_000_000:
            raise ContractError("Invalid goal revision")
        prose(self.objective)
        for values in (self.assumptions, self.exclusions, self.acceptance_criteria):
            if type(values) is not tuple or len(values) > 32:
                raise ContractError("Goal lists must be bounded immutable tuples")
            for value in values:
                prose(value)
        if not self.acceptance_criteria:
            raise ContractError("A versioned acceptance criterion is required")

    def to_dict(self):
        return {"goal_id": self.goal_id, "revision": self.revision, "domain_id": self.domain_id,
                "objective": self.objective, "assumptions": list(self.assumptions),
                "exclusions": list(self.exclusions), "acceptance_version": self.acceptance_version,
                "acceptance_criteria": list(self.acceptance_criteria)}

    @classmethod
    def from_dict(cls, value):
        value = exact_fields(value, {"goal_id", "revision", "domain_id", "objective", "assumptions",
                                     "exclusions", "acceptance_version", "acceptance_criteria"})
        if any(type(value[k]) is not list for k in ("assumptions", "exclusions", "acceptance_criteria")):
            raise ContractError("Goal lists must be JSON arrays")
        return cls(**{**value, **{k: tuple(value[k]) for k in ("assumptions", "exclusions", "acceptance_criteria")}})


@dataclass(frozen=True)
class GoalSnapshot:
    contract: GoalContract
    phase: Phase
    closed: bool = False
    formal_proof: bool = False
    runtime_goal_acceptance: bool = False

    def to_dict(self):
        return {"contract": self.contract.to_dict(), "phase": self.phase.value,
                "closed": self.closed, "formal_proof": self.formal_proof,
                "runtime_goal_acceptance": self.runtime_goal_acceptance}


@dataclass(frozen=True)
class PhaseCheckpoint:
    checkpoint_id: str
    rationale: str
    research_references: tuple[str, ...] = ()
    option_ids: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.checkpoint_id)
        prose(self.rationale)
        if type(self.research_references) is not tuple or type(self.option_ids) is not tuple:
            raise ContractError("Checkpoint lists must be immutable")
        if len(self.research_references) > 32 or len(self.option_ids) > 20:
            raise ContractError("Checkpoint exceeds budget")
        for ref in self.research_references:
            prose(ref)
        for option in self.option_ids:
            identifier(option)


@dataclass(frozen=True)
class Precommitment:
    expected_observation: str
    success_boundary: str
    failure_meaning: str
    oracle_id: str
    oracle_version: str

    def __post_init__(self):
        for value in (self.expected_observation, self.success_boundary, self.failure_meaning):
            prose(value)
        identifier(self.oracle_id)
        identifier(self.oracle_version)

    def to_dict(self):
        return dict(vars(self))


@dataclass(frozen=True)
class CapabilityRequest:
    document: Document

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, {"schema", "request_id", "goal_id", "goal_revision", "decision_id",
                             "capability_id", "operation", "arguments", "required_evidence"})
        if value["schema"] != REQUEST_VERSION:
            raise ContractError("Unsupported request contract version")
        for key in ("request_id", "goal_id", "decision_id", "capability_id", "operation"):
            identifier(value[key])
        if type(value["goal_revision"]) is not int or not 1 <= value["goal_revision"] <= 1_000_000:
            raise ContractError("Invalid request goal revision")
        if type(value["arguments"]) is not dict:
            raise ContractError("Capability arguments must be an object")
        if value["required_evidence"] not in ("tool_observation", "formal_proof"):
            raise ContractError("Unknown required evidence")
        return cls(Document.capture(value))

    def to_dict(self):
        return self.document.read()

    @property
    def sha256(self):
        return self.document.sha256

    def __getattr__(self, name):
        data = self.document.read()
        if name in data:
            return data[name]
        raise AttributeError(name)


OUTCOME_FIELDS = {"schema", "request_id", "attempt_id", "goal_id", "goal_revision", "decision_id",
                  "capability_id", "operation", "execution_status", "execution_certainty", "assessment",
                  "epistemic_status", "formal_proof", "runtime_goal_acceptance", "raw_result", "request_sha256",
                  "source_manifest_sha256", "inventory_sha256", "scope", "limitations"}
EXECUTION_STATUSES = {"completed", "unavailable", "timed_out", "cancelled", "protocol_error", "tool_error",
                      "resource_rejected", "indeterminate"}


@dataclass(frozen=True)
class CapabilityOutcome:
    document: Document

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, OUTCOME_FIELDS)
        if value["schema"] != OUTCOME_VERSION:
            raise ContractError("Unsupported outcome contract version")
        for key in ("request_id", "attempt_id", "goal_id", "decision_id", "capability_id", "operation"):
            identifier(value[key])
        if type(value["goal_revision"]) is not int or value["goal_revision"] < 1:
            raise ContractError("Invalid outcome revision")
        for key in ("formal_proof", "runtime_goal_acceptance"):
            if value[key] is not False:
                raise ContractError("Evidence ceiling exceeded")
        if value["execution_status"] not in EXECUTION_STATUSES:
            raise ContractError("Unknown execution status")
        if value["execution_certainty"] not in ("not_dispatched", "responded", "unknown"):
            raise ContractError("Unknown execution certainty")
        completed = value["execution_status"] == "completed"
        if value["epistemic_status"] != ("observed" if completed else "unassessed"):
            raise ContractError("Invalid epistemic classification")
        if completed and (type(value["raw_result"]) is not dict or value["execution_certainty"] != "responded"):
            raise ContractError("Completed result requires a complete response")
        if value["raw_result"] is not None and type(value["raw_result"]) is not dict:
            raise ContractError("Invalid raw result")
        if value["execution_status"] not in ("completed", "tool_error") and value["raw_result"] is not None:
            raise ContractError("Unaccepted evidence must be quarantined")
        for key in ("request_sha256", "source_manifest_sha256", "inventory_sha256"):
            x = value[key]
            if x is None and key != "request_sha256":
                continue
            if type(x) is not str or _SHA.fullmatch(x) is None:
                raise ContractError("Invalid provenance hash")
        prose(value["assessment"], 256)
        if type(value["scope"]) is not str or len(value["scope"]) > 4096:
            raise ContractError("Invalid scope")
        if type(value["limitations"]) is not list or len(value["limitations"]) > 32:
            raise ContractError("Invalid limitations")
        for item in value["limitations"]:
            prose(item)
        return cls(Document.capture(value))

    def to_dict(self):
        return self.document.read()


def outcome_for(request, attempt_id, status, assessment, *, certainty="not_dispatched", raw_result=None,
                source_hash=None, inventory_hash=None, scope="", limitations=()):
    data = request.to_dict()
    return CapabilityOutcome.from_dict({
        "schema": OUTCOME_VERSION, **{k: data[k] for k in ("request_id", "goal_id", "goal_revision",
        "decision_id", "capability_id", "operation")}, "attempt_id": attempt_id, "execution_status": status,
        "execution_certainty": certainty, "assessment": assessment,
        "epistemic_status": "observed" if status == "completed" else "unassessed",
        "formal_proof": False, "runtime_goal_acceptance": False, "raw_result": raw_result,
        "request_sha256": request.sha256, "source_manifest_sha256": source_hash,
        "inventory_sha256": inventory_hash, "scope": scope, "limitations": list(limitations)})


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    contract_version: str
    operations: tuple[str, ...]
    evidence_ceiling: str = "tool_observation"
    # ADR 005: the port lane this capability attaches on. Required; set by the extension, never by a request.
    lane: str = field(kw_only=True)

    def __post_init__(self):
        port_lane(self.lane)


@dataclass(frozen=True)
class DomainDescriptor:
    domain_id: str
    version: str
    capabilities: tuple[CapabilityDescriptor, ...]
    numeric_semantics: str
    extension_contract: str = EXTENSION_VERSION


@dataclass(frozen=True)
class Admission:
    admitted: bool
    reason: str


@dataclass(frozen=True)
class Interpretation:
    evidence_kind: str
    covered_scope: str
    limitations: tuple[str, ...]
    formal_proof: bool = False
    runtime_goal_acceptance: bool = False


@dataclass(frozen=True)
class DecisionRecord:
    request: CapabilityRequest
    request_sha256: str
    grant_id: str
    precommitment: Precommitment
    approval: Document | None = None



WAITING_ON = ("agent", "approval", "external")


@dataclass(frozen=True)
class LivenessRecord:
    """Host-supplied next-action owner for one open goal revision. Evidence (logs, PIDs, comments) is not liveness.

    waiting_on is "agent" (the owner acts next), "approval" (an ask is pending with the configured approver) or
    "external" (a named outside party). review_by, when set, bounds the wait in host clock epoch seconds.
    """
    goal_id: str
    goal_revision: int
    owner: str
    waiting_on: str
    reason: str
    review_by: int | None = None

    def __post_init__(self):
        identifier(self.goal_id)
        identifier(self.owner)
        prose(self.reason, 512)
        if type(self.goal_revision) is not int or not 1 <= self.goal_revision <= 1_000_000:
            raise ContractError("Liveness must bind a goal revision")
        if type(self.waiting_on) is not str or self.waiting_on not in WAITING_ON:
            raise ContractError("waiting_on is agent, approval or external")
        if self.review_by is not None and (type(self.review_by) is not int or self.review_by < 1):
            raise ContractError("review_by is integer epoch seconds")

    def to_dict(self):
        return dict(vars(self))

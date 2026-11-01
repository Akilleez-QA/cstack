"""Endoforge's lifecycle model : data and rules only.

Generate, qualify, preview, activate and dispose. Nothing here executes, calls a model or grants
authority. Every transition is a proposal that applies only with a POODO decision bound to its exact digest.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import re

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class LifecycleError(ValueError):
    """A refused transition is not evidence, a decision or a successful action."""


def _identifier(value: object) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise LifecycleError("Expected a bounded opaque identifier")
    return value


def _sha(value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise LifecycleError("Expected a lowercase SHA-256 hex digest")
    return value


def _reason(value: object) -> str:
    if type(value) is not str or not value.strip() or len(value) > 1024:
        raise LifecycleError("Expected a nonempty bounded reason")
    return value


def digest(value: object) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class State(str, Enum):
    PROPOSED = "proposed"
    GENERATED = "generated"
    QUALIFIED = "qualified"
    PREVIEWED = "previewed"
    ACTIVATED = "activated"
    DISPOSED = "disposed"
    FAILED = "failed"
    REJECTED = "rejected"


_LIVE = (State.PROPOSED, State.GENERATED, State.QUALIFIED, State.PREVIEWED)

LEGAL = {
    State.GENERATED: (State.PROPOSED,),
    State.QUALIFIED: (State.GENERATED,),
    State.PREVIEWED: (State.QUALIFIED,),
    State.ACTIVATED: (State.PREVIEWED,),
    State.FAILED: _LIVE,
    State.REJECTED: _LIVE,
    State.DISPOSED: tuple(s for s in State if s is not State.DISPOSED),
}

_EVIDENCE = {
    State.GENERATED: {"candidate_sha256"},
    State.QUALIFIED: {"receipt"},
    State.PREVIEWED: {"preview_ref"},
    State.ACTIVATED: {"host_approval_ref"},
    State.FAILED: {"reason"},
    State.REJECTED: {"reason"},
    State.DISPOSED: {"reason"},
}


@dataclass(frozen=True)
class Artifact:
    """Four distinct identities : the task, the generation inputs, the candidate bytes and the
    qualification receipt. A later identity is absent until its stage, and no two may share a digest."""
    task_id: str
    generation_inputs_sha256: str
    candidate_sha256: str | None = None
    qualification_receipt_sha256: str | None = None

    def __post_init__(self):
        _identifier(self.task_id)
        digests = [_sha(self.generation_inputs_sha256)]
        if self.qualification_receipt_sha256 is not None and self.candidate_sha256 is None:
            raise LifecycleError("A qualification receipt needs a candidate")
        for value in (self.candidate_sha256, self.qualification_receipt_sha256):
            if value is not None:
                digests.append(_sha(value))
        if len(set(digests)) != len(digests):
            raise LifecycleError("Inputs, candidate and receipt are distinct identities")

    def to_dict(self):
        return dict(vars(self))

    @property
    def key(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class QualificationReceipt:
    """An outside evaluator's verdict on exact candidate bytes, under the oracle frozen before generation."""
    candidate_sha256: str
    oracle_id: str
    verdict: str

    def __post_init__(self):
        _sha(self.candidate_sha256)
        _identifier(self.oracle_id)
        if self.verdict not in ("pass", "fail"):
            raise LifecycleError("A receipt verdict is pass or fail")

    def to_dict(self):
        return dict(vars(self))

    @property
    def sha256(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class TransitionProposal:
    """One proposed state change. It carries no authority until a POODO decision binds its digest."""
    artifact_key: str
    from_state: State
    to_state: State
    evidence: tuple[tuple[str, object], ...]

    def to_dict(self):
        return {"artifact_key": self.artifact_key, "from_state": self.from_state.value,
                "to_state": self.to_state.value,
                "evidence": {k: v.to_dict() if type(v) is QualificationReceipt else v for k, v in self.evidence}}

    @property
    def sha256(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class PoodoDecision:
    """A reference to a POODO decision. The bridge that issues it is EndoforgePort, not this module."""
    decision_id: str
    proposal_sha256: str

    def __post_init__(self):
        _identifier(self.decision_id)
        _sha(self.proposal_sha256)


@dataclass(frozen=True)
class Transition:
    proposal: TransitionProposal
    decision_id: str


@dataclass(frozen=True)
class LifecycleRecord:
    artifact: Artifact
    frozen_oracle_id: str
    state: State = State.PROPOSED
    history: tuple[Transition, ...] = field(default=())

    def __post_init__(self):
        """A record is exactly what its decided history replays to; a hand-set state or artifact is refused."""
        _identifier(self.frozen_oracle_id)
        start = Artifact(self.artifact.task_id, self.artifact.generation_inputs_sha256)
        if self.history == ():
            if (self.state, self.artifact) != (State.PROPOSED, start):
                raise LifecycleError("A record starts proposed, with no candidate or receipt")
            return
        if type(self.history) is not tuple or any(type(t) is not Transition for t in self.history):
            raise LifecycleError("History is a tuple of transitions")
        record = LifecycleRecord(start, self.frozen_oracle_id)
        for t in self.history:
            record = record.apply(t.proposal, PoodoDecision(t.decision_id, t.proposal.sha256))
        if (record.state, record.artifact) != (self.state, self.artifact):
            raise LifecycleError("The state and artifact do not match the decided history")

    @classmethod
    def propose(cls, task_id: str, generation_inputs_sha256: str, frozen_oracle_id: str) -> "LifecycleRecord":
        """The specification precedes the workcell: the oracle is frozen before any candidate."""
        return cls(Artifact(task_id, generation_inputs_sha256), _identifier(frozen_oracle_id))

    def proposal(self, to_state: State, **evidence) -> TransitionProposal:
        if type(to_state) is not State or self.state not in LEGAL.get(to_state, ()):
            raise LifecycleError(f"Illegal transition {self.state.value} -> {getattr(to_state, 'value', to_state)}")
        if set(evidence) != _EVIDENCE[to_state]:
            raise LifecycleError(f"{to_state.value} carries exactly {sorted(_EVIDENCE[to_state])}")
        self._check_evidence(to_state, evidence)
        return TransitionProposal(self.artifact.key, self.state, to_state, tuple(sorted(evidence.items())))

    def _check_evidence(self, to_state: State, evidence: dict) -> None:
        if to_state is State.GENERATED:
            Artifact(self.artifact.task_id, self.artifact.generation_inputs_sha256, evidence["candidate_sha256"])
        elif to_state is State.QUALIFIED:
            receipt = evidence["receipt"]
            if type(receipt) is not QualificationReceipt:
                raise LifecycleError("Qualification needs a QualificationReceipt")
            if receipt.oracle_id != self.frozen_oracle_id:
                raise LifecycleError("The receipt's oracle is not the oracle frozen at proposal")
            if receipt.candidate_sha256 != self.artifact.candidate_sha256:
                raise LifecycleError("The receipt is for different candidate bytes")
            if receipt.verdict != "pass":
                raise LifecycleError("A failing receipt cannot qualify; propose rejected instead")
        elif to_state is State.PREVIEWED:
            _identifier(evidence["preview_ref"])
        elif to_state is State.ACTIVATED:
            _identifier(evidence["host_approval_ref"])
            if self.artifact.qualification_receipt_sha256 is None:
                raise LifecycleError("Activation needs a qualified artifact")
        else:
            _reason(evidence["reason"])

    def apply(self, proposal: TransitionProposal, decision: PoodoDecision) -> "LifecycleRecord":
        """Return the next record. The decision must bind this exact proposal, which must still be current."""
        if type(proposal) is not TransitionProposal or type(decision) is not PoodoDecision:
            raise LifecycleError("A transition needs a proposal and a POODO decision")
        if decision.proposal_sha256 != proposal.sha256:
            raise LifecycleError("The decision binds a different proposal")
        if any(t.decision_id == decision.decision_id for t in self.history):
            raise LifecycleError("A decision is consumed once")
        if proposal.artifact_key != self.artifact.key or proposal.from_state is not self.state:
            raise LifecycleError("Stale proposal: the record has moved on")
        evidence = dict(proposal.evidence)
        if self.proposal(proposal.to_state, **evidence) != proposal:
            raise LifecycleError("The proposal does not match the rules for this record")
        artifact = self.artifact
        if proposal.to_state is State.GENERATED:
            artifact = replace(artifact, candidate_sha256=evidence["candidate_sha256"])
        elif proposal.to_state is State.QUALIFIED:
            artifact = replace(artifact, qualification_receipt_sha256=evidence["receipt"].sha256)

        record = object.__new__(LifecycleRecord)
        for name, value in (("artifact", artifact), ("frozen_oracle_id", self.frozen_oracle_id),
                            ("state", proposal.to_state),
                            ("history", self.history + (Transition(proposal, decision.decision_id),))):
            object.__setattr__(record, name, value)
        return record

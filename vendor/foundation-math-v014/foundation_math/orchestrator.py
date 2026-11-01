"""Small, provider-neutral work queue. Agent proposals are never proof.

The queue is single-process and thread-safe, not a distributed scheduler. Receipts
are immutable snapshots linked by hashes; exported hashes detect alteration, not
authorship. Only exact domain computation can satisfy an exact-computation goal.
Natural-language goals/assumptions are context, not machine-checked theorems.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any, Callable, Mapping, Protocol

from .domains import DomainError, RequiredEvidence, domain_handler

ROLES = frozenset({"proposer", "calculator", "verifier", "critic", "formalizer"})
SUCCESS_STATES = frozenset({"produced", "verified"})
TERMINAL_STATES = SUCCESS_STATES | {"rejected", "failed", "blocked"}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
MAX_JSON_BYTES = 65536


class WorkflowError(ValueError):
    """A workflow, lease, or proposal violated a runtime contract."""


def canonical_json(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise WorkflowError("Expected finite, JSON-serializable structured data") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise WorkflowError("Structured input exceeds 64 KiB limit")
    return encoded


def _object(value: Any, name: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise WorkflowError(f"{name} must be an object")
    keys = set(value)
    if not required <= keys or keys - required - (optional or set()):
        raise WorkflowError(f"{name} has missing or unsupported fields")
    return value


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise WorkflowError(f"{name} must be a simple identifier of 1–80 characters")
    return value


def _positive_int(value: Any, name: str, ceiling: int) -> int:
    if type(value) is not int or not 1 <= value <= ceiling:
        raise WorkflowError(f"{name} must be an integer from 1 to {ceiling}")
    return value


@dataclass(frozen=True)
class Problem:
    id: str
    domain: str
    assumptions: tuple[str, ...]
    goal: str
    goal_request_json: str
    required_evidence: RequiredEvidence = "exact_computation"

    @classmethod
    def from_dict(cls, value: Any) -> "Problem":
        data = _object(value, "problem", {"id", "domain", "assumptions", "goal", "goal_request"}, {"required_evidence"})
        _id(data["id"], "problem.id")
        required = data.get("required_evidence", "exact_computation")
        if type(required) is not str or required not in ("exact_computation", "formal_proof"):
            raise WorkflowError("required_evidence must be exact_computation or formal_proof")
        if not isinstance(data["goal"], str) or not data["goal"].strip():
            raise WorkflowError("problem.goal must be nonempty text")
        assumptions = data["assumptions"]
        if not isinstance(assumptions, list) or any(not isinstance(a, str) or not a.strip() for a in assumptions):
            raise WorkflowError("problem.assumptions must be an explicit list of nonempty strings")
        request = data["goal_request"]
        if not isinstance(request, dict) or request.get("domain") != data["domain"]:
            raise WorkflowError("goal_request must use the declared problem domain")
        canonical_json(data)
        try:
            domain_handler(data["domain"]).validate_goal(request)
        except DomainError as exc:
            raise WorkflowError(str(exc)) from exc
        return cls(data["id"], data["domain"], tuple(assumptions), data["goal"], canonical_json(request), required)

    def to_dict(self) -> dict:
        return {"id": self.id, "domain": self.domain, "assumptions": list(self.assumptions),
                "goal": self.goal, "goal_request": json.loads(self.goal_request_json),
                "required_evidence": self.required_evidence}


@dataclass(frozen=True)
class Task:
    id: str
    role: str
    dependencies: tuple[str, ...] = ()
    payload_json: str = "{}"
    max_attempts: int = 2

    @classmethod
    def from_dict(cls, value: Any) -> "Task":
        data = _object(value, "task", {"id", "role", "dependencies"}, {"payload", "max_attempts"})
        _id(data["id"], "task.id")
        if not isinstance(data["role"], str) or data["role"] not in ROLES:
            raise WorkflowError("Unknown task role")
        deps = data["dependencies"]
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise WorkflowError("dependencies must be a list of task identifiers")
        if len(set(deps)) != len(deps) or data["id"] in deps:
            raise WorkflowError("Duplicate or self dependencies are not allowed")
        for dep in deps:
            _id(dep, "dependency")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise WorkflowError("task.payload must be an object")
        if data["role"] != "proposer" and payload:
            raise WorkflowError("Only proposer tasks accept payloads; arbitrary task commands are not supported")
        attempts = _positive_int(data.get("max_attempts", 2), "max_attempts", 100)
        return cls(data["id"], data["role"], tuple(deps), canonical_json(payload), attempts)

    def to_dict(self) -> dict:
        return {"id": self.id, "role": self.role, "dependencies": list(self.dependencies),
                "payload": json.loads(self.payload_json), "max_attempts": self.max_attempts}


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner: str
    token: str
    expires_at: float
    attempt: int


@dataclass(frozen=True)
class Receipt:
    sequence: int
    timestamp: float
    problem_id: str
    task_id: str
    role: str
    event: str
    payload_json: str
    previous_sha256: str
    sha256: str

    @property
    def payload(self) -> dict:
        return json.loads(self.payload_json)

    def to_dict(self) -> dict:
        return {"sequence": self.sequence, "timestamp": self.timestamp, "problem_id": self.problem_id,
                "task_id": self.task_id, "role": self.role, "event": self.event,
                "payload": self.payload, "previous_sha256": self.previous_sha256, "sha256": self.sha256}


class ProposalProvider(Protocol):
    """Future LLM adapters return JSON proposals only, never task success flags.

    Providers run outside the queue lock and must enforce their own I/O timeouts.
    The runtime offers an attempt budget, not a sandbox for untrusted Python plugins.
    """
    def propose(self, problem: dict, task: dict, evidence: tuple[dict, ...]) -> Mapping[str, Any]: ...


class LiteralProposalProvider:
    """Offline fixture provider; no network, credentials, model, shell, or eval."""
    def propose(self, problem: dict, task: dict, evidence: tuple[dict, ...]) -> Mapping[str, Any]:
        return task["payload"]


def validate_receipt_chain(receipts: Any) -> bool:
    """Check exported integrity only. A valid chain is NOT proof or provenance."""
    if not isinstance(receipts, list):
        return False
    previous = "0" * 64
    try:
        for index, receipt in enumerate(receipts, 1):
            fields = {"sequence", "timestamp", "problem_id", "task_id", "role", "event", "payload", "previous_sha256", "sha256"}
            _object(receipt, "receipt", fields)
            body = {k: v for k, v in receipt.items() if k != "sha256"}
            if type(body["sequence"]) is not int or body["sequence"] != index or body["previous_sha256"] != previous:
                return False
            digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
            if receipt["sha256"] != digest:
                return False
            previous = digest
    except (WorkflowError, TypeError, ValueError):
        return False
    return True


class Runtime:
    """Exclusive in-memory leases, bounded attempts, append-only evidence receipts."""
    def __init__(self, problem: Problem, tasks: list[Task], goal_task_id: str,
                 max_total_attempts: int = 20, lease_seconds: float = 30,
                 clock: Callable[[], float] = time.monotonic):
        # Revalidate even programmatically constructed frozen dataclasses.
        self.problem = Problem.from_dict(problem.to_dict())
        self.tasks: dict[str, Task] = {}
        self._state: dict[str, dict] = {}
        self._receipts: list[Receipt] = []
        self._results: dict[str, Receipt] = {}
        self._lock = threading.RLock()
        self._clock = clock
        self.max_total_attempts = _positive_int(max_total_attempts, "max_total_attempts", 10000)
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise WorkflowError("lease_seconds must be finite and positive")
        self.lease_seconds = float(lease_seconds)
        self.total_attempts = 0
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 1000:
            raise WorkflowError("A workflow requires 1–1000 tasks")
        for original in tasks:
            task = Task.from_dict(original.to_dict())
            if task.id in self.tasks:
                raise WorkflowError("Duplicate task identifier")
            if any(dep not in self.tasks for dep in task.dependencies):
                raise WorkflowError("Dependencies must refer to earlier tasks; cycles and missing tasks are invalid")
            self.tasks[task.id] = task
            self._state[task.id] = {"status": "queued", "attempts": 0, "lease": None}
        _id(goal_task_id, "goal_task_id")
        if goal_task_id not in self.tasks or self.tasks[goal_task_id].role != "verifier":
            raise WorkflowError("goal_task_id must name a verifier task")
        self.goal_task_id = goal_task_id

    @classmethod
    def from_dict(cls, value: Any, **kwargs: Any) -> "Runtime":
        data = _object(value, "workflow", {"schema_version", "problem", "tasks", "goal_task_id"}, {"max_total_attempts", "lease_seconds"})
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise WorkflowError("Unsupported workflow schema_version")
        if not isinstance(data["tasks"], list):
            raise WorkflowError("tasks must be a list")
        return cls(Problem.from_dict(data["problem"]), [Task.from_dict(t) for t in data["tasks"]], data["goal_task_id"],
                   data.get("max_total_attempts", 20), data.get("lease_seconds", 30), **kwargs)

    @property
    def receipts(self) -> tuple[Receipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    def _append(self, task: Task, event: str, payload: dict) -> Receipt:
        body = {"sequence": len(self._receipts) + 1, "timestamp": self._clock(), "problem_id": self.problem.id,
                "task_id": task.id, "role": task.role, "event": event, "payload": payload,
                "previous_sha256": self._receipts[-1].sha256 if self._receipts else "0" * 64}
        digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        receipt = Receipt(body["sequence"], body["timestamp"], body["problem_id"], task.id, task.role,
                          event, canonical_json(payload), body["previous_sha256"], digest)
        self._receipts.append(receipt)
        return receipt

    def _refresh(self) -> None:
        now = self._clock()
        for task_id, state in self._state.items():
            task = self.tasks[task_id]
            if state["status"] == "leased" and state["lease"].expires_at <= now:
                state["status"] = "failed" if state["attempts"] >= task.max_attempts else "queued"
                state["lease"] = None
                self._append(task, "lease_expired", {"attempt": state["attempts"], "state": state["status"]})
            if state["status"] == "queued" and any(self._state[d]["status"] in {"rejected", "failed", "blocked"} for d in task.dependencies):
                state["status"] = "blocked"
                self._append(task, "blocked", {"reason": "dependency_failed"})
            if state["status"] == "queued" and self.total_attempts >= self.max_total_attempts:
                state["status"] = "blocked"
                self._append(task, "blocked", {"reason": "attempt_budget_exhausted"})

    def lease_next(self, owner: str, roles: set[str] | None = None) -> Lease | None:
        _id(owner, "owner")
        if roles is not None and (not isinstance(roles, (set, frozenset)) or not roles <= ROLES):
            raise WorkflowError("roles must be a set of recognized roles")
        with self._lock:
            self._refresh()
            for task_id, task in self.tasks.items():
                state = self._state[task_id]
                if state["status"] != "queued" or (roles is not None and task.role not in roles):
                    continue
                if not all(self._state[d]["status"] in SUCCESS_STATES for d in task.dependencies):
                    continue
                state["attempts"] += 1
                self.total_attempts += 1
                lease = Lease(task_id, owner, secrets.token_urlsafe(24), self._clock() + self.lease_seconds, state["attempts"])
                state.update(status="leased", lease=lease)
                self._append(task, "leased", {"owner": owner, "attempt": lease.attempt, "expires_at": lease.expires_at})
                return lease
            return None

    def _check_lease(self, lease: Lease) -> Task:
        self._refresh()
        state = self._state.get(lease.task_id)
        if state is None or state["status"] != "leased" or state["lease"] != lease:
            raise WorkflowError("Lease is stale, expired, or not owned by this worker")
        return self.tasks[lease.task_id]

    def fail(self, lease: Lease, reason: str, retry: bool = True) -> Receipt:
        with self._lock:
            task = self._check_lease(lease)
            state = self._state[task.id]
            status = "queued" if retry and state["attempts"] < task.max_attempts else "failed"
            receipt = self._append(task, "attempt_failed", {"reason": str(reason)[:1000], "state": status})
            state.update(status=status, lease=None)
            return receipt

    def _dependency(self, task: Task, role: str) -> Receipt:
        matches = [self._results[d] for d in task.dependencies if self.tasks[d].role == role and d in self._results]
        if len(matches) != 1:
            raise WorkflowError(f"{task.role} requires exactly one direct {role} dependency")
        return matches[0]

    def execute(self, lease: Lease, provider: ProposalProvider | None = None) -> Receipt:
        """Run a fixed role implementation. There is no 'mark verified' API."""
        with self._lock:
            task = self._check_lease(lease)
            evidence = tuple(self._results[d].to_dict() for d in task.dependencies)
        # Provider and arithmetic calls run without holding the lock. A stale
        # worker cannot publish after its lease expires or is reassigned.
        try:
            status, event, payload = self._dispatch(task, provider or LiteralProposalProvider(), evidence)
        except Exception as exc:
            return self.fail(lease, f"{type(exc).__name__}: {exc}")
        with self._lock:
            self._check_lease(lease)
            try:
                receipt = self._append(task, event, payload)
            except WorkflowError as exc:
                # Expanded polynomial evidence can exceed the queue's receipt
                # budget even when its input fits. Do not publish partial data
                # or leave an uncaught serialization error outside the task loop.
                return self.fail(lease, f"Receipt publication rejected: {exc}")
            self._results[task.id] = receipt
            self._state[task.id].update(status=status, lease=None)
            return receipt

    def _dispatch(self, task: Task, provider: ProposalProvider, evidence: tuple[dict, ...]) -> tuple[str, str, dict]:
        handler = domain_handler(self.problem.domain)
        goal_request = json.loads(self.problem.goal_request_json)
        if task.role == "proposer":
            supplied = provider.propose(self.problem.to_dict(), task.to_dict(), evidence)
            # Round-trip detaches mutable provider objects before validation.
            proposal = json.loads(canonical_json(supplied))
            _object(proposal, "proposal", {"request", "expected"}, {"rationale"})
            if canonical_json(proposal["request"]) != self.problem.goal_request_json:
                raise WorkflowError("Proposal request does not match the structured goal")
            handler.validate_expected(proposal["expected"], goal_request)
            if "rationale" in proposal and not isinstance(proposal["rationale"], str):
                raise WorkflowError("rationale must be text, never executable instructions")
            return "produced", "proposal_recorded", {"trusted": False, "proposal": proposal}
        if task.role == "calculator":
            proposal_receipt = self._dependency(task, "proposer")
            proposal = proposal_receipt.payload["proposal"]
            calculation = handler.calculate(proposal["request"])
            if calculation.get("status") != "success":
                return "failed", "calculation_failed", {"calculation": calculation, "proposal_sha256": proposal_receipt.sha256}
            return "produced", "calculation_recorded", {"calculation": calculation, "proposal_sha256": proposal_receipt.sha256}
        if task.role == "verifier":
            proposal_receipt = self._dependency(task, "proposer")
            calculation_receipt = self._dependency(task, "calculator")
            proposal = proposal_receipt.payload["proposal"]
            prior = calculation_receipt.payload
            if prior.get("proposal_sha256") != proposal_receipt.sha256:
                raise WorkflowError("Calculator evidence belongs to a different proposal")
            # Rebind the proposal even at verification; receipt hashes alone do
            # not establish the goal, ring, or mathematical acceptance.
            if canonical_json(proposal["request"]) != self.problem.goal_request_json:
                raise WorkflowError("Proposal request does not match the structured goal")
            handler.validate_expected(proposal["expected"], goal_request)
            checked = handler.calculate(goal_request)
            if checked.get("status") != "success":
                raise WorkflowError("Exact verifier could not evaluate the structured goal")
            # These local backends produce deterministic receipts. Compare the
            # complete receipt, not only a value or attacker-controlled hashes:
            # original input, normalized request, ordered ring, scope, versions,
            # source hashes, result, and usage must match trusted replay.
            receipt_matches = canonical_json(prior["calculation"]) == canonical_json(checked)
            result_accepted = handler.accepts(proposal["expected"], checked["result"], goal_request)
            exact_passed = receipt_matches and result_accepted
            requirement_satisfied = exact_passed and self.problem.required_evidence == "exact_computation"
            if not exact_passed:
                status = "rejected"
                reason = "receipt_replay_mismatch" if not receipt_matches else "mathematical_acceptance_failed"
            elif not requirement_satisfied:
                status, reason = "blocked", "formal_proof_not_available"
            else:
                status, reason = "verified", None
            return status, "exact_verification", {
                "passed": requirement_satisfied, "exact_check_passed": exact_passed,
                "receipt_replay_matches": receipt_matches, "result_accepted": result_accepted,
                "required_evidence": self.problem.required_evidence,
                "requirement_satisfied": requirement_satisfied,
                "evidence_level": handler.evidence_level, "reason": reason,
                "goal_request_sha256": hashlib.sha256(self.problem.goal_request_json.encode("utf-8")).hexdigest(),
                "acceptance_source_sha256": {
                    name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                    for name in ("orchestrator.py", "domains.py")},
                "domain": self.problem.domain, "ring": checked.get("ring"),
                "result": checked["result"], "expected": proposal["expected"],
                "proposal_sha256": proposal_receipt.sha256, "calculation_sha256": calculation_receipt.sha256,
                "scope": "Exact evaluation of structured goal_request only; natural-language goal and assumptions are not proved.",
                "trust": ["Python interpreter", "fractions.Fraction", "Foundation Math domain calculator and runtime"],
                "independent_backend": False, "informal_correspondence_verified": False, "formal_proof": False}
        if task.role == "critic":
            verification = self._dependency(task, "verifier")
            if verification.event != "exact_verification" or not verification.payload.get("passed"):
                raise WorkflowError("Critic requires satisfied exact-computation verification")
            return "produced", "scope_audit", {"verification_sha256": verification.sha256,
                "findings": ["Recomputation shares the calculator implementation, so it is not independent verification.",
                             "Only the declared structured-domain result was checked; natural-language correspondence and Lean proof remain unchecked."],
                "formal_proof": False}
        return "blocked", "formalization_deferred", {"status": "not_run",
            "reason": "Untrusted task text is not executed as Lean. Use the reviewed-file Lean adapter separately.",
            "formal_proof": False}

    def run(self, provider: ProposalProvider | None = None, owner: str = "local-worker") -> dict:
        while True:
            lease = self.lease_next(owner)
            if lease is None:
                return self.report()
            self.execute(lease, provider)

    def report(self) -> dict:
        with self._lock:
            self._refresh()
            goal_receipt = self._results.get(self.goal_task_id)
            verified = (self.problem.required_evidence == "exact_computation"
                        and self._state[self.goal_task_id]["status"] == "verified"
                        and goal_receipt is not None and goal_receipt.event == "exact_verification"
                        and goal_receipt.payload.get("passed") is True
                        and goal_receipt.payload.get("requirement_satisfied") is True)
            return {"schema_version": 1, "problem": self.problem.to_dict(), "goal_task_id": self.goal_task_id,
                    "goal_status": "exact_result_verified" if verified else "not_verified",
                    "proof_status": "not_formally_verified", "result": goal_receipt.payload["result"] if verified else None,
                    "required_evidence": self.problem.required_evidence,
                    "evidence_requirement_satisfied": verified,
                    "evidence_level": goal_receipt.payload.get("evidence_level") if goal_receipt else None,
                    "informal_correspondence_verified": False,
                    "total_attempts": self.total_attempts, "max_total_attempts": self.max_total_attempts,
                    "tasks": {key: {"role": self.tasks[key].role, "status": state["status"], "attempts": state["attempts"]} for key, state in self._state.items()},
                    "receipt_integrity_only": True, "receipts": [r.to_dict() for r in self._receipts]}

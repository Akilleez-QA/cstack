import fcntl
import hashlib
import json
import os
from pathlib import Path

from poodo_core.models import (CapabilityOutcome, CapabilityRequest, ContractError,
                               DecisionRecord, Document, MAX_DOCUMENT_BYTES, Precommitment,
                               canonical, digest, exact_fields, identifier, outcome_for)
from poodo_core.policy import ApprovalRecord


class DecisionReuseRefused(ContractError):
    """A goal's decision binds one request for the life of this ledger."""


class WitnessChainBroken(RuntimeError):
    """A complete record fails its chain. Nothing is repaired; the host has to look."""


class EndoforgeLedger:
    def __init__(self, path, *, resume=None):
        self.path = Path(path).resolve()
        self._resume = resume
        self.quarantined = []
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._quarantine_torn_tail()
            os.fsync(self._fd)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            self.close()
            raise

    def _quarantine_torn_tail(self):
        """A last line with no newline is a write that was never acknowledged. Keep its bytes aside, and record that."""
        size = os.fstat(self._fd).st_size
        if not size or os.pread(self._fd, 1, size - 1) == b"\n":
            return
        raw = os.pread(self._fd, size, 0)
        tail = raw[raw.rfind(b"\n") + 1:]
        side = self.path.with_name(f"{self.path.name}.torn-{hashlib.sha256(tail).hexdigest()[:16]}")
        fd = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, tail)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.ftruncate(self._fd, size - len(tail))
        self.quarantined.append({"path": str(side), "bytes": len(tail), "sha256": hashlib.sha256(tail).hexdigest()})

    def close(self):
        if self._fd != -1:
            fd, self._fd = self._fd, -1
            os.close(fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def _payload_goal(kind, payload):
        if kind == "precommit":
            exact_fields(payload, {"request", "request_sha256", "grant_id", "precommitment"} |
                         ({"approval"} if "approval" in payload else set()))
            request = CapabilityRequest.from_dict(payload["request"])
            if request.sha256 != payload["request_sha256"]:
                raise ContractError("Request hash mismatch")
            identifier(payload["grant_id"])
            Precommitment(**payload["precommitment"])
            if "approval" in payload:
                approval = ApprovalRecord(**payload["approval"])
                if (approval.decision_id != request.decision_id or approval.request_sha256 != request.sha256
                        or approval.goal_id != request.goal_id or approval.goal_revision != request.goal_revision):
                    raise ContractError("Approval does not bind the precommit")
            return request.goal_id
        if kind == "outcome":
            return CapabilityOutcome.from_dict(payload).to_dict()["goal_id"]
        raise ContractError("Unknown record kind")

    @staticmethod
    def _binding(session_id, payload, request):
        fields = ("request_id", "decision_id", "goal_id", "goal_revision", "capability_id", "operation")
        return (session_id, payload["request_sha256"], *(request[k] for k in fields))

    def _snapshot(self):
        records, bindings, previous = [], set(), None
        try:
            with os.fdopen(os.dup(self._fd), "rb") as stream:
                stream.seek(0)
                while line := stream.readline(MAX_DOCUMENT_BYTES + 2):
                    record = json.loads(line)
                    exact_fields(record, {"schema", "record_id", "previous_id", "kind",
                                          "session_id", "goal_id", "payload"})
                    if line != (canonical(record) + "\n").encode("ascii"):
                        raise ContractError("Invalid record encoding")
                    body = {k: v for k, v in record.items() if k != "record_id"}
                    schema = "0.2" if record["kind"] == "precommit" and "approval" in record["payload"] else "0.1"
                    if (record["schema"] != "poodo.endoforge-record/" + schema or
                            record["previous_id"] != previous or digest(body) != record["record_id"]):
                        raise ContractError("Invalid record chain")
                    identifier(record["session_id"])
                    payload = record["payload"]
                    if self._payload_goal(record["kind"], payload) != identifier(record["goal_id"]):
                        raise ContractError("Record goal mismatch")
                    request = payload["request"] if record["kind"] == "precommit" else payload
                    binding = self._binding(record["session_id"], payload, request)
                    if record["kind"] == "precommit":
                        bindings.add(binding)
                    elif binding not in bindings:
                        raise ContractError("Outcome has no matching precommit")
                    records.append(record)
                    previous = record["record_id"]
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            raise WitnessChainBroken(f"The witness chain is broken at record {len(records) + 1}") from exc
        return records, bindings

    def verify_chain(self) -> bool:
        try:
            self._snapshot()
        except RuntimeError:
            return False
        return True

    def _append(self, session_id, kind, payload):
        try:
            identifier(session_id)
            goal_id = self._payload_goal(kind, payload)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            raise ContractError("Invalid append input") from exc
        records, bindings = self._snapshot()
        if kind == "outcome" and self._binding(session_id, payload, payload) not in bindings:
            raise ContractError("Outcome has no matching precommit")
        schema = "0.2" if kind == "precommit" and "approval" in payload else "0.1"
        body = {"schema": "poodo.endoforge-record/" + schema, "kind": kind,
                "session_id": session_id, "goal_id": goal_id, "payload": payload,
                "previous_id": records[-1]["record_id"] if records else None}
        record_id = digest(body)
        record = Document.capture({**body, "record_id": record_id})
        data = (canonical(record.read()) + "\n").encode("ascii")
        if os.write(self._fd, data) != len(data):
            raise OSError("Incomplete ledger append")
        os.fsync(self._fd)
        return record_id

    def _check_decision_identity(self, session_id, request):
        """Keyed on goal and decision. A different request is always refused. An earlier attempt that may have executed
        needs the host's explicit resume; one with a known outcome, or that never dispatched, may run again."""
        last_certainty = None
        for record in self._snapshot()[0]:
            payload = record["payload"]
            found = payload["request"] if record["kind"] == "precommit" else payload
            if record["goal_id"] != request.goal_id or found["decision_id"] != request.decision_id:
                continue
            if payload["request_sha256"] != request.sha256:
                raise DecisionReuseRefused(f"Decision {request.decision_id} is bound to another request in this ledger")
            if record["kind"] == "outcome" and record["session_id"] != session_id:
                last_certainty = payload["execution_certainty"]
        if last_certainty == "unknown" and self._resume != request.decision_id:
            raise DecisionReuseRefused(f"Decision {request.decision_id} has an unknown outcome; resume it explicitly")

    def append_precommit(self, session_id: str, decision: DecisionRecord) -> str:
        if (type(decision) is not DecisionRecord or type(decision.request) is not CapabilityRequest
                or type(decision.precommitment) is not Precommitment):
            raise ContractError("Expected a decision record")
        self._check_decision_identity(session_id, decision.request)
        try:
            payload = {"request": decision.request.to_dict(), "request_sha256": decision.request_sha256,
                       "grant_id": decision.grant_id, "precommitment": decision.precommitment.to_dict()}
            if decision.approval is not None:
                payload["approval"] = decision.approval.read()
        except (ValueError, TypeError, AttributeError, RecursionError) as exc:
            raise ContractError("Invalid decision") from exc
        return self._append(session_id, "precommit", payload)

    def append_outcome(self, session_id: str, outcome: CapabilityOutcome) -> str:
        if type(outcome) is not CapabilityOutcome:
            raise ContractError("Expected an outcome record")
        try:
            payload = outcome.to_dict()
        except (ValueError, TypeError, AttributeError, RecursionError) as exc:
            raise ContractError("Invalid outcome") from exc
        return self._append(session_id, "outcome", payload)

    def reconcile(self, current_session, resolve=None):
        """Record an earlier session's dispatched attempt with no outcome. Unknown, unless the host's resolve shows durable
        proof of what it did; never inferred from leftovers, and never retried.

        The core witnesses a second precommit only after every execution gate, so that is where execution may have begun.
        A declined approval is a refusal, and a lone precommit was decided but never gated."""
        identifier(current_session)
        records, _ = self._snapshot()
        gated, finished = {}, set()
        for record in records:
            payload = record["payload"]
            if record["session_id"] == current_session:
                continue
            request = payload["request"] if record["kind"] == "precommit" else payload
            key = self._binding(record["session_id"], payload, request)
            if record["kind"] == "outcome":
                finished.add(key)
            elif payload.get("approval", {}).get("verdict", "approve") == "approve":
                gated.setdefault(key, []).append(record)
        reconciled = []
        for key, seen in gated.items():
            if key in finished or len(seen) < 2:
                continue
            request = CapabilityRequest.from_dict(seen[-1]["payload"]["request"])
            attempt_id, known = resolve(request, seen[-1]["session_id"]) if resolve else ("attempt-unknown", None)
            outcome = known or outcome_for(request, attempt_id, "indeterminate", "process_ended_before_outcome", certainty="unknown",
                                           limitations=("No automatic retry; execution may have occurred.",))
            self.append_outcome(seen[-1]["session_id"], outcome)
            reconciled.append({"session_id": seen[-1]["session_id"], "decision_id": request.decision_id, "goal_id": request.goal_id,
                               "request_sha256": request.sha256, "status": known.to_dict()["assessment"] if known else "outcome_unknown"})
        return tuple(reconciled)

    def read_records(self, *, goal_id: str | None = None,
                     session_id: str | None = None) -> tuple[Document, ...]:
        if goal_id is None and session_id is None:
            raise ContractError("A goal or session filter is required")
        for value in (goal_id, session_id):
            if value is not None:
                identifier(value)
        records, _ = self._snapshot()
        return tuple(Document.capture(r) for r in records
                     if (goal_id is None or r["goal_id"] == goal_id) and
                     (session_id is None or r["session_id"] == session_id))

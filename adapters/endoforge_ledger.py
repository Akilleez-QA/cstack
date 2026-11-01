import fcntl
import json
import os
from pathlib import Path

from poodo_core.models import (CapabilityOutcome, CapabilityRequest, ContractError,
                               DecisionRecord, Document, MAX_DOCUMENT_BYTES, Precommitment,
                               canonical, digest, exact_fields, identifier)
from poodo_core.policy import ApprovalRecord


class EndoforgeLedger:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fsync(self._fd)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            self.close()
            raise

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
            raise RuntimeError("Invalid ledger chain") from exc
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

    def append_precommit(self, session_id: str, decision: DecisionRecord) -> str:
        if (type(decision) is not DecisionRecord or type(decision.request) is not CapabilityRequest
                or type(decision.precommitment) is not Precommitment):
            raise ContractError("Expected a decision record")
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

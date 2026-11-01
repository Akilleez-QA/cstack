import inspect
import unittest

from poodo_core.models import (CapabilityOutcome, ContractError, DecisionRecord, Document,
                               digest, identifier, outcome_for)
from poodo_core.ports import EndoforgePort
from tests.helpers import precommit, request


class InMemoryEndoforge:
    def __init__(self):
        self.records = []

    def append_precommit(self, session_id: str, decision: DecisionRecord) -> str:
        if decision.request_sha256 != decision.request.sha256:
            raise ContractError("Request hash mismatch")
        identifier(decision.grant_id)
        return self._append(session_id, decision.request.goal_id, "precommit", {
            "request": decision.request.to_dict(), "request_sha256": decision.request_sha256,
            "grant_id": decision.grant_id, "precommitment": decision.precommitment.to_dict()})

    def append_outcome(self, session_id: str, outcome: CapabilityOutcome) -> str:
        self._require_valid_chain()
        payload = outcome.to_dict()
        fields = ("request_id", "decision_id", "goal_id", "goal_revision", "capability_id", "operation")
        matches = [r.read()["payload"] for r in self.records
                   if r.read()["kind"] == "precommit" and r.read()["session_id"] == session_id]
        if not any(p["request_sha256"] == payload["request_sha256"] and
                   all(p["request"][k] == payload[k] for k in fields) for p in matches):
            raise ContractError("Outcome has no matching precommit")
        return self._append(session_id, payload["goal_id"], "outcome", payload)

    def _append(self, session_id, goal_id, kind, payload):
        self._require_valid_chain()
        body = {"schema": "poodo.endoforge-record/0.1", "kind": kind,
                "session_id": identifier(session_id), "goal_id": identifier(goal_id),
                "previous_id": self.records[-1].read()["record_id"] if self.records else None,
                "payload": payload}
        record_id = digest(body)
        self.records.append(Document.capture({**body, "record_id": record_id}))
        return record_id

    def verify_chain(self) -> bool:
        previous = None
        for document in self.records:
            body = document.read()
            record_id = body.pop("record_id")
            if body["previous_id"] != previous or digest(body) != record_id:
                return False
            previous = record_id
        return True

    def _require_valid_chain(self):
        if not self.verify_chain():
            raise RuntimeError("Invalid ledger chain")

    def read_records(self, *, goal_id: str | None = None,
                     session_id: str | None = None) -> tuple[Document, ...]:
        if goal_id is None and session_id is None:
            raise ContractError("A goal or session filter is required")
        for value in (goal_id, session_id):
            if value is not None:
                identifier(value)
        self._require_valid_chain()
        return tuple(r for r in self.records
                     if (goal_id is None or r.read()["goal_id"] == goal_id) and
                     (session_id is None or r.read()["session_id"] == session_id))


class EndoforgePortTests(unittest.TestCase):
    def setUp(self):
        self.fake = InMemoryEndoforge()
        self.port: EndoforgePort = self.fake
        self.request = request()
        self.decision = DecisionRecord(self.request, self.request.sha256, "grant", precommit())
        self.outcome = outcome_for(self.request, "attempt", "completed", "observed",
                                   certainty="responded", raw_result={"value": 1})

    def test_protocol_surface(self):
        self.assertIsInstance(self.fake, EndoforgePort)
        self.assertNotIsInstance(object(), EndoforgePort)
        methods = {name for name in vars(EndoforgePort) if not name.startswith("_")}
        self.assertEqual(methods, {"append_precommit", "append_outcome", "verify_chain", "read_records"})
        for name in methods:
            self.assertEqual(inspect.signature(getattr(EndoforgePort, name)),
                             inspect.signature(getattr(InMemoryEndoforge, name)))

    def test_append_and_filter_preserve_evidence(self):
        self.assertTrue(self.port.verify_chain())
        first = self.port.append_precommit("s1", self.decision)
        second = self.port.append_outcome("s1", self.outcome)
        self.port.append_precommit("s2", self.decision)
        other = request(goal_id="other")
        self.port.append_precommit("s1", DecisionRecord(other, other.sha256, "grant", precommit()))
        records = self.port.read_records(goal_id="g", session_id="s1")
        self.assertEqual([r.read()["record_id"] for r in records], [first, second])
        for record_id in (first, second):
            self.assertRegex(record_id, r"^[0-9a-f]{64}$")
        self.assertIsNone(records[0].read()["previous_id"])
        self.assertEqual(records[1].read()["previous_id"], first)
        self.assertEqual(records[0].read()["payload"], {
            "request": self.request.to_dict(), "request_sha256": self.request.sha256,
            "grant_id": "grant", "precommitment": precommit().to_dict()})
        self.assertEqual(records[1].read()["payload"], self.outcome.to_dict())
        detached = records[1].read()
        detached["payload"]["raw_result"]["value"] = 9
        self.assertEqual(records[1].read()["payload"]["raw_result"], {"value": 1})
        self.assertEqual(len(self.port.read_records(goal_id="g")), 3)
        self.assertEqual(len(self.port.read_records(session_id="s1")), 3)
        self.assertEqual(self.port.read_records(goal_id="missing"), ())
        self.assertTrue(self.port.verify_chain())

    def test_reject_unbound_or_invalid_input(self):
        with self.assertRaises(ContractError):
            self.port.append_outcome("s1", self.outcome)
        with self.assertRaises(ContractError):
            self.port.append_precommit("bad session", self.decision)
        with self.assertRaises(ContractError):
            self.port.append_precommit("s1", DecisionRecord(self.request, "0" * 64, "grant", precommit()))
        self.assertEqual(self.fake.records, [])
        self.port.append_precommit("s1", self.decision)
        with self.assertRaises(ContractError):
            self.port.append_outcome("s2", self.outcome)
        changed = self.outcome.to_dict()
        changed["goal_revision"] = 2
        with self.assertRaises(ContractError):
            self.port.append_outcome("s1", CapabilityOutcome.from_dict(changed))
        with self.assertRaises(ContractError):
            self.port.read_records()
        self.assertEqual(len(self.fake.records), 1)

    def test_corruption_fails_closed(self):
        for field, value in (("session_id", "changed"), ("previous_id", "0" * 64)):
            with self.subTest(field=field):
                self.fake.records = []
                self.port.append_precommit("s1", self.decision)
                body = self.fake.records[0].read()
                body[field] = value
                self.fake.records[0] = Document.capture(body)
                self.assertFalse(self.port.verify_chain())
                with self.assertRaises(RuntimeError):
                    self.port.read_records(goal_id="missing")
                with self.assertRaises(RuntimeError):
                    self.port.append_precommit("s1", self.decision)
                with self.assertRaises(RuntimeError):
                    self.port.append_outcome("s1", self.outcome)
                self.assertEqual(len(self.fake.records), 1)

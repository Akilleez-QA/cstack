"""PR #57 review regressions: store isolation, ownership and session serialization."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
import unittest

from adapters.aor_session import LedgerStoreClaim
from adapters.approval_store import ApprovalWriter
from bootstrap import build_aor_session
from poodo_core import ApprovalRecord, ContractError
from tests.aor_fixtures import DOMAIN, HAVE_CRYPTO, NO_CRYPTO, APPROVER, write_fleet, write_witnessed_config
from tests.test_aor_session import SessionCase


class SessionSerializationTests(SessionCase):
    def test_concurrent_goal_writes_have_unique_ids_and_contiguous_events(self):
        session = self.open()
        def write(i):
            goal = session.start_goal(DOMAIN, f"Observe fixture {i}.", ["Scoped observation."])
            session.ledger()  # readers must use the same lock as writers
            return goal["contract"]["goal_id"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(write, range(24)))
        self.assertEqual(len(set(ids)), 24)
        events = session.ledger(DOMAIN, last=50)["events"]
        self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))

    def test_every_public_call_waits_for_the_session_lock(self):
        # Include invalid calls: validation and refusal must be serialized too.
        calls = [lambda s: s.aor(), lambda s: s.shields_up(), lambda s: s.ledger(),
                 lambda s: s.start_goal(DOMAIN, "Observe.", ["Evidence."]),
                 lambda s: s.advance(DOMAIN, "absent", "observe", "Checkpoint."),
                 lambda s: s.decide(DOMAIN, "absent", "echo_observation", {}, "x", "y", "z"),
                 lambda s: s.execute(DOMAIN, "absent"), lambda s: s.close()]
        for call in calls:
            with self.subTest(call=call):
                session = self.open()
                started, finished = Event(), Event()
                def invoke():
                    started.set()
                    try:
                        call(session)
                    except ContractError:
                        pass
                    finally:
                        finished.set()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with session._lock:
                        future = pool.submit(invoke)
                        self.assertTrue(started.wait(2))
                        self.assertFalse(finished.wait(.05))
                    future.result(timeout=5)
                session.close()

    def test_ask_approval_lookup_and_consume_can_run_on_a_worker_thread(self):
        session = self.open(write_fleet(self.dir, alpha_read="ask"))
        goal_id, decision = self.run_to_execute(session)
        writer = ApprovalWriter(self.state / "approvals.db", clock=lambda: 1000)
        try:
            writer.record(ApprovalRecord("approval-thread", decision["decision_id"], decision["request_sha256"],
                                         goal_id, 1, APPROVER, "approved", 2**40))
        finally:
            writer.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(session.execute, DOMAIN, decision["decision_id"]).result(timeout=15)
        self.assertEqual(result["status"], "executed")


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class SessionStoreTests(SessionCase):
    def setUp(self):
        super().setUp()
        self.base_log = write_witnessed_config(self.state)

    def path(self, domain):
        return self.base_log.with_suffix("") / "alpha" / f"{domain}.jsonl"

    def test_domain_stores_and_core_ledgers_are_separate(self):
        session = self.open()
        for domain in ("foundation_math", DOMAIN):
            session.start_goal(domain, f"Observe {domain}.", ["Scoped observation."])
        self.assertFalse(self.base_log.exists())
        self.assertNotEqual(self.path(DOMAIN), self.path("foundation_math"))
        for domain in ("foundation_math", DOMAIN):
            events = session._cores[domain].ledger()
            entries = [json.loads(line) for line in self.path(domain).read_text().splitlines()]
            self.assertEqual(events, [json.loads(e["body"]["event_json"]) for e in entries])
            self.assertEqual({e["body"]["stream"] for e in entries}, {f"alpha.{domain}"})
            self.assertTrue(all(e["data"]["snapshot"]["contract"]["domain_id"] == domain
                                for e in events if e["kind"] == "proposal"))
        anchors = json.loads((self.state / "alpha/anchors.json").read_text())
        for domain in ("foundation_math", DOMAIN):
            self.assertEqual(anchors[f"alpha.{domain}"], session.ledger(domain)["head"])

    def test_second_session_refused_until_close_and_reopens_at_domain_anchor(self):
        first = self.open()
        first.start_goal(DOMAIN, "Observe.", ["Evidence."])
        head = first.ledger(DOMAIN)["head"]
        with self.assertRaisesRegex(ContractError, "already has a live owner"):
            self.open()
        first.close()
        second = self.open()
        self.assertEqual(second.ledger(DOMAIN)["head"], head)
        first.close()  # idempotent; must not release the second session's claim
        with self.assertRaises(ContractError):
            self.open()

    def test_another_process_cannot_open_the_same_bot_and_domain(self):
        first = self.open()
        code = '''import sys
from bootstrap import build_aor_session
from poodo_core import ContractError
try:
    s = build_aor_session("alpha", state_root=sys.argv[1], hostname="testbox", fleet_path=sys.argv[2])
except ContractError as error:
    print(error)
    sys.exit(3)
s.close()
'''
        def attempt():
            return subprocess.run([sys.executable, "-B", "-c", code, str(self.state), str(self.dir / "fleet.json")],
                                  capture_output=True, text=True, timeout=15)
        refused = attempt()
        self.assertEqual(refused.returncode, 3, refused.stderr)
        self.assertIn("already has a live owner", refused.stdout)
        first.close()
        accepted = attempt()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_domain_store_tamper_and_truncation_are_refused(self):
        session = self.open()
        self.run_to_execute(session)
        session.close()
        path = self.path(DOMAIN)
        original = path.read_text()
        variants = [(original.replace("Fixture", "Forged"), "verification"),
                    ("\n".join(original.splitlines()[:-1]) + "\n", "truncated")]
        for changed, message in variants:
            with self.subTest(message=message):
                path.write_text(changed)
                with self.assertRaisesRegex(ContractError, message):
                    self.open()
                path.write_text(original)

    def test_partial_build_failure_releases_previously_opened_domain(self):
        claim = LedgerStoreClaim(self.path(DOMAIN))
        try:
            with self.assertRaises(ContractError):
                self.open()
        finally:
            claim.close()
        self.open().close()


class StoreClaimTests(unittest.TestCase):
    def test_process_registry_refuses_resolved_alias_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "domain.jsonl"
            first = LedgerStoreClaim(path)
            try:
                with self.assertRaisesRegex(ContractError, "live owner"):
                    LedgerStoreClaim(path.parent / "." / path.name)
            finally:
                first.close()
            LedgerStoreClaim(path).close()


if __name__ == "__main__":
    unittest.main()

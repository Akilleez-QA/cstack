"""Second review of PR 525: the ledger, not this boot's memory, says which attempts are unresolved.

Predictions: tests/crash_predictions/poodo_core.md
"""
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from poodo_core.policy import AuthorityGrant, CostBudget
from tests.aor_fixtures import HAVE_CRYPTO, write_witnessed_config
from tests.helpers import FAKE_CAP, FakeExtension, PoodoCore, execute_one, request
from tests.test_core_crash import FixedCost, JsonlLedger, build

ROOT = Path(__file__).resolve().parents[1]
FIRST_KILL = """
import sys
sys.path.insert(0, ".")
from tests.test_core_crash import build, drive
core, ledger = build(sys.argv[1], sys.argv[2], kill_at="after_effect", budgeted=True)
drive(core)
"""
SECOND_OPEN_ATTEMPT = """
import sys
sys.path.insert(0, ".")
from poodo_core import core as module
from tests.helpers import execute_one, request
from tests.test_core_crash import build
module.PoodoCore._recover = lambda self: None
core, ledger = build(sys.argv[1], sys.argv[2], kill_at="after_effect", budgeted=True)
core._attempt_number = 1
execute_one(core, request(i=2))
"""
PATCH = """
import os, signal, sys
sys.path.insert(0, ".")
from adapters.witnessed_ledger import WitnessedLedger
from tests.test_core_crash import JsonlLedger, build
from tests.test_core_unresolved import failing_core
root, kind, target, when = sys.argv[1:5]
for cls in (JsonlLedger, WitnessedLedger):
    def append(self, event_kind, data, _original=cls.append):
        hit = target in (event_kind, data.get("action"))
        if hit and when == "before":
            os.kill(os.getpid(), signal.SIGKILL)
        event = _original(self, event_kind, data)
        if hit and when == "after":
            os.kill(os.getpid(), signal.SIGKILL)
        return event
    cls.append = append
"""
KILL_DURING_RECOVERY = PATCH + """
build(root, kind, budgeted=True)
"""
KILL_AFTER_ADAPTER_FAILURE = PATCH + """
from tests.helpers import execute_one, request
execute_one(failing_core(root), request(i=1))
"""


class Raises:
    def describe(self):
        return FAKE_CAP

    def invoke(self, req, attempt_id, cancellation=None):
        raise RuntimeError("adapter failed")


def failing_core(root):
    grant = AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 3, lane="ToolFace",
                           aor_id="aor-a")
    return PoodoCore(FakeExtension(), {"synthetic_sensor": Raises()}, (grant,), JsonlLedger(Path(root) / "ledger.jsonl"),
                     budgets=(CostBudget("aor-a", 100, "usd_cents"),), costs=FixedCost())


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def child(self, code, *args):
        done = subprocess.run([sys.executable, "-B", "-c", code, str(self.root), *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(done.returncode, -signal.SIGKILL, done.stderr)

    def first_kill(self, kind="jsonl"):
        if kind == "witnessed":
            write_witnessed_config(self.root, node="box")
        self.child(FIRST_KILL, kind)

    def effects(self):
        path = self.root / "effects.txt"
        return path.read_text().split() if path.exists() else []

    def assert_listed_across_restarts(self, kind, attempts, spent):
        for _ in range(3):
            core, ledger = build(self.root, kind, budgeted=True)
            events = ledger.read()
            self.assertEqual([u["attempt_id"] for u in core.unresolved_attempts()], attempts)
            self.assertEqual(sum(e["kind"] == "outcome" for e in events), len(attempts))
            self.assertEqual(sum(e["data"].get("action") == "budget_settled" for e in events), len(attempts))
            self.assertEqual((core.budget("aor-a")["spent"], core.budget("aor-a")["held"]), (spent, 0))
            self.assertEqual(len(self.effects()), len(attempts))
            if kind == "witnessed":
                ledger.close()


class Restarts(Case):
    def test_a_plain_second_restart_still_lists_the_attempt(self):
        self.first_kill()
        self.assert_listed_across_restarts("jsonl", ["attempt-1"], 7)

    def test_the_row_keeps_its_identities_across_restarts(self):
        self.first_kill()
        first = build(self.root, "jsonl", budgeted=True)[0].unresolved_attempts()
        again = build(self.root, "jsonl", budgeted=True)[0].unresolved_attempts()
        self.assertEqual(first, again)
        self.assertEqual(sorted(first[0]), ["attempt_id", "decision_id", "goal_id", "request_sha256"])
        self.assertEqual((first[0]["decision_id"], first[0]["request_sha256"], first[0]["goal_id"]),
                         (request(i=1).decision_id, request(i=1).sha256, "g"))

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_a_witnessed_second_restart_still_lists_the_attempt(self):
        self.first_kill("witnessed")
        self.assert_listed_across_restarts("witnessed", ["attempt-1"], 7)

    def test_a_returned_answer_is_never_listed(self):
        first, _ = build(self.root, "jsonl", budgeted=True)
        execute_one(first, request(i=1))
        self.assertEqual(first.unresolved_attempts(), ())
        self.assertEqual(build(self.root, "jsonl", budgeted=True)[0].unresolved_attempts(), ())


class KillDuringRecovery(Case):
    def kill_recovery(self, kind, target, when):
        self.first_kill(kind)
        self.child(KILL_DURING_RECOVERY, kind, target, when)
        self.assert_listed_across_restarts(kind, ["attempt-1"], 7)

    def test_before_the_unknown_outcome(self):
        self.kill_recovery("jsonl", "outcome", "before")

    def test_after_the_unknown_outcome(self):
        self.kill_recovery("jsonl", "outcome", "after")

    def test_before_settlement(self):
        self.kill_recovery("jsonl", "budget_settled", "before")

    def test_after_settlement(self):
        self.kill_recovery("jsonl", "budget_settled", "after")

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_witnessed_after_the_unknown_outcome(self):
        self.kill_recovery("witnessed", "outcome", "after")

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_witnessed_after_settlement(self):
        self.kill_recovery("witnessed", "budget_settled", "after")

    def test_two_open_attempts_killed_after_the_first_unknown(self):
        self.first_kill()
        self.child(SECOND_OPEN_ATTEMPT, "jsonl")
        self.child(KILL_DURING_RECOVERY, "jsonl", "outcome", "after")
        self.assert_listed_across_restarts("jsonl", ["attempt-1", "attempt-2"], 14)


class AdapterFailure(Case):
    def test_the_core_that_recorded_it_lists_it(self):
        core = failing_core(self.root)
        execute_one(core, request(i=1))
        self.assertEqual([u["attempt_id"] for u in core.unresolved_attempts()], ["attempt-1"])

    def test_a_restart_lists_it(self):
        execute_one(failing_core(self.root), request(i=1))
        self.assertEqual([u["attempt_id"] for u in failing_core(self.root).unresolved_attempts()], ["attempt-1"])

    def test_a_kill_before_settlement_lists_it_and_settles_once(self):
        self.child(KILL_AFTER_ADAPTER_FAILURE, "jsonl", "outcome", "after")
        for _ in range(3):
            core = failing_core(self.root)
            self.assertEqual([u["attempt_id"] for u in core.unresolved_attempts()], ["attempt-1"])
            self.assertEqual(core.budget("aor-a")["spent"], 7)
            self.assertEqual(sum(e["data"].get("action") == "budget_settled" for e in core.ledger()), 1)


if __name__ == "__main__":
    unittest.main()

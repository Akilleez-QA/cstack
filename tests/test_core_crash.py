"""Real SIGKILL inside a capability, then a new core on the same durable ledger.

Predictions: tests/crash_predictions/poodo_core.md
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from adapters.memory_ledger import MemoryLedger
from poodo_core import ContractError, Phase, PhaseCheckpoint
from poodo_core.models import canonical, digest
from poodo_core.policy import AuthorityGrant, CostBudget
from tests.aor_fixtures import HAVE_CRYPTO, write_witnessed_config
from tests.helpers import FAKE_CAP, FakeExtension, execute_one, goal, outcome_for, PoodoCore, precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
CHILD = """
import os, signal, sys
sys.path.insert(0, ".")
from tests.test_core_crash import build, drive
root, kind, point = sys.argv[1:4]
if kind == "witnessed-enforce":
    from adapters.witnessed_ledger import ledger_lib
    ledger_lib().Log.witnessed_size = lambda self: 10 ** 9
core, ledger = build(root, kind, kill_at=point)
try:
    drive(core)
finally:
    if point == "after_outcome":
        os.kill(os.getpid(), signal.SIGKILL)
"""


class JsonlLedger(MemoryLedger):
    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        self.saved = [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []

    def read(self):
        return list(self.saved)

    def append(self, kind, data):
        frame = {"sequence": len(self.saved) + 1, "kind": kind, "data": data,
                 "prior_event_sha256": self.saved[-1]["event_sha256"] if self.saved else None}
        event = json.loads(canonical({**frame, "event_sha256": digest(frame)}))
        with self.path.open("a") as stream:
            stream.write(json.dumps(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.saved.append(event)
        return event


class EffectCapability:
    def __init__(self, root, kill_at=None):
        self.root, self.kill_at = Path(root), kill_at

    def describe(self):
        return FAKE_CAP

    def invoke(self, req, attempt_id, cancellation=None):
        if self.kill_at == "before_effect":
            os.kill(os.getpid(), signal.SIGKILL)
        with (self.root / "effects.txt").open("a") as stream:
            stream.write(attempt_id + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if self.kill_at == "after_effect":
            os.kill(os.getpid(), signal.SIGKILL)
        return outcome_for(req, attempt_id, "completed", "sensor_returned", certainty="responded", raw_result={"ok": 1})


class FixedCost:
    def estimate(self, req):
        return 7

    def actual(self, req, attempt_id, outcome):
        return None if outcome.to_dict()["execution_certainty"] == "unknown" else 5


def make_ledger(root, kind):
    root = Path(root)
    if kind == "jsonl":
        return JsonlLedger(root / "ledger.jsonl")
    from adapters.witnessed_ledger import WitnessedLedger
    node = json.loads((root / "ledger.json").read_text())
    return WitnessedLedger(root / node["log"], node["node"], root / node["roster"], "alpha", root / "ledger/alpha.key",
                           stream="alpha.fake", enforce=kind == "witnessed-enforce")


def build(root, kind, kill_at=None, budgeted=False):
    ledger = make_ledger(root, kind)
    aor = "aor-a" if budgeted else None
    grant = AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 3, lane="ToolFace",
                           aor_id=aor)
    extra = {"budgets": (CostBudget(aor, 100, "usd_cents"),), "costs": FixedCost()} if budgeted else {}
    return PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(root, kill_at)}, (grant,), ledger, **extra), ledger


def drive(core):
    return execute_one(core, request(i=1))


class CrashWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def effects(self):
        path = self.root / "effects.txt"
        return path.read_text().split() if path.exists() else []

    def crash(self, kind, point):
        if kind.startswith("witnessed"):
            write_witnessed_config(self.root, node="box")
        done = subprocess.run([sys.executable, "-B", "-c", CHILD, str(self.root), kind, point], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, -signal.SIGKILL, done.stderr)

    def assert_unknown_after_restart(self, kind, effects):
        core, ledger = build(self.root, kind)
        outcomes = [e["data"]["outcome"] for e in ledger.read() if e["kind"] == "outcome"]
        self.assertEqual(len(outcomes), 1)
        self.assertEqual((outcomes[0]["execution_status"], outcomes[0]["execution_certainty"]), ("indeterminate", "unknown"))
        self.assertEqual([u["attempt_id"] for u in core.unresolved_attempts()], ["attempt-1"])
        self.assertEqual(len(self.effects()), effects)
        return core, ledger

    def test_kill_before_effect_records_unknown_on_restart(self):
        self.crash("jsonl", "before_effect")
        self.assert_unknown_after_restart("jsonl", 0)

    def test_kill_after_effect_records_unknown_on_restart(self):
        self.crash("jsonl", "after_effect")
        self.assert_unknown_after_restart("jsonl", 1)

    def test_kill_after_effect_refuses_the_same_identities_on_restart(self):
        self.crash("jsonl", "after_effect")
        core, ledger = self.assert_unknown_after_restart("jsonl", 1)
        to_decide(core)
        with self.assertRaisesRegex(ContractError, "must be new"):
            core.decide(request(i=1), precommit())
        self.assertEqual(len(self.effects()), 1)

    def test_a_new_identity_after_restart_gets_a_new_attempt_id(self):
        self.crash("jsonl", "after_effect")
        core, ledger = self.assert_unknown_after_restart("jsonl", 1)
        self.assertEqual(execute_one(core, request(i=2)).to_dict()["attempt_id"], "attempt-2")

    def test_second_restart_does_not_add_another_unknown(self):
        self.crash("jsonl", "after_effect")
        self.assert_unknown_after_restart("jsonl", 1)
        core, ledger = build(self.root, "jsonl")
        self.assertEqual(sum(e["kind"] == "outcome" for e in ledger.read()), 1)
        self.assertEqual([u["attempt_id"] for u in core.unresolved_attempts()], ["attempt-1"])

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_witnessed_kill_after_effect_writes_a_result_on_the_original_intent(self):
        self.crash("witnessed", "after_effect")
        core, ledger = self.assert_unknown_after_restart("witnessed", 1)
        log = ledger.verified_log()
        intent = next(e for e in log.entries if e["kind"] == "intent")
        results = [e for e in log.entries if e["kind"] == "result"]
        self.assertEqual([(e["ref"], e["body"]["outcome"]) for e in results], [(intent["hash"], "unknown")])
        ledger.close()

    @unittest.skipUnless(HAVE_CRYPTO, "needs cryptography")
    def test_witnessed_enforced_restart_cannot_rerun_the_identities(self):
        self.crash("witnessed-enforce", "after_effect")
        from adapters.witnessed_ledger import ledger_lib
        with mock.patch.object(ledger_lib().Log, "witnessed_size", lambda log: 10 ** 9):
            core, ledger = self.assert_unknown_after_restart("witnessed-enforce", 1)
            to_decide(core)
            with self.assertRaisesRegex(ContractError, "must be new"):
                core.decide(request(i=1), precommit())
            ledger.close()

    def test_budget_keeps_the_whole_hold_of_an_unknown_attempt(self):
        code = CHILD.replace('build(root, kind, kill_at=point)', 'build(root, kind, kill_at=point, budgeted=True)')
        done = subprocess.run([sys.executable, "-B", "-c", code, str(self.root), "jsonl", "after_effect"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, -signal.SIGKILL, done.stderr)
        core, ledger = build(self.root, "jsonl", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 7)
        self.assertEqual(core.budget("aor-a")["held"], 0)
        self.assertEqual([e["data"]["priced"] for e in ledger.read() if e["data"].get("action") == "budget_settled"], [False])

    def test_budget_spend_survives_a_restart(self):
        ledger = JsonlLedger(self.root / "ledger.jsonl")
        first = PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)},
                          (AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 3,
                                          lane="ToolFace", aor_id="aor-a"),), ledger,
                          budgets=(CostBudget("aor-a", 100, "usd_cents"),), costs=FixedCost())
        execute_one(first, request(i=1))
        self.assertEqual(first.budget("aor-a")["spent"], 5)
        core, _ = build(self.root, "jsonl", budgeted=True)
        self.assertEqual(core.budget("aor-a")["spent"], 5)

    def test_grant_uses_survive_a_restart(self):
        ledger = JsonlLedger(self.root / "ledger.jsonl")
        first, _ = build(self.root, "jsonl")
        execute_one(first, request(i=1))
        core, _ = build(self.root, "jsonl")
        self.assertEqual(core._grant_uses["fake-grant"], 1)

    def test_a_ledger_that_cannot_be_read_refuses_the_core(self):
        class Broken(MemoryLedger):
            def read(self):
                raise OSError("disk")
        with self.assertRaises(OSError):
            PoodoCore(FakeExtension(), {"synthetic_sensor": EffectCapability(self.root)},
                      (AuthorityGrant("fake-grant", "synthetic_sensor", "synthetic_sensor", ("reading",), ("g",), 3,
                                      lane="ToolFace"),), Broken())

    def test_empty_ledger_appends_nothing(self):
        core, ledger = build(self.root, "jsonl")
        self.assertEqual(ledger.read(), [])
        self.assertEqual(core.unresolved_attempts(), ())


if __name__ == "__main__":
    unittest.main()

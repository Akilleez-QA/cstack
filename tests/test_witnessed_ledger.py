"""WitnessedLedger: POODO through the ADR 004 witnessed ledger. Skips cleanly without `cryptography`."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from poodo_core import *
from adapters.witnessed_ledger import WitnessedLedger, ledger_lib
from tests.helpers import *

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
SKIP = "WitnessedLedger tests need 'cryptography' (ADR 004 open question 3): uv run --with cryptography ..."
WITNESSES = ("example-host", "example-peer", "pi")
UNREACHABLE = "http://127.0.0.1:9"


@unittest.skipUnless(HAVE_CRYPTO, SKIP)
class WitnessedLedgerTest(unittest.TestCase):
    def setUp(self):
        self.L = L = ledger_lib()
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.k = {n: L.Ed25519PrivateKey.generate() for n in ("poodo-bot", "ops", *WITNESSES)}
        roster = {"quorum": 2, "witnesses": {n: L.pub_hex(self.k[n]) for n in WITNESSES},
                  "writers": {"poodo-bot": {"pub": L.pub_hex(self.k["poodo-bot"]), "node": "example-host"},
                              "ops": {"pub": L.pub_hex(self.k["ops"]), "node": "example-host"}}}
        self.roster = self.d / "roster.json"
        self.roster.write_text(json.dumps(roster))
        self.key = self.d / "poodo-bot.key"
        L.save_key(self.k["poodo-bot"], str(self.key))
        self.path = self.d / "example-host.jsonl"

    def ledger(self, stream="poodo.math", **kw):
        wl = WitnessedLedger(self.path, "example-host", self.roster, "poodo-bot", self.key, stream=stream, **kw)
        self.addCleanup(wl.close)
        return wl

    def log(self):
        return self.L.Log(str(self.path), "example-host", self.L.load_roster(str(self.roster)))

    def entries(self, kind):
        return [e for e in self.log().entries if e["kind"] == kind]

    def spawn(self, name):
        kp = self.d / (name + ".key")
        self.L.save_key(self.k[name], str(kp))
        proc = subprocess.Popen([sys.executable, "-B", str(Path(self.L.__file__)), "serve", "--name", name,
                                 "--key", str(kp), "--roster", str(self.roster), "--dir", str(self.d / ("w-" + name)),
                                 "--host", "127.0.0.1", "--allow-loopback"],
                                stdout=subprocess.PIPE, text=True)
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.terminate)
        return f"http://127.0.0.1:{int(proc.stdout.readline())}"

    def ready(self, enforce, capability=None):
        core = FakeFoundation(capability, ledger=self.ledger(enforce=enforce))
        to_decide(core)
        core.decide(request(), precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
        return core

    def test_full_goal_through_core(self):
        core = FakeFoundation(ledger=self.ledger())
        self.assertEqual(execute_one(core).to_dict()["execution_status"], "completed")
        events = core.ledger()
        self.assertEqual([e["kind"] for e in events],
                         ["proposal"] + ["decision"] * 5 + ["action", "outcome"])
        prior = None
        for i, e in enumerate(events, 1):
            self.assertEqual(set(e), {"sequence", "kind", "data", "prior_event_sha256", "event_sha256"})
            self.assertEqual((e["sequence"], e["prior_event_sha256"]), (i, prior))
            prior = e["event_sha256"]
        [intent], [result] = self.entries("intent"), self.entries("result")
        self.assertEqual(intent["body"]["digest"], request().sha256)
        self.assertEqual((result["ref"], result["body"]["outcome"]), (intent["hash"], "applied"))
        [claim] = self.entries("claim")
        self.assertEqual((claim["ref"], claim["body"]["digest"]), (intent["hash"], intent["body"]["digest"]))
        self.assertEqual(len(self.entries("note")), 5)
        self.assertEqual({e["body"]["stream"] for e in self.log().entries}, {"poodo.math"})
        core._ledger.close()
        self.assertEqual(self.ledger().read(), events)  # survives a restart, verified on open

    def test_enforced_without_quorum_denies_and_dispatches_nothing(self):
        core = self.ready(True)
        with self.assertRaisesRegex(ContractError, "not-witnessed"):
            core.execute("d-1")
        self.assertEqual(core.fake.calls, [])
        self.assertNotIn("action", [e["kind"] for e in core.ledger()])
        denied = [e for e in self.entries("note") if "poodo_denied" in e["body"]]
        self.assertEqual(denied[0]["body"]["poodo_denied"]["decision_id"], "d-1")
        self.assertIsNone(self.L.reconcile(self.log(), [self.spawn("example-peer"), UNREACHABLE]))  # one witness: below quorum
        with self.assertRaises(ContractError):
            core.execute("d-1")
        self.assertEqual(core.fake.calls, [])

    def test_enforced_with_quorum_allows_once(self):
        core = self.ready(True)
        self.assertIsNotNone(self.L.reconcile(self.log(), [self.spawn("example-peer"), self.spawn("pi")]))
        outcome = core.execute("d-1").to_dict()
        self.assertEqual((outcome["execution_status"], len(core.fake.calls)), ("completed", 1))
        [intent], [result] = self.entries("intent"), self.entries("result")
        self.assertEqual((result["ref"], result["body"]["outcome"]), (intent["hash"], "applied"))
        action = [e for e in core.ledger() if e["kind"] == "action"][0]["data"]
        with self.assertRaisesRegex(ContractError, "already-used"):  # single use: the intent has a result
            core._ledger.append("action", action)
        self.assertEqual(len(core.fake.calls), 1)

    def witnessed(self, capability=None):
        """An enforced core with d-1's intent co-signed by 2 of 3 witnesses; returns (core, intent hash, request JSON)."""
        core = self.ready(True, capability)
        self.assertIsNotNone(self.L.reconcile(self.log(), [self.spawn("example-peer"), self.spawn("pi")]))
        [intent] = self.entries("intent")
        return core, intent["hash"], json.dumps(json.loads(intent["body"]["event_json"])["data"]["request"])

    def gate_claim(self, intent, action, go=None):
        """`ledger.py gate --claim` as another writer on the node, optionally held until `go` exists."""
        kp = self.d / "ops.key"
        if not kp.exists():
            self.L.save_key(self.k["ops"], str(kp))
        argv = [sys.executable, "-B", str(Path(self.L.__file__)), "gate", "--log", str(self.path), "--origin", "example-host",
                "--roster", str(self.roster), "--intent", intent, "--action", action, "--claim", "--key", str(kp),
                "--writer", "ops"]
        if go is not None:
            wait = f"import os, runpy, sys, time\nwhile not os.path.exists({str(go)!r}): time.sleep(0.0005)\n"
            argv = [sys.executable, "-B", "-c", wait + "sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')",
                    *argv[2:]]
        return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def claims(self, intent):
        return [e for e in self.log().entries if e["kind"] == "claim" and e["ref"] == intent]

    def test_adapter_dispatch_consumes_intent_for_other_writers(self):
        """While the adapter's dispatch is in flight (action recorded, no result yet) another writer must be denied."""
        test, seen = self, {}

        class ClaimDuringDispatch(FakeCapability):
            def invoke(self, request, attempt_id, cancellation=None):
                proc = test.gate_claim(seen["intent"], seen["action"])
                seen["out"] = (*proc.communicate(timeout=60), proc.returncode)
                return super().invoke(request, attempt_id, cancellation)

        core, seen["intent"], seen["action"] = self.witnessed(ClaimDuringDispatch())
        self.assertEqual(core.execute("d-1").to_dict()["execution_status"], "completed")
        out, err, code = seen["out"]
        self.assertEqual(code, 77, out)  # an action `note` left the intent claimable here
        self.assertIn("intent-already-used", err)
        self.assertEqual((len(self.claims(seen["intent"])), len(core.fake.calls)), (1, 1))

    def test_other_writer_claim_blocks_adapter_dispatch(self):
        core, intent, action = self.witnessed()
        proc = self.gate_claim(intent, action)
        self.assertEqual((proc.communicate(timeout=60)[0].strip(), proc.returncode), ("claimed", 0))
        with self.assertRaisesRegex(ContractError, "already-used"):
            core.execute("d-1")
        self.assertEqual((len(self.claims(intent)), core.fake.calls), (1, []))

    def test_adapter_and_gate_claim_race_one_wins(self):
        core, intent, action = self.witnessed()
        go = self.d / "go"
        proc = self.gate_claim(intent, action, go)
        go.touch()
        try:
            adapter_won = core.execute("d-1").to_dict()["execution_status"] == "completed"
        except ContractError as error:
            self.assertIn("already-used", str(error))
            adapter_won = False
        _, err = proc.communicate(timeout=60)
        cli_won = proc.returncode == 0
        self.assertNotEqual(adapter_won, cli_won, err)  # exactly one consumer
        self.assertEqual((len(self.claims(intent)), len(core.fake.calls)), (1, int(adapter_won)))


    def test_refuses_to_sign_board_unsafe_fields(self):
        from adapters.witnessed_ledger import _board_safe
        for bad in (0.5, 2 ** 53, "a\x7f", {"\uffff": 1, "\U0001F600": 2}, [1, 2.0]):
            self.assertFalse(_board_safe({"x": bad}), bad)
        self.assertTrue(_board_safe({"a": [1, -(2 ** 53 - 1), None, True, "\u00e9\U0001F600"], "b": {"c": "d"}}))

    def test_tampering_and_truncation_detected(self):
        wl = self.ledger()
        execute_one(FakeFoundation(ledger=wl))
        lines = self.path.read_text().splitlines()
        edited = json.loads(lines[2])
        event = json.loads(edited["body"]["event_json"])
        event["data"]["rationale"] = "rewritten"
        edited["body"]["event_json"] = json.dumps(event, sort_keys=True, separators=(",", ":"))
        self.path.write_text("\n".join(lines[:2] + [json.dumps(edited)] + lines[3:]) + "\n")
        with self.assertRaisesRegex(ContractError, "bad-signature"):
            self.ledger("poodo.other")
        with self.assertRaises(ContractError):
            wl.read()
        self.path.write_text("\n".join(lines[:-1]) + "\n")  # drop the newest entry: chain still valid
        with self.assertRaisesRegex(ContractError, "truncated"):
            wl.read()
        head = wl.head()
        wl.close()
        with self.assertRaisesRegex(ContractError, "truncated"):
            self.ledger(anchor=head)

    def test_streams_interleave_on_one_log_each_reading_only_its_own(self):
        a, b = self.ledger("bot.math"), self.ledger("bot.refrigeration")
        for i in range(3):
            a.append("observation", {"i": i})
            b.append("learning", {"i": i})
        a.append("observation", {"i": 0})
        b.append("observation", {"i": 0})
        for wl, kind in ((a, "observation"), (b, "learning")):
            events, prior = wl.read(), None
            self.assertEqual([e["kind"] for e in events], [kind] * 3 + ["observation"])
            for i, e in enumerate(events, 1):  # contiguous per stream, chained per stream
                self.assertEqual((e["sequence"], e["prior_event_sha256"]), (i, prior))
                prior = e["event_sha256"]
        entries = self.log().entries
        self.assertEqual([e["seq"] for e in entries], list(range(1, 9)))  # one node log, one node chain
        self.assertEqual([e["body"]["stream"] for e in entries], ["bot.math", "bot.refrigeration"] * 4)
        self.assertEqual(self.L.Log(str(self.path), "example-host", self.L.load_roster(str(self.roster))).head,
                         entries[-1]["hash"])  # the prototype's own verifier accepts the log unchanged
        a.close()
        self.assertEqual([e["sequence"] for e in self.ledger("bot.math").read()], [1, 2, 3, 4])

    def test_core_cannot_read_or_execute_another_streams_records(self):
        math = FakeFoundation(ledger=self.ledger("bot.math", enforce=True))
        to_decide(math)
        math.decide(request(), precommit())
        other = self.ledger("bot.refrigeration", enforce=True)
        self.assertEqual(other.read(), [])
        [intent] = self.entries("intent")
        other._intents["d-1"] = intent["hash"]  # even a leaked intent hash is not this stream's intent
        with self.assertRaisesRegex(ContractError, "no-intent"):
            other.append("action", {"decision_id": "d-1", "request_sha256": request().sha256})
        self.assertEqual([e["kind"] for e in other.read()], [])
        self.assertNotIn("action", [e["kind"] for e in math.ledger()])

    def test_second_live_instance_on_a_stream_is_refused(self):
        wl = self.ledger("bot.math")
        with self.assertRaisesRegex(ContractError, "already has a live owner"):
            self.ledger("bot.math")
        code = ("import sys\nfrom adapters.witnessed_ledger import WitnessedLedger\n"
                "WitnessedLedger(*sys.argv[1:4], 'poodo-bot', sys.argv[4], stream='bot.math')\n")
        done = subprocess.run([sys.executable, "-B", "-c", code, str(self.path), "example-host", str(self.roster),
                               str(self.key)], cwd=Path(__file__).resolve().parents[1], capture_output=True,
                              text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("already has a live owner", done.stderr)
        self.assertEqual(oct(os.stat(f"{self.path}.streams/bot.math.lock").st_mode & 0o777), "0o600")
        self.assertEqual(oct(os.stat(f"{self.path}.streams").st_mode & 0o777), "0o700")
        self.ledger("bot.refrigeration").append("observation", {})  # other streams are unaffected
        wl.append("observation", {})
        wl.close()
        wl.close()
        with self.assertRaisesRegex(ContractError, "closed"):
            wl.append("observation", {})
        with self.assertRaisesRegex(ContractError, "closed"):
            wl.reserve(1, 1)
        self.assertEqual(len(self.ledger("bot.math").read()), 1)  # released by close()
        del wl

    def test_forked_child_cannot_use_the_parents_claim(self):
        wl = self.ledger("bot.math")
        wl.append("observation", {"x": 1})
        read, write = os.pipe()
        pid = os.fork()
        if pid == 0:  # child: the inherited instance refuses; exit without running the parent's cleanups
            try:
                wl.append("observation", {"from": "child"})
                message = b"appended"
            except ContractError as error:
                message = str(error).encode()
            os.write(write, message)
            os._exit(0)
        os.close(write)
        with os.fdopen(read, "rb") as pipe:
            message = pipe.read().decode()
        os.waitpid(pid, 0)
        self.assertIn("closed", message)
        with self.assertRaisesRegex(ContractError, "already has a live owner"):
            self.ledger("bot.math")  # the parent still owns the stream
        wl.append("observation", {"from": "parent"})
        self.assertEqual([e["data"] for e in wl.read()], [{"x": 1}, {"from": "parent"}])
        wl.close()
        self.ledger("bot.math").close()

    def test_replaced_claim_file_stops_the_owner(self):
        a = self.ledger("bot.math")
        os.unlink(f"{self.path}.streams/bot.math.lock")  # a "stale lock" cleaner
        b = self.ledger("bot.math")
        b.append("observation", {"who": "b"})
        with self.assertRaisesRegex(ContractError, "removed or replaced"):
            a.append("observation", {"who": "a"})
        with self.assertRaisesRegex(ContractError, "closed"):
            a.read()
        self.assertEqual([e["data"] for e in b.read()], [{"who": "b"}])

    def test_stream_claims_cannot_collide_with_other_logs(self):
        """A claim of (log, "v2") must not be the node lock of log "<log>.v2", nor share a file with another pair."""
        a = self.ledger("v2")
        other = WitnessedLedger(f"{self.path}.v2", "example-host", self.roster, "poodo-bot", self.key, stream="math")
        self.addCleanup(other.close)
        other.append("observation", {})  # would block forever on a.claim if claims lived beside node locks
        self.ledger("v2.math").close()
        a.close()

    def test_stream_names_are_validated(self):
        for bad in ("", "Bot.math", "bot/math", "../x", ".hidden", "-x", "a" * 65, "bot math", "b\u00f6t", None, 7):
            with self.assertRaisesRegex(ContractError, "stream name"):
                self.ledger(bad)
        self.assertEqual(self.ledger("a" * 64).stream, "a" * 64)
        with self.assertRaises(TypeError):
            WitnessedLedger(self.path, "example-host", self.roster, "poodo-bot", self.key)  # stream is required

    def test_identical_events_in_two_streams_stay_separate(self):
        """Events keep MemoryLedger's shape, so two streams can hold the same bytes; the signed body.stream separates them."""
        a, b = self.ledger("bot.a"), self.ledger("bot.b")
        self.assertEqual(a.append("observation", {"x": 1}), b.append("observation", {"x": 1}))
        first, second = self.log().entries
        self.assertEqual(first["body"]["event_json"], second["body"]["event_json"])
        self.assertEqual((first["body"]["stream"], second["body"]["stream"]), ("bot.a", "bot.b"))
        self.assertEqual((len(a.read()), len(b.read())), (1, 1))

    def test_budget_is_per_stream(self):
        a = self.ledger("bot.math", max_events=2)
        b = self.ledger("bot.refrigeration", max_events=2)
        a.append("observation", {})
        a.append("observation", {})
        with self.assertRaisesRegex(ContractError, "budget"):
            a.reserve(1, 1)
        b.reserve(2, 1)  # a's full stream does not spend b's room
        b.append("observation", {})
        b.append("observation", {})
        with self.assertRaisesRegex(ContractError, "budget"):
            b.append("observation", {})
        size = self.path.stat().st_size
        c = self.ledger("bot.bytes", max_bytes=size)  # the node file is already this big; c's stream is empty
        c.reserve(1, 1)

    def test_stream_anchor(self):
        a, b = self.ledger("bot.math"), self.ledger("bot.refrigeration")
        a.append("observation", {"i": 1})
        b.append("observation", {"i": 1})
        last = a.read()[-1]["event_sha256"]
        head = a.head()
        self.assertEqual(head[2:], ("bot.math", 1, last))
        self.assertEqual(head[:2], (2, self.log().entries[-1]["hash"]))
        a.close()
        self.ledger("bot.math", anchor=head).close()
        self.ledger("bot.math", anchor=head[:2]).close()  # a node-only anchor is still accepted
        with self.assertRaisesRegex(ContractError, "stream differs"):
            self.ledger("bot.math", anchor=(*head[:3], 0, None))
        with self.assertRaisesRegex(ContractError, "belongs to ledger stream 'bot.math'"):
            self.ledger("bot.copy", anchor=head)  # another stream with identical events cannot use this anchor
        genesis = self.L.GENESIS
        for bad in ((1,), (1, "x", 1), ("1", "x"), (1, "x", "bot.math", "1", None), (-5, "x"), (0, "garbage"),
                    (1, genesis), (2, head[1], "bot.math", 3, last), (2, head[1], "bot.math", 1, None),
                    (2, head[1], "bot.math", 0, last)):
            with self.assertRaisesRegex(ContractError, "anchor"):
                self.ledger("bot.math", anchor=bad)
        self.ledger("bot.math", anchor=(0, genesis)).close()

    def test_pre_stream_poodo_entries_are_refused_other_entries_skipped(self):
        self.ledger("bot.init").close()  # creates the node files 0600
        log = self.log()
        key = self.L.load_key(str(self.key))
        log.intent(key, "poodo-bot", {"op": "shields.down"})  # the writer's own non-POODO entry: skipped
        log.write(self.k["ops"], "ops", "note", {"event_json": "{}"})  # another writer's entry: skipped unread
        self.assertEqual(self.ledger("bot.math").read(), [])
        log.write(key, "poodo-bot", "note", {"event_json": "{}"})  # a POODO entry from before streams
        with self.assertRaisesRegex(ContractError, "predates streams"):
            self.ledger("bot.refrigeration")

    def test_writer_processes_finish_under_a_deadline(self):
        """Regression: an adapter-held flock on <log>.lock deadlocked against Log.write(). Fail, do not hang."""
        code = ("import sys\nfrom adapters.witnessed_ledger import WitnessedLedger\n"
                "wl = WitnessedLedger(*sys.argv[1:4], 'poodo-bot', sys.argv[4], stream=sys.argv[5])\n"
                "for i in range(5): wl.append('observation', {'pid': i})\n"
                "print(len(wl.read()))\n")
        args = [str(self.path), "example-host", str(self.roster), str(self.key)]
        procs = [subprocess.Popen([sys.executable, "-B", "-c", code, *args, f"bot.p{i}"],
                                  cwd=Path(__file__).resolve().parents[1],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(3)]
        try:
            out = [p.communicate(timeout=60) for p in procs]
        except subprocess.TimeoutExpired:
            for p in procs:
                p.kill()
                p.communicate()
            self.fail("WitnessedLedger writers deadlocked (no exit within 60 s)")
        for p, (_, err) in zip(procs, out):
            self.assertEqual(p.returncode, 0, err)
        for i in range(3):
            self.assertEqual([e["sequence"] for e in self.ledger(f"bot.p{i}").read()], list(range(1, 6)))
        self.assertEqual([e["seq"] for e in self.log().entries], list(range(1, 16)))

    def test_refuses_unsafe_files_and_unbound_writer(self):
        self.ledger().append("observation", {})
        os.chmod(self.path, 0o644)
        with self.assertRaisesRegex(ContractError, "0600"):
            self.ledger("poodo.second")
        os.chmod(self.path, 0o600)
        link = self.d / "link.jsonl"
        link.symlink_to(self.path)
        with self.assertRaises(ContractError):
            WitnessedLedger(link, "example-host", self.roster, "poodo-bot", self.key, stream="poodo.link")
        with self.assertRaisesRegex(ContractError, "bound to this node"):
            WitnessedLedger(self.d / "box.jsonl", "box", self.roster, "poodo-bot", self.key, stream="poodo.box")
        self.ledger("poodo.claim0").close()
        claim = self.d / "example-host.jsonl.streams/poodo.claim.lock"
        claim.symlink_to(self.d / "elsewhere")
        with self.assertRaises(ContractError):  # the claim file is never followed through a symlink
            self.ledger("poodo.claim")


if __name__ == "__main__":
    unittest.main()

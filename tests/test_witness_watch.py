"""ADR 005 decision 6: witness staleness. No witness data is an alarm, never a healthy result."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from tools import runtime_watch
from tools.runtime_watch import EXIT_ALARM
from tools.witness_watch import main

NOW, BOUND = 1_000_000, 900
HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None


class WitnessWatchTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def run_watch(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--stale-after", str(BOUND), "--now", str(NOW), *args])
        return code, json.loads(out.getvalue()), err.getvalue()

    def test_no_witness_data_alarms(self):
        for args in ([], ["--replicas", str(self.dir), "--roster", str(self.dir / "roster.json")],
                     ["--checkpoints", f"box={self.dir / 'box.log'}"]):
            with self.subTest(args=args):
                code, report, err = self.run_watch(*args)
                self.assertEqual((code, report["origins"][0]["status"]), (EXIT_ALARM, "no_witness_data"))
                self.assertIn("ALARM NO_WITNESS_DATA box", err)
                self.assertIn("ALARM WATCHER_BLIND box: no witness copy", err)  # no data is never alive
                self.assertNotIn("DEADMAN", err)
                self.assertEqual(report["deadman"]["status"], "blind")
                self.assertNotIn("fresh", report["brief"][0])

    def test_data_that_cannot_be_verified_alarms(self):
        (self.dir / "box.replica.jsonl").write_text("{}\n")
        code, report, _ = self.run_watch("--replicas", str(self.dir))
        self.assertEqual((code, report["alarms"][0]["code"]), (EXIT_ALARM, "WITNESS_UNVERIFIABLE"))
        real = importlib.util.find_spec
        with mock.patch.object(importlib.util, "find_spec", lambda n, *a: None if n == "cryptography" else real(n, *a)):
            code, report, _ = self.run_watch("--replicas", str(self.dir), "--roster", str(self.dir / "r.json"))
        self.assertIn("cryptography", report["alarms"][0]["detail"])

    @unittest.skipUnless(HAVE_CRYPTO, "the ADR 004 ledger needs 'cryptography'")
    def test_watch_preserves_sources_and_directory_listing(self):
        lib = runtime_watch.hmi_ledger()
        keys = {n: lib.Ed25519PrivateKey.generate() for n in ("box", "w1", "w2")}
        roster = {"writers": {"bot.box": {"pub": lib.pub_hex(keys["box"]), "node": "box"}},
                  "witnesses": {n: lib.pub_hex(keys[n]) for n in ("w1", "w2")}, "quorum": 2}
        roster_path = self.dir / "roster.json"
        roster_path.write_text(json.dumps(roster))
        path = self.dir / "box.replica.jsonl"
        log = lib.Log(str(path), "box", roster)
        with mock.patch.object(lib.time, "time", lambda: NOW - 10):
            log.write(keys["box"], "bot.box", "checkin", {"machine": "box", "level": 0, "outcome": "noop"})
        log.add_checkpoint(1, log.head, [lib.cosign(keys[n], n, "box", 1, log.head, ts=NOW - 5)
                                         for n in ("w1", "w2")])
        for corrupt in (False, True):
            if corrupt:
                path.write_text("{}\n")
            before = {p.name: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                      for p in (self.dir, *self.dir.iterdir())}
            with self.subTest(corrupt=corrupt), \
                    mock.patch.dict(os.environ, {"LEDGER_ALARMS": str(self.dir / "alarms.jsonl")}):
                code, report, _ = self.run_watch("--roster", str(roster_path), "--replicas", str(self.dir),
                                                  "--checkpoints", f"box={path}")
                self.assertEqual(code, EXIT_ALARM if corrupt else 0)
                self.assertEqual({p.name: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                                  for p in (self.dir, *self.dir.iterdir())}, before)

    @unittest.skipUnless(HAVE_CRYPTO, "the ADR 004 ledger needs 'cryptography'")
    def test_replica_and_quorum_checkpoint_ages(self):
        lib = runtime_watch.hmi_ledger()
        keys = {n: lib.Ed25519PrivateKey.generate() for n in ("box", "w1", "w2")}
        roster = {"writers": {"example-agent.box": {"pub": lib.pub_hex(keys["box"]), "node": "box"}},
                  "witnesses": {"w1": lib.pub_hex(keys["w1"]), "w2": lib.pub_hex(keys["w2"])}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(roster))
        log = lib.Log(str(self.dir / "box.log"), "box", roster)
        with mock.patch.object(lib.time, "time", lambda: NOW - 100):
            log.write(keys["box"], "example-agent.box", "checkin", {"machine": "box", "level": 0, "outcome": "noop"})
        (self.dir / "w1").mkdir()
        (self.dir / "w1" / "box.replica.jsonl").write_text((self.dir / "box.log").read_text())
        args = ("--roster", str(self.dir / "roster.json"), "--replicas", str(self.dir / "w1"))
        with mock.patch("tools.witness_watch.hmi_ledger", lambda: lib):
            code, report, _ = self.run_watch(*args)
            self.assertEqual((code, report["origins"][0]["age_seconds"]), (0, 100))
            code, report, _ = self.run_watch(*args, "--now", str(NOW + BOUND), "--deadman-after", str(2 * BOUND))
            self.assertEqual((code, report["alarms"][0]["code"]), (EXIT_ALARM, "WITNESS_STALE"))
            one = lib.cosign(keys["w1"], "w1", "box", 1, log.head, ts=NOW - 50)
            with self.assertRaises(lib.Denied):  # a single cosignature is below quorum and is never stored
                log.add_checkpoint(1, log.head, [one])
            log.add_checkpoint(1, log.head, [one, lib.cosign(keys["w2"], "w2", "box", 1, log.head, ts=NOW - 40)])
            code, report, _ = self.run_watch("--roster", str(self.dir / "roster.json"),
                                             "--checkpoints", f"box={self.dir / 'box.log'}")
        row = report["origins"][0]
        self.assertEqual((code, row["newest_kind"], row["age_seconds"]), (0, "quorum_checkpoint", 40))



@unittest.skipUnless(HAVE_CRYPTO, "the ADR 004 ledger needs 'cryptography'")
class DeadmanTests(unittest.TestCase):
    """#96's signed `checkin` entries in example-host's witness copy of the box log. Test keys only."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.lib = lib = runtime_watch.hmi_ledger()
        self.keys = {n: lib.Ed25519PrivateKey.generate() for n in ("box", "w1", "w2", "forger")}
        self.roster = {"writers": {"example-agent.box": {"pub": lib.pub_hex(self.keys["box"]), "node": "box"}},
                       "witnesses": {n: lib.pub_hex(self.keys[n]) for n in ("w1", "w2")}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(self.roster))
        (self.dir / "w1").mkdir()
        self.replica = self.dir / "w1" / "box.replica.jsonl"
        self.log = lib.Log(str(self.replica), "box", self.roster)  # the fixture writer; the watcher only reads

    def checkin(self, at, level=0, outcome="noop", machine="box"):
        with mock.patch.object(self.lib.time, "time", lambda: at):
            self.log.write(self.keys["box"], "example-agent.box", "checkin",
                           {"machine": machine, "level": level, "outcome": outcome, "cseq": len(self.log.entries) + 1,
                            "ts": at})

    def forge(self, at):
        """A check-in under the box writer's name signed with a key the roster does not hold, appended raw."""
        log = self.lib.Log(str(self.replica), "box", self.roster)
        e = {"v": 1, "origin": "box", "seq": len(log.entries) + 1, "prev": log.head, "writer": "example-agent.box",
             "wseq": log.wseq.get("example-agent.box", 0) + 1, "kind": "checkin", "ts": at,
             "body": {"machine": "box", "level": 0, "outcome": "noop", "cseq": 99, "ts": at}, "ref": None}
        e["sig"] = self.lib.sign(self.keys["forger"], self.lib.canon(e))
        e["hash"] = self.lib.sha(self.lib.canon(e))
        with self.replica.open("a") as f:
            f.write(json.dumps(e, sort_keys=True) + "\n")

    def run_watch(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("tools.witness_watch.hmi_ledger", lambda: self.lib), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--stale-after", "86400", "--now", str(NOW), "--roster", str(self.dir / "roster.json"),
                         "--replicas", str(self.dir / "w1"), *args])
        report = json.loads(out.getvalue())
        return code, report, [a["code"] for a in report["alarms"]]

    def test_fresh_checkin_is_healthy(self):
        self.checkin(NOW - 2000, level=2, outcome="applied")
        self.checkin(NOW - 120)
        self.checkin(NOW - 60, machine="example-host")  # another machine's check-in is not the box's
        code, report, codes = self.run_watch()
        dead = report["deadman"]
        self.assertEqual((code, codes, dead["status"], dead["age_seconds"]), (0, [], "fresh", 120))
        self.assertEqual((dead["last_checkin"]["level"], dead["last_checkin"]["outcome"]), (0, "noop"))
        self.assertEqual(report["brief"][1], "Dead-man box@box: fresh, last check-in 120s ago (bound 900s), "
                                             "level 0, outcome noop.")
        self.assertLessEqual(len(report["brief"]), 3)

    def test_stale_checkin_is_deadman_and_the_bound_is_settable(self):
        self.checkin(NOW - 901)
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes, report["deadman"]["status"]), (EXIT_ALARM, ["DEADMAN"], "down"))
        self.assertIn("Alarms: DEADMAN 1.", report["brief"])
        code, report, codes = self.run_watch("--deadman-after", "1000")  # deprecated alias: period kept, rest grace
        self.assertEqual((code, codes, report["deadman"]["period"], report["deadman"]["grace"]), (0, [], 300, 700))

    def test_missing_checkin_is_deadman(self):
        with mock.patch.object(self.lib.time, "time", lambda: NOW - 10):
            self.log.write(self.keys["box"], "example-agent.box", "note", {"text": "not a check-in"})
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes, report["deadman"]["status"]), (EXIT_ALARM, ["DEADMAN"], "missing"))
        self.assertIn("no verified check-in", report["brief"][1])
        self.replica.unlink()
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes), (EXIT_ALARM, ["NO_WITNESS_DATA", "WATCHER_BLIND"]))

    def test_forged_checkin_is_unverifiable_and_never_fresh(self):
        self.checkin(NOW - 5000)
        self.forge(NOW - 5)
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes), (EXIT_ALARM, ["WITNESS_UNVERIFIABLE", "DEADMAN"]))
        self.assertIn("bad-signature", report["alarms"][0]["detail"])
        self.assertEqual(report["deadman"]["status"], "missing")
        (self.dir / "w2").mkdir()  # another witness's good copy still counts; the forged one never does
        good = self.replica.read_text().splitlines(keepends=True)[0]
        (self.dir / "w2" / "box.replica.jsonl").write_text(good)
        code, report, codes = self.run_watch("--replicas", str(self.dir / "w2"))
        self.assertEqual((codes, report["deadman"]["status"], report["deadman"]["age_seconds"]),
                         (["WITNESS_UNVERIFIABLE", "DEADMAN"], "down", 5000))

    def test_future_timestamp_is_clock_skew_not_fresh(self):
        self.checkin(NOW + 30)  # within the 60 s skew: counts
        code, report, codes = self.run_watch()
        self.assertEqual((code, report["deadman"]["status"]), (0, "fresh"))
        self.checkin(NOW + 3600)
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes), (EXIT_ALARM, ["CLOCK_SKEW", "CLOCK_SKEW"]))
        self.assertEqual((report["deadman"]["future"], report["deadman"]["age_seconds"]), (1, -30))
        self.replica.unlink()
        self.log = self.lib.Log(str(self.replica), "box", self.roster)
        self.checkin(NOW + 3600)
        code, report, codes = self.run_watch()
        self.assertEqual(codes, ["CLOCK_SKEW", "CLOCK_SKEW", "DEADMAN"])
        self.assertEqual(report["deadman"]["status"], "missing")

    def test_shields_up_level_alarms_and_is_reported(self):
        self.checkin(NOW - 30, level=2, outcome="applied")
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes, report["deadman"]["status"]), (EXIT_ALARM, ["SHIELDS_UP"], "fresh"))
        self.assertIn("level 2, outcome applied", report["brief"][1])
        self.assertIn("does not act", report["alarms"][0]["detail"])

    def test_every_boundary_of_fresh_late_and_down(self):
        for age, state, codes in ((300, "fresh", []), (301, "late", []), (900, "late", []), (901, "down", ["DEADMAN"])):
            with self.subTest(age=age):
                self.setUp()
                self.checkin(NOW - age)
                code, report, got = self.run_watch()
                dead = report["deadman"]
                self.assertEqual((code, got, dead["status"], dead["late_since"], dead["down_since"]),
                                 (EXIT_ALARM if codes else 0, codes, state, NOW - age + 300, NOW - age + 900))
                self.assertIn(f"Dead-man box@box: {state},", report["brief"][1])

    def test_a_failure_outcome_is_down_at_once(self):
        for outcome, codes in (("failed", ["DEADMAN"]), ("unknown", ["DEADMAN"]), ("held", [])):
            with self.subTest(outcome=outcome):
                self.setUp()
                self.checkin(NOW - 10, outcome=outcome)
                code, report, got = self.run_watch()
                self.assertEqual((got, report["deadman"]["status"]), (codes, "down" if codes else "fresh"))
                if codes:
                    self.assertEqual((code, report["alarms"][0]["down_since"]), (EXIT_ALARM, NOW - 10))
        self.checkin(NOW - 5)  # the next good check-in clears it, as a Healthchecks success ping does
        self.assertEqual(self.run_watch()[2], [])

    def test_watcher_blind_replaces_deadman_when_the_roster_is_unreadable(self):
        self.checkin(NOW - 5000)
        (self.dir / "roster.json").write_text("{not json")
        code, report, codes = self.run_watch()
        self.assertEqual((code, codes, report["deadman"]["status"]), (EXIT_ALARM, ["WITNESS_UNVERIFIABLE",
                                                                                  "WATCHER_BLIND"], "blind"))
        self.assertIn("roster unreadable", report["brief"][1])

    def test_deadman_suppresses_witness_stale_for_the_same_origin_and_says_so(self):
        self.checkin(NOW - 1000)
        code, report, codes = self.run_watch("--stale-after", "60")
        self.assertEqual((code, codes), (EXIT_ALARM, ["DEADMAN"]))
        (hidden,) = report["suppressed"]
        self.assertEqual((hidden["code"], hidden["suppressed_by"]), ("WITNESS_STALE", report["alarms"][0]["alarm_id"]))
        self.assertIn("Alarms: DEADMAN 1; suppressed WITNESS_STALE 1.", report["brief"])
        self.checkin(NOW - 100)  # box alive, witnesses still behind: nothing to blame it on, so it alarms
        code, report, codes = self.run_watch("--stale-after", "60")
        self.assertEqual((codes, report["suppressed"]), (["WITNESS_STALE"], []))

    def test_alarm_ids_are_stable_across_runs(self):
        self.checkin(NOW - 2000, level=2, outcome="applied")
        self.checkin(NOW - 1000, level=2, outcome="noop")
        _, first, codes = self.run_watch()
        _, again, _ = self.run_watch("--now", str(NOW + 60))
        self.assertEqual(codes, ["DEADMAN", "SHIELDS_UP"])
        self.assertEqual([a["alarm_id"] for a in first["alarms"]], [a["alarm_id"] for a in again["alarms"]])
        self.assertEqual(first["alarms"][1]["down_since"], NOW - 2000)  # since the level went up, not the last ping
        self.checkin(NOW - 10, level=2)
        _, later, codes = self.run_watch()
        self.assertEqual((codes, later["alarms"][0]["alarm_id"]), (["SHIELDS_UP"], first["alarms"][1]["alarm_id"]))

    def test_the_shared_config_sets_the_deadman_policy(self):
        self.checkin(NOW - 120)
        config = self.dir / "watch.json"
        config.write_text(json.dumps({"default": {"period": 3600}, "deadman": {"box/box": {"period": 60, "grace": 0}}}))
        code, report, codes = self.run_watch("--config", str(config))
        self.assertEqual((code, codes, report["deadman"]["bound"]), (EXIT_ALARM, ["DEADMAN"], 60))

    def test_the_deadman_read_writes_nothing(self):
        self.checkin(NOW - 2000)
        self.forge(NOW - 5)  # ledger.py raises Alarm on it, which would append to $LEDGER_ALARMS if left set
        files = [p for p in self.dir.rglob("*") if p.is_file()]
        for p in files:
            os.chmod(p, stat.S_IRUSR)
        os.chmod(self.dir / "w1", stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.dir / "w1", stat.S_IRWXU)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
        alarms = self.dir / "ledger-alarms.jsonl"
        with mock.patch.dict(os.environ, {"LEDGER_ALARMS": str(alarms)}):
            code, report, codes = self.run_watch()
            self.assertEqual(os.environ["LEDGER_ALARMS"], str(alarms))
        self.assertEqual(codes, ["WITNESS_UNVERIFIABLE", "DEADMAN"])
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}, before)
        self.assertEqual(sorted(p for p in self.dir.rglob("*") if p.is_file()), sorted(files))
        self.assertFalse(alarms.exists())


if __name__ == "__main__":
    unittest.main()

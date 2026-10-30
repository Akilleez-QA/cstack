"""ADR 005 decision 6: the read-only runtime watcher reports and alarms on fixture ledgers, and never writes."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest import mock

from adapters.memory_ledger import MemoryLedger
from poodo_core import ApprovalDeclined, ContractError, LivenessRecord
from tests.helpers import FakeCapability, FakeFoundation, execute_one, precommit, request, to_decide
from tests.test_approval_policy import Foundation, approve, decided
from tools import runtime_watch
from tools.runtime_watch import EXIT_ALARM, main

ROOT = Path(__file__).resolve().parents[1]
NOW, BOUND = 1_000_000, 3600


class Exploding(FakeCapability):
    def invoke(self, request, attempt_id, cancellation=None):
        raise RuntimeError("transport died mid-call")


def replay(events, *extra):
    """A fresh MemoryLedger holding events (a valid chain prefix) plus extra (kind, data) appends."""
    ledger = MemoryLedger()
    for event in events:
        ledger.append(event["kind"], event["data"])
    for kind, data in extra:
        ledger.append(kind, data)
    return ledger.read()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [os.chmod(p, 0o700) for p in (self.dir, *self.dir.rglob("*")) if p.is_dir()])

    def export(self, events, name="rt.ledger.json", age=10, where=None):
        path = (where or self.dir) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(events))
        os.utime(path, (NOW - age, NOW - age))
        return path

    def run_watch(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--stale-after", str(BOUND), "--now", str(NOW), *args])
        return code, json.loads(out.getvalue()), err.getvalue()


class RuntimeWatchTests(Fixture):
    def test_a_fresh_runtime_passes_and_reports_goals_with_no_owner(self):
        core = FakeFoundation()
        execute_one(core)
        code, report, err = self.run_watch("--export", f"rt={self.export(core.ledger())}")
        self.assertEqual((code, report["alarms"], err), (0, [], ""))
        row = report["runtimes"][0]
        self.assertEqual((row["status"], row["age_seconds"], row["time_source"]), ("ok", 10, "file_mtime"))
        self.assertEqual(row["counts"], {"unsettled_attempts": 0, "unknown_outcomes": 0, "refusals": 0,
                                         "goals_without_live_path": 1})
        self.assertEqual(row["goals_without_live_path"][0]["reason"], "no_next_action_owner")
        self.assertLessEqual(len(report["brief"]), 3)

    def test_a_stale_runtime_alarms_and_exits_75(self):
        core = FakeFoundation()
        execute_one(core)
        code, report, err = self.run_watch("--export", f"rt={self.export(core.ledger(), age=BOUND + 1)}")
        self.assertEqual(code, EXIT_ALARM)
        self.assertEqual([a["code"] for a in report["alarms"]], ["STALE"])
        self.assertIn("ALARM STALE rt", err)
        self.assertIn("STALE 1", report["brief"][0])

    def test_unsettled_attempts_are_in_flight_at_the_tail_and_abandoned_once_anything_follows(self):
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        cut = next(e["sequence"] for e in events if e["kind"] == "action")
        code, report, _ = self.run_watch("--export", f"rt={self.export(events[:cut])}")
        self.assertEqual((code, report["runtimes"][0]["unsettled_attempts"][0]["state"]), (0, "in_flight"))
        later = replay(events[:cut], ("observation", {"action": "restart"}))
        code, report, _ = self.run_watch("--export", f"rt={self.export(later)}")
        self.assertEqual(code, EXIT_ALARM)
        self.assertEqual([a["code"] for a in report["alarms"]], ["UNSETTLED"])
        code, report, _ = self.run_watch("--export", f"rt={self.export(events[:cut], age=BOUND + 1)}")
        self.assertEqual(sorted(a["code"] for a in report["alarms"]), ["STALE", "UNSETTLED"])

    def test_unknown_certainty_and_refusals_are_reported(self):
        core = FakeFoundation(Exploding())
        execute_one(core)
        refusing = Foundation()
        decided(refusing, request("send_report"))
        approve(refusing, request("send_report"), verdict="declined")
        with self.assertRaises(ApprovalDeclined):
            refusing.execute("d-1")
        denier = Foundation()
        to_decide(denier)
        with self.assertRaises(ContractError):
            denier.decide(request("wipe"), precommit())
        code, report, _ = self.run_watch("--export", f"a={self.export(core.ledger(), 'a.json')}",
                                         "--export", f"b={self.export(refusing.ledger(), 'b.json')}",
                                         "--export", f"c={self.export(denier.ledger(), 'c.json')}")
        self.assertEqual(code, 0)
        a, b, c = report["runtimes"]
        self.assertEqual([u["status"] for u in a["unknown_outcomes"]], ["indeterminate"])
        self.assertEqual([r["action"] for r in b["refusals"] + c["refusals"]], ["declined", "denied"])
        self.assertEqual(c["refusals"][0]["reason"], "host_policy_deny")
        self.assertIn("unknown outcomes 1, refusals 2", report["brief"][-1])

    def test_an_approval_wait_with_nothing_pending_is_not_a_live_path(self):
        core = Foundation()
        decided(core, request("reading"))
        core.record_liveness(LivenessRecord("g", 1, "owner-via-approver", "approval", "Wait"))
        _, report, _ = self.run_watch("--export", f"rt={self.export(core.ledger())}")
        self.assertEqual([g["reason"] for g in report["runtimes"][0]["goals_without_live_path"]],
                         [r["reason"] for r in core.goals_without_live_path()])

    def test_a_missing_ledger_always_alarms(self):
        for args in (["--export", f"rt={self.dir / 'absent.json'}"], ["--sqlite", f"rt={self.dir / 'absent.db'}"],
                     ["--state-root", str(self.dir / "no-such-root")], ["--require", "example-agent"], []):
            with self.subTest(args=args):
                code, report, _ = self.run_watch(*args)
                self.assertEqual(code, EXIT_ALARM)
                self.assertIn("NO_LEDGER", [a["code"] for a in report["alarms"]])
        (self.dir / "example-agent").mkdir()  # an MCP bot dir with only a MemoryLedger has nothing durable to watch
        code, report, _ = self.run_watch("--state-root", str(self.dir))
        self.assertEqual((code, report["alarms"][0]["code"], report["alarms"][0]["runtime"]),
                         (EXIT_ALARM, "NO_LEDGER", "example-agent"))

    def test_a_broken_chain_alarms_rather_than_reporting(self):
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        events[2]["data"]["rationale"] = "edited"
        code, report, _ = self.run_watch("--export", f"rt={self.export(events)}")
        self.assertEqual((code, report["alarms"][0]["code"]), (EXIT_ALARM, "LEDGER_INVALID"))

    def test_state_root_reads_exports_and_read_only_sqlite(self):
        core = FakeFoundation()
        execute_one(core)
        bot = self.dir / "coordinator"
        self.export(core.ledger(), "foundation_math.ledger.json", where=bot)
        db = sqlite3.connect(bot / "foundation_refrigeration.ledger.db")
        db.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, kind TEXT, event TEXT, event_sha256 TEXT, bytes INTEGER)")
        db.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [(e["sequence"], e["kind"], json.dumps(e),
                       e["event_sha256"], 0) for e in core.ledger()])
        db.commit()
        db.close()
        os.utime(bot / "foundation_refrigeration.ledger.db", (NOW, NOW))
        code, report, _ = self.run_watch("--state-root", str(self.dir), "--require", "coordinator")
        self.assertEqual(code, 0)
        self.assertEqual([r["runtime"] for r in report["runtimes"]],
                         ["coordinator/foundation_math", "coordinator/foundation_refrigeration"])

    def test_witnessed_log_without_cryptography_alarms(self):
        (self.dir / "ledger.json").write_text(json.dumps({"log": "node.log", "roster": "roster.json", "writers": {}}))
        real = importlib.util.find_spec
        with mock.patch.object(importlib.util, "find_spec", lambda n, *a: None if n == "cryptography" else real(n, *a)):
            code, report, _ = self.run_watch("--state-root", str(self.dir))
        self.assertEqual(code, EXIT_ALARM)
        self.assertIn("cryptography", report["alarms"][0]["detail"])


    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "the ADR 004 node log needs 'cryptography'")
    def test_witnessed_node_log_uses_entry_times_and_gate_denials(self):
        lib = runtime_watch.hmi_ledger()
        keys = {n: lib.Ed25519PrivateKey.generate() for n in ("example-agent", "w1", "w2")}
        roster = {"writers": {"example-agent.box": {"pub": lib.pub_hex(keys["example-agent"]), "node": "box"}},
                  "witnesses": {"w1": lib.pub_hex(keys["w1"]), "w2": lib.pub_hex(keys["w2"])}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(roster))
        (self.dir / "ledger.json").write_text(json.dumps({"log": "box.log", "roster": "roster.json", "node": "box",
                                                          "writers": {"example-agent": {"writer": "example-agent.box"}}}))
        core = FakeFoundation()
        execute_one(core)
        log = lib.Log(str(self.dir / "box.log"), "box", roster)
        with mock.patch.object(lib.time, "time", lambda: NOW - 30):
            for i, event in enumerate(core.ledger()):  # both stored forms: #25's event_json and #47's event
                log.write(keys["example-agent"], "example-agent.box", "note",
                          {"event_json": runtime_watch.canonical(event)} if i % 2 else {"event": event})
            log.write(keys["example-agent"], "example-agent.box", "note", {"poodo_denied": {"decision_id": "d-9", "reason": "x"}})
        before = {p: p.read_bytes() for p in self.dir.iterdir()}
        with mock.patch.object(runtime_watch, "hmi_ledger", lambda: lib):
            code, report, _ = self.run_watch("--state-root", str(self.dir), "--require", "example-agent")
        self.assertEqual((code, {p: p.read_bytes() for p in self.dir.iterdir()}), (0, before))
        row = report["runtimes"][0]
        self.assertEqual((row["runtime"], row["time_source"], row["age_seconds"], row["events"]),
                         ("example-agent@witnessed", "entry_ts", 30, len(core.ledger())))
        self.assertEqual(row["refusals"][0]["action"], "ledger_gate_denied")

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "the ADR 004 node log needs 'cryptography'")
    def test_witnessed_node_log_reports_each_stream_as_its_own_chain(self):
        """#25 streams: two cores of one bot interleave their chains on one node log; one broken stream alarms alone."""
        lib = runtime_watch.hmi_ledger()
        key, w1, w2 = (lib.Ed25519PrivateKey.generate() for _ in range(3))
        roster = {"writers": {"example-agent.box": {"pub": lib.pub_hex(key), "node": "box"}},
                  "witnesses": {"w1": lib.pub_hex(w1), "w2": lib.pub_hex(w2)}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(roster))
        (self.dir / "ledger.json").write_text(json.dumps({"log": "box.log", "roster": "roster.json", "node": "box",
                                                          "writers": {"example-agent": {"writer": "example-agent.box"}}}))
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        streams = ("example-agent.foundation_math", "example-agent.foundation_refrigeration")
        log = lib.Log(str(self.dir / "box.log"), "box", roster)
        with mock.patch.object(lib.time, "time", lambda: NOW - 30):
            for event in events:
                for stream in streams:
                    body = {"event_json": runtime_watch.canonical(event), "stream": stream}
                    log.write(key, "example-agent.box", "note", body)
            log.write(key, "example-agent.box", "note", {"event_json": runtime_watch.canonical(events[0]),
                                                    "stream": "example-agent.broken"})
            log.write(key, "example-agent.box", "note", {"event_json": runtime_watch.canonical(events[0]),
                                                    "stream": "example-agent.broken"})  # sequence 1 twice
        with mock.patch.object(runtime_watch, "hmi_ledger", lambda: lib):
            code, report, _ = self.run_watch("--state-root", str(self.dir), "--require", "example-agent")
        rows = {r["runtime"]: r for r in report["runtimes"]}
        self.assertEqual(set(rows), {f"example-agent@witnessed/{s}" for s in (*streams, "example-agent.broken")})
        for stream in streams:
            self.assertEqual((rows[f"example-agent@witnessed/{stream}"]["status"],
                              rows[f"example-agent@witnessed/{stream}"]["events"]), ("ok", len(events)))
        self.assertEqual([(a["code"], a["runtime"]) for a in report["alarms"]],
                         [("LEDGER_INVALID", "example-agent@witnessed/example-agent.broken")])
        self.assertEqual(code, EXIT_ALARM)

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "the ADR 004 node log needs 'cryptography'")
    def test_witnessed_node_log_dates_attempts_for_run_grace(self):
        lib = runtime_watch.hmi_ledger()
        key, w1, w2 = (lib.Ed25519PrivateKey.generate() for _ in range(3))
        roster = {"writers": {"example-agent.box": {"pub": lib.pub_hex(key), "node": "box"}},
                  "witnesses": {"w1": lib.pub_hex(w1), "w2": lib.pub_hex(w2)}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(roster))
        (self.dir / "ledger.json").write_text(json.dumps({"log": "box.log", "roster": "roster.json", "node": "box",
                                                          "writers": {"example-agent": {"writer": "example-agent.box"}}}))
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        cut = next(e["sequence"] for e in events if e["kind"] == "action")
        log = lib.Log(str(self.dir / "box.log"), "box", roster)
        with mock.patch.object(lib.time, "time", lambda: NOW - 1000):
            for event in events[:cut]:  # dispatched 1000 s ago, no outcome
                log.write(key, "example-agent.box", "note", {"event": event})
        with mock.patch.object(lib.time, "time", lambda: NOW - 5):  # the runtime keeps writing
            log.write(key, "example-agent.box", "note", {"poodo_denied": {"decision_id": "d-9", "reason": "x"}})
        (self.dir / "watch.json").write_text(json.dumps({"runtimes": {"example-agent": {"run_grace": 600}}}))
        with mock.patch.object(runtime_watch, "hmi_ledger", lambda: lib):
            code, report, _ = self.run_watch("--state-root", str(self.dir))
            self.assertEqual((code, report["runtimes"][0]["unsettled_attempts"][0]["state"]), (0, "in_flight"))
            code, report, _ = self.run_watch("--state-root", str(self.dir), "--config", str(self.dir / "watch.json"))
        row = report["runtimes"][0]
        self.assertEqual((code, row["freshness"], row["unsettled_attempts"][0]["state"]),
                         (EXIT_ALARM, "fresh", "overdue"))
        self.assertEqual((report["alarms"][0]["code"], report["alarms"][0]["down_since"]), ("UNSETTLED", NOW - 400))


class FreshnessTests(Fixture):
    """Healthchecks' late-is-not-down: per-source period and grace, dated transitions, stable alarm ids."""
    POLICY = {"period": 300, "grace": 600}

    def config(self, **runtimes):
        path = self.dir / "watch.json"
        path.write_text(json.dumps({"default": {"period": BOUND, "grace": 0}, "runtimes": runtimes}))
        return str(path)

    def watch_age(self, age, now=NOW):
        core = FakeFoundation()
        execute_one(core)
        path = self.export(core.ledger(), age=age)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--now", str(now), "--config", self.config(rt=self.POLICY), "--export", f"rt={path}"])
        return code, json.loads(out.getvalue())

    def test_every_boundary_of_fresh_late_and_down(self):
        for age, state, code in ((300, "fresh", 0), (301, "late", 0), (900, "late", 0), (901, "down", EXIT_ALARM)):
            with self.subTest(age=age):
                got, report = self.watch_age(age)
                row = report["runtimes"][0]
                self.assertEqual((got, row["freshness"], row["late_since"], row["down_since"]),
                                 (code, state, NOW - age + 300, NOW - age + 900))
                self.assertEqual([a["code"] for a in report["alarms"]], ["STALE"] if code else [])
                self.assertEqual("late" in report["brief"][0], state == "late")
        self.assertEqual(runtime_watch.freshness(None, period=1, grace=1, now=NOW),
                         {"freshness": "down", "late_since": None, "down_since": None})

    def test_stale_after_stays_the_default_with_no_grace(self):
        core = FakeFoundation()
        execute_one(core)
        for age, code in ((BOUND, 0), (BOUND + 1, EXIT_ALARM)):
            got, report, _ = self.run_watch("--export", f"rt={self.export(core.ledger(), age=age)}")
            self.assertEqual((got, report["runtimes"][0]["grace"]), (code, 0))

    def test_alarm_id_is_stable_across_runs_and_changes_with_down_since(self):
        _, first = self.watch_age(1000)
        _, again = self.watch_age(1000, now=NOW + 60)  # same last event, the watcher ran a minute later
        ids = [r["alarms"][0]["alarm_id"] for r in (first, again)]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(first["alarms"][0]["down_since"], NOW - 1000 + 900)
        _, moved = self.watch_age(2000)  # a different outage (older last event) is a new alarm
        self.assertNotEqual(moved["alarms"][0]["alarm_id"], ids[0])
        self.assertEqual(ids[0], runtime_watch.alarm_id("STALE", "rt", NOW - 100))

    def test_config_matches_the_bot_name_and_rejects_bad_policies(self):
        report = runtime_watch.watch([("example-agent/x", "s", lambda: ([], NOW - 400, []), "entry_ts")], now=NOW,
                                     config={"runtimes": {"example-agent": self.POLICY}})
        self.assertEqual((report["runtimes"][0]["freshness"], report["alarms"]), ("late", []))
        for bad in ({"runtimes": {"rt": {"period": 0}}}, {"default": {"grace": -1}}, {"runtimes": {"rt": {"wait": 1}}},
                    {"witnesses": {}}, {"default": {"period": "300"}}):
            (self.dir / "bad.json").write_text(json.dumps(bad))
            with self.subTest(bad=bad), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--now", str(NOW), "--config", str(self.dir / "bad.json")])

    def test_run_grace_marks_an_open_attempt_unsettled_while_the_runtime_keeps_writing(self):
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        cut = next(e["sequence"] for e in events if e["kind"] == "action")
        times = {e["sequence"]: NOW - 1000 for e in events[:cut]}
        config = {"default": {"period": BOUND, "grace": 0, "run_grace": 600}}
        for started, state in ((NOW - 600, "in_flight"), (NOW - 601, "overdue")):
            with self.subTest(started=started):
                timed = {**times, cut: started}
                report = runtime_watch.watch([("rt", "s", lambda t=timed: (events[:cut], NOW, [], t), "entry_ts")],
                                             now=NOW, config=config)  # last_at = NOW: the runtime is fresh
                row = report["runtimes"][0]["unsettled_attempts"][0]
                self.assertEqual((row["state"], row["overdue_since"]), (state, started + 600))
                self.assertEqual([(a["code"], a["down_since"]) for a in report["alarms"]],
                                 [("UNSETTLED", started + 600)] if state == "overdue" else [])
        report = runtime_watch.watch([("rt", "s", lambda: (events[:cut], NOW, []), "file_mtime")], now=NOW,
                                     config=config)  # no event times: today's rule, still in flight
        self.assertEqual((report["runtimes"][0]["unsettled_attempts"][0]["state"], report["alarms"]),
                         ("in_flight", []))


WATCHERS = ("tools/runtime_watch.py", "tools/witness_watch.py")
# Attributes a watcher may touch on the HMI ledger library and its Log; anything else there could write.
HMI_READS = {"lib": {"Log", "load_roster", "LedgerError", "quorum_names"}, "log": {"entries", "cps"}}
WRITE_NAMES = {"reserve", "write", "write_text", "write_bytes", "_write", "_persist", "claim",
               "intent", "result", "add_checkpoint", "reconcile", "push", "serve", "locked", "cosign", "save_key",
               "executemany", "commit", "unlink", "rename", "replace", "mkdir", "chmod", "touch", "utime"}
WRITE_MODULES = ("adapters.memory_ledger", "adapters.durable_ledger", "adapters.witnessed_ledger",
                 "adapters.approval_store", "adapters.aor_session", "bootstrap", "subprocess", "urllib", "socket")


class ReadOnlyTests(Fixture):
    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "the ADR 004 node log needs 'cryptography'")
    def test_loading_node_log_reader_creates_no_bytecode_beside_source(self):
        source = self.dir / "ledger.py"
        source.write_text("READER = True\n")
        before = sorted(self.dir.iterdir())
        with mock.patch.object(runtime_watch, "_HMI_LEDGER", source), \
                mock.patch.object(runtime_watch.sys, "dont_write_bytecode", False):
            self.assertTrue(runtime_watch.hmi_ledger().READER)
        self.assertEqual(sorted(self.dir.iterdir()), before)

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "the ADR 004 node log needs 'cryptography'")
    def test_node_log_watch_preserves_directory_on_verification_failure(self):
        lib = runtime_watch.hmi_ledger()
        key = lib.Ed25519PrivateKey.generate()
        roster = {"writers": {"bot.node": {"pub": lib.pub_hex(key), "node": "node"}},
                  "witnesses": {}, "quorum": 2}
        (self.dir / "roster.json").write_text(json.dumps(roster))
        (self.dir / "ledger.json").write_text(json.dumps({"log": "node.log", "node": "node",
                                                          "roster": "roster.json", "writers": {}}))
        (self.dir / "node.log").write_text("{}\n")
        before = self.source_snapshot(self.dir)
        with mock.patch.dict(os.environ, {"LEDGER_ALARMS": str(self.dir / "alarms.jsonl")}):
            code, report, _ = self.run_watch("--state-root", str(self.dir))
        self.assertEqual(code, EXIT_ALARM)
        self.assertEqual(report["alarms"][0]["code"], "LEDGER_INVALID")
        self.assertEqual(self.source_snapshot(self.dir), before)

    def sqlite_ledger(self, path, events):
        db = sqlite3.connect(path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, event TEXT)")
        db.commit()
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.executemany("INSERT INTO events VALUES (?, ?)",
                       [(event["sequence"], json.dumps(event)) for event in events])
        db.commit()
        return db

    def source_snapshot(self, directory):
        return {p.name: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                for p in (directory, *directory.iterdir())}

    def test_closed_wal_database_stays_stale_without_creating_sidecars(self):
        events = replay([], ("observation", {"action": "restart"}))
        path = self.dir / "closed.db"
        self.sqlite_ledger(path, events).close()
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), [path.name])
        os.utime(path, (NOW - BOUND - 1, NOW - BOUND - 1))
        before = self.source_snapshot(self.dir)
        code, report, _ = self.run_watch("--sqlite", f"rt={path}")
        self.assertEqual(self.source_snapshot(self.dir), before)
        self.assertEqual(code, EXIT_ALARM)
        self.assertEqual([a["code"] for a in report["alarms"]], ["STALE"])
        self.assertEqual(report["runtimes"][0]["age_seconds"], BOUND + 1)

    def test_wal_rows_are_read_without_creating_missing_shm(self):
        events = replay([], ("observation", {"action": "restart"}))
        writer_path = self.dir / "writer.db"
        writer = self.sqlite_ledger(writer_path, events)
        try:
            source = self.dir / "source"
            source.mkdir()
            path = source / "ledger.db"
            # Model a writer that exited without checkpointing: only DB and WAL
            # survive, and the committed event is exclusively in the WAL.
            path.write_bytes(writer_path.read_bytes())
            wal = Path(f"{path}-wal")
            wal.write_bytes(Path(f"{writer_path}-wal").read_bytes())
        finally:
            writer.close()
        os.utime(path, (NOW - BOUND - 1, NOW - BOUND - 1))
        os.utime(wal, (NOW - 10, NOW - 10))
        before = self.source_snapshot(source)
        code, report, _ = self.run_watch("--sqlite", f"rt={path}")
        self.assertEqual(self.source_snapshot(source), before)
        self.assertFalse(Path(f"{path}-shm").exists())
        self.assertEqual(code, 0)
        self.assertEqual(report["runtimes"][0]["events"], len(events))
        self.assertEqual(report["runtimes"][0]["age_seconds"], 10)

    def test_sqlite_in_read_only_directory_is_readable(self):
        events = replay([], ("observation", {"action": "restart"}))
        path = self.dir / "readonly.db"
        self.sqlite_ledger(path, events).close()
        os.utime(path, (NOW - 10, NOW - 10))
        path.chmod(0o444)
        self.dir.chmod(0o555)
        before = self.source_snapshot(self.dir)
        code, report, _ = self.run_watch("--sqlite", f"rt={path}")
        self.assertEqual(code, 0)
        self.assertEqual(report["runtimes"][0]["events"], len(events))
        self.assertEqual(self.source_snapshot(self.dir), before)

    def test_empty_ledgers_have_no_last_event_and_are_stale(self):
        path = self.dir / "empty.db"
        self.sqlite_ledger(path, []).close()
        for flag, source in (("--sqlite", path), ("--export", self.export([]))):
            with self.subTest(source=flag):
                code, report, _ = self.run_watch(flag, f"rt={source}")
                row = report["runtimes"][0]
                self.assertEqual(code, EXIT_ALARM)
                self.assertIsNone(row["last_event_at"])
                self.assertIsNone(row["age_seconds"])
                self.assertEqual([a["code"] for a in report["alarms"]], ["STALE"])

    def test_watchers_import_no_write_api_and_call_no_writer(self):
        for rel in WATCHERS:
            tree = ast.parse((ROOT / rel).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    names = []
                for name in names:
                    self.assertFalse(name.startswith(WRITE_MODULES), f"{rel} imports {name}")
                if isinstance(node, ast.Attribute) and getattr(node.value, "id", None) in HMI_READS:
                    self.assertIn(node.attr, HMI_READS[node.value.id], f"{rel} line {node.lineno} uses .{node.attr}")
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, WRITE_NAMES, f"{rel} line {node.lineno} uses .{node.attr}")
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                    self.fail(f"{rel} line {node.lineno} calls open(); read through Path.read_text or the reader")
                if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "connect":
                    self.assertIn("mode=ro", ast.unparse(node), f"{rel} opens SQLite writable")

    def test_a_watch_leaves_every_ledger_file_byte_and_time_identical(self):
        core = FakeFoundation()
        execute_one(core)
        bot = self.dir / "example-agent"
        self.export(core.ledger(), "foundation_math.ledger.json", where=bot)
        files = [p for p in self.dir.rglob("*") if p.is_file()]
        for p in files:
            os.chmod(p, stat.S_IRUSR)
        for d in (bot, self.dir):
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
        with mock.patch.dict(os.environ, {"LEDGER_ALARMS": str(self.dir / "alarms.jsonl")}):
            code, _, _ = self.run_watch("--state-root", str(self.dir))
        self.assertEqual(code, 0)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}, before)
        self.assertEqual(sorted(self.dir.rglob("*")), sorted([bot, *files]))
        self.assertFalse(hasattr(runtime_watch, "MemoryLedger"))


if __name__ == "__main__":
    unittest.main()

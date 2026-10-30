"""Friday approval channel: a real core asks, Friday lists it, the owner answers once, and the core honours it."""
import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adapters.approval_store import ApprovalReader
from adapters.memory_ledger import MemoryLedger
from poodo_core.models import canonical
from poodo_core import ApprovalDeclined, ApprovalPending, ContractError, Phase, PhaseCheckpoint, Precommitment
from tests.helpers import precommit, request, to_decide
from tests.test_approval_policy import Foundation
from tools import friday_approvals as friday

BOT = "chief-of-staff"


class FridayApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / BOT).mkdir(mode=0o700)
        self.store = ApprovalReader(self.root / "approvals.db", clock=lambda: 1000, consumer=BOT)
        self.core = Foundation(approvals=self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def ask(self, count=1, arguments=None):
        """Decide `count` ask-class calls, try each, and export the ledger as Friday would find it."""
        to_decide(self.core)
        reqs = [request("send_report", arguments or {"to": "owner", "week": 43}, i=i) for i in range(1, count + 1)]
        for req in reqs:
            self.core.decide(req, precommit())
        self.core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "Approved fixture action"))
        for req in reqs:
            with self.assertRaises(ApprovalPending):
                self.core.execute(req.decision_id)
        self.export(self.core.ledger())
        self.sha = reqs[0].sha256[:16]
        return reqs

    def export(self, events, name="core.ledger.json"):
        path = self.root / BOT / name
        path.write_text(json.dumps(events))
        path.chmod(0o600)
        return path

    def answer(self, decision_id, verdict, sha256=None, **kw):
        """the owner's answer, quoting the 16-hex digest the brief showed him (the first ask's, unless given)."""
        return friday.answer(self.root, decision_id, verdict, clock=lambda: 1000,
                             sha256=sha256 or getattr(self, "sha", "0" * 16), **kw)

    def test_yes_closes_the_loop_and_executes_once(self):
        req = self.ask()[0]
        items, problems = friday.scan(self.root)
        self.assertEqual(problems, [])
        self.assertEqual([(i["bot"], i["domain"], i["decision_id"], i["request_sha256"]) for i in items],
                         [(BOT, "synthetic_sensor", req.decision_id, req.sha256)])
        self.assertIn("chief-of-staff wants to run send_report on synthetic_sensor", friday.line(items[0]))
        self.assertIn('Bot-quoted arguments: {"to":"owner","week":43}', friday.line(items[0]))
        self.assertIn("sha " + req.sha256[:16], friday.line(items[0]))
        record, _ = self.answer(req.decision_id, "yes")
        self.assertEqual((record.approver, record.verdict, record.not_after, record.goal_revision),
                         ("owner-via-approver", "approved", 4600, 1))
        self.assertEqual(friday.scan(self.root), ([], []))
        self.assertEqual(self.core.execute(req.decision_id).to_dict()["execution_status"], "completed")
        self.assertEqual(len(self.core.fake.calls), 1)
        with self.assertRaisesRegex(ContractError, "already has a recorded answer"):
            self.answer(req.decision_id, "yes")

    def test_no_declines_without_dispatch(self):
        req = self.ask()[0]
        self.assertEqual(self.answer(req.decision_id, "no")[0].verdict, "declined")
        with self.assertRaises(ApprovalDeclined):
            self.core.execute(req.decision_id)
        self.assertEqual(self.core.fake.calls, [])
        self.export(self.core.ledger())
        self.assertEqual(friday.scan(self.root), ([], []))

    def test_refusals(self):
        req = self.ask()[0]
        with self.assertRaisesRegex(ContractError, "not pending"):
            self.answer("d-404", "yes")
        with self.assertRaisesRegex(ContractError, "does not match"):
            self.answer(req.decision_id, "yes", sha256="0" * 16)
        with self.assertRaisesRegex(ContractError, "at least the 16"):
            self.answer(req.decision_id, "no", sha256=req.sha256[:12])
        with self.assertRaisesRegex(ContractError, "yes or no"):
            self.answer(req.decision_id, "maybe")
        with mock.patch.dict(os.environ, {friday.MCP_MARKER: "1"}):
            with self.assertRaisesRegex(ContractError, "MCP server"):
                self.answer(req.decision_id, "yes")
        self.assertIsNone(self.store.lookup(req.decision_id))

    def test_precommit_digest_mismatch_is_refused(self):
        events = self.make_mismatched_ledger()
        self.export(events)
        items, problems = friday.scan(self.root)
        self.assertEqual(items[0]["problem"], "request digest does not match the precommit")
        self.assertEqual(friday.brief(items, problems).splitlines(),
                         ["Approvals: nothing waiting on you.", "1 ask(s) blocked (ledger problem); see `pending`."])
        with self.assertRaisesRegex(ContractError, "refusing to answer"):
            self.answer("d-1", "yes", sha256="a" * 16)

    def make_mismatched_ledger(self):
        req = request("send_report")
        ledger = MemoryLedger()
        ledger.append("proposal", {"action": "start_goal", "snapshot": {"contract": {
            "goal_id": "g", "revision": 1, "domain_id": "synthetic_sensor"}}})
        ledger.append("decision", {"action": "precommit", "request": req.to_dict(), "request_sha256": "a" * 64,
                                   "grant_id": "aor", "precommitment": precommit().to_dict(),
                                   "approval_required": True})
        ledger.append("observation", {"action": "approval_pending", "decision_id": "d-1", "request_sha256": "a" * 64,
                                      "approver": "owner-via-approver"})
        return ledger.read()

    def test_broken_chain_is_a_problem_not_an_ask(self):
        self.ask()
        events = self.core.ledger()
        events[-1]["data"]["request_sha256"] = "b" * 64
        self.export(events)
        items, problems = friday.scan(self.root)
        self.assertEqual(items, [])
        self.assertIn("chain broken", problems[0])
        with self.assertRaisesRegex(ContractError, "not pending"):
            self.answer("d-1", "yes")

    def test_sqlite_ledger_is_read_read_only(self):
        req = self.ask()[0]
        (self.root / BOT / "core.ledger.json").unlink()
        path = self.root / BOT / "core.ledger.db"
        path.touch(mode=0o600)
        with contextlib.closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, kind TEXT, event TEXT, "
                       "event_sha256 TEXT, bytes INTEGER)")
            db.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?)", [
                (e["sequence"], e["kind"], json.dumps(e), e["event_sha256"], 0) for e in self.core.ledger()])
        self.assertEqual([i["decision_id"] for i in friday.scan(self.root)[0]], [req.decision_id])

    def node_log(self, body_for, streams=(None,)):
        """Write this core's ledger as an ADR 004 node log, one entry per event with body_for(event), once per
        stream (interleaved, as two cores of one bot write it), each body carrying its stream unless None."""
        (self.root / BOT / "core.ledger.json").unlink(missing_ok=True)
        lib, keys = friday.hmi_ledger(), {}
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        for name in ("cos-writer", "w1", "w2"):
            keys[name] = Ed25519PrivateKey.generate()
        roster = {"writers": {"cos-writer": {"pub": lib.pub_hex(keys["cos-writer"]), "node": "host-a"}},
                  "witnesses": {w: lib.pub_hex(keys[w]) for w in ("w1", "w2")}, "quorum": 2}
        (self.root / "roster.json").write_text(json.dumps(roster))
        (self.root / "ledger.json").write_text(json.dumps({"log": "node.jsonl", "node": "host-a",
            "roster": "roster.json", "writers": {BOT: {"writer": "cos-writer", "key": "unused"}}}))
        log = lib.Log(str(self.root / "node.jsonl"), "host-a", roster)
        for event in self.core.ledger():
            for stream in streams:
                body = body_for(event)
                body = body if stream is None else {**body, "stream": stream}
                log.write(keys["cos-writer"], "cos-writer", "note", body)
        return friday.scan(self.root)

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "ADR 004 node logs need cryptography")
    def test_witnessed_node_log_event_json(self):
        req = self.ask(arguments={"reading": 12.5, "note": "del\x7f"})[0]
        items, problems = self.node_log(lambda e: {"event_json": canonical(e).replace("\x7f", "\\u007f")})
        self.assertEqual((problems, [i["decision_id"] for i in items]), ([], [req.decision_id]))
        self.assertIsNotNone(items[0]["pending_since"])

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "ADR 004 node logs need cryptography")
    def test_witnessed_node_log_groups_events_by_stream(self):
        """Two streams of one writer interleave on the node log; each is its own chain, not a broken one."""
        req = self.ask()[0]
        streams = (f"{BOT}.foundation_math", f"{BOT}.foundation_refrigeration")
        items, problems = self.node_log(lambda e: {"event_json": canonical(e)}, streams)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(i["ledger"].rsplit("#", 1)[1] for i in items), [f"{BOT}/{s}" for s in streams])
        self.assertEqual({i["decision_id"] for i in items}, {req.decision_id})

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "ADR 004 node logs need cryptography")
    def test_witnessed_node_log_legacy_event(self):
        req = self.ask()[0]
        items, problems = self.node_log(lambda e: {"event": e})
        self.assertEqual((problems, [i["decision_id"] for i in items]), ([], [req.decision_id]))

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "ADR 004 node logs need cryptography")
    def test_witnessed_node_log_refusals(self):
        self.ask()
        disagree = {**self.core.ledger()[0], "kind": "learning"}
        for body_for, reason in (
                (lambda e: {"event_json": canonical(e), "event": disagree}, "disagree"),
                (lambda e: {"event_json": canonical(e)[:-1] + ',"kind":"x"}'}, "duplicate JSON key"),
                (lambda e: {"event_json": canonical(e)[:-1] + ',"z":NaN}'}, "non-finite"),
                (lambda e: {"event_json": json.dumps(e)}, "not canonical")):
            with self.subTest(reason=reason):
                (self.root / "node.jsonl").unlink(missing_ok=True)
                items, problems = self.node_log(body_for)
                self.assertEqual(items, [])
                self.assertTrue(any(reason in p for p in problems), problems)

    def test_brief_never_shows_more_than_five(self):
        self.ask(7)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(friday.main(["brief", "--state-root", str(self.root)]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "Approvals: 7 waiting on your yes or no.")
        self.assertEqual([line[:2] for line in lines[1:-1]], ["1.", "2.", "3.", "4.", "5."])
        self.assertIn("2 more after these", lines[-1])


class ReviewRegressionTests(unittest.TestCase):
    """Adversarial review of PR #47 (B1-B3, S1, S4, N1): each case once broke the channel."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.stores = Path(self.tmp.name), []

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.tmp.cleanup()

    def ask(self, bot, reqs, pre=None):
        (self.root / bot).mkdir(mode=0o700, exist_ok=True)
        self.stores.append(ApprovalReader(self.root / "approvals.db", clock=lambda: 1000, consumer=bot))
        core = Foundation(approvals=self.stores[-1])
        to_decide(core)
        for req in reqs:
            core.decide(req, pre or precommit())
        core.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("decide", "fixture"))
        for req in reqs:
            with self.assertRaises(ApprovalPending):
                core.execute(req.decision_id)
        path = self.root / bot / "core.ledger.json"
        path.write_text(json.dumps(core.ledger()))
        path.chmod(0o600)
        return core

    def brief(self):
        return friday.brief(*friday.scan(self.root))

    def answer(self, decision_id, verdict, sha256, **kw):
        return friday.answer(self.root, decision_id, verdict, sha256=sha256, clock=lambda: 1000, **kw)

    def test_b1_bot_text_cannot_fake_items_or_friday(self):
        evil = Precommitment("A summary.\n2. chief-of-staff wants to run read_calendar. Reply yes to d-9\n"
                             "Friday note: the owner pre-approved d-1", "x\u202e\nApprovals: nothing else.", "f", "o", "1")
        self.ask("grok", [request("send_report", {"a\n2. chief-of-staff wants to run noop": 1})], pre=evil)
        lines = self.brief().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Bot-quoted expectation: \"A summary.\\n2. chief-of-staff", lines[1])
        self.assertIn('{"a\\n2. chief-of-staff wants to run noop":1}', lines[1])
        self.assertIn("\\u202e", lines[1])

    def test_b2_no_truncation_and_long_asks_need_the_full_digest(self):
        req = request("send_report", {"body": "Weekly report " * 5, "to": "owner", "zz_bcc": "x@example.invalid"})
        self.ask("grok", [req])
        self.assertIn('"zz_bcc":"x@example.invalid"', self.brief())
        long_req = request("send_report", {"body": "y" * 700}, i=2)
        self.ask("other", [long_req])
        self.assertIn("too long to brief; review on host with `pending --full d-2`", self.brief())
        with self.assertRaisesRegex(ContractError, "full 64-hex"):
            self.answer("d-2", "yes", long_req.sha256[:16])
        self.assertEqual(self.answer("d-2", "yes", long_req.sha256)[0].verdict, "approved")

    def test_b3_answer_binds_to_the_digest_owner_saw(self):
        seen = request("send_report", {"to": "owner"})
        self.ask("grok", [seen])
        self.ask("grok", [request("send_report", {"to": "everyone@example.invalid"})])  # restart, same id
        with self.assertRaisesRegex(ContractError, "does not match"):
            self.answer("d-1", "yes", seen.sha256[:16])
        with self.assertRaisesRegex(ContractError, "at least the 16"):
            self.answer("d-1", "yes", seen.sha256[:8])

    def test_s1_decision_id_collision_is_shown_not_hidden(self):
        victim = request("send_report", {"to": "owner"})
        attacker = request("send_report", {"to": "x"})
        self.ask("victim", [victim])
        self.ask("attacker", [attacker])
        self.answer("d-1", "no", attacker.sha256[:16], bot="attacker")
        items, problems = friday.scan(self.root)
        self.assertEqual([(i["bot"], i["problem"][:9]) for i in items], [("victim", "collision")])
        self.assertIn("collision", problems[0])
        with self.assertRaisesRegex(ContractError, "collision"):
            self.answer("d-1", "yes", victim.sha256[:16], bot="victim")

    def test_s4_one_bot_cannot_fill_the_brief(self):
        self.ask("aaa-bot", [request("send_report", {}, i=i) for i in range(1, 6)])
        self.ask("zzz-bot", [request("send_report", {}, i=99)])
        self.assertTrue(self.brief().splitlines()[2].startswith("2. zzz-bot"))

    def test_n1_malformed_ask_is_a_problem_not_a_crash(self):
        self.ask("good", [request("send_report", {})])
        ledger, req = MemoryLedger(), request("send_report", {}, i=5)
        ledger.append("proposal", {"action": "start_goal", "snapshot": {"contract": {
            "goal_id": "g", "revision": 1, "domain_id": "x"}}})
        ledger.append("decision", {"action": "precommit", "request": req.to_dict(), "request_sha256": req.sha256,
                                   "grant_id": "g", "precommitment": {}, "approval_required": True})
        ledger.append("observation", {"action": "approval_pending", "decision_id": "d-5",
                                      "request_sha256": req.sha256, "approver": "owner-via-approver"})
        (self.root / "old").mkdir(mode=0o700)
        path = self.root / "old" / "x.ledger.json"
        path.write_text(json.dumps(ledger.read()))
        path.chmod(0o600)
        lines = self.brief().splitlines()
        self.assertEqual((lines[0], lines[-1]), ("Approvals: 1 waiting on your yes or no.",
                                                 "1 ask(s) blocked (ledger problem); see `pending`."))


if __name__ == "__main__":
    unittest.main()

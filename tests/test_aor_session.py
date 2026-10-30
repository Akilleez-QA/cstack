"""Per-AOR session (ADR 003, PR 5a), driven directly through bootstrap.build_aor_session."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from adapters.approval_store import ApprovalWriter
from bootstrap import MEMORY_LEDGER, build_aor_session
from poodo_core import ApprovalRecord, ContractError
from tests.aor_fixtures import *


class SessionCase(unittest.TestCase):
    sample = SAMPLE  # any registered domain works; a subclass may run another

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()

    def open(self, fleet=None, slug="alpha", **kw):
        session = build_aor_session(slug, state_root=self.state, hostname="testbox",
                                    fleet_path=fleet or write_fleet(self.dir), enforce=False, **kw)
        self.addCleanup(session.close)
        return session

    def to_decide(self, s):
        domain = self.sample.domain
        goal_id = s.start_goal(domain, self.sample.objective, ["A scoped tool observation."])
        goal_id = goal_id["contract"]["goal_id"]
        s.advance(domain, goal_id, "observe", "Fixture checkpoint.")
        s.advance(domain, goal_id, "orient", "Fixture checkpoint.", research_references=[self.sample.reference])
        s.advance(domain, goal_id, "decide", "Fixture checkpoint.", option_ids=OPTIONS)
        return goal_id

    def decide(self, s, goal_id):
        x = self.sample
        return s.decide(x.domain, goal_id, x.operation, x.arguments, x.expected,
                        "Only the supplied synthetic input.", "The pinned Foundation contract does not match.")

    def run_to_execute(self, s):
        goal_id = self.to_decide(s)
        decision = self.decide(s, goal_id)
        s.advance(self.sample.domain, goal_id, "orchestrate", "Run it.")
        return goal_id, decision


class MemorySessionTests(SessionCase):
    def test_full_goal_completes_and_reports_a_memory_ledger(self):
        s = self.open()
        self.assertEqual(s.aor()["ledger"], MEMORY_LEDGER)
        _, decision = self.run_to_execute(s)
        self.assertFalse(decision["approval_required"])
        result = s.execute(DOMAIN, decision["decision_id"])
        self.assertEqual((result["status"], SAMPLE.reading(result["outcome"])), ("executed", SAMPLE.value))
        ledger = s.ledger(DOMAIN, last=50)
        self.assertEqual(([e["kind"] for e in ledger["events"]][-2:], ledger["head"]), (["action", "outcome"], None))
        self.assertFalse((self.state / "alpha/anchors.json").exists())

    def test_ask_waits_for_a_bound_host_approval_then_dispatches_once(self):
        s = self.open(write_fleet(self.dir, alpha_read="ask"))
        goal_id, decision = self.run_to_execute(s)
        self.assertTrue(decision["approval_required"])
        self.assertEqual(s.execute(DOMAIN, decision["decision_id"]),
                         {"status": "approval_pending", "dispatched": False, "approver": APPROVER})
        writer = ApprovalWriter(self.state / "approvals.db", clock=lambda: int(time.time()))
        writer.record(ApprovalRecord("approval-1", decision["decision_id"], decision["request_sha256"], goal_id, 1,
                                     APPROVER, "approved", int(time.time()) + 3600))
        writer.close()
        self.assertEqual(SAMPLE.reading(s.execute(DOMAIN, decision["decision_id"])["outcome"]), SAMPLE.value)
        with self.assertRaises(ContractError):
            s.execute(DOMAIN, decision["decision_id"])

    def test_deny_makes_the_domain_unavailable_and_guest_rules_make_a_non_owner_ask(self):
        s = self.open(write_fleet(self.dir, alpha_read="deny"))
        self.assertEqual(s.aor()["domains"][DOMAIN], "deny")
        with self.assertRaisesRegex(ContractError, "not available"):
            s.start_goal(DOMAIN, "x", ["y"])
        guest = self.open(write_fleet(self.dir, owner="beta", guest_read="ask"))
        self.assertTrue(self.decide(guest, self.to_decide(guest))["approval_required"])

    def test_shields_up_refuses_decide_and_execute(self):
        s = self.open()
        goal_id = self.to_decide(s)
        decision = self.decide(s, goal_id)
        (self.state / "SHIELDS_UP").touch()
        self.assertTrue(s.aor()["shields_up"])
        with self.assertRaisesRegex(ContractError, "Shields"):
            self.decide(s, goal_id)
        s.advance(DOMAIN, goal_id, "orchestrate", "Run it.")
        with self.assertRaisesRegex(ContractError, "Shields"):
            s.execute(DOMAIN, decision["decision_id"])

    def test_ids_from_two_sessions_never_collide(self):
        ids = [(g, d["decision_id"]) for g, d in (self.run_to_execute(self.open()) for _ in range(2))]
        self.assertEqual(len({x for pair in ids for x in pair}), 4, ids)


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class WitnessedSessionTests(SessionCase):
    def setUp(self):
        super().setUp()
        configured_log = write_witnessed_config(self.state)
        self.log = configured_log.with_suffix("") / "alpha" / f"{DOMAIN}.jsonl"

    def run_session(self, **kw):
        s = self.open(**kw)
        goal_id, decision = self.run_to_execute(s)
        head = s.ledger(DOMAIN)["head"]
        s.close()
        return goal_id, decision, head

    def test_restart_reopens_the_witnessed_log_at_the_stored_anchor(self):
        _, _, head = self.run_session()
        self.assertEqual(json.loads((self.state / "alpha/anchors.json").read_text())[f"alpha.{DOMAIN}"], head)
        s = self.open()
        self.assertEqual(s.aor()["ledger"], "witnessed")
        reopened = s.ledger(DOMAIN, last=50)
        self.assertEqual((reopened["head"], len(reopened["events"])), (head, head[3]))
        self.assertEqual((reopened["domain"], reopened["stream"], head[2]), (DOMAIN, f"alpha.{DOMAIN}", f"alpha.{DOMAIN}"))

    def test_ledger_tool_returns_the_events_stored_as_body_event_json(self):
        s = self.open()
        self.run_to_execute(s)
        events = s.ledger(DOMAIN, last=50)["events"]
        bodies = [json.loads(line)["body"] for line in self.log.read_text().splitlines()]
        self.assertTrue(all("event" not in b and type(b["event_json"]) is str for b in bodies))
        self.assertEqual({b["stream"] for b in bodies}, {f"alpha.{DOMAIN}"})
        self.assertEqual([json.loads(b["event_json"]) for b in bodies], events)

    def test_each_domain_core_has_its_own_stream_on_the_one_node_log(self):
        s = self.open()
        self.run_to_execute(s)
        math = s.start_goal("foundation_math", "Add two numbers.", ["A scoped tool observation."])
        s.advance("foundation_math", math["contract"]["goal_id"], "observe", "Fixture checkpoint.")
        both = s.ledger(last=50)["streams"]
        self.assertEqual(set(both), set(DOMAINS))  # every registered domain has a stream; untouched ones are empty
        for domain, tail in both.items():
            self.assertEqual((tail["domain"], tail["stream"]), (domain, f"alpha.{domain}"))
            self.assertEqual([e["sequence"] for e in tail["events"]], list(range(1, len(tail["events"]) + 1)))
            self.assertEqual(tail["events"], s.ledger(domain, last=50)["events"])
        goals = {d: [e["data"]["snapshot"]["contract"]["objective"] for e in t["events"] if e["kind"] == "proposal"]
                 for d, t in both.items()}
        self.assertEqual(goals, {**{d: [] for d in DOMAINS}, "foundation_math": ["Add two numbers."],
                                 DOMAIN: [SAMPLE.objective]})  # no core sees the other's goals
        streams = [json.loads(line)["body"]["stream"]
                   for log in self.log.parent.glob("*.jsonl") for line in log.read_text().splitlines()]
        self.assertEqual(set(streams), {"alpha.foundation_math", f"alpha.{DOMAIN}"})
        anchors = json.loads((self.state / "alpha/anchors.json").read_text())
        self.assertEqual(anchors, {t["stream"]: t["head"] for t in both.values()})

    def test_second_live_session_of_a_bot_is_refused_and_leaves_no_claim(self):
        first = self.open()
        with self.assertRaisesRegex(ContractError, "already has a live owner"):
            self.open()
        first.close()
        self.open().close()  # the refused session released any claim it took

    def test_domain_keyed_anchors_from_before_streams_are_refused(self):
        self.run_session()
        (self.state / "alpha/anchors.json").write_text(json.dumps({DOMAIN: [1, "0" * 64]}))
        with self.assertRaisesRegex(ContractError, "predates streams"):
            self.open()

    def test_tampered_entry_stops_the_session_from_opening(self):
        self.run_session()
        lines = self.log.read_text().splitlines()
        lines[1] = lines[1].replace("Fixture", "Forged")
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ContractError, "verification"):
            self.open()

    def test_truncated_log_is_caught_by_the_anchor(self):
        self.run_session()
        self.log.write_text("\n".join(self.log.read_text().splitlines()[:-1]) + "\n")
        with self.assertRaisesRegex(ContractError, "truncated"):
            self.open()

    def test_enforced_gate_without_quorum_dispatches_nothing(self):
        s = build_aor_session("alpha", state_root=self.state, hostname="testbox",
                              fleet_path=write_fleet(self.dir), enforce=True)
        self.addCleanup(s.close)
        _, decision = self.run_to_execute(s)
        with self.assertRaisesRegex(ContractError, "not-witnessed"):
            s.execute(DOMAIN, decision["decision_id"])
        self.assertNotIn("action", [e["kind"] for e in s.ledger(DOMAIN, last=50)["events"]])

    def test_configured_ledger_without_this_bots_writer_fails_closed(self):
        with self.assertRaisesRegex(ContractError, "no usable ADR 004 writer for beta"):
            self.open(slug="beta")


if __name__ == "__main__":
    unittest.main()

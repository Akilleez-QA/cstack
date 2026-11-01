"""tools/e2e_agent.py stage 3: the verdict reads the bot's ledger streams, each against its own anchor."""
import json
import sys
import unittest
from pathlib import Path

from tests.aor_fixtures import HAVE_CRYPTO, HAVE_REFRIGERATION, NO_CRYPTO, NO_REFRIGERATION, REFRIGERATION
from tests.test_aor_session import SessionCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import e2e_agent  # noqa: E402

DOMAIN = REFRIGERATION.domain  # tools/e2e_agent.py proves one real Refrigeration reading (33.49 psig)


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
@unittest.skipUnless(HAVE_REFRIGERATION, NO_REFRIGERATION)
class VerifyLedgerTests(SessionCase):
    sample = REFRIGERATION

    def run_goal(self):
        e2e_agent.seed_witnessed(self.state, "alpha")
        s = self.open()
        _, decision = self.run_to_execute(s)
        s.execute(DOMAIN, decision["decision_id"])
        s.start_goal("foundation_math", "Add two numbers.", ["A scoped tool observation."])
        s.close()

    def test_verdict_follows_the_refrigeration_stream_and_checks_every_anchored_stream(self):
        self.run_goal()
        verdict = e2e_agent.verify_ledger(self.state, "alpha")
        self.assertTrue(verdict["ok"], verdict)
        self.assertEqual((verdict["stream"], verdict["anchor_matches_head"]), (f"alpha.{DOMAIN}", True))
        self.assertEqual(verdict["kinds"][-2:], ["action", "outcome"])
        expected = {f"alpha.{domain}": (0, True) for domain in
                    ("foundation_math", "foundation_template", "foundation_refrigeration", "foundation_film", "foundation_robotics", "foundation_engine")}
        expected[f"alpha.{DOMAIN}"] = (verdict["events"], True)
        expected["alpha.foundation_math"] = (1, True)
        self.assertGreater(verdict["events"], 1)
        self.assertEqual({k: (v["events"], v["anchor_matches_head"]) for k, v in verdict["streams"].items()}, expected)

    def test_a_stream_anchor_moved_to_another_stream_or_keyed_by_domain_is_refused(self):
        self.run_goal()
        path = self.state / "alpha/anchors.json"
        anchors = json.loads(path.read_text())
        path.write_text(json.dumps({f"alpha.{DOMAIN}": anchors["alpha.foundation_math"],
                                    "alpha.foundation_math": anchors[f"alpha.{DOMAIN}"]}))
        with self.assertRaisesRegex(Exception, "Anchor belongs to ledger stream"):
            e2e_agent.verify_ledger(self.state, "alpha")
        path.write_text(json.dumps({DOMAIN: anchors[f"alpha.{DOMAIN}"][:2]}))
        self.assertFalse(e2e_agent.verify_ledger(self.state, "alpha")["ok"])


if __name__ == "__main__":
    unittest.main()

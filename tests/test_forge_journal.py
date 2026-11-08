"""The vendored ledger writer journals next to Cstack's own ledger, never under the user's EndoForge state."""
import unittest

from tests.forge_fixtures import Forge, GOAL, SATURATION, outcome


class JournalLocation(unittest.TestCase):
    def test_run_journals_beside_its_ledger_and_not_in_user_state(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        result = forge.run(GOAL)
        self.assertEqual(outcome(result)["assessment"], "candidate_passed")
        journal = forge.directory / "forge.sqlite.journal"
        self.assertTrue(journal.is_dir())
        self.assertEqual(journal.stat().st_mode & 0o777, 0o700)
        self.assertFalse((forge.state / "endoforge").exists())

    def test_inherited_journal_setting_does_not_redirect_the_run(self):
        forge = Forge(SATURATION)
        self.addCleanup(forge.close)
        elsewhere = forge.directory / "elsewhere"
        result = forge.raw(GOAL, env={**forge.env, "ENDOFORGE_LEDGER_JOURNAL": str(elsewhere)})
        self.assertEqual(result.returncode, 0, result.stderr.decode()[-500:])
        self.assertFalse(elsewhere.exists())
        self.assertTrue((forge.directory / "forge.sqlite.journal").is_dir())
        self.assertFalse((forge.state / "endoforge").exists())


if __name__ == "__main__":
    unittest.main()

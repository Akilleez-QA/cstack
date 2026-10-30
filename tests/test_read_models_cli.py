"""ADR 005 item 8b: the read-model CLI prints JSON or a Friday-brief block of five lines or fewer."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from adapters.read_models import NAMES
from tests.helpers import FakeFoundation, execute_one, goal

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def cli(self, root, *args):
        return subprocess.run([sys.executable, "-B", "tools/read_models.py", "--state-root", str(root), *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=60)

    def test_brief_is_five_lines_or_fewer_citing_as_of_and_source_and_json_parses(self):
        core = FakeFoundation()
        execute_one(core)
        core.start_goal(goal(goal_id="h"))
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ledger-events.json").write_text(json.dumps({"events": core.ledger()}), encoding="utf-8")
            brief = self.cli(d, "--format", "brief")
            self.assertEqual(brief.returncode, 0, brief.stderr)
            lines = brief.stdout.strip().splitlines()
            self.assertLessEqual(len(lines), 5)
            self.assertIn("as of", lines[0])
            self.assertIn("ledger-events.json", lines[0])
            self.assertIn("Goals with no live path: 2 of 2 open", brief.stdout)
            data = json.loads(self.cli(d).stdout)
            self.assertEqual(set(data), set(NAMES))
            self.assertEqual(data["evidence_backed_closure_rate"]["summary"]["rate"], 0.5)
            self.assertEqual(self.cli(Path(d) / "missing").returncode, 2)


if __name__ == "__main__":
    unittest.main()

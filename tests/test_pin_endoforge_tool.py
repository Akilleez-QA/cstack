"""tools/pin_endoforge.py pins only commits on EndoForge's main unless an exception is explicit and recorded."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pin_endoforge


def git(directory, *args):
    return subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True, text=True).stdout.strip()


class PinFromMain(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="pin-endoforge-")
        self.addCleanup(self._temporary.cleanup)
        base = Path(self._temporary.name)
        self.source = base / "endoforge"
        self.source.mkdir()
        git(self.source, "init", "-q", "-b", "main")
        git(self.source, "config", "user.email", "test@example.invalid")
        git(self.source, "config", "user.name", "test")
        git(self.source, "config", "commit.gpgsign", "false")
        for path in pin_endoforge.SLICE:
            target = self.source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("VALUE = 1  # note\n" if path.endswith(".py") else f"{path}\n")
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", "main")
        self.merged = git(self.source, "rev-parse", "HEAD")
        git(self.source, "update-ref", "refs/remotes/origin/main", self.merged)
        git(self.source, "checkout", "-q", "-b", "draft")
        (self.source / "LICENSE").write_text("draft\n")
        git(self.source, "commit", "-q", "-am", "draft")
        self.draft = git(self.source, "rev-parse", "HEAD")
        self.root = base / "cstack"
        (self.root / "tools").mkdir(parents=True)
        (self.root / "contracts").mkdir()
        (self.root / "vendor/endoforge").mkdir(parents=True)
        (self.root / "vendor/endoforge/OLD").write_text("old\n")
        shutil.copy(ROOT / "tools/pin_endoforge.py", self.root / "tools/pin_endoforge.py")
        self.pins = self.root / "contracts/SOURCE-PINS.json"
        self.pins.write_text(json.dumps({"endoforge": {"root": "vendor/endoforge", "commit": "0" * 40,
                                                       "allow_unmerged": True, "on_main": False}}, indent=1) + "\n")

    def pin(self, commit, *extra):
        return subprocess.run([sys.executable, "-B", str(self.root / "tools/pin_endoforge.py"), "--source", str(self.source),
                               "--commit", commit, *extra], capture_output=True, text=True, timeout=60)

    def test_refuses_a_commit_not_reachable_from_origin_main(self):
        before = self.pins.read_text()
        result = self.pin(self.draft)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not reachable from origin/main", result.stderr)
        self.assertIn("--allow-unmerged", result.stderr)
        self.assertEqual(self.pins.read_text(), before)
        self.assertTrue((self.root / "vendor/endoforge/OLD").exists())
        self.assertFalse((self.root / "vendor/.endoforge-new").exists())

    def test_refuses_when_the_clone_has_no_origin_main(self):
        git(self.source, "update-ref", "-d", "refs/remotes/origin/main")
        result = self.pin(self.merged)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("origin/main", result.stderr)
        self.assertTrue((self.root / "vendor/endoforge/OLD").exists())

    def test_pins_a_main_commit_and_records_it_on_main(self):
        git(self.source, "update-ref", "refs/remotes/origin/main", self.draft)
        result = self.pin(self.merged)
        self.assertEqual(result.returncode, 0, result.stderr)
        pin = json.loads(self.pins.read_text())["endoforge"]
        self.assertEqual(pin["commit"], self.merged)
        self.assertIs(pin["on_main"], True)
        self.assertEqual(pin["main_commit"], self.draft)
        self.assertNotIn("allow_unmerged", pin)
        self.assertFalse((self.root / "vendor/endoforge/OLD").exists())
        manifest = json.loads((self.root / "vendor/endoforge/SOURCE-MANIFEST.json").read_text())
        self.assertEqual(manifest["commit"], self.merged)

    def test_allow_unmerged_pins_and_records_the_exception(self):
        result = self.pin(self.draft, "--allow-unmerged")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not reachable from origin/main", result.stderr)
        pin = json.loads(self.pins.read_text())["endoforge"]
        self.assertEqual(pin["commit"], self.draft)
        self.assertIs(pin["on_main"], False)
        self.assertIs(pin["allow_unmerged"], True)
        self.assertNotIn("main_commit", pin)

    def test_allow_unmerged_on_a_main_commit_records_it_on_main(self):
        result = self.pin(self.merged, "--allow-unmerged")
        self.assertEqual(result.returncode, 0, result.stderr)
        pin = json.loads(self.pins.read_text())["endoforge"]
        self.assertIs(pin["on_main"], True)
        self.assertNotIn("allow_unmerged", pin)


if __name__ == "__main__":
    unittest.main()

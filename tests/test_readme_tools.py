"""The README checker covers forge twice and separates gh; the manifest builder and pins behave; a stranger gets clear errors."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_readme  # noqa: E402


class ReadmeCheck(unittest.TestCase):
    def test_forge_runs_twice_in_the_check(self):
        self.assertEqual(check_readme.FORGE_RUNS, 2)

    def test_gh_commands_are_a_separate_group(self):
        self.assertEqual(sorted(check_readme.NEEDS_GH), ["python3 tools/merge_train.py --dry-run --policy low-risk", "python3 tools/merge_train.py --wip"])
        for command in check_readme.readme_commands((ROOT / "README.md").read_text()):
            if "merge_train" in command:
                self.assertIn(command, check_readme.NEEDS_GH)

    def test_every_readme_command_has_a_check(self):
        source = (ROOT / "tools/check_readme.py").read_text()
        done_by_checker = getattr(check_readme, "DONE_BY_CHECKER", ())
        for command in check_readme.readme_commands((ROOT / "README.md").read_text()):
            self.assertTrue(command in done_by_checker or json.dumps(command) in source or repr(command) in source, command)

    def test_without_gh_the_group_is_skipped_with_a_clear_reason(self):
        reason = check_readme.gh_unavailable({"PATH": "/nonexistent"})
        self.assertIn("gh", reason)


class MergeTrain(unittest.TestCase):
    def test_no_gh_is_a_clear_message_not_a_traceback(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/merge_train.py"), "--wip"], capture_output=True, text=True, env={"PATH": "/nonexistent"}, cwd=ROOT, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("gh", result.stderr)


class ExportManifest(unittest.TestCase):
    def test_help_writes_nothing(self):
        before = (ROOT / "EXPORT-MANIFEST.json").read_bytes()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/build_export_manifest.py"), "--help"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual((ROOT / "EXPORT-MANIFEST.json").read_bytes(), before)
        self.assertIn("usage", result.stdout)

    def test_it_lists_exactly_the_tracked_files(self):
        document = json.loads((ROOT / "EXPORT-MANIFEST.json").read_text())
        self.assertFalse([name for name in document["files"] if name.startswith(".venv/") or "/node_modules/" in name])
        self.assertIn("adapters/workcell/host-port.mjs", document["files"])


class CorePin(unittest.TestCase):
    def test_the_named_crash_recovery_pin_holds(self):
        import hashlib
        pins = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())
        recovery = pins["poodo_core_crash_recovery_0_3"]["files"]
        self.assertIn("poodo_core/core.py", recovery)
        for name, expected in recovery.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
        self.assertEqual([k for k in pins if k.startswith("poodo_core_")][-1], "poodo_core_crash_recovery_0_3")


if __name__ == "__main__":
    unittest.main()

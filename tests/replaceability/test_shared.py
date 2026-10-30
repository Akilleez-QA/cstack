"""ADR 005 decision 3, checks shared by every lane: the core imports only the stdlib it uses today, the change that
adds a fake must not touch the core, and every named lane suite has a fake for its port."""
import ast
import importlib
import shutil
import subprocess
import unittest
from pathlib import Path

from poodo_core import ports
from tests.replaceability.compose import FAKES, LANE_SUITES

ROOT = Path(__file__).resolve().parents[2]
CORE_PATHS = ("poodo_core", "forge/endoforge/core")  # the Endoforge core path is created by ADR 005 item 12a
# Exactly what poodo_core/ imports today. Anything else (adapter, vendor, network, subprocess, a new stdlib module)
# fails until this allowlist is changed on purpose in review.
STDLIB_ALLOWLIST = frozenset({"__future__", "dataclasses", "enum", "hashlib", "json", "re", "typing"})
LANES = ("HMIFace", "TruthFace", "RuntimeFace", "EvidenceFace", "SupervisorFace", "ToolFace", "ReadModelFace",
         "LearningFace")


def core_imports(package_dir):
    """Map each absolute top-level module imported anywhere under package_dir to the files importing it."""
    found = {}
    for path in sorted(package_dir.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module]
            else:
                continue  # relative imports stay inside the package
            for name in names:
                found.setdefault(name.split(".")[0], set()).add(str(path.relative_to(ROOT)))
    return found


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=30)


class SharedReplaceabilityChecks(unittest.TestCase):
    def test_core_imports_only_allowlisted_stdlib(self):
        for core_path in CORE_PATHS:
            package = ROOT / core_path
            if not package.is_dir():
                continue
            imports = core_imports(package)
            outside = {name: sorted(files) for name, files in imports.items() if name not in STDLIB_ALLOWLIST}
            self.assertEqual(outside, {}, core_path + " imports modules outside the stdlib allowlist")
        self.assertEqual(set(core_imports(ROOT / "poodo_core")), STDLIB_ALLOWLIST,
                         "Keep the allowlist exact: remove entries the core no longer imports")

    def test_the_change_that_adds_a_fake_does_not_touch_the_core(self):
        # `git diff --quiet <merge-base with origin/main> -- poodo_core/ forge/endoforge/core/`, plus no untracked core
        # files. The merge base, not origin/main itself, so later core work landing on main is not blamed here.
        if shutil.which("git") is None:
            self.skipTest("git is not installed; the no-core-edit check needs a git checkout")
        if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            self.skipTest("not a git checkout; the no-core-edit check needs one")
        base = git("merge-base", "HEAD", "origin/main")
        if base.returncode != 0:
            self.skipTest("no origin/main ref to compare against; the no-core-edit check was not run")
        base = base.stdout.strip()
        fakes = "tests/replaceability/"
        if (git("diff", "--quiet", base, "--", fakes).returncode == 0
                and not git("ls-files", "--others", "--exclude-standard", "--", fakes).stdout.strip()):
            self.skipTest("this change adds or edits no replaceability fake, so the no-core-edit rule does not apply")
        paths = [p + "/" for p in CORE_PATHS]
        changed = git("diff", "--name-only", base, "--", *paths).stdout.split()
        untracked = git("ls-files", "--others", "--exclude-standard", "--", *paths).stdout.split()
        self.assertEqual(changed + untracked, [], "A change that adds a fake must not touch the core")

    def test_every_named_lane_suite_has_a_fake_for_its_port(self):
        self.assertTrue(LANE_SUITES)
        for lane, suite in LANE_SUITES.items():
            with self.subTest(lane=lane):
                self.assertIn(lane, LANES)
                port = getattr(ports, suite["port"])
                methods = {m for m in vars(port) if not m.startswith("_")}
                self.assertTrue(suite["fakes"])
                for fake_id in suite["fakes"]:
                    self.assertTrue(fake_id.startswith("fake."), fake_id)
                    self.assertIn(fake_id, FAKES)
                implementing = [f for f in suite["fakes"] if methods <= set(dir(FAKES[f]))]
                self.assertTrue(implementing, lane + " has no fake implementing " + suite["port"])
                for module in suite["tests"]:
                    loaded = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(module))
                    self.assertGreater(loaded.countTestCases(), 0, module)


if __name__ == "__main__":
    unittest.main()

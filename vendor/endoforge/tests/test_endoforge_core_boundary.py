"""The core imports only the standard-library allowlist and loads no concrete integrations."""
import ast
import importlib
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
STDLIB_ALLOWLIST = frozenset({"__future__", "dataclasses", "enum", "hashlib", "json", "re", "typing"})
TEST_ONLY = frozenset({"unittest"})


def imports(path):
    """Absolute top-level modules imported by one file, plus any relative import that leaves the package."""
    found, escapes = set(), []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                found.add(node.module.split(".")[0])
            elif node.level > 1:
                escapes.append(node.lineno)
    return found, escapes


class EndoforgeCoreBoundaryTests(unittest.TestCase):
    def test_core_imports_only_the_allowlisted_stdlib(self):
        files = sorted(CORE.rglob("*.py"))
        self.assertTrue(any(f.name == "lifecycle.py" for f in files))
        for path in files:
            allowed = STDLIB_ALLOWLIST | (TEST_ONLY if path.name.startswith("test_") else frozenset())
            found, escapes = imports(path)
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(found - allowed, set())
                self.assertEqual(escapes, [], "relative imports must stay inside the core package")

    def test_importing_the_core_loads_nothing_concrete(self):
        code = ("import sys, core; print(sorted(m for m in sys.modules if m.split('.')[0] in "
                "('subprocess', 'socket', 'poodo_core', 'adapters', 'extensions', 'bootstrap', 'urllib', 'http')))")
        proc = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, b"[]"), proc.stderr)


def load_tests(loader, tests, pattern):
    for path in sorted(CORE.glob("test_*.py")):
        tests.addTests(loader.loadTestsFromModule(importlib.import_module("core." + path.stem)))
    return tests


if __name__ == "__main__":
    unittest.main()

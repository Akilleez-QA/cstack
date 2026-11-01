"""Domains are pluggable: the template runs end to end, and a checkout without Refrigeration imports and runs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_EXAMPLE = ROOT / "examples/template-echo.json"
# The open-core export leaves exactly these out and ships foundations/template instead.
REFRIGERATION_GLUE = ("foundations/refrigeration", "extensions/foundation_refrigeration.py",
                      "adapters/refrigeration_stdio.py")
KEEP = ("poodo_core", "adapters", "extensions", "contracts", "schemas", "examples", "foundations/template",
        "foundations/refrigeration", "tests", "bootstrap.py", "cli.py", "__init__.py", "__main__.py")
SUBSET = ("tests.test_template_conformance", "tests.test_inventory_crosscheck", "tests.test_bootstrap",
          "tests.test_core", "tests.test_refrigeration_conformance")


def run_cli(cwd, raw):
    return subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), "cli.py"], cwd=cwd,
                          input=raw, capture_output=True, timeout=60)


class TemplateCliTests(unittest.TestCase):
    def test_template_round_trip_through_the_driver(self):
        result = run_cli(ROOT, TEMPLATE_EXAMPLE.read_bytes())
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        document = json.loads(result.stdout)
        outcomes = [e["data"]["outcome"] for e in document["events"] if e["kind"] == "outcome"]
        self.assertEqual([(o["execution_status"], o["assessment"]) for o in outcomes],
                         [("completed", "observation_echoed"), ("tool_error", "tool_error")])
        receipt = outcomes[0]["raw_result"]["structuredContent"]["receipt"]
        self.assertEqual(receipt["result"], {"observation": "fixture reading 7"})
        self.assertTrue(all(o["raw_result"]["structuredContent"]["receipt"]["evidence"] for o in outcomes))
        self.assertFalse(document["goal"]["closed"])

    def test_unregistered_or_float_documents_are_rejected(self):
        raw = TEMPLATE_EXAMPLE.read_bytes()
        for mutate in (lambda d: d["goal"].update(domain_id="foundation_engine"),
                       lambda d: d["calls"][0]["request"].update(operation="read_file"),
                       lambda d: d["calls"][0]["request"]["arguments"].update(observation=1.5)):
            document = json.loads(raw)
            mutate(document)
            self.assertEqual(run_cli(ROOT, json.dumps(document).encode()).returncode, 2)


class WithoutRefrigerationTests(unittest.TestCase):
    """A copy of the control base minus Refrigeration's glue imports cleanly and runs the template."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name) / "cstack"
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for name in KEEP:
            source, target = ROOT / name, cls.root / name
            if source.is_dir():
                shutil.copytree(source, target, ignore=ignore)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for name in REFRIGERATION_GLUE:  # already absent in a checkout that never had Refrigeration
            path = cls.root / name
            shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)

    def python(self, *args, **kw):
        return subprocess.run([sys.executable, "-B", *args], cwd=self.root, capture_output=True, timeout=300, **kw)

    def test_bootstrap_and_cli_import_without_refrigeration(self):
        code = ("import sys, bootstrap, cli; "
                "from adapters.mcp_stdio_server import McpServer; "
                "print(sorted(bootstrap.DOMAINS)); "
                "print(sorted(m for m in sys.modules if 'refrigeration' in m))")
        result = self.python("-c", code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode().splitlines(), ["['foundation_math', 'foundation_template']", "[]"])
        refused = self.python("-c", "import bootstrap; bootstrap.build_refrigeration('g')")
        self.assertIn(b"Domain foundation_refrigeration is not registered on this host", refused.stderr)

    def test_driver_runs_the_template_and_refuses_refrigeration(self):
        self.assertEqual(run_cli(self.root, TEMPLATE_EXAMPLE.read_bytes()).returncode, 0)
        document = json.loads(TEMPLATE_EXAMPLE.read_bytes())
        document["goal"]["domain_id"] = "foundation_refrigeration"
        for call in document["calls"]:
            call["request"].update(capability_id="foundation_refrigeration", operation="saturation_pressure")
        self.assertEqual(run_cli(self.root, json.dumps(document).encode()).returncode, 2)

    def test_core_subset_passes_and_refrigeration_tests_skip(self):
        # The open-core export also drops the Refrigeration test module itself; run what this checkout has.
        present = [m for m in SUBSET if (self.root / (m.replace(".", "/") + ".py")).is_file()]
        result = self.python("-m", "unittest", "-v", *present)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        if "tests.test_refrigeration_conformance" in present:
            self.assertIn(b"skipped 'Foundation Refrigeration is not in this checkout", result.stderr)


if __name__ == "__main__":
    unittest.main()

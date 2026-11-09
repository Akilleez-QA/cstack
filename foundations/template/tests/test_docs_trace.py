import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentationTraceTests(unittest.TestCase):
    def test_requirements_trace_to_tests_design_and_live_links(self):
        problems, summary = tool("check_trace").check()
        self.assertEqual(problems, [])
        self.assertEqual(summary["requirements"], summary["traced"])

    def test_manifest_copy_passes_its_own_trace_check(self):
        files = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["files"]
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp)
            for name in [*files, "SOURCE-MANIFEST.json"]:
                (copy / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, copy / name)
            proc = subprocess.run([sys.executable, "-B", "tools/check_trace.py"], cwd=copy, capture_output=True,
                                  text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_generated_reference_documents_are_current(self):
        for path, build in tool("gen_docs").GENERATED:
            with self.subTest(path=path.name):
                self.assertEqual(path.read_text(), build())


if __name__ == "__main__":
    unittest.main()

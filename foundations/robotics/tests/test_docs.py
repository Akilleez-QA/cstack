import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tool(*args):
    return subprocess.run([sys.executable, "-B", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


class DocTests(unittest.TestCase):
    def test_trace_and_links_pass(self):
        proc = tool("tools/check_trace.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)

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

    def test_generated_docs_are_current(self):
        proc = tool("tools/gen_docs.py", "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tool(*args):
    return subprocess.run([sys.executable, "-B", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


class DocTests(unittest.TestCase):
    def test_trace_and_links_pass(self):
        proc = tool("tools/check_trace.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_generated_docs_are_current(self):
        proc = tool("tools/gen_docs.py", "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

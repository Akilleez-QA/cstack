"""The TS intent contract's golden digest vectors still match Python's v1 canonical form."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class IntentVectorsTest(unittest.TestCase):
    def test_vectors_match_python_canonical_form(self):
        run = subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'intent_vectors.py'), '--check'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()

"""The Robotics kernel must agree with the pinned Python through its real frame decoder, or refuse."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests/kernels"), str(ROOT / "tools")]
import fuzz_ports  # noqa: E402
import port_reference  # noqa: E402
import robotics_vectors  # noqa: E402


class Differential(unittest.TestCase):
    def clean(self, report, minimum_success):
        self.assertEqual(report["disagreed"], 0, report["first"])
        self.assertGreaterEqual(report["agreed_success"] / report["compared"], minimum_success, report)
        return report

    def test_every_path(self):
        self.clean(port_reference.compare("foundation_robotics", robotics_vectors.structured()), 0.1)

    def test_text_traps(self):
        self.clean(port_reference.compare("foundation_robotics", robotics_vectors.lexical_vectors()), 0.05)

    def test_seeded_fuzz(self):
        report = self.clean(port_reference.compare("foundation_robotics", robotics_vectors.fuzz(4000, 11)), 0.5)
        self.assertLess(report["refused_port_only"] / report["compared"], 0.03)
        self.assertEqual(set(report["refusal_codes"]) - {"numeric_boundary", "outside_domain"}, set())

    def test_rounding_boundaries(self):
        vectors = [(tool, json.dumps(args, separators=(",", ":"))) for name, pairs in json.loads((ROOT / "tests/kernels/robotics_boundaries.json").read_text()).items() for tool, args in (fuzz_ports.FAMILIES[name](a, b) for a, b in pairs)]
        self.assertGreater(len(vectors), 50)
        report = port_reference.compare("foundation_robotics", vectors)
        self.assertEqual(report["disagreed"], 0, report["first"])
        self.assertGreater(report["refusal_codes"]["numeric_boundary"], 0)


class Refusals(unittest.TestCase):
    def test_a_window_the_reference_cannot_finish_is_refused(self):
        text = json.dumps({"fps_milli": 10 ** 6, "frames": [{"com_mm": [0, 900, 0], "support_mm": [[0, 0, 0]]}], "thresholds": {"derivative_window_ms": 10 ** 12}})
        self.assertEqual(port_reference.outcome_of("foundation_robotics", "balance_check", text), {"code": "outside_domain"})


if __name__ == "__main__":
    unittest.main()

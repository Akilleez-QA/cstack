"""The Film kernel must agree with the pinned Python through its real frame decoder, or refuse."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/kernels"))
import film_vectors  # noqa: E402
import port_reference  # noqa: E402


class Differential(unittest.TestCase):
    def clean(self, report, minimum_success):
        self.assertEqual(report["disagreed"], 0, report["first"])
        self.assertGreaterEqual(report["agreed_success"] / report["compared"], minimum_success, report)
        return report

    def test_every_path(self):
        self.clean(port_reference.compare("foundation_film", film_vectors.structured()), 0.1)

    def test_text_traps(self):
        self.assertGreater(self.clean(port_reference.compare("foundation_film", film_vectors.lexical_vectors()), 0.05)["refused_both"], 50)

    def test_seeded_fuzz(self):
        self.assertEqual(self.clean(port_reference.compare("foundation_film", film_vectors.fuzz(4000, 11)), 0.5)["refused_port_only"], 0)

    def test_the_differential_sees_a_changed_result(self):
        rows = port_reference.reference("foundation_film", [("look_gate", json.dumps({"frames": [{"id": "f", "metrics": film_vectors.LOOK_METRICS}]}))])
        rows[0]["python"]["receipt"]["result"]["thresholds"]["clip_white"] += 1
        self.assertEqual(port_reference.compare_rows("foundation_film", rows)["disagreed"], 1)


class Refusals(unittest.TestCase):
    def test_a_long_number_does_not_hang(self):
        self.assertEqual(port_reference.outcome_of("foundation_film", "look_gate", '{"frames":' + "9" * 450 + "}"), {"code": "integer_too_large"})

    def test_prototype_keys_are_plain_keys(self):
        self.assertIn("unexpected ['__proto__']", port_reference.outcome_of("foundation_film", "look_gate", '{"__proto__":{"frames":[]}}')["error"])


if __name__ == "__main__":
    unittest.main()

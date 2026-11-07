"""The Film kernel must agree with the pinned Python through its real frame decoder, or refuse."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/kernels"))
import port_reference  # noqa: E402


class Refusals(unittest.TestCase):
    def test_a_long_number_does_not_hang(self):
        self.assertEqual(port_reference.outcome_of("foundation_film", "look_gate", '{"frames":' + "9" * 450 + "}"), {"code": "integer_too_large"})

    def test_prototype_keys_are_plain_keys(self):
        self.assertIn("unexpected ['__proto__']", port_reference.outcome_of("foundation_film", "look_gate", '{"__proto__":{"frames":[]}}')["error"])


if __name__ == "__main__":
    unittest.main()

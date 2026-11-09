import json
import unittest
from pathlib import Path

from tools import gen_data_dictionary as dd

ROOT = Path(__file__).resolve().parents[1]


class DataDictionary(unittest.TestCase):
    def test_the_committed_dictionary_matches_its_sources(self):
        self.assertEqual(dd.main(["--check"]), 0)

    def test_every_tool_and_schema_field_appears(self):
        text = dd.render()
        for path in sorted((ROOT / "schemas").glob("*-tools.json")):
            for tool in json.loads(path.read_text()):
                self.assertIn(f"| `{tool['name']}` |", text)
        for path in sorted((ROOT / "contracts").glob("*.schema.json")):
            for name in json.loads(path.read_text()).get("properties", {}):
                self.assertIn(f"| `{name}` |", text)

    def test_limits_are_evaluated_exactly(self):
        self.assertEqual(dd.evaluate("33 * 1024 * 1024"), 34_603_008)
        self.assertEqual(dd.evaluate("10**15"), 10 ** 15)
        self.assertEqual(dd.evaluate("1_048_576"), 1_048_576)
        self.assertIn("| `MAX_FRAME` | 1,048,576 | `adapters/mcp_stdio_server.py` |", dd.render())


if __name__ == "__main__":
    unittest.main()

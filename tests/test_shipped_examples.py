import json
from pathlib import Path
import unittest

from adapters.aor_registry import load_fleet, parse_fleet

ROOT = Path(__file__).resolve().parents[1]


class ShippedExamples(unittest.TestCase):
    def test_the_example_fleet_passes_the_validation_the_readme_names(self):
        fleet = load_fleet(ROOT / "aors" / "fleet.json")
        self.assertEqual(parse_fleet(json.loads((ROOT / "aors" / "fleet.json").read_text())), fleet)

    def test_the_example_config_is_valid_json_with_the_fleet_file_it_names(self):
        config = json.loads((ROOT / "cstack.config.example.json").read_text())
        self.assertTrue((ROOT / config["fleet_file"]).is_file())


if __name__ == "__main__":
    unittest.main()

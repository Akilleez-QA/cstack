import copy
import hashlib
import json
from pathlib import Path
import unittest

from foundation_refrigeration import invariants

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "golden/coolprop-8.0.0-points.json").read_text())


def quantity(value, unit):
    return {"value": value, "unit": unit}


def pressure_claim():
    return {"left": quantity(0, "psig"), "right": quantity(101.325, "kPa(a)"),
            "relation": "eq", "atmosphere": {"basis": "standard"}}


def saturation_claim(point, side="bubble"):
    return {"fluid": point["fluid"], "side": side,
            "pressure": quantity(point[side + "_kpa_a"], "kPa(a)"),
            "temperature": quantity(point["temperature_c"], "degC"), "atmosphere": None}


class InvariantTests(unittest.TestCase):
    def test_pressure_relations_and_atmosphere(self):
        claim = pressure_claim()
        result = invariants.evaluate("pressure_relation", claim)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["measurements"]["unit"], "kPa(a)")
        self.assertFalse(result["measurements"]["atmosphere"]["assumed"])
        self.assertTrue(result["measurements"]["evidence"])
        claim["atmosphere"] = None
        self.assertFalse(invariants.evaluate("pressure_relation", claim)["passed"])
        claim["atmosphere"] = {"basis": "measured", "pressure": quantity(90, "kPa(a)")}
        claim["right"] = quantity(90, "kPa(a)")
        self.assertTrue(invariants.evaluate("pressure_relation", claim)["passed"])
        claim.update(left=quantity(1, "bar(a)"), right=quantity(101, "kPa(a)"), atmosphere=None)
        for relation, passed in (("lt", True), ("gt", False), ("eq", False)):
            claim["relation"] = relation
            self.assertEqual(invariants.evaluate("pressure_relation", claim)["passed"], passed)
        claim.update(left=quantity(1.000000005, "bar(a)"), right=quantity(100, "kPa(a)"))
        for relation, passed in (("eq", True), ("lt", False), ("gt", False)):
            claim["relation"] = relation
            self.assertEqual(invariants.evaluate("pressure_relation", claim)["passed"], passed)

    def test_temperature_scales_and_order(self):
        for value, unit in ((32, "degF"), (273.15, "K"), (491.67, "degR")):
            claim = {"left": quantity(value, unit), "right": quantity(0, "degC"), "relation": "eq"}
            result = invariants.evaluate("temperature_relation", claim)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["measurements"]["unit"], "degC")
        claim.update(left=quantity(1, "degC"), relation="gt")
        self.assertTrue(invariants.evaluate("temperature_relation", claim)["passed"])
        claim["relation"] = "lt"
        self.assertFalse(invariants.evaluate("temperature_relation", claim)["passed"])

    def test_saturation_against_independent_coolprop_points(self):
        for point in GOLDEN["by_temperature"]:
            for side in ("bubble", "dew"):
                with self.subTest(fluid=point["fluid"], side=side):
                    claim = saturation_claim(point, side)
                    before = copy.deepcopy(claim)
                    result = invariants.evaluate("saturation_temperature", claim)
                    self.assertTrue(result["passed"], result)
                    self.assertTrue(result["measurements"]["evidence"])
                    self.assertEqual(claim, before)
                    claim["temperature"]["value"] += 10
                    self.assertFalse(invariants.evaluate("saturation_temperature", claim)["passed"])

    def test_saturation_refuses_missing_side_unknown_fluid_and_extrapolation(self):
        point = next(p for p in GOLDEN["by_temperature"] if p["fluid"] == "R448A")
        for override in ({"side": None}, {"side": "vapour"}, {"fluid": "unknown"},
                         {"pressure": quantity(0.001, "kPa(a)")},
                         {"pressure": quantity(1, "psig"), "atmosphere": None}):
            result = invariants.evaluate("saturation_temperature", saturation_claim(point) | override)
            self.assertFalse(result["passed"], result)
            self.assertTrue(result["reason"])

    def test_malformed_claims_fail_as_results(self):
        for check in invariants.CHECKS:
            for claim in (None, [], {}, {"extra": True}):
                result = invariants.evaluate(check, claim)
                self.assertFalse(result["passed"], result)
                self.assertNotIn("measurements", result)
        for check in (None, [], "unknown"):
            self.assertFalse(invariants.evaluate(check, {})["passed"])
        for value in (True, float("nan"), float("inf"), 10**400, "32"):
            claim = pressure_claim() | {"left": quantity(value, "psig")}
            self.assertFalse(invariants.evaluate("pressure_relation", claim)["passed"])
        claim = {"left": quantity(0, "K"), "right": quantity(1, "K"), "relation": "lt"}
        self.assertFalse(invariants.evaluate("temperature_relation", claim)["passed"])
        for override in ({"relation": "le"}, {"relation": []}, {"left": 1},
                         {"left": quantity(1, "invalid")}, {"left": quantity(0, "kPa(a)")}):
            self.assertFalse(invariants.evaluate("pressure_relation", pressure_claim() | override)["passed"])

    def test_library_version_binds_local_sources_and_data(self):
        package = ROOT / "foundation_refrigeration"
        paths = [*package.glob("*.py"), *package.joinpath("data").glob("*.json")]
        expected = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        self.assertEqual(invariants.SOURCE_HASHES, expected)
        digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(invariants.LIBRARY_VERSION, invariants.VERSION + ":" + digest)
        self.assertEqual(invariants.evaluate("unknown", {})["library_version"], invariants.LIBRARY_VERSION)


if __name__ == "__main__":
    unittest.main()

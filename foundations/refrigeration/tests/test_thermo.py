import ast
import json
from pathlib import Path
import unittest

from foundation_refrigeration import thermo, units
from foundation_refrigeration.projection import DATA_DIR
from foundation_refrigeration.thermo import ThermoError, saturation_pressure_kpa, saturation_temperature_c

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_GEN = json.loads((ROOT / "golden/generator-golden-points.json").read_text())
GOLDEN_CP = json.loads((ROOT / "golden/coolprop-8.0.0-points.json").read_text())
PSIA_ATM_GOLDEN = 14.696


def f_to_c(f):
    return (f - 32.0) / 1.8


def psia(kpa):
    return kpa / units.KPA_PER_PSI


class ProvenanceTests(unittest.TestCase):
    def test_nine_generated_tables_with_t1_provenance(self):
        self.assertEqual(set(thermo.TABLES), {"NH3", "CO2", "R134a", "R290", "R22", "R404A", "R410A", "R507A", "R448A"})
        for fid in thermo.FLUID_FILES:
            data = json.loads((DATA_DIR / ("refrigerant-saturation." + fid + ".json")).read_text())
            self.assertEqual(data["schema"], "refrigerant-saturation/1")
            body = data["data"]
            self.assertEqual(body["source"], "CoolProp 8.0.0")
            self.assertEqual(body["evidence"]["basis"]["kind"], "generated")
            self.assertEqual(body["evidence"]["status"], "CHECK")
            self.assertIsNone(body["verifiedBy"])
            self.assertIn("generate_pt_tables.py", body["generatedBy"] if "generatedBy" in body else data["generatedBy"])
            self.assertTrue(body["generator"]["rows_match_committed_refrigeration_ai_table"])
            for canon, raw in zip(body["rows"], body["generated_rows"], strict=True):
                self.assertEqual(canon[0], f_to_c(raw[0]))
                self.assertEqual(canon[1], raw[1] * units.KPA_PER_PSI)
                self.assertEqual(canon[2], raw[2] * units.KPA_PER_PSI)
                self.assertEqual(canon[3:], raw[3:])


    def test_no_hand_typed_numeric_table_in_package_source(self):
        for path in (ROOT / "foundation_refrigeration").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.List, ast.Tuple)):
                    numbers = [e for e in node.elts if isinstance(e, ast.Constant) and type(e.value) in (int, float)]
                    self.assertLess(len(numbers), 5, "%s:%d looks like a typed table" % (path.name, node.lineno))


class MonotonicityTests(unittest.TestCase):
    def test_rows_strictly_increase_and_blend_sides_are_ordered(self):
        for fid, table in thermo.TABLES.items():
            with self.subTest(fluid=fid):
                ts, pb, pd = table.temperatures_c, table.bubble_kpa, table.dew_kpa
                self.assertTrue(all(a < b for a, b in zip(ts, ts[1:])))
                self.assertTrue(all(a < b for a, b in zip(pb, pb[1:])))
                self.assertTrue(all(a < b for a, b in zip(pd, pd[1:])))
                if table.is_blend:
                    self.assertTrue(all(b >= d for b, d in zip(pb, pd)))
                else:
                    self.assertEqual(pb, pd)

    def test_enthalpy_vapour_exceeds_liquid(self):
        for fid in thermo.FLUID_FILES:
            rows = json.loads((DATA_DIR / ("refrigerant-saturation." + fid + ".json")).read_text())["data"]["rows"]
            self.assertTrue(all(r[4] > r[3] for r in rows), fid)
            self.assertTrue(all(a[3] < b[3] for a, b in zip(rows, rows[1:])), fid)

    def test_lookup_is_monotonic_and_inverts(self):
        for fid, table in thermo.TABLES.items():
            sides = ("bubble", "dew") if table.is_blend else (None,)
            for side in sides:
                with self.subTest(fluid=fid, side=side):
                    steps = 400
                    span = table.max_c - table.min_c
                    last = 0.0
                    for i in range(steps + 1):
                        t = table.max_c if i == steps else table.min_c + span * i / steps
                        p, _ = saturation_pressure_kpa(table, t, side)
                        self.assertGreater(p, last)
                        last = p
                        back, _ = saturation_temperature_c(table, p, side)
                        self.assertAlmostEqual(back, t, places=6)


class GoldenTests(unittest.TestCase):
    def test_census_ammonia_anchor_points(self):
        nh3 = thermo.resolve_fluid("NH3")
        for t_f, psig in ((0.0, 15.69), (20.0, 33.49), (95.0, 181.10)):
            kpa, _ = saturation_pressure_kpa(nh3, f_to_c(t_f))
            gauge = units.from_absolute_kpa(kpa, "psig", units.STANDARD_ATMOSPHERE_KPA)
            self.assertEqual(round(gauge, 2), psig, t_f)
        for point in GOLDEN_CP["census_nh3_anchor_points"]:
            kpa, _ = saturation_pressure_kpa(nh3, f_to_c(point["temperature_f"]))
            self.assertAlmostEqual(psia(kpa), point["pressure_psia"], delta=1e-4)
            self.assertEqual(round(point["pressure_psig_standard_atmosphere"], 2),
                             {0.0: 15.69, 20.0: 33.49, 95.0: 181.10}[point["temperature_f"]])

    def test_generator_off_grid_golden_points(self):
        count = 0
        for fid, golden in GOLDEN_GEN["fluids"].items():
            table = thermo.TABLES[fid]
            tolerance_f = table.error_k * 1.8 + 0.002
            sides = (("bubble", "bubblePsia", "bubbleTempF"), ("dew", "dewPsia", "dewTempF"))
            for point in golden["byTemp"]:
                for side, p_key, _ in sides:
                    t_c, _ = saturation_temperature_c(table, point[p_key] * units.KPA_PER_PSI, side)
                    self.assertLessEqual(abs(units.c_to_f(t_c) - point["tempF"]), tolerance_f, (fid, point, side))
                    count += 1
            for point in golden["byPressure"]:
                kpa = (point["psig"] + PSIA_ATM_GOLDEN) * units.KPA_PER_PSI
                for side, _, t_key in sides:
                    t_c, _ = saturation_temperature_c(table, kpa, side)
                    self.assertLessEqual(abs(units.c_to_f(t_c) - point[t_key]), tolerance_f, (fid, point, side))
                    count += 1
        self.assertGreater(count, 250)

    def test_direct_coolprop_golden_points(self):
        for point in GOLDEN_CP["by_temperature"]:
            table = thermo.TABLES[point["fluid"]]
            tolerance_k = table.error_k + 0.001
            for side, key in (("bubble", "bubble_kpa_a"), ("dew", "dew_kpa_a")):
                t_c, _ = saturation_temperature_c(table, point[key], side)
                self.assertLessEqual(abs(t_c - point["temperature_c"]), tolerance_k, (point, side))
                p, _ = saturation_pressure_kpa(table, point["temperature_c"], side)
                self.assertLess(abs(p - point[key]) / point[key], 2e-4, (point, side))
        for point in GOLDEN_CP["by_pressure"]:
            table = thermo.TABLES[point["fluid"]]
            for side, key in (("bubble", "bubble_temperature_c"), ("dew", "dew_temperature_c")):
                t_c, _ = saturation_temperature_c(table, point["pressure_kpa_a"], side)
                self.assertLessEqual(abs(t_c - point[key]), table.error_k + 0.001, (point, side))
        self.assertEqual(GOLDEN_CP["oracle"].split()[1], "8.0.0")


class RefusalTests(unittest.TestCase):
    def test_no_extrapolation(self):
        nh3 = thermo.TABLES["NH3"]
        for t in (nh3.min_c - 0.01, nh3.max_c + 0.01):
            with self.assertRaises(ThermoError) as caught:
                saturation_pressure_kpa(nh3, t)
            self.assertEqual(caught.exception.code, "outside_table_range")
        for p in (nh3.bubble_kpa[0] * 0.999, nh3.bubble_kpa[-1] * 1.001):
            with self.assertRaises(ThermoError):
                saturation_temperature_c(nh3, p)
        self.assertEqual(saturation_pressure_kpa(nh3, nh3.min_c)[0], nh3.bubble_kpa[0])

    def test_blends_refuse_to_guess_a_side(self):
        for fid in ("R404A", "R410A", "R507A", "R448A"):
            with self.assertRaises(ThermoError) as caught:
                saturation_pressure_kpa(thermo.TABLES[fid], 0.0)
            self.assertEqual(caught.exception.code, "side_required")
        with self.assertRaises(ThermoError):
            saturation_pressure_kpa(thermo.TABLES["NH3"], 0.0, "vapour")
        self.assertEqual(saturation_pressure_kpa(thermo.TABLES["NH3"], 0.0, "dew")[0],
                         saturation_pressure_kpa(thermo.TABLES["NH3"], 0.0)[0])

    def test_fluid_aliases(self):
        for name, fid in (("R717", "NH3"), ("ammonia", "NH3"), ("R-717", "NH3"), ("r744", "CO2"),
                          ("Carbon dioxide", "CO2"), ("propane", "R290"), ("R-290", "R290"), ("R-134a", "R134a")):
            self.assertEqual(thermo.resolve_fluid(name).id, fid)
        for bad in ("R1234yf", "", 717, "x" * 65):
            with self.assertRaises(ThermoError):
                thermo.resolve_fluid(bad)


if __name__ == "__main__":
    unittest.main()

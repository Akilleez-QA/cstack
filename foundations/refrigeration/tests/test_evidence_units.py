import json
import math
import unittest

from foundation_refrigeration.evidence import (
    CitedBasis, Evidence, EvidenceError, GeneratedBasis, LEGACY_STATUS, PolicyBasis, PracticeBasis,
    evidence_from_dict, from_legacy_basis, from_legacy_verification, is_approved, legacy_status, record_problem)
from foundation_refrigeration import units
from foundation_refrigeration.projection import stable_json
from foundation_refrigeration.units import UnitError

CITED = CitedBasis("OSHA Table Z-1", "29 CFR 1910.1000")


class EvidenceTests(unittest.TestCase):
    def test_silence_is_not_approval(self):
        self.assertFalse(is_approved(Evidence(CITED, "CHECK")))
        with self.assertRaisesRegex(EvidenceError, "silence is not approval"):
            Evidence(CITED, "APPROVED")
        with self.assertRaises(EvidenceError):
            Evidence(CITED, "APPROVED", approved_by="Refrigeration SME")
        with self.assertRaises(EvidenceError):
            Evidence(CITED, "APPROVED", approved_on="2026-10-24")
        self.assertTrue(is_approved(Evidence(CITED, "APPROVED", approved_by="Refrigeration SME",
                                             approved_on="2026-10-24")))

    def test_approval_fields_only_on_approved_and_dispute_only_on_disputed(self):
        with self.assertRaises(EvidenceError):
            Evidence(CITED, "CHECK", approved_by="Refrigeration SME", approved_on="2026-10-24")
        with self.assertRaises(EvidenceError):
            Evidence(PracticeBasis("n"), "DISPUTED")
        with self.assertRaises(EvidenceError):
            Evidence(PracticeBasis("n"), "CHECK", dispute="conflict")
        self.assertEqual(Evidence(PracticeBasis("n"), "DISPUTED", dispute="A vs B").status, "DISPUTED")

    def test_basis_without_required_fields_is_refused(self):
        for record in ({"basis": {"kind": "cited", "source": "", "version": "x", "clause": None}, "status": "CHECK"},
                       {"basis": {"kind": "cited", "source": "s", "version": " ", "clause": None}, "status": "CHECK"},
                       {"basis": {"kind": "policy", "setBy": "Client", "scope": "client", "reason": ""}, "status": "CHECK"},
                       {"basis": {"kind": "policy", "setBy": "Client", "scope": "nation", "reason": "r"}, "status": "CHECK"},
                       {"basis": {"kind": "generated", "model": "", "generator": "g", "generatedOn": "2026-10-24"}, "status": "CHECK"},
                       {"basis": {"kind": "practice", "note": "n"}, "status": "DISPUTED"},
                       {"basis": {"kind": "rumour", "note": "n"}, "status": "CHECK"},
                       {"basis": {"kind": "practice", "note": "n"}, "status": "VERIFIED"},
                       {"basis": {"kind": "practice", "note": "n"}, "status": "CHECK", "extra": 1},
                       {"basis": {"kind": "generated", "model": "m", "generator": "g", "generatedOn": "2026-02-30"},
                        "status": "CHECK"}):
            with self.subTest(record=record):
                self.assertIsNotNone(record_problem(record))

    def test_round_trip_is_exact(self):
        for evidence in (Evidence(CITED, "CHECK"),
                         Evidence(GeneratedBasis("CoolProp 8.0.0 HEOS", "gen", "2026-10-24"), "CHECK"),
                         Evidence(PolicyBasis("Plant engineering", "plant", "Local practice"), "CHECK"),
                         Evidence(PracticeBasis("n"), "APPROVED", approved_by="Refrigeration SME",
                                  approved_on="2026-10-24", fresh_for_days=365)):
            self.assertEqual(evidence_from_dict(json.loads(json.dumps(evidence.to_dict()))), evidence)

    def test_every_legacy_vocabulary_maps_and_none_but_approved_means_approved(self):
        for legacy in ("CHECK", "APPROVED", "VERIFIED", "REPORTED", "SOURCED", "NEEDS-ENGINEER",
                       "COMMON-PRACTICE", "cited", "plant-configured", "UNVERIFIED"):
            self.assertIn(legacy, LEGACY_STATUS)
        for legacy, status in LEGACY_STATUS.items():
            if legacy != "APPROVED":
                self.assertNotEqual(status, "APPROVED", legacy)
        self.assertEqual(legacy_status("VERIFIED"), "CHECK")
        with self.assertRaises(EvidenceError):
            legacy_status("signed-off")

    def test_basis_ts_and_verified_by_ports(self):
        plant = from_legacy_basis({"kind": "plant-configured", "setBy": "Plant engineering", "reason": "Site interval"})
        self.assertEqual((plant.basis.kind, plant.basis.scope, plant.status), ("policy", "plant", "CHECK"))
        cited = from_legacy_basis({"kind": "cited", "source": "Standard", "version": "2024", "clause": "4.2",
                                   "checkedOn": "2026-10-01"})
        self.assertEqual(cited.status, "CHECK")
        self.assertFalse(cited.approved)
        generated = GeneratedBasis("CoolProp 8.0.0 HEOS", "gen", "2026-10-24")
        self.assertEqual(from_legacy_verification(generated, None, None).status, "CHECK")
        self.assertEqual(from_legacy_verification(generated, "Refrigeration SME", "2026-10-24").status, "APPROVED")
        with self.assertRaises(EvidenceError):
            from_legacy_verification(generated, "Refrigeration SME", None)

    def test_projection_json_is_stable_regardless_of_key_order(self):
        self.assertEqual(stable_json({"b": 1, "a": {"d": 2, "c": 3}}), stable_json({"a": {"c": 3, "d": 2}, "b": 1}))
        with self.assertRaises(ValueError):
            stable_json({"x": float("nan")})


class UnitTests(unittest.TestCase):
    def test_constants(self):
        self.assertAlmostEqual(units.KPA_PER_PSI, 6.894757293168361, places=14)
        self.assertEqual(units.STANDARD_ATMOSPHERE_KPA, 101.325)

    def test_gauge_and_absolute_round_trip(self):
        atm = units.STANDARD_ATMOSPHERE_KPA
        self.assertEqual(units.absolute_kpa(0, "psig", atm), 101.325)
        self.assertEqual(units.absolute_kpa(0, "bar(g)", atm), 101.325)
        for unit in units.PRESSURE_UNITS:
            for value in (0.5, 33.49, 181.1):
                kpa = units.absolute_kpa(value, unit, atm)
                self.assertAlmostEqual(units.from_absolute_kpa(kpa, unit, atm), value, places=9)
        self.assertAlmostEqual(units.absolute_kpa(1, "bar(a)", atm), 100.0)
        with self.assertRaises(UnitError):
            units.absolute_kpa(-20, "psig", atm)
        with self.assertRaises(UnitError):
            units.absolute_kpa(1, "inHg", atm)

    def test_temperature(self):
        self.assertEqual(units.to_celsius(32, "degF"), 0)
        self.assertAlmostEqual(units.to_celsius(-40, "degF"), -40)
        self.assertAlmostEqual(units.to_celsius(273.15, "K"), 0)
        self.assertAlmostEqual(units.to_celsius(491.67, "degR"), 0, places=9)
        for unit in units.TEMPERATURE_UNITS:
            self.assertAlmostEqual(units.to_celsius(units.from_celsius(-28.0, unit), unit), -28.0, places=9)
        for value, unit in ((-273.15, "degC"), (0, "K"), (-460, "degF")):
            with self.assertRaises(UnitError):
                units.to_celsius(value, unit)

    def test_site_atmosphere_from_elevation(self):
        self.assertEqual(units.atmosphere_at_elevation_kpa(0), 101.325)
        self.assertTrue(83 < units.atmosphere_at_elevation_kpa(1600) < 85)
        kpa, record, _ = units.read_atmosphere({"basis": "elevation", "elevation": {"value": 5280, "unit": "ft"}})
        self.assertTrue(83 < kpa < 85)
        self.assertFalse(record["assumed"])
        self.assertTrue(units.read_atmosphere(None)[1]["assumed"])
        for bad in ({"basis": "elevation", "elevation": {"value": 9000, "unit": "m"}},
                    {"basis": "measured", "pressure": {"value": 30, "unit": "kPa(a)"}},
                    {"basis": "standard", "pressure": {"value": 101, "unit": "kPa(a)"}},
                    {"basis": "guess"}, {"elevation": 10}, 101.325):
            with self.assertRaises(UnitError):
                units.read_atmosphere(bad)

    def test_quantities_need_explicit_units_and_finite_numbers(self):
        self.assertEqual(units.quantity({"value": 5, "unit": "psig"}, units.PRESSURE_UNITS, "p"), (5.0, "psig"))
        for bad in (5, {"value": 5}, {"value": 5, "unit": "psi"}, {"value": True, "unit": "psig"},
                    {"value": "5", "unit": "psig"}, {"value": math.nan, "unit": "psig"},
                    {"value": math.inf, "unit": "psig"}, {"value": 1e12, "unit": "psig"},
                    {"value": 5, "unit": "psig", "extra": 1}):
            with self.assertRaises(UnitError):
                units.quantity(bad, units.PRESSURE_UNITS, "p")


if __name__ == "__main__":
    unittest.main()

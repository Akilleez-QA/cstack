"""Safety limits, plant taxonomy and open SME decisions, checked as data."""
import json
from pathlib import Path
import re
import unittest

from foundation_refrigeration import decisions, plant_model, safety_limits
from foundation_refrigeration.evidence import CitedBasis, Evidence, PolicyBasis
from foundation_refrigeration.safety_limits import PolicySetPoint, PublishedLimit, SafetyLimitError

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
LIMITS_TS = REPO / "upstream/app/packages/domain/src/safety/ammonia-exposure-limits.ts"
SERVICES_TS = REPO / "upstream/app/src/features/engineering/canvas/canvas-services.ts"
KINDS_TS = REPO / "upstream/app/packages/domain/src/pid-sim-bridge/types.ts"


def policy(label="Evacuation level", ppm=150):
    return {"label": label, "concentration": {"value": ppm, "unit": "ppm"}, "set_by": "Plant safety committee",
            "scope": "plant", "reason": "Site emergency plan"}


class SafetyLimitTests(unittest.TestCase):
    def test_osha_pel_is_50_and_25_belongs_to_niosh_and_acgih(self):
        self.assertEqual(safety_limits.ammonia_limit("osha-pel-twa").ppm, 50)
        self.assertEqual(safety_limits.ammonia_limit("osha-pel-twa").legal_status, "enforceable")
        twenty_five = {x.id for x in safety_limits.AMMONIA_LIMITS if x.ppm == 25}
        self.assertEqual(twenty_five, {"niosh-rel-twa", "acgih-tlv-twa"})
        self.assertEqual([x.issuer for x in safety_limits.AMMONIA_LIMITS if x.legal_status == "enforceable"], ["OSHA"])
        self.assertEqual(safety_limits.ammonia_limit("niosh-idlh").ppm, 300)

    def test_every_limit_is_cited_with_url_quote_and_check(self):
        self.assertEqual(len(safety_limits.AMMONIA_LIMITS), 6)
        for limit in safety_limits.AMMONIA_LIMITS:
            basis = limit.evidence.basis
            self.assertEqual(basis.kind, "cited")
            self.assertTrue(basis.url.startswith("https://"))
            self.assertIn(str(int(limit.ppm)) + " ppm", basis.quoted)
            self.assertEqual(basis.retrieved_on, "2026-10-06")
            self.assertEqual(limit.evidence.status, "CHECK")  # Legacy VERIFIED is not approval.

    def test_erpg_is_an_explicit_gap_not_a_value(self):
        self.assertEqual([g["id"] for g in safety_limits.GAPS], ["erpg"])
        self.assertFalse(any("ERPG" in x.kind or "ERPG" in x.label for x in safety_limits.AMMONIA_LIMITS))

    def test_policy_value_is_never_presentable_as_a_legal_limit(self):
        point = safety_limits.policy_set_point(policy())
        shown = point.to_dict()
        self.assertEqual(shown["legal_status"], "not_a_legal_limit")
        self.assertIn("not a legal or published limit", shown["display"])
        self.assertEqual(shown["evidence"]["basis"]["kind"], "policy")
        for label in ("OSHA PEL alarm", "Legal limit", "TLV warning", "IDLH evacuation", "ERPG-2", "Client limit"):
            with self.assertRaises(SafetyLimitError):
                safety_limits.policy_set_point(policy(label))
        with self.assertRaises(SafetyLimitError):
            PolicySetPoint("Evacuation", 25, Evidence(CitedBasis("29 CFR 1910.1000", "current"), "CHECK"))
        with self.assertRaises(SafetyLimitError):
            PublishedLimit("x", "OSHA", "PEL-TWA", "OSHA PEL", 50, 35, "TWA", "enforceable",
                           Evidence(PolicyBasis("Client", "client", "Their alarm"), "CHECK"))
        for bad in (policy() | {"legal_status": "enforceable"}, policy(ppm=-1),
                    policy() | {"set_by": ""}, policy() | {"scope": "law"}):
            with self.assertRaises(SafetyLimitError):
                safety_limits.policy_set_point(bad)

    def test_mislabel_detector(self):
        self.assertEqual(safety_limits.find_mislabelled_ammonia_limits(
            "The OSHA PEL for ammonia is 25 ppm.\nNIOSH REL is 25 ppm."), ["The OSHA PEL for ammonia is 25 ppm."])
        self.assertEqual(safety_limits.find_mislabelled_ammonia_limits("OSHA PEL (8-hour TWA): 50 ppm"), [])

    @unittest.skipUnless(LIMITS_TS.is_file(), "the reference app source not present in this copy")
    def test_values_match_the_typescript_source(self):
        text = LIMITS_TS.read_text()
        rows = re.findall(r"id: '([a-z-]+)',\s+issuer: '(\w+)',\s+kind: '([\w-]+)',\s+label: '([^']+)',\s+"
                          r"ppm: (\d+),\s+mgPerM3: (\d+|null),\s+averaging: '(\w+)',\s+status: '(\w+)'", text)
        ported = [(x.id, x.issuer, x.kind, x.label, int(x.ppm), None if x.mg_per_m3 is None else int(x.mg_per_m3),
                   x.averaging, x.legal_status) for x in safety_limits.AMMONIA_LIMITS]
        source = [(i, s, k, lab, int(p), None if m == "null" else int(m), a, st) for i, s, k, lab, p, m, a, st in rows]
        self.assertEqual(ported, source)
        for limit in safety_limits.AMMONIA_LIMITS:
            self.assertIn(limit.evidence.basis.quoted, text)


class PlantModelTests(unittest.TestCase):
    def test_every_value_of_every_legacy_list_resolves(self):
        ids = {entry["id"] for entry in plant_model.LEGACY_LISTS}
        self.assertGreaterEqual(len(ids), 9)
        for required in ("rai.pid-sim-bridge.PLANT_COMPONENT_KINDS", "rai.engineering-assembly.NetworkComponentKind",
                         "rai.supabase.equipment_class", "rai.canvas.VisualEquipmentKind",
                         "rai.equipmentRegistry.EquipmentType", "rai.compliance.mi-schedule.EquipmentClass",
                         "rai.orchestrator.EquipmentClass", "rai.equipment-library.FamilyId",
                         "fos.spatial-industrial-grammar.entity_primitives", "kit.import-kit.MODELS",
                         "archive.prototype-facility.EquipmentTypeSchema"):
            self.assertIn(required, ids)
        sizes = {entry["id"]: len(entry["values"]) for entry in plant_model.LEGACY_LISTS}
        self.assertEqual(sizes["rai.supabase.equipment_class"], 28)
        self.assertEqual(sizes["rai.canvas.VisualEquipmentKind"], 12)
        self.assertEqual(sizes["rai.equipmentRegistry.EquipmentType"], 9)
        for entry in plant_model.LEGACY_LISTS:
            for value in entry["values"]:
                with self.subTest(source=entry["id"], value=value):
                    result = plant_model.resolve_equipment_kind(value)
                    self.assertTrue(result["resolved"])
                    self.assertIn(entry["id"], result["legacy_sources"])

    def test_taxonomy_is_closed_acyclic_and_check(self):
        for kind_id in plant_model.KINDS:
            chain = plant_model.lineage(kind_id)
            self.assertEqual(len(chain), len(set(chain)))
            self.assertIsNone(plant_model.KINDS[chain[-1]]["parent"])
        self.assertEqual(plant_model.TAXONOMY_EVIDENCE.status, "CHECK")
        self.assertEqual(plant_model.resolve_equipment_kind("Expansion_Valve")["kind"]["id"], "expansion-valve")
        self.assertEqual(plant_model.resolve_equipment_kind("hpr")["kind"]["lineage"],
                         ["high-pressure-receiver", "receiver", "vessel"])

    def test_unknown_term_is_unresolved_not_guessed(self):
        result = plant_model.resolve_equipment_kind("flux capacitor")
        self.assertFalse(result["resolved"])
        self.assertIsNone(result["kind"])

    def test_line_services_include_example_codes_as_check(self):
        self.assertEqual(set(plant_model.LINE_SERVICES), {
            "LSS", "ISS", "HSS", "LTRS", "BD", "HSD", "HG", "DF", "HPL", "IL", "PL", "OIL",
            "RV", "EQ", "DP", "GLY", "CW", "HR", "?", "CD", "OD", "LTRL", "LTL", "LTS"})
        for row in plant_model.LINE_SERVICES.values():
            self.assertEqual(row["origin"], "example provenance: replace with the source you verified")
            self.assertEqual(row["evidence"]["status"], "CHECK")
        for code in ("CD", "OD", "LTRL"):
            self.assertIn("(name inferred)", plant_model.LINE_SERVICES[code]["name"])
        self.assertFalse(plant_model.resolve_line_service("ZZ")["resolved"])
        self.assertFalse(plant_model.resolve_line_service("?")["resolved"])
        self.assertEqual(plant_model.resolve_line_service("hpl")["service"]["name"], "High-pressure liquid")

    @unittest.skipUnless(SERVICES_TS.is_file() and KINDS_TS.is_file(), "the reference app source not present")
    def test_ported_lists_match_their_sources(self):
        codes = re.findall(r"^  code\('([A-Z?]+)'", SERVICES_TS.read_text(), re.M)
        rai = [c for c, r in plant_model.LINE_SERVICES.items() if r["origin"].endswith("canvas-services.ts")]
        self.assertEqual(rai, codes)
        block = re.search(r"PLANT_COMPONENT_KINDS = \[(.*?)\]", KINDS_TS.read_text(), re.S).group(1)
        listed = next(e for e in plant_model.LEGACY_LISTS if e["id"] == "rai.pid-sim-bridge.PLANT_COMPONENT_KINDS")
        self.assertEqual(re.findall(r"'([a-z-]+)'", block), listed["values"])


class OpenDecisionTests(unittest.TestCase):
    def test_open_decisions_are_disputed_and_unchosen(self):
        self.assertEqual(set(decisions.OPEN_DECISIONS),
                         {"b114-marker-colour-scheme", "b114-70-psig-split", "canonical-northfield", "alarm-wording"})
        for item in decisions.OPEN_DECISIONS.values():
            self.assertEqual(item["evidence"]["status"], "DISPUTED")
            self.assertTrue(item["evidence"]["dispute"])
            self.assertIsNone(item["chosen"])
            self.assertGreaterEqual(len(item["positions"]), 2)

    def test_projection_refuses_a_chosen_decision(self):
        raw = json.loads((ROOT / "foundation_refrigeration/data/open-decisions.json").read_text())
        items = raw["data"]["decisions"]
        self.assertEqual(set(decisions.check(items)), set(decisions.OPEN_DECISIONS))
        for mutate in (lambda d: d.update(chosen="yellow body"),
                       lambda d: d.update(positions=d["positions"][:1]),
                       lambda d: d.update(evidence={"basis": {"kind": "practice", "note": "n"}, "status": "CHECK"})):
            copy = json.loads(json.dumps(items))
            mutate(copy[0])
            with self.assertRaises(decisions.DecisionError):
                decisions.check(copy)


if __name__ == "__main__":
    unittest.main()

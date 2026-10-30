"""Anhydrous ammonia quantity screen and standard-selection guard, ported from the reference app."""
import hashlib
import math
from pathlib import Path
import unittest

from foundation_refrigeration import process_safety
from foundation_refrigeration.process_safety import ProcessSafetyError
from foundation_refrigeration.tools import TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCREEN_TS = REPO / "upstream/app/packages/domain/src/process-safety/ammonia-quantity-screen.ts"
STANDARD_TS = REPO / "upstream/app/packages/domain/src/process-safety/standard-selection.ts"


def inventory(**overrides):
    value = {"framework": "osha-psm", "process_id": "process-1", "substance": "anhydrous-ammonia",
             "maximum_quantity_lb": {"lower": 10000, "upper": 10000}, "quantity_basis": "process-maximum",
             "boundary_review": "reviewed", "inventory_review": "reviewed", "freshness": "current",
             "source_kind": "retained", "source_ids": ["inventory-original"],
             "boundary_review_id": "boundary-review-1", "inventory_review_id": "inventory-review-1"}
    value.update(overrides)
    return value


def selection(**overrides):
    value = {"process_id": "process-1", "designation": "TEST-REFERENCE", "selected_edition": "2020",
             "latest_known_edition": "2025", "publication_status": "published",
             "authority_basis": "employer-selected", "selection_review_id": "selection-review",
             "applicability": "applicable", "applicability_review_id": "scope-review", "source_kind": "retained",
             "source_id": "original", "source_edition": "2020", "requirement_locator": "section-x",
             "source_access": "verified-content", "amendments_review_id": "amendments-review",
             "requirement_review_id": "content-review"}
    value.update(overrides)
    return value


class ProcessSafetyTests(unittest.TestCase):
    def test_thresholds_are_cited_ecfr_screens(self):
        self.assertEqual(set(process_safety.RULES), {"osha-psm", "epa-rmp"})
        osha, epa = process_safety.RULES["osha-psm"], process_safety.RULES["epa-rmp"]
        self.assertEqual((osha["threshold_lb"], osha["comparison"]), (10000, "at-or-above"))
        self.assertEqual((epa["threshold_lb"], epa["comparison"]), (10000, "above"))
        for rule, needle in ((osha, "1910.119"), (epa, "68.130")):
            self.assertEqual(rule["cas"], "7664-41-7")
            self.assertEqual(rule["threshold_evidence"].status, "CHECK")
            self.assertIn(needle, rule["threshold_evidence"].basis.url)
            self.assertTrue(rule["threshold_evidence"].basis.url.startswith("https://www.ecfr.gov/"))
        self.assertIn("10000", osha["threshold_evidence"].basis.quoted)
        self.assertIn("10,000", epa["threshold_evidence"].basis.quoted)
        self.assertIn("exceeds the threshold", epa["comparison_evidence"].basis.quoted)
        self.assertIn("68.115", epa["comparison_evidence"].basis.url)

    def test_federal_triggers_and_uncertain_bounds(self):
        exact = ((9999, "quantity-trigger-not-met", "quantity-trigger-not-met"),
                 (10000, "quantity-trigger-met", "quantity-trigger-not-met"),
                 (10001, "quantity-trigger-met", "quantity-trigger-met"))
        for pounds, osha, epa in exact:
            bounds = {"lower": pounds, "upper": pounds}
            self.assertEqual(process_safety.screen_ammonia_quantity(inventory(maximum_quantity_lb=bounds))["status"], osha)
            self.assertEqual(process_safety.screen_ammonia_quantity(
                inventory(framework="epa-rmp", maximum_quantity_lb=bounds))["status"], epa)
        spans = (("osha-psm", 9999, 10000, "unknown"), ("epa-rmp", 9999, 10000, "quantity-trigger-not-met"),
                 ("osha-psm", 10000, 10001, "quantity-trigger-met"), ("epa-rmp", 10000, 10001, "unknown"))
        for framework, lower, upper, status in spans:
            result = process_safety.screen_ammonia_quantity(
                inventory(framework=framework, maximum_quantity_lb={"lower": lower, "upper": upper}))
            self.assertEqual(result["status"], status)
            if status == "unknown":
                self.assertIn("threshold-straddled", result["gaps"])

    def test_bad_quantity_or_evidence_is_not_a_verdict(self):
        for bounds in (None, {"lower": -1, "upper": 1}, {"lower": 12000, "upper": 11000},
                       {"lower": math.nan, "upper": 10000}, {"lower": 10000, "upper": math.inf}):
            result = process_safety.screen_ammonia_quantity(inventory(maximum_quantity_lb=bounds))
            self.assertEqual(result["status"], "unknown")
            self.assertIn("invalid-or-missing-quantity", result["gaps"])
        overrides = ({"process_id": " "}, {"substance": "aqueous-ammonia"}, {"substance": "unknown"},
                     {"quantity_basis": "rough-estimate"}, {"quantity_basis": "current-reading"},
                     {"quantity_basis": "unknown"}, {"boundary_review": "pending"}, {"boundary_review_id": None},
                     {"inventory_review": "pending"}, {"inventory_review_id": " "}, {"freshness": "stale"},
                     {"freshness": "unknown"}, {"source_kind": "fixture"}, {"source_ids": []}, {"source_ids": [" "]})
        for override in overrides:
            result = process_safety.screen_ammonia_quantity(inventory(**override))
            self.assertEqual(result["status"], "unknown")
            self.assertGreater(len(result["gaps"]), 0)
        result = process_safety.screen_ammonia_quantity(
            inventory(boundary_review="pending", freshness="stale", source_ids=[]))
        self.assertEqual(result["gaps"], ["boundary-review-required", "current-evidence-required", "retained-source-required"])
        self.assertIn("does not establish site compliance", result["claim_boundary"])
        with self.assertRaises(ProcessSafetyError):
            process_safety.screen_ammonia_quantity(inventory(framework="state-plan"))

    def test_standard_selection_guard(self):
        kept = process_safety.assess_standard_requirement_selection(selection())
        self.assertEqual((kept["status"], kept["selected_edition"], kept["gaps"]), ("reference-supported", "2020", []))
        overrides = ({"publication_status": "draft"}, {"publication_status": "unknown"},
                     {"source_access": "metadata-only"}, {"source_access": "unavailable"}, {"source_edition": "2025"},
                     {"source_edition": None}, {"applicability": "not-applicable"}, {"applicability": "unassessed"},
                     {"authority_basis": "unresolved"}, {"process_id": " "}, {"designation": ""},
                     {"selected_edition": ""}, {"selection_review_id": None}, {"applicability_review_id": None},
                     {"amendments_review_id": None}, {"requirement_review_id": None}, {"source_kind": "fixture"},
                     {"source_id": None}, {"requirement_locator": " "})
        for override in overrides:
            result = process_safety.assess_standard_requirement_selection(selection(**override))
            self.assertEqual(result["status"], "review-required")
            self.assertGreater(len(result["gaps"]), 0)
        for basis in ("jurisdiction-adopted", "employer-selected", "manufacturer-applicable", "internal-practice"):
            self.assertEqual(process_safety.assess_standard_requirement_selection(
                selection(authority_basis=basis))["status"], "reference-supported")
        gaps = process_safety.assess_standard_requirement_selection(selection(
            applicability="unassessed", source_access="metadata-only", amendments_review_id=None))
        self.assertEqual(gaps["gaps"], ["applicability-review-required", "requirement-content-required",
                                         "amendments-review-required"])
        self.assertIn("does not approve equipment", gaps["claim_boundary"])

    def test_outputs_are_labeled_as_a_screen(self):
        results = (process_safety.screen_ammonia_quantity(inventory()),
                   process_safety.screen_ammonia_quantity(inventory(substance="aqueous-ammonia")),
                   process_safety.assess_standard_requirement_selection(selection()),
                   process_safety.assess_standard_requirement_selection(selection(publication_status="draft")))
        for result in results:
            self.assertEqual(result["label"], "screen")
            self.assertEqual(result["result_kind"], "screen")
            self.assertFalse(result["compliance_determination"])
            self.assertTrue(result["observation_only"])
            self.assertTrue(result["display"].startswith("Screen:"))
            self.assertIn("Not a compliance determination", result["display"])
            self.assertNotIn(result["status"], {"compliant", "noncompliant", "applicable", "covered"})
        self.assertEqual(len(TOOL_NAMES), 7)
        self.assertNotIn("screen_ammonia_quantity", TOOL_NAMES)

    @unittest.skipUnless(SCREEN_TS.is_file() and STANDARD_TS.is_file(), "the reference app source not present")
    def test_projection_is_pinned_to_the_typescript_sources(self):
        for row in process_safety._DATA["source_files"]:
            self.assertEqual(hashlib.sha256((REPO / row["path"]).read_bytes()).hexdigest(), row["sha256"])
        text = SCREEN_TS.read_text()
        self.assertIn("thresholdLb: 10_000", text)
        self.assertIn("comparison: 'at-or-above'", text)
        self.assertIn("comparison: 'above'", text)
        self.assertIn("assessStandardRequirementSelection", STANDARD_TS.read_text())


if __name__ == "__main__":
    unittest.main()

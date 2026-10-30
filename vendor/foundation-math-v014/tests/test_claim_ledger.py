"""Contract tests. Checker/reviewer names in fixtures are synthetic, not credentials."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.validate_claim_ledger import validate_ledger


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_claim_ledger.py"


class ClaimLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.artifact = self.base / "proof.txt"
        self.artifact.write_text("Synthetic test evidence. Not an actual formal checker receipt.\n")
        self.pin = {"path": "proof.txt", "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}

    def claim(self, identifier: str = "test.claim", status: str = "proof_draft") -> dict:
        return {
            "id": identifier,
            "statement": "Synthetic fixture claim for validating bookkeeping only.",
            "assumptions": [],
            "dependencies": [],
            "status": status,
            "closure": "open",
            "evidence": [{"kind": "proof", "description": "Synthetic fixture, not reviewed evidence.", "artifact": dict(self.pin)}],
            "verification": {"scope": "Synthetic test fixture only.", "reviewers": [], "trust": []},
        }

    def reviewed(self, identifier: str = "test.reviewed") -> dict:
        claim = self.claim(identifier, "reviewed_conditional")
        claim["verification"]["reviewers"] = ["synthetic-reviewer-for-tests-only"]
        claim["closure"] = "closed"
        return claim

    def formal(self, identifier: str = "test.formal") -> dict:
        claim = self.claim(identifier, "formally_checked")
        claim["assumptions"] = ["Fixture premise, not an asserted mathematical axiom."]
        claim["verification"]["trust"] = ["Synthetic fixture trust boundary."]
        claim["evidence"] = [{
            "kind": "formal_check", "description": "Synthetic fixture: no proof assistant was run.",
            "artifact": dict(self.pin), "checker": {"name": "fixture-checker", "version": "test-only-1"},
            "encoded_statement": "Fixture.proposition", "assumptions": list(claim["assumptions"]),
            "trust": ["Synthetic fixture trust boundary."], "result": "pass",
        }]
        claim["closure"] = "closed"
        return claim

    def ledger(self, *claims: dict) -> dict:
        return {"schema_version": 1, "title": "Synthetic unit-test ledger", "claims": list(claims)}

    def codes(self, data: object, **kwargs: object) -> set[str]:
        return {issue.code for issue in validate_ledger(data, base_dir=self.base, **kwargs)}

    def test_toy_ledger_valid_and_still_draft(self) -> None:
        path = ROOT / "examples" / "toy-ledger.json"
        data = json.loads(path.read_text())
        self.assertEqual(validate_ledger(data, base_dir=path.parent), [])
        self.assertEqual({c["status"] for c in data["claims"]}, {"proof_draft"})

    def test_draft_and_conjecture_need_no_evidence(self) -> None:
        for status in ("proof_draft", "conjecture"):
            with self.subTest(status=status):
                claim = self.claim(status=status)
                claim["evidence"] = []
                self.assertEqual(self.codes(self.ledger(claim)), set())

    def test_reviewed_and_formal_fixtures_pass_contract_not_truth(self) -> None:
        first = self.reviewed()
        second = self.formal()
        second["dependencies"] = [first["id"]]
        self.assertEqual(self.codes(self.ledger(first, second)), set())

    def test_status_is_not_promoted_by_evidence(self) -> None:
        claim = self.formal()
        claim.update(status="proof_draft", closure="open")
        data = self.ledger(claim)
        original = copy.deepcopy(data)
        self.assertEqual(self.codes(data), set())
        self.assertEqual(data, original)

    def test_missing_duplicate_and_cyclic_dependencies(self) -> None:
        claim = self.claim()
        claim["dependencies"] = ["missing"]
        self.assertIn("missing_dependency", self.codes(self.ledger(claim)))
        self.assertIn("duplicate_id", self.codes(self.ledger(self.claim(), self.claim())))
        first, second = self.claim("a"), self.claim("b")
        first["dependencies"], second["dependencies"] = ["b"], ["a"]
        self.assertIn("dependency_cycle", self.codes(self.ledger(first, second)))
        first["dependencies"] = ["a"]
        self.assertIn("dependency_cycle", self.codes(self.ledger(first)))
        first["dependencies"] = ["b", "b"]
        self.assertIn("duplicate_value", self.codes(self.ledger(first, second)))

    def test_closed_claim_cannot_hide_unresolved_dependencies(self) -> None:
        for status in ("proof_draft", "conjecture", "refuted"):
            with self.subTest(status=status):
                premise = self.claim("premise", status)
                conclusion = self.reviewed("conclusion")
                conclusion["dependencies"] = ["premise"]
                self.assertIn("unresolved_dependency", self.codes(self.ledger(premise, conclusion)))
        premise = self.reviewed("premise")
        premise["closure"] = "open"
        self.assertIn("unresolved_dependency", self.codes(self.ledger(premise, conclusion)))

    def test_open_checked_claim_may_record_unresolved_obligation(self) -> None:
        premise = self.claim("premise", "conjecture")
        conclusion = self.formal("conclusion")
        conclusion["dependencies"] = ["premise"]
        conclusion["closure"] = "open"
        self.assertEqual(self.codes(self.ledger(premise, conclusion)), set())

    def test_draft_and_conjecture_cannot_close(self) -> None:
        for status in ("proof_draft", "conjecture"):
            claim = self.claim(status=status)
            claim["closure"] = "closed"
            self.assertIn("closure_status", self.codes(self.ledger(claim)))

    def test_refutation_is_not_support_for_downstream_claim(self) -> None:
        premise = self.reviewed("refuted")
        premise["status"] = "refuted"
        premise["evidence"][0]["kind"] = "counterexample"
        self.assertEqual(self.codes(self.ledger(premise)), set())
        conclusion = self.reviewed("conclusion")
        conclusion["dependencies"] = [premise["id"]]
        self.assertIn("unresolved_dependency", self.codes(self.ledger(premise, conclusion)))

    def test_tests_alone_do_not_establish_reviewed_proof(self) -> None:
        claim = self.reviewed()
        claim["evidence"][0]["kind"] = "test"
        self.assertIn("review_evidence", self.codes(self.ledger(claim)))

    def test_checked_statuses_require_pinned_evidence(self) -> None:
        for claim, code in ((self.reviewed(), "review_evidence"), (self.formal(), "formal_evidence")):
            with self.subTest(status=claim["status"]):
                claim["evidence"] = []
                self.assertIn(code, self.codes(self.ledger(claim)))
        claim = self.reviewed()
        del claim["evidence"][0]["artifact"]["sha256"]
        self.assertIn("artifact_hash", self.codes(self.ledger(claim)))
        self.assertIn("review_evidence", self.codes(self.ledger(claim)))

    def test_review_scope_and_reviewers_required(self) -> None:
        claim = self.reviewed()
        claim["verification"]["scope"] = "  "
        claim["verification"]["reviewers"] = []
        self.assertIn("type", self.codes(self.ledger(claim)))
        self.assertIn("empty", self.codes(self.ledger(claim)))

    def test_formal_metadata_is_explicit_and_complete(self) -> None:
        for key in ("checker", "encoded_statement", "assumptions", "trust", "result"):
            with self.subTest(missing=key):
                claim = self.formal()
                del claim["evidence"][0][key]
                self.assertIn("formal_evidence", self.codes(self.ledger(claim)))
        for key in ("name", "version"):
            claim = self.formal()
            del claim["evidence"][0]["checker"][key]
            self.assertIn("formal_evidence", self.codes(self.ledger(claim)))
        claim = self.formal()
        claim["evidence"][0]["trust"] = []
        self.assertIn("formal_evidence", self.codes(self.ledger(claim)))
        claim = self.formal()
        claim["verification"]["trust"] = []
        self.assertIn("empty", self.codes(self.ledger(claim)))

    def test_formal_assumptions_must_match_and_cannot_be_omitted(self) -> None:
        claim = self.formal()
        claim["evidence"][0]["assumptions"] = []
        self.assertIn("formal_assumptions", self.codes(self.ledger(claim)))
        claim["assumptions"] = []
        self.assertEqual(self.codes(self.ledger(claim)), set())
        del claim["assumptions"]
        self.assertIn("missing_field", self.codes(self.ledger(claim)))

    def test_unsuccessful_checker_result_never_qualifies(self) -> None:
        for result in ("failed", "timeout", "unavailable", "simulated", "rejected", None):
            claim = self.formal()
            claim["evidence"][0]["result"] = result
            self.assertIn("formal_evidence", self.codes(self.ledger(claim)))

    def test_hash_mismatch_missing_file_and_invalid_hash(self) -> None:
        claim = self.reviewed()
        self.artifact.write_text("Changed bytes.\n")
        self.assertIn("artifact_mismatch", self.codes(self.ledger(claim)))
        self.assertIn("review_evidence", self.codes(self.ledger(claim)))
        self.artifact.unlink()
        self.assertIn("artifact_missing", self.codes(self.ledger(claim)))
        claim["evidence"][0]["artifact"]["sha256"] = "not a hash"
        self.assertIn("artifact_hash", self.codes(self.ledger(claim)))

    def test_unsafe_and_nonportable_paths_rejected(self) -> None:
        for path in ("/tmp/x", "../x", "a/../x", "./x", "a//x", "a/", "C:/x", "a\\x"):
            with self.subTest(path=path):
                claim = self.claim()
                claim["evidence"][0]["artifact"]["path"] = path
                self.assertIn("artifact_path", self.codes(self.ledger(claim)))

    def test_symlink_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as outer:
            outside = Path(outer) / "outside.txt"
            outside.write_text("Outside evidence.\n")
            link = self.base / "escape.txt"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError):
                self.skipTest("Creating symlinks is unsupported on this platform.")
            claim = self.claim()
            claim["evidence"][0]["artifact"] = {"path": "escape.txt", "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}
            self.assertIn("artifact_path", self.codes(self.ledger(claim)))

    def test_structure_only_does_not_verify_bytes(self) -> None:
        self.artifact.unlink()
        self.assertEqual(self.codes(self.ledger(self.reviewed()), verify_artifacts=False), set())

    def test_bad_shapes_report_issues_not_crashes(self) -> None:
        for data in (None, [], {}, {"schema_version": True, "title": "x", "claims": []}):
            self.assertTrue(self.codes(data))
        for key in ("id", "statement", "assumptions", "dependencies", "status", "closure", "evidence", "verification"):
            for bad in (None, 7, {}, [None]):
                with self.subTest(key=key, bad=bad):
                    claim = self.claim()
                    claim[key] = bad
                    self.assertTrue(self.codes(self.ledger(claim)))

    def test_unknown_fields_and_statuses_rejected(self) -> None:
        claim = self.claim()
        claim["status"] = "proven"
        claim["confidence"] = 1.0
        self.assertIn("status", self.codes(self.ledger(claim)))
        self.assertIn("unknown_field", self.codes(self.ledger(claim)))
        claim = self.claim()
        claim["evidence"][0]["result"] = "pass"
        self.assertIn("unexpected_formal_field", self.codes(self.ledger(claim)))

    def test_deep_dependency_graph_is_iterative(self) -> None:
        claims = [self.claim(f"claim{i}") for i in range(1500)]
        for i, claim in enumerate(claims[:-1]):
            claim["dependencies"] = [claims[i + 1]["id"]]
        self.assertEqual(self.codes(self.ledger(*claims), verify_artifacts=False), set())

    def test_deliberately_invalid_examples_fail(self) -> None:
        expected = {
            "missing-dependency.json": "missing_dependency",
            "dependency-cycle.json": "dependency_cycle",
            "duplicate-id.json": "duplicate_id",
            "unsupported-closure.json": "unresolved_dependency",
            "missing-formal-evidence.json": "formal_evidence",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                path = ROOT / "examples" / "invalid" / name
                issues = validate_ledger(json.loads(path.read_text()), base_dir=path.parent)
                self.assertIn(code, {issue.code for issue in issues})

    def test_cli_portable_paths_and_optimized_mode(self) -> None:
        for flag in ([], ["-O"]):
            result = subprocess.run([sys.executable, *flag, str(VALIDATOR), str(ROOT / "examples" / "toy-ledger.json")], cwd=self.base, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("not a proof certificate", result.stdout)
        result = subprocess.run([sys.executable, str(VALIDATOR), str(ROOT / "examples" / "toy-ledger.json"), "--structure-only"], cwd=self.base, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("artifact bytes were not checked", result.stdout)

    def test_cli_rejects_duplicate_keys_non_json_constants_and_missing_input(self) -> None:
        for text in ('{"title":"a","title":"b"}', '{"value":NaN}', '{"value":Infinity}', '{invalid'):
            path = self.base / "input.json"
            path.write_text(text)
            result = subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stderr)
        result = subprocess.run([sys.executable, str(VALIDATOR), str(self.base / "missing.json")], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)

    def test_cli_invalid_ledger_returns_one(self) -> None:
        result = subprocess.run([sys.executable, str(VALIDATOR), str(ROOT / "examples" / "invalid" / "dependency-cycle.json")], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("dependency_cycle", result.stderr)

    def test_tiny_finite_regression_normal_and_optimized(self) -> None:
        for flag in ([], ["-O"]):
            result = subprocess.run([sys.executable, *flag, str(ROOT / "examples" / "artifacts" / "check_triangular.py")], cwd=self.base, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("1001 finite cases", result.stdout)
            self.assertIn("not a universal proof", result.stdout)


if __name__ == "__main__":
    unittest.main()

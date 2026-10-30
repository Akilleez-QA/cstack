#!/usr/bin/env python3

import copy
import tempfile

import yaml

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_capsule.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CapsuleLinterTests(unittest.TestCase):
    def run_fixture(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURES / name)],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_payload(self, payload: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capsule.yaml"
            path.write_text(payload, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False, capture_output=True, text=True,
            )

    def valid_data(self) -> dict:
        return yaml.safe_load((FIXTURES / "valid-capsule.yaml").read_text())

    def assert_invalid(self, data: dict, message: str) -> None:
        result = self.run_payload(yaml.safe_dump(data))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(message, result.stderr)

    def test_malformed_reference_collections(self) -> None:
        for field, key in (
            ("claims", "supports"), ("evidence_bundles", "supports_claims"),
            ("evidence_bundles", "artifacts"), ("orientations", "depends_on"),
            ("decisions", "depends_on"), ("predictions", "outcome_evidence"),
        ):
            for value in (None, "D-demo-retest", {}, [{}], [[]], [42]):
                with self.subTest(field=field, key=key, value=value):
                    data = self.valid_data()
                    data[field][0][key] = value
                    self.assert_invalid(data, f"{field}[0].{key}")

    def test_malformed_scalar_references(self) -> None:
        for key in ("oracle", "artifact"):
            for value in (None, [], {}, ["AC-demo-visible"], 42):
                with self.subTest(key=key, value=value):
                    data = self.valid_data()
                    data["predictions"][0][key] = value
                    self.assert_invalid(data, f"predictions[0].{key}")
        for value in ([], {}, ["D-demo-retest"]):
            data = self.valid_data()
            data["current_head"] = value
            self.assert_invalid(data, "current_head")

    def test_unhashable_enum_values(self) -> None:
        paths = (
            ("schema",), ("delivery_state",), ("outcome_state",),
            ("claims", 0, "state"), ("claims", 0, "status"),
            ("evidence_bundles", 0, "completeness"),
            ("predictions", 0, "status"),
            ("predictions", 0, "status_history", 0),
        )
        for path in paths:
            for value in ([], {}):
                with self.subTest(path=path, value=value):
                    data = self.valid_data()
                    target = data
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = value
                    self.assert_invalid(data, "invalid" if path[0] != "schema" else "schema")

    def test_malformed_contradiction_references(self) -> None:
        base = self.valid_data()
        base["contradictions"] = [{
            "id": "C-demo-one", "target": "D-demo-retest", "evidence": [],
            "scope": "demo", "effect": "reopen", "affected_ids": [],
            "disposition": "unresolved", "repaired_by": [],
        }]
        for key in ("target", "evidence", "affected_ids", "repaired_by", "disposition"):
            for value in (None, {}, [[1]]):
                with self.subTest(key=key, value=value):
                    data = copy.deepcopy(base)
                    data["contradictions"][0][key] = value
                    self.assert_invalid(data, f"contradictions[0].{key}")

    def test_rejects_impossible_dates_and_offsets(self) -> None:
        for value in ("2026-99-99T99:99:99Z", "2026-02-29T12:00:00Z",
                      "2026-10-01T24:00:00Z", "2026-10-01T12:00:00+01:99"):
            with self.subTest(value=value):
                data = self.valid_data()
                data["generated_at"] = value
                self.assert_invalid(data, "generated_at")
        result = self.run_payload("generated_at: 2026-99-99T99:99:99Z\n")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_accepts_real_rfc3339_dates(self) -> None:
        for value in ("2024-02-29T12:00:00Z", "2026-10-01T12:00:00.123-04:00"):
            data = self.valid_data()
            data["generated_at"] = value
            result = self.run_payload(yaml.safe_dump(data))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_nonstring_mapping_keys(self) -> None:
        for payload in ("? [a, b]\n: value\n", "42: value\n"):
            result = self.run_payload(payload)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("mapping keys must be strings", result.stderr)

    def oversize(self) -> dict:
        data = self.valid_data()
        data["constraints"] = "x" * 8000
        return data

    def test_oversize_capsule_rejected_without_overflow(self) -> None:
        self.assert_invalid(self.oversize(), "exceeds ceiling")

    def test_declared_overflow_allows_oversize_capsule(self) -> None:
        data = self.oversize()
        data["capsule_overflow"] = "Raw logs archived; locator in rehydration."
        result = self.run_payload(yaml.safe_dump(data))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_overflow_does_not_waive_ceiling(self) -> None:
        data = self.oversize()
        data["capsule_overflow"] = "  "
        self.assert_invalid(data, "exceeds ceiling")

    def test_valid_capsule(self) -> None:
        result = self.run_fixture("valid-capsule.yaml")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("epistemic and behavioral correctness remain untested", result.stdout)

    def test_rejects_failed_prediction_resurrection(self) -> None:
        result = self.run_fixture("invalid-resurrection.yaml")
        self.assertEqual(result.returncode, 1)
        self.assertIn("terminal prediction was resurrected", result.stderr)

    def test_rejects_truncated_evidence(self) -> None:
        result = self.run_fixture("invalid-truncated-evidence.yaml")
        self.assertEqual(result.returncode, 1)
        self.assertIn("partial or truncated evidence", result.stderr)


if __name__ == "__main__":
    unittest.main()

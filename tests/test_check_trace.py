import contextlib
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools import check_trace

ROOT = Path(__file__).resolve().parents[1]

SRS = """\
# SRS

## 1. Intro

### CS-REQ-001 — First

The thing shall work.

- Derivation: `src/a.py`
- Allocated to: SDD-C1
- Verification: T
- Status: Baselined

### CS-REQ-002 — Second

The other thing shall work.

- Derivation: `src/a.py`
- Allocated to: SDD-C1
- Verification: I
- Status: Baselined
"""

VM = """\
# VM

See [the SRS](../requirements/requirements.md#cs-req-001--first).

## Requirement to test

| Requirement | Method | Tests | Observation | Last result |
|---|---|---|---|---|
| CS-REQ-001 | T | `tests/test_a.py::ATests.test_one` | x | y |
| CS-REQ-002 | I | Inspection: `src/a.py` | x | y |

## Untested requirement gaps

| Requirement | Why | Interim |
|---|---|---|
| CS-REQ-002 | no test | inspect |

## Tests without a requirement

| File | Classification |
|---|---|
"""

SDD = """\
# SDD

## 4. Decomposition and allocation

| ID | Element | Implementation | Responsibility | Requirements |
|---|---|---|---|---|
| SDD-C1 | Thing | `src/a.py` | Does it | CS-REQ-001, CS-REQ-002 |
| SDD-C2 | Vendor | `src/` | Copied | Infrastructure |
"""

TEST_A = """\
import unittest


class Base(unittest.TestCase):
    def test_inherited(self):
        pass


class ATests(Base):
    def test_one(self):
        pass
"""


def tree(root, srs=SRS, vm=VM, sdd=SDD, tests=None):
    files = {"docs/requirements/requirements.md": srs, "docs/verification/verification-matrix.md": vm,
             "docs/architecture/architecture.md": sdd, "src/a.py": "", "tests/test_a.py": TEST_A}
    files.update(tests or {})
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class CheckTrace(unittest.TestCase):
    def run_check(self, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree(root, **kwargs)
            return check_trace.check(root)

    def test_a_consistent_tree_passes_and_reports_its_gaps(self):
        result = self.run_check()
        self.assertEqual(check_trace.failures(result), [])
        self.assertEqual(result["requirements"], 2)
        self.assertEqual(result["gaps"], ["CS-REQ-002"])
        self.assertEqual(result["traced_test_files"], 1)

    def test_a_requirement_with_no_row_is_untraced(self):
        result = self.run_check(vm=VM.replace("| CS-REQ-001 | T | `tests/test_a.py::ATests.test_one` | x | y |\n", ""))
        self.assertIn("CS-REQ-001", result["untraced"])

    def test_a_requirement_with_no_test_fails_unless_it_is_a_listed_gap(self):
        result = self.run_check(vm=VM.replace("| CS-REQ-002 | no test | inspect |\n", ""))
        self.assertEqual(result["untested"], ["CS-REQ-002"])
        self.assertEqual(result["gaps"], [])

    def test_a_listed_gap_that_has_a_test_is_stale(self):
        vm = VM.replace("| CS-REQ-002 | no test | inspect |", "| CS-REQ-001 | no test | inspect |\n| CS-REQ-002 | no test | inspect |")
        self.assertIn("CS-REQ-001", self.run_check(vm=vm)["stale_gaps"])

    def test_missing_test_files_classes_and_methods_are_reported(self):
        for ref in ("tests/test_b.py", "tests/test_a.py::NoTests", "tests/test_a.py::ATests.test_two"):
            with self.subTest(ref=ref):
                result = self.run_check(vm=VM.replace("tests/test_a.py::ATests.test_one", ref))
                self.assertEqual([m["ref"] for m in result["missing_tests"]], [ref])

    def test_inherited_methods_and_whole_files_resolve(self):
        for ref in ("tests/test_a.py", "tests/test_a.py::ATests", "tests/test_a.py::ATests.test_inherited"):
            with self.subTest(ref=ref):
                self.assertEqual(check_trace.failures(self.run_check(vm=VM.replace(
                    "tests/test_a.py::ATests.test_one", ref))), [])

    def test_a_test_file_neither_traced_nor_classified_fails(self):
        extra = {"tests/test_c.py": "import unittest\n\n\nclass C(unittest.TestCase):\n    def test_x(self):\n        pass\n"}
        self.assertEqual(self.run_check(tests=extra)["unclassified_tests"], ["tests/test_c.py"])
        classified = VM + "| `tests/test_c.py` | Infrastructure: smoke |\n"
        self.assertEqual(self.run_check(vm=classified, tests=extra)["unclassified_tests"], [])

    def test_allocation_must_agree_in_both_directions(self):
        result = self.run_check(sdd=SDD.replace("CS-REQ-001, CS-REQ-002", "CS-REQ-002"))
        self.assertIn("CS-REQ-001", [m["requirement"] for m in result["allocation"]])
        result = self.run_check(srs=SRS.replace("Allocated to: SDD-C1\n- Verification: T", "Allocated to: SDD-C9\n- Verification: T"))
        self.assertIn("CS-REQ-001", [m["requirement"] for m in result["allocation"]])
        result = self.run_check(sdd=SDD.replace("CS-REQ-001, CS-REQ-002", "CS-REQ-001, CS-REQ-002, CS-REQ-003"))
        self.assertIn("CS-REQ-003", [m["requirement"] for m in result["allocation"]])
        result = self.run_check(sdd=SDD.replace("| Infrastructure |", "| |"))
        self.assertIn("SDD-C2", [m["component"] for m in result["allocation"]])

    def test_requirement_fields_and_derivation_paths_are_checked(self):
        result = self.run_check(srs=SRS.replace("- Status: Baselined\n", "", 1))
        self.assertIn("CS-REQ-001", [m["requirement"] for m in result["fields"]])
        result = self.run_check(srs=SRS.replace("`src/a.py`", "`src/gone.py`", 1))
        self.assertIn("src/gone.py", [m["path"] for m in result["fields"]])

    def test_dead_links_and_anchors_in_control_documents_fail(self):
        for bad in ("../requirements/missing.md", "../requirements/requirements.md#no-such-heading", "#nowhere"):
            with self.subTest(bad=bad):
                result = self.run_check(vm=VM.replace("../requirements/requirements.md#cs-req-001--first", bad))
                self.assertEqual([d["target"] for d in result["dead_links"]], [bad])

    def test_github_slugs(self):
        self.assertEqual(check_trace.slug("1. Software classification (self-assessed)"),
                         "1-software-classification-self-assessed")
        self.assertEqual(check_trace.slug("CS-REQ-001 — Composition"), "cs-req-001--composition")
        self.assertEqual(check_trace.slug("`check_trace.py` and **CI**"), "check_tracepy-and-ci")

    def test_the_cli_exits_nonzero_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree(root, vm=VM.replace("tests/test_a.py::ATests.test_one", "tests/test_b.py"))
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_trace.main(["--root", str(root)]), 1)
            self.assertIn("tests/test_b.py", out.getvalue())

    def test_the_repository_trace_is_clean(self):
        result = check_trace.check(ROOT)
        self.assertEqual(check_trace.failures(result), [], textwrap.shorten(str(check_trace.failures(result)), 2000))


if __name__ == "__main__":
    unittest.main()

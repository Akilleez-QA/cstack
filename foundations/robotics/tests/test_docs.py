import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foundation_robotics_bridge.schemas import tool_definitions
from tools import gen_docs, gen_reports


def tool(*args):
    return subprocess.run([sys.executable, "-B", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


def field_paths(schema, path, found):
    if schema.get("type") == "array":
        field_paths(schema["items"], path + "[]", found)
    for option in schema.get("anyOf", []) + schema.get("oneOf", []):
        field_paths(option, path, found)
    if type(schema.get("additionalProperties")) is dict:
        field_paths(schema["additionalProperties"], path + ".<key>", found)
    for name, sub in schema.get("properties", {}).items():
        found.add(f"{path}.{name}".lstrip("."))
        field_paths(sub, f"{path}.{name}", found)
    return found


def suite(code, results, ran):
    return ("python -m unittest", code, results, "", "0" * 64, ran)


SUBTEST_FAILURE = """test_a (tests.test_x.A.test_a) ... ok
test_b (tests.test_x.A.test_b) ...
  test_b (tests.test_x.A.test_b) (i=1) ... FAIL
test_c (tests.test_x.A.test_c)
Docstring line ... ok
test_d (tests.test_x.A.test_d) ... skipped 'no data'

======================================================================
FAIL: test_b (tests.test_x.A.test_b) (i=1)
----------------------------------------------------------------------
Ran 4 tests in 0.001s

FAILED (failures=1, skipped=1)
"""


class DocTests(unittest.TestCase):
    def test_trace_and_links_pass(self):
        proc = tool("tools/check_trace.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_manifest_copy_passes_its_own_trace_check(self):
        files = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["files"]
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp)
            for name in [*files, "SOURCE-MANIFEST.json"]:
                (copy / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, copy / name)
            proc = subprocess.run([sys.executable, "-B", "tools/check_trace.py"], cwd=copy, capture_output=True,
                                  text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_generated_docs_are_current(self):
        proc = tool("tools/gen_docs.py", "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_catalog_documents_fields_inside_unions_and_maps(self):
        text = gen_docs.catalog()
        for path in ("result.detail.gears[].speed_mrad_s", "result.detail.reads_as",
                     "result.detail.frames[].expected_mrad", "result.expected.at_this_speed.froude_permille",
                     "result.worst.<key>.frame"):
            self.assertIn(f"| `{path}` |", text)

    def test_catalog_documents_every_schema_field(self):
        text = gen_docs.catalog()
        for definition in tool_definitions():
            result = definition["outputSchema"]["properties"]["receipt"]["properties"]["result"]
            expected = field_paths(result, "result", set()) | field_paths(definition["inputSchema"], "", set())
            missing = sorted(p for p in expected if f"| `{p}` |" not in text)
            self.assertEqual(missing, [], definition["name"])

    def test_catalog_labels_each_union_variant(self):
        rows = []
        gen_docs.walk({"properties": {"detail": {"anyOf": [
            {"type": "object", "properties": {"a": {"type": "boolean"}}, "required": ["a"]},
            {"type": "object", "properties": {"b": {"type": "boolean"}}, "required": []}]}},
            "required": ["detail"]}, "", rows)
        self.assertEqual(rows[1:], [("detail.a", "boolean", "yes; in `detail` variant 1 of 2"),
                                    ("detail.b", "boolean", "no; in `detail` variant 2 of 2")])

    def test_report_parser_keeps_subtest_failures_and_skips(self):
        results, ran = gen_reports.parse(SUBTEST_FAILURE)
        self.assertEqual(ran, 4)
        self.assertEqual(results, {"tests/test_x.py::A.test_a": "ok", "tests/test_x.py::A.test_b": "FAIL",
                                   "tests/test_x.py::A.test_c": "ok",
                                   "tests/test_x.py::A.test_d": "skipped 'no data'"})

    def test_report_does_not_call_skipped_tests_passed(self):
        conclusion, gates = gen_reports.assess([suite(0, {"t::A.a": "ok", "t::A.b": "skipped 'x'"}, 2)] * 2, [],
                                               True)
        self.assertTrue(conclusion.startswith("NOT PASSED"), conclusion)
        self.assertIn("1 skipped", conclusion)
        self.assertTrue(gates)

    def test_report_does_not_call_expected_failures_or_unexpected_successes_passed(self):
        for outcome in ("expected failure", "unexpected success"):
            conclusion, gates = gen_reports.assess([suite(0, {"t::A.a": outcome}, 1)], [], True)
            self.assertTrue(conclusion.startswith("NOT PASSED"), outcome)

    def test_report_fails_on_failed_trace_gate(self):
        conclusion, gates = gen_reports.assess([suite(0, {"t::A.a": "ok"}, 1)], ["dead link"], True)
        self.assertTrue(conclusion.startswith("NOT PASSED"), conclusion)
        self.assertIn("trace check failed with 1 problems", gates)

    def test_report_fails_on_stale_manifest(self):
        conclusion, gates = gen_reports.assess([suite(0, {"t::A.a": "ok"}, 1)], [], False)
        self.assertTrue(conclusion.startswith("NOT PASSED"), conclusion)

    def test_report_fails_when_outcomes_go_unparsed(self):
        for results, ran in (({"t::A.a": "ok"}, 2), ({}, 0), ({"t::A.a": "ok"}, None)):
            conclusion, gates = gen_reports.assess([suite(0, results, ran)], [], True)
            self.assertTrue(conclusion.startswith("NOT PASSED"), (results, ran))

    def test_report_fails_on_nonzero_exit(self):
        conclusion, gates = gen_reports.assess([suite(1, {"t::A.a": "ok"}, 1)], [], True)
        self.assertTrue(conclusion.startswith("NOT PASSED"), conclusion)

    def test_report_passes_only_when_every_gate_passes(self):
        conclusion, gates = gen_reports.assess([suite(0, {"t::A.a": "ok"}, 1)] * 2, [], True)
        self.assertEqual(gates, [])
        self.assertTrue(conclusion.startswith("all suites passed"), conclusion)


if __name__ == "__main__":
    unittest.main()

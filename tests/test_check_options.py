import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import check_options

ROOT = Path(__file__).resolve().parent.parent
KINDS = ["conventional"] * 14 + list(check_options.REQUIRED_KINDS)
TOPICS = ["cache", "queue", "index", "shard", "replica", "batch", "stream", "lease", "quota", "retry", "canary",
          "rollback", "audit", "fixture", "probe", "mirror", "throttle", "snapshot", "pause", "owner"]
VERBS = ["add", "split", "rebuild", "move", "copy", "group", "pipe", "renew", "limit", "repeat", "ship", "revert",
         "log", "freeze", "measure", "clone", "slow", "save", "stop", "ask"]


def record(**changes):
    options = [{"id": f"o{n:02d}", "kind": KINDS[n], "mechanism": f"{VERBS[n]} {TOPICS[n]}",
                "summary": f"{TOPICS[n]} approach number {n} via {VERBS[n]}ing"} for n in range(20)]
    document = {"schema": "cstack.options/0.1", "goal": "Synthetic goal", "options": options}
    document.update(changes)
    return document


class OptionsRecord(unittest.TestCase):
    def test_twenty_distinct_options_with_every_kind_pass(self):
        self.assertEqual(check_options.problems(record()), [])

    def test_fewer_than_twenty_options_fail(self):
        document = record()
        document["options"] = document["options"][:19]
        self.assertTrue(any("19 given; exactly 20" in p for p in check_options.problems(document)))

    def test_a_missing_required_kind_fails(self):
        document = record()
        document["options"][19]["kind"] = "conventional"
        self.assertIn("no escalation option; include at least one", check_options.problems(document))

    def test_duplicate_ids_and_unknown_kinds_fail(self):
        document = record()
        document["options"][1]["id"] = "o00"
        document["options"][2]["kind"] = "other"
        found = check_options.problems(document)
        self.assertIn("id 'o00' is used more than once", found)
        self.assertTrue(any("kind 'other'" in p for p in found))

    def test_a_shared_mechanism_fails(self):
        document = record()
        document["options"][5]["mechanism"] = "Add the CACHE"
        self.assertTrue(any("o00 and o05 share one mechanism" in p for p in check_options.problems(document)))

    def test_a_near_verbatim_rephrasing_fails(self):
        document = record()
        document["options"][7] = dict(document["options"][0], id="o07", kind="conventional",
                                      mechanism="add cache layer", summary="cache approach number 0 via adding")
        self.assertTrue(any("o00 and o07 are near-duplicates" in p for p in check_options.problems(document)))

    def test_malformed_records_fail_without_raising(self):
        self.assertEqual(check_options.problems([]), ["the record must be a JSON object"])
        found = check_options.problems(record(schema="x", goal="", options=[{"id": "a"}, 3]))
        self.assertTrue(any("schema must be" in p for p in found))
        self.assertTrue(any("missing kind, mechanism, summary" in p for p in found))
        self.assertTrue(any("must be an object" in p for p in found))

    def test_the_command_exits_by_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / "good.json", Path(tmp) / "bad.json"
            good.write_text(json.dumps(record()))
            bad.write_text(json.dumps(record(options=[])))
            run = [sys.executable, "-I", "-B", str(ROOT / "tools/check_options.py")]
            self.assertEqual(subprocess.run(run + [str(good)], capture_output=True).returncode, 0)
            failed = subprocess.run(run + [str(bad)], capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1)
            self.assertIn("exactly 20", failed.stdout)


if __name__ == "__main__":
    unittest.main()

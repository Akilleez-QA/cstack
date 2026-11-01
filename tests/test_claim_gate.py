import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import FakeFoundation, execute_one
from tools.claim_gate import REPORTED_ONLY, SUPPORTED, UNSUPPORTED, extract_claims, gate

ROOT = Path(__file__).resolve().parents[1]


def outcome(seq, operation, raw, status="completed", capability="local_checks"):
    return {"sequence": seq, "kind": "outcome", "data": {"outcome": {
        "operation": operation, "capability_id": capability, "execution_status": status,
        "raw_result": raw if status in ("completed", "tool_error") else None},
        "interpretation": {"evidence_kind": "tool_observation" if status == "completed" else "unassessed"}}}


def event(seq, kind, data):
    return {"sequence": seq, "kind": kind, "data": data}


def verdicts(report, events):
    return [(c["verdict"], c["sequences"]) for c in gate(report, events)["claims"]]


class ClaimExtraction(unittest.TestCase):
    def test_strong_words_and_numbers_with_units_are_claims(self):
        claims = extract_claims("The parser is verified. Ran 42 tests in 3.5 s. Release 3.12 is out.")
        self.assertEqual([c["requires"] for c in claims], [["effect"], ["numeric"]])

    def test_questions_negations_hedges_code_and_quotes_are_not_claims(self):
        report = ("Is it live? Deployed but not verified live. It should be fixed once CI runs.\n"
                  "```\nall tests passed\n```\n> the login flow works\nRun the tests to verify.")
        self.assertEqual([c["text"] for c in extract_claims(report)], [])

    def test_dotted_and_grouped_numbers_survive_sentence_split(self):
        claims = extract_claims("Read 1,470,679 files and 660.7 GB")
        self.assertEqual(claims[0]["requires"], ["numeric"])


class Verdicts(unittest.TestCase):
    def test_verified_claim_with_only_a_type_check_is_unsupported(self):
        # pstack verdict ladder: type-check only is below live-verified.
        events = [outcome(1, "typecheck", {"exit_code": 0, "errors": 0})]
        result = gate("The handoff parser is verified.", events)
        self.assertFalse(result["passed"])
        self.assertEqual(result["claims"][0]["verdict"], UNSUPPORTED)
        self.assertIn("static", result["claims"][0]["reason"])

    def test_type_check_claim_is_supported_by_a_type_check(self):
        events = [outcome(4, "typecheck", {"exit_code": 0})]
        self.assertEqual(verdicts("Type-check passed.", events), [(SUPPORTED, [4])])

    def test_unit_tests_support_passed_but_not_live(self):
        events = [outcome(2, "unittest", {"exit_code": 0, "tests_run": 52})]
        self.assertEqual(verdicts("All 52 tests passed.", events), [(SUPPORTED, [2])])
        self.assertEqual(verdicts("The gate works", events)[0][0], UNSUPPORTED)

    def test_deploy_supports_deployed_but_deployed_is_not_live(self):
        # PAI T1: deployed is not live; implementation is not effect.
        events = [outcome(3, "deploy_worker", {"exit_code": 0})]
        self.assertEqual(verdicts("Worker deployed.", events), [(SUPPORTED, [3])])
        live = gate("The worker is live.", events)["claims"][0]
        self.assertEqual(live["verdict"], UNSUPPORTED)
        self.assertIn("implementation is not effect", live["reason"])
        probed = events + [outcome(5, "probe_worker_url", {"status": 200})]
        self.assertEqual(verdicts("The worker is live.", probed), [(SUPPORTED, [5])])

    def test_number_needs_an_outcome_containing_that_number(self):
        events = [outcome(7, "reading", {"suction_psig": 31.4})]
        self.assertEqual(verdicts("Suction measured 31.4 psig", events), [(SUPPORTED, [7])])
        self.assertEqual(verdicts("Suction measured 33 psig", events)[0][0], UNSUPPORTED)

    def test_hash_or_summary_is_not_corroboration(self):
        events = [outcome(1, "sha256_manifest", {"files": 561, "matched": True}),
                  outcome(2, "reading", {"summary": "42 tests passed", "sha256": "42" * 32})]
        self.assertEqual(verdicts("Validated 561 files", events)[0][0], UNSUPPORTED)
        self.assertEqual(verdicts("Ran 42 tests", events)[0][0], UNSUPPORTED)

    def test_proposal_or_inference_only_is_reported_only(self):
        # t3code handoff: an agent-claimed test stays "reported" until something runs it.
        events = [event(1, "proposal", {"plan": "deploy the sensor bridge"}),
                  event(2, "inference", {"claim": "bridge tests passed"})]
        self.assertEqual(verdicts("Sensor bridge tested", events), [(REPORTED_ONLY, [1, 2])])

    def test_action_without_outcome_is_not_effect(self):
        events = [event(1, "action", {"attempt_id": "a-1", "operation": "deploy_bridge"})]
        self.assertEqual(verdicts("Bridge deployed", events)[0][0], REPORTED_ONLY)

    def test_failed_timed_out_and_corrected_outcomes_support_nothing(self):
        failing = [outcome(1, "unittest", {"exit_code": 1, "tests_run": 9})]
        self.assertEqual(verdicts("Tests passed", failing)[0][0], UNSUPPORTED)
        timed_out = [outcome(2, "reading", None, status="timed_out")]
        self.assertEqual(verdicts("Reading verified", timed_out)[0][0], UNSUPPORTED)
        corrected = [outcome(3, "reading", {"t": 1}), event(4, "correction", {"corrects": 3})]
        self.assertEqual(verdicts("Reading verified", corrected)[0][0], UNSUPPORTED)

    def test_no_evidence_at_all_is_unsupported_and_no_claims_pass(self):
        self.assertEqual(verdicts("Fixed the drift alarm.", []), [(UNSUPPORTED, [])])
        self.assertTrue(gate("Opened the PR for review.", [])["passed"])

    def test_real_memory_ledger_events(self):
        core = FakeFoundation()
        execute_one(core)
        events = core.ledger()
        seq = [e["sequence"] for e in events if e["kind"] == "outcome"]
        self.assertEqual(verdicts("Sensor reading verified at 12.5 °C", events), [(SUPPORTED, seq)])

    def test_malformed_ledger_is_rejected(self):
        with self.assertRaises(ValueError):
            gate("Verified.", {"not": "a list"})


class Cli(unittest.TestCase):
    def run_cli(self, report, events, *, atom_refs=None):
        with tempfile.TemporaryDirectory() as td:
            r, l = Path(td)/"r.md", Path(td)/"events.json"
            r.write_text(report)
            l.write_text(json.dumps(events))
            args = [sys.executable, "-B", "tools/claim_gate.py", "--report", str(r), "--ledger", str(l)]
            if atom_refs is not None:
                atoms, refs = Path(td)/"atoms.jsonl", Path(td)/"refs.json"
                atoms.write_text("")
                refs.write_text(json.dumps(atom_refs))
                args.extend(["--atoms", str(atoms), "--atom-refs", str(refs), "--consumer", "test-report"])
            return subprocess.run(args,
                                  cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_unavailable_atom_registry_fails_closed(self):
        for refs in ([], [{"id": "atom-1", "sha256": "0" * 64}]):
            with self.subTest(refs=refs):
                result = self.run_cli("Opened the PR for review.", [], atom_refs=refs)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                error = json.loads(result.stderr)
                self.assertEqual(error["schema"], "cstack.claim-gate/0.1")
                self.assertIn("Approved-atoms Registry is unavailable", error["error"])
                self.assertIn("cannot validate --atoms", error["error"])

    def test_exit_codes(self):
        bad = self.run_cli("All checks verified.", [outcome(1, "typecheck", {"exit_code": 0})])
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(json.loads(bad.stdout)["unsupported"], 1)
        good = self.run_cli("Type-check passed.", [outcome(1, "typecheck", {"exit_code": 0})])
        self.assertEqual(good.returncode, 0, good.stdout)
        self.assertEqual(self.run_cli("Verified.", {"ledger": "x"}).returncode, 2)


if __name__ == "__main__":
    unittest.main()

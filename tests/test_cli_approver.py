import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from adapters.terminal_approver import TerminalApprover
from poodo_core import CapabilityRequest


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "examples/ask-approval.json").read_text())
REQUEST = CapabilityRequest.from_dict(DOCUMENT["calls"][0]["request"])


class CliApproverTests(unittest.TestCase):
    def run_cli(self, mode=None, answer=None):
        with tempfile.TemporaryDirectory() as directory:
            args = [] if mode is None else ["--approver=" + mode]
            if answer is not None:
                path = Path(directory) / "answers.json"
                path.write_text(json.dumps(answer))
                args = ["--approver=file:" + str(path)]
            result = subprocess.run([sys.executable, "-B", "cli.py", *args], cwd=ROOT,
                                    input=json.dumps(DOCUMENT).encode(), capture_output=True,
                                    env={**os.environ, "XDG_STATE_HOME": directory}, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_approve_dispatches_through_core(self):
        result = self.run_cli(answer={REQUEST.sha256: "approve"})
        self.assertEqual(result["run_status"], "completed")
        actions = [e["data"] for e in result["events"] if e["kind"] == "action"]
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]["approval_id"].startswith("cli-"))
        self.assertTrue(any(e["data"].get("action") == "approved" for e in result["events"]))

    def test_deny_and_missing_approver_never_dispatch(self):
        for mode in (None, "deny"):
            with self.subTest(mode=mode):
                self.assert_denied(self.run_cli(mode))
        self.assert_denied(self.run_cli(answer={REQUEST.sha256: "deny"}))

    def test_missing_or_mismatched_file_answer_denies(self):
        self.assert_denied(self.run_cli(answer={}))
        self.assert_denied(self.run_cli(answer={"0" * 64: "approve"}))

    def assert_denied(self, result):
        self.assertEqual(result["run_status"], "stopped")
        self.assertEqual(result["stopped"]["execution_certainty"], "not_dispatched")
        self.assertFalse(any(e["kind"] in ("action", "outcome") for e in result["events"]))
        self.assertTrue(any(e["data"].get("action") == "declined" for e in result["events"]))

    def test_terminal_answer_and_unavailable_terminal(self):
        for answer, verdict in (("approve\n", "approved"), ("yes\n", "declined"), ("", "declined")):
            terminal = MagicMock()
            terminal.readline.return_value = answer
            terminal.__enter__.return_value = terminal
            with patch("builtins.open", return_value=terminal):
                approver = TerminalApprover("terminal")
                approver.prepare(REQUEST)
                self.assertEqual(approver.lookup(REQUEST.decision_id).verdict, verdict)
        with patch("builtins.open", side_effect=OSError):
            approver = TerminalApprover("terminal")
            approver.prepare(REQUEST)
            self.assertEqual(approver.lookup(REQUEST.decision_id).verdict, "declined")

    def test_consumption_survives_new_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            first = TerminalApprover(state_root=directory)
            first.prepare(REQUEST)
            from dataclasses import replace
            record = replace(first.lookup(REQUEST.decision_id), verdict="approved")
            first.records[REQUEST.decision_id] = record
            self.assertTrue(first.consume(record.approval_id))
            second = TerminalApprover(state_root=directory)
            second.records[REQUEST.decision_id] = record
            self.assertFalse(second.consume(record.approval_id))

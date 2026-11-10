import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import gen_reports

COMMIT = "0" * 40
GIT = {("rev-parse", "HEAD"): COMMIT, ("status", "--porcelain"): "", ("ls-files",): "README.md\ntools/gen_reports.py\n",
       ("tag", "--list"): "", ("log", "--first-parent", "--format=%h %s", COMMIT): "0000000 Example commit\n"}
REAL_TRACE = gen_reports.trace_module
OK = "test_a (tests.test_bridge.BridgeTests.test_a) ... ok"
SECOND = "test_b (tests.test_bridge.BridgeTests.test_b) ... "


def suite_stderr(lines, ran, verdict="OK"):
    return "\n".join(lines) + "\n\n" + "-" * 70 + "\nRan %d test%s in 0.010s\n\n%s\n" % (
        ran, "" if ran == 1 else "s", verdict)


def completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class Harness:
    def __init__(self, suite=None, gitleaks=(0, "no leaks found"), gitleaks_installed=True, gen_docs=0, diff=0,
                 trace_problems=(), root=None):
        self.root = root
        self.git_calls = []
        self.suite = suite or (0, suite_stderr([OK, SECOND + "ok"], 2))
        self.trace_problems = list(trace_problems)
        self.gitleaks = gitleaks
        self.gitleaks_installed = gitleaks_installed
        self.gen_docs = gen_docs
        self.diff = diff

    def run(self, command, *args, **kwargs):
        if command[0] == "gitleaks":
            return completed(command, self.gitleaks[0], self.gitleaks[1])
        if "unittest" in command:
            return completed(command, self.suite[0], "", self.suite[1])
        if "tools/build_manifest.py" in command:
            return completed(command)
        if "tools/gen_docs.py" in command:
            return completed(command, self.gen_docs)
        if command[:2] == ["git", "diff"]:
            return completed(command, self.diff)
        if command[0] == "git" and tuple(command[1:]) in GIT:
            self.git_calls.append(tuple(command[1:]))
            return completed(command, 0, GIT[tuple(command[1:])])
        raise AssertionError("unexpected subprocess in report test: %r" % (command,))

    def which(self, name):
        if name == "gitleaks":
            return "/usr/bin/gitleaks" if self.gitleaks_installed else None
        return None

    def trace(self):
        trace = REAL_TRACE()
        summary = trace.check()[1]
        trace.check = lambda: (list(self.trace_problems), summary)
        return trace

    def main(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(gen_reports, "trace_module", side_effect=self.trace))
            stack.enter_context(mock.patch.object(gen_reports.subprocess, "run", side_effect=self.run))
            stack.enter_context(mock.patch.object(gen_reports.shutil, "which", side_effect=self.which))
            stack.enter_context(mock.patch.object(gen_reports, "gh", return_value=None))
            stack.enter_context(mock.patch.object(gen_reports, "REPORTS", Path(tmp) / "reports"))
            stack.enter_context(mock.patch.object(gen_reports, "RELEASES", Path(tmp) / "releases"))
            stack.enter_context(mock.patch.object(sys, "argv", ["gen_reports.py"]))
            if self.root is not None:
                stack.enter_context(mock.patch.object(gen_reports, "ROOT", self.root))
                stack.enter_context(mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root.parent)}))
            out = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(out))
            code = gen_reports.main()
            report = (Path(tmp) / "reports" / "STR-unreleased.md").read_text()
        return code, out.getvalue(), report


class GenerateReportsTests(unittest.TestCase):
    def assertFailed(self, harness):
        code, out, report = harness.main()
        self.assertEqual(code, 1, out)
        self.assertIn('"passed": false', out)
        self.assertIn("FAILED", report)
        return report

    def test_clean_runs_and_gates_pass(self):
        code, out, report = Harness().main()
        self.assertEqual(code, 0, out + report)
        self.assertIn('"passed": true', out)

    def test_main_exits_nonzero_when_gitleaks_finds_a_secret(self):
        report = self.assertFailed(Harness(gitleaks=(1, "leaks found: 1")))
        self.assertIn("leaks found: 1", report.split("## 4.")[1])

    def test_failing_gate_fails_the_report(self):
        self.assertFailed(Harness(gen_docs=1))
        self.assertFailed(Harness(diff=1))

    def test_gate_not_run_fails_the_report(self):
        report = self.assertFailed(Harness(gitleaks_installed=False))
        self.assertIn("not run", report.split("## 4.")[1])

    def test_skipped_test_fails_the_report(self):
        stderr = suite_stderr([OK, SECOND + "skipped 'required check disabled'"], 2, "OK (skipped=1)")
        report = self.assertFailed(Harness(suite=(0, stderr)))
        self.assertIn("skipped", report.split("## 4.")[1])

    def test_expected_failure_fails_the_report(self):
        stderr = suite_stderr([OK, SECOND + "expected failure"], 2, "OK (expected failures=1)")
        self.assertFailed(Harness(suite=(0, stderr)))

    def test_unparsed_test_outcome_fails_the_report(self):
        stderr = suite_stderr([OK, SECOND + "\nsome output\nok"], 2)
        self.assertFailed(Harness(suite=(0, stderr)))

    def test_trace_problem_fails_the_report(self):
        report = self.assertFailed(Harness(trace_problems=["VM: example problem"]))
        self.assertIn("VM: example problem", report.split("## 4.")[1])

    def test_empty_suite_fails_the_report(self):
        self.assertFailed(Harness(suite=(0, suite_stderr([], 0, "NO TESTS RAN"))))


class HermeticReportTests(unittest.TestCase):
    def export(self, tmp):
        root = Path(tmp) / "export"
        shutil.copytree(gen_reports.ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        self.assertFalse((root / ".git").exists())
        return root

    def empty_repository(self, tmp):
        root = self.export(tmp)
        for name in ("objects", "refs/heads", "refs/tags"):
            (root / ".git" / name).mkdir(parents=True)
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        return root

    def assertVerdicts(self, root):
        harness = Harness(root=root)
        code, out, report = harness.main()
        self.assertEqual(code, 0, out + report)
        self.assertIn('"passed": true', out)
        self.assertIn(COMMIT, out)
        self.assertEqual({call[0] for call in harness.git_calls}, {"rev-parse", "status", "ls-files", "tag", "log"})
        code, out, report = Harness(root=root, gitleaks=(1, "leaks found: 1")).main()
        self.assertEqual(code, 1, out)
        self.assertIn('"passed": false', out)
        self.assertIn("leaks found: 1", report.split("## 4.")[1])
        stderr = suite_stderr([OK, SECOND + "skipped 'required check disabled'"], 2, "OK (skipped=1)")
        code, out, report = Harness(root=root, suite=(0, stderr)).main()
        self.assertEqual(code, 1, out)
        self.assertIn("skipped", report.split("## 4.")[1])

    def test_verdict_without_git_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertVerdicts(self.export(tmp))

    def test_verdict_in_empty_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertVerdicts(self.empty_repository(tmp))


if __name__ == "__main__":
    unittest.main()

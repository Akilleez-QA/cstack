import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import threading
import unittest
from unittest.mock import patch

from adapters.execution import LocalBridgeExecutor, ProcessResult
from adapters.math_stdio import MathStdioCapability
from bootstrap import DEFAULT_MATH_ROOT
from poodo_core import *
from adapters.memory_ledger import MemoryLedger
from extensions.foundation_math import FoundationMath, MATH_CAPABILITY, TOOL_NAMES
from cli import run_document
from tests.test_math_adapter import math_request

ROOT = Path(__file__).resolve().parents[1]


def fixture_process(source):
    # Trusted literal fault fixtures only. Never exposed as a runtime capability.
    return subprocess.Popen([sys.executable, "-B", "-c", source], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)


class ExecutorTests(unittest.TestCase):
    def run_fixture(self, source, *, timeout=0.2, cancellation=None, frames=(b"{}", b"{}")):
        executor = LocalBridgeExecutor(DEFAULT_MATH_ROOT, timeout_seconds=timeout)
        with patch.object(executor, "_spawn", lambda: fixture_process(source)):
            result = executor.exchange(frames, cancellation)
        self.assertIsNotNone(executor.last_returncode)
        with self.assertRaises(ProcessLookupError):
            os.kill(executor.last_pid, 0)
        return result

    def test_timeout_terminates_and_unknown_execution(self):
        result = self.run_fixture("import time; time.sleep(5)", timeout=0.05)
        self.assertEqual((result.status, result.certainty, result.stdout), ("timed_out", "unknown", b""))

    def test_cancellation_terminates_and_no_partial_evidence(self):
        event = threading.Event()
        timer = threading.Timer(0.05, event.set)
        timer.start()
        try:
            result = self.run_fixture("import time; time.sleep(5)", timeout=1, cancellation=event)
        finally:
            timer.join()
        self.assertEqual((result.status, result.certainty, result.stdout), ("cancelled", "unknown", b""))

    def test_cancel_before_spawn(self):
        event = threading.Event(); event.set()
        executor = LocalBridgeExecutor(DEFAULT_MATH_ROOT)
        with patch.object(executor, "_spawn", side_effect=RuntimeError("must not spawn")):
            result = executor.exchange((b"{}",), event)
        self.assertEqual((result.status, result.certainty), ("cancelled", "not_dispatched"))

    def test_child_not_reading_full_pipe_still_times_out(self):
        result = self.run_fixture("import time; time.sleep(5)", timeout=0.05, frames=(b"x"*65_536, b"x"*65_536))
        self.assertEqual(result.status, "timed_out")

    def test_crash_and_late_reply_are_not_success(self):
        crash = self.run_fixture("import sys; sys.exit(7)")
        self.assertEqual(crash.status, "indeterminate")
        late = self.run_fixture("import time; time.sleep(0.5); print('{}'); print('{}')", timeout=0.05)
        self.assertEqual(late.status, "timed_out")
        self.assertEqual(late.stdout, b"")

    def test_bounded_stdout_and_stderr_overflow(self):
        for source in ("import sys; sys.stdout.buffer.write(b'x'*1048577); sys.stdout.flush()",
                       "import sys; sys.stderr.buffer.write(b'x'*16385); sys.stderr.flush()"):
            result = self.run_fixture(source, timeout=1)
            self.assertEqual(result.status, "resource_rejected")
            self.assertEqual(result.stdout, b"")
            self.assertLessEqual(len(result.stderr), 16_384)

    def test_nonempty_stderr_is_not_itself_failure(self):
        result = self.run_fixture("import sys; sys.stdin.read(); print('{}'); print('{}'); print('diagnostic',file=sys.stderr)", timeout=1)
        self.assertEqual(result.status, "completed")
        self.assertIn(b"diagnostic", result.stderr)

    def test_oversized_request_rejected_without_process(self):
        executor = LocalBridgeExecutor(DEFAULT_MATH_ROOT)
        with patch.object(executor, "_spawn", side_effect=RuntimeError("must not spawn")):
            result = executor.exchange((b"x"*65_537,))
        self.assertEqual((result.status, result.certainty), ("resource_rejected", "not_dispatched"))

    def test_adapter_keeps_execution_uncertainty(self):
        for status in ("timed_out", "cancelled", "indeterminate", "resource_rejected"):
            class FailedExecutor:
                def exchange(self, frames, cancellation=None):
                    return ProcessResult(status, "unknown", b"", b"", -9)
            cap = MathStdioCapability(DEFAULT_MATH_ROOT, executor=FailedExecutor())
            cap._ready = True
            result = cap.invoke(math_request(), "attempt-failed").to_dict()
            self.assertEqual((result["execution_status"], result["execution_certainty"]), (status, "unknown"))
            self.assertIsNone(result["raw_result"])


class CliTests(unittest.TestCase):
    def run_cli_without_host_config(self, raw):
        with tempfile.TemporaryDirectory() as tmp:
            return self.run_cli(raw, ("--config", str(Path(tmp) / "absent.json")))

    def run_cli(self, raw, args=()):
        return subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), "cli.py", *args],
            cwd=ROOT, input=raw, capture_output=True, timeout=30)

    def test_real_local_harness_process(self):
        result = self.run_cli_without_host_config((ROOT / "examples/scalar-and-negative.json").read_bytes())
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        outcomes = [e["data"]["outcome"] for e in document["events"] if e["kind"] == "outcome"]
        self.assertEqual([o["assessment"] for o in outcomes], ["exact_scalar_result", "formal_polynomial_identity_not_equal"])
        self.assertFalse(document["goal"]["closed"])
        self.assertFalse(document["mcp_compatible"])
        self.assertFalse(document["endoforge_implemented"])
        self.assertEqual(result.stderr, b"")

    def test_parent_directory_module_entrypoint(self):
        result = subprocess.run([sys.executable, "-B", "-m", ROOT.name], cwd=ROOT.parent,
            input=(ROOT/"examples/scalar-and-negative.json").read_bytes(), capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_json_profiles_and_size(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":1.0}', b'NaN', b'\xff', b'x'*65_537, b'{}'):
            result = self.run_cli(raw)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["formal_proof"])

    def test_no_path_flags_grants_or_future_capabilities(self):
        raw = (ROOT/"examples/scalar-and-negative.json").read_bytes()
        self.assertEqual(self.run_cli(raw, ("--source-root", "/tmp")).returncode, 2)
        for mutate in (lambda d: d.update(grant={"all":True}),
                       lambda d: d["calls"][0]["request"].update(capability_id="foundation_engine"),
                       lambda d: d["calls"][0]["request"].update(required_evidence="formal_proof"),
                       lambda d: d["checkpoints"][2].update(option_ids=["same"]*20)):
            document = json.loads(raw); mutate(document)
            result = self.run_cli(json.dumps(document).encode())
            self.assertEqual(result.returncode, 2)

    def test_later_retention_stop_preserves_completed_run_history(self):
        class LargeMathDouble:
            def describe(self):
                return MATH_CAPABILITY
            def invoke(self, request, attempt_id, cancellation=None):
                return outcome_for(request, attempt_id, "completed", "synthetic_large_return", certainty="responded",
                                   raw_result={"synthetic_padding": "x"*1_000_000})
        def limited_host(domain_id, goal_id):
            self.assertEqual(domain_id, "foundation_math")
            cap = LargeMathDouble()
            core = FoundationMath(cap, (AuthorityGrant("limited", "foundation_math", "foundation_math", TOOL_NAMES,
                                                       (goal_id,), 2, lane="ToolFace"),), MemoryLedger(max_bytes=2_500_000))
            return core, cap
        with patch("cli.build_domain", limited_host):
            with tempfile.TemporaryDirectory() as tmp:
                result = run_document(json.loads((ROOT/"examples/scalar-and-negative.json").read_text()),
                                      config=Path(tmp) / "absent.json")
        self.assertEqual(result["run_status"], "stopped")
        self.assertEqual(result["stopped"]["execution_certainty"], "not_dispatched")
        self.assertEqual(result["stopped"]["decision_id"], "decision-2")
        self.assertEqual(len([e for e in result["events"] if e["kind"] == "outcome"]), 1)
        self.assertEqual(len([e for e in result["events"] if e["kind"] == "action"]), 1)

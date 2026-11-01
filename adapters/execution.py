"""Bounded local stdio execution. No core import or request-controlled command.

This is a trusted single-operator process boundary, not an OS security sandbox.
It owns deadline, cancellation, output bounds and cleanup, not evidence meaning.
"""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
from typing import Protocol


@dataclass(frozen=True)
class ProcessResult:
    status: str
    certainty: str
    stdout: bytes
    stderr: bytes
    returncode: int | None


class BridgeExecutor(Protocol):
    def exchange(self, frames: tuple[bytes, ...], cancellation=None) -> ProcessResult: ...


class LocalBridgeExecutor:
    INPUT_CAP = 65_536
    OUTPUT_CAP = 1_048_576
    STDERR_CAP = 16_384
    # Fixed bridge modules a trusted host may select; never request data.
    BRIDGE_MODULES = frozenset({"foundation_math_bridge", "foundation_refrigeration_bridge",
                                "foundation_template_bridge", "foundation_robotics_bridge",
                                "foundation_film_bridge"})

    def __init__(self, source_root: Path, *, timeout_seconds=15.0, module="foundation_math_bridge"):
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Host timeout must be in (0, 60] seconds")
        if module not in self.BRIDGE_MODULES:
            raise ValueError("Unknown bridge module")
        self._module = module
        self._root = Path(source_root).resolve()
        self._timeout = timeout_seconds
        self.last_pid = None
        self.last_returncode = None

    def _spawn(self):
        # Only trusted constructor configuration determines cwd and interpreter.
        return subprocess.Popen([sys.executable, "-B", "-m", self._module],
            cwd=self._root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"},
            shell=False, close_fds=True, start_new_session=True)

    @staticmethod
    def _cleanup(proc):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()

    def exchange(self, frames, cancellation=None):
        if (type(frames) is not tuple or not 1 <= len(frames) <= 3
                or any(type(f) is not bytes or len(f) > self.INPUT_CAP or b"\n" in f for f in frames)):
            return ProcessResult("resource_rejected", "not_dispatched", b"", b"", None)
        if cancellation is not None and cancellation.is_set():
            return ProcessResult("cancelled", "not_dispatched", b"", b"", None)
        payload = b"".join(f + b"\n" for f in frames)
        try:
            proc = self._spawn()
        except (OSError, ValueError):
            return ProcessResult("unavailable", "not_dispatched", b"", b"", None)
        self.last_pid = proc.pid
        start = time.monotonic()
        output, errors = bytearray(), bytearray()
        offset = 0
        status = "completed"
        selector = selectors.DefaultSelector()
        try:
            for stream, name, events in ((proc.stdin, "stdin", selectors.EVENT_WRITE),
                                         (proc.stdout, "stdout", selectors.EVENT_READ),
                                         (proc.stderr, "stderr", selectors.EVENT_READ)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, events, name)
            while selector.get_map():
                if cancellation is not None and cancellation.is_set():
                    status = "cancelled"
                    break
                if time.monotonic() - start >= self._timeout:
                    status = "timed_out"
                    break
                for key, _ in selector.select(min(0.025, self._timeout)):
                    stream, name = key.fileobj, key.data
                    try:
                        if name == "stdin":
                            sent = os.write(stream.fileno(), payload[offset:offset + 4096])
                            offset += sent
                            if offset == len(payload):
                                selector.unregister(stream)
                                stream.close()
                            continue
                        block = os.read(stream.fileno(), 8192)
                    except BlockingIOError:
                        continue
                    except (BrokenPipeError, OSError):
                        status = "indeterminate"
                        break
                    if not block:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    target = output if name == "stdout" else errors
                    target.extend(block)
                    if name == "stderr" and len(errors) > self.STDERR_CAP:
                        status = "resource_rejected"
                        break
                    if name == "stdout":
                        lines = output.split(b"\n")
                        if (len(output) > len(frames) * (self.OUTPUT_CAP + 1)
                                or len(lines) > len(frames) + 1
                                or any(len(line) > self.OUTPUT_CAP for line in lines)):
                            status = "resource_rejected"
                            break
                if status != "completed":
                    break
            if status == "completed":
                remaining = self._timeout - (time.monotonic() - start)
                try:
                    proc.wait(timeout=max(0.001, remaining))
                except subprocess.TimeoutExpired:
                    status = "timed_out"
                if status == "completed" and proc.returncode != 0:
                    status = "indeterminate"
        finally:
            selector.close()
            self._cleanup(proc)
            self.last_returncode = proc.returncode
        # Error bytes are diagnostic only; nonempty stderr is not itself failure.
        if status != "completed":
            return ProcessResult(status, "unknown", b"", bytes(errors[:self.STDERR_CAP]), proc.returncode)
        return ProcessResult("completed", "responded", bytes(output), bytes(errors), proc.returncode)



def run_argv(argv, *, stdin=b"", timeout_seconds=20.0, stdout_cap=1_048_576, stderr_cap=16_384, env=None):
    """One fixed host command (never a shell): bounded stdin, deadline and output. For host CLIs such as gh.

    argv[0] must be an absolute path the host resolved at startup. Exceeding a cap or the deadline kills the
    process group and returns a non-completed status; nothing partial is returned as a success.
    """
    if (type(argv) not in (list, tuple) or not argv or any(type(a) is not str or "\x00" in a for a in argv)
            or not os.path.isabs(argv[0]) or type(stdin) is not bytes or not 0 < timeout_seconds <= 120):
        return ProcessResult("resource_rejected", "not_dispatched", b"", b"", None)
    try:
        proc = subprocess.Popen(list(argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=dict(env or {}), shell=False, close_fds=True, start_new_session=True)
    except (OSError, ValueError):
        return ProcessResult("unavailable", "not_dispatched", b"", b"", None)
    start, offset, status = time.monotonic(), 0, "completed"
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    caps = {"stdout": stdout_cap, "stderr": stderr_cap}
    selector = selectors.DefaultSelector()
    try:
        for stream, name, events in ((proc.stdin, "stdin", selectors.EVENT_WRITE),
                                     (proc.stdout, "stdout", selectors.EVENT_READ),
                                     (proc.stderr, "stderr", selectors.EVENT_READ)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, events, name)
        if not stdin:
            selector.unregister(proc.stdin)
            proc.stdin.close()
        while selector.get_map() and status == "completed":
            if time.monotonic() - start >= timeout_seconds:
                status = "timed_out"
                break
            for key, _ in selector.select(0.025):
                stream, name = key.fileobj, key.data
                try:
                    if name == "stdin":
                        offset += os.write(stream.fileno(), stdin[offset:offset + 4096])
                        if offset == len(stdin):
                            selector.unregister(stream)
                            stream.close()
                        continue
                    block = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                except OSError:
                    status = "indeterminate"
                    break
                if not block:
                    selector.unregister(stream)
                    stream.close()
                    continue
                buffers[name].extend(block)
                if len(buffers[name]) > caps[name]:
                    status = "resource_rejected"
                    break
        while status == "completed":  # wait for exit WITHOUT reaping, so the group id stays ours to kill
            if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                break
            if time.monotonic() - start >= timeout_seconds:
                status = "timed_out"
            time.sleep(0.01)
    finally:
        selector.close()
        try:  # the whole group, always: the leader is unreaped until wait(), so its pgid cannot be reused
            os.killpg(proc.pid, 9)
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            status = "indeterminate"
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None and not stream.closed:
                stream.close()
    errors = bytes(buffers["stderr"][:stderr_cap])
    if status != "completed":
        return ProcessResult(status, "unknown", b"", errors, proc.returncode)
    return ProcessResult("completed", "responded", bytes(buffers["stdout"]), errors, proc.returncode)

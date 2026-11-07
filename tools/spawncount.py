"""Count real process creation under a command, by ptrace. Threads don't count; no syscall stops, so little slowdown."""
import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time

PTRACE_TRACEME, PTRACE_CONT, PTRACE_SETOPTIONS, PTRACE_GETEVENTMSG = 0, 7, 0x4200, 0x4201
OPTIONS = 0x1 | 0x2 | 0x4 | 0x8 | 0x10 | 0x100000
EVENTS = {1: "fork", 2: "vfork", 3: "clone", 4: "exec"}
libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.argtypes = (ctypes.c_long, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)
libc.ptrace.restype = ctypes.c_long


def _is_process(tid):
    try:
        with open(f"/proc/{tid}/status") as stream:
            fields = dict(line.split(":", 1) for line in stream if ":" in line)
        return fields["Tgid"].strip() == str(tid)
    except OSError:
        return False


def trace(command, out, env=None, stdin=None, stdout=None):
    pid = os.fork()
    if pid == 0:
        for path, flags, target in ((stdin, os.O_RDONLY, 0), (stdout, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 1)):
            if path is not None:
                os.dup2(os.open(path, flags, 0o600), target)
        libc.ptrace(PTRACE_TRACEME, 0, None, None)
        os.kill(os.getpid(), signal.SIGSTOP)
        if env:
            os.environ.update(env)
        os.execvp(command[0], command)
    events = []
    os.waitpid(pid, 0)
    libc.ptrace(PTRACE_SETOPTIONS, pid, None, ctypes.c_void_p(OPTIONS))
    libc.ptrace(PTRACE_CONT, pid, None, None)
    status_of_root = None
    live = {pid}
    while live:
        try:
            tid, status = os.waitpid(-1, 0x40000000)
        except ChildProcessError:
            break
        now = time.monotonic_ns()
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            live.discard(tid)
            if tid == pid:
                status_of_root = status
            continue
        delivered = 0
        if os.WIFSTOPPED(status):
            live.add(tid)
            signal_number = os.WSTOPSIG(status)
            event = status >> 16
            if signal_number == signal.SIGTRAP and event in EVENTS:
                message = ctypes.c_ulong()
                libc.ptrace(PTRACE_GETEVENTMSG, tid, None, ctypes.byref(message))
                if event == 4:
                    events.append({"event": "exec", "pid": tid, "ns": now})
                else:
                    child = message.value
                    live.add(child)
                    events.append({"event": EVENTS[event], "pid": child, "parent": tid, "ns": now, "process": event != 3 or _is_process(child)})
            elif signal_number not in (signal.SIGSTOP, signal.SIGTRAP):
                delivered = signal_number
        libc.ptrace(PTRACE_CONT, tid, None, ctypes.c_void_p(delivered))
    with open(out, "w") as stream:
        json.dump(events, stream)
    return os.waitstatus_to_exitcode(status_of_root) if status_of_root is not None else 1


def count(events, start_ns=None, end_ns=None):
    window = [e for e in events if (start_ns is None or e["ns"] >= start_ns) and (end_ns is None or e["ns"] <= end_ns)]
    return {"exec": sum(e["event"] == "exec" for e in window),
            "process": sum(e["event"] != "exec" and e["process"] for e in window),
            "thread": sum(e["event"] != "exec" and not e["process"] for e in window)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.exit(trace(args.command[1:] if args.command[0] == "--" else args.command, args.out))


if __name__ == "__main__":
    main()

"""Drive a bare --approver run on a real pseudo-terminal, typing the approval a person would type. Prints the run's output."""
import os
import pty
import select
import sys
import time


def main():
    command = sys.argv[1]
    pid, master = pty.fork()
    if pid == 0:
        os.execvp("bash", ["bash", "-c", command])
    seen = b""
    typed = False
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
        if not typed and b"approve" in seen.lower():
            os.write(master, b"approve\n")
            typed = True
    os.waitpid(pid, 0)
    sys.stdout.write(seen.decode("utf-8", "replace").replace("\r\n", "\n"))


if __name__ == "__main__":
    main()

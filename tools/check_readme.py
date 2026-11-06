"""Run every README command on a fresh clone and report each result. Refuses to pass if a README command isn't covered."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def readme_commands(text):
    commands = []
    for block in re.findall(r"^\s*```sh\n(.*?)^\s*```", text, re.S | re.M):
        commands.extend(line.strip() for line in block.splitlines() if line.strip())
    return commands


class Check:
    def __init__(self, clone, covered):
        self.clone, self.covered, self.rows = clone, covered, []
        self.env = {**os.environ, "PATH": f"{clone}/.venv/bin:{os.environ['PATH']}", "VIRTUAL_ENV": f"{clone}/.venv"}

    def shell(self, command, *, stdin=None, timeout=900):
        return subprocess.run(["bash", "-c", command], cwd=self.clone, env=self.env, capture_output=True, text=True, input=stdin, timeout=timeout)

    def record(self, command, passed, note):
        self.rows.append(dict(command=command, passed=bool(passed), note=note))
        self.covered.add(command)
        print(("ok    " if passed else "FAIL  ") + command + "\n      " + note, flush=True)

    def plain(self, command, expect=None, timeout=900):
        result = self.shell(command, timeout=timeout)
        tail = (result.stdout + result.stderr).strip().splitlines()[-1:] or [""]
        passed = result.returncode == 0 and (expect is None or expect(result.stdout))
        self.record(command, passed, f"exit {result.returncode}: {tail[0][:160]}")
        return result

    def run_status(self, command, status):
        result = self.shell(command)
        try:
            document = json.loads(result.stdout)
            actual = document.get("run_status"), [e["data"]["outcome"]["assessment"] for e in document["events"] if e["kind"] == "outcome"]
        except (json.JSONDecodeError, KeyError) as error:
            self.record(command, False, f"exit {result.returncode}: {error}")
            return
        self.record(command, actual[0] == status and result.returncode == 0, f"exit {result.returncode}: run_status {actual[0]}, outcomes {actual[1]}")


def approve_on_tty(check, command):
    result = subprocess.run(["python", "-B", "tools/tty_approve.py", command], cwd=check.clone, env=check.env, capture_output=True, text=True, timeout=120)
    try:
        document = next(json.loads(line) for line in result.stdout.splitlines() if '"cstack.run-result/0.1"' in line and line.startswith("{"))
    except (ValueError, StopIteration):
        check.record(command, False, f"driver exit {result.returncode}: {result.stdout[-120:]} {result.stderr[-160:]}")
        return
    outcomes = [e["data"]["outcome"]["assessment"] for e in document["events"] if e["kind"] == "outcome"]
    check.record(command, document.get("run_status") == "completed" and outcomes, f"typed approve on a real pty: run_status {document.get('run_status')}, outcomes {outcomes}")


def mcp_session(check, command):
    state = Path(tempfile.mkdtemp(prefix="cstack-state-"))
    argv = command.replace("/tmp/cstack-state", str(state)).split()
    process = subprocess.Popen(argv, cwd=check.clone, env=check.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    frames = [dict(jsonrpc="2.0", id=1, method="initialize", params=dict(protocolVersion="2024-11-05", capabilities={}, clientInfo=dict(name="check", version="1"))),
              dict(jsonrpc="2.0", method="notifications/initialized"), dict(jsonrpc="2.0", id=2, method="tools/list"),
              dict(jsonrpc="2.0", id=3, method="tools/call", params=dict(name="aor", arguments={}))]
    stdout, stderr = process.communicate("".join(json.dumps(f) + "\n" for f in frames), timeout=60)
    shutil.rmtree(state, ignore_errors=True)
    replies = [json.loads(line) for line in stdout.splitlines()]
    tools = [t["name"] for t in replies[1]["result"]["tools"]] if len(replies) > 1 else []
    aor = json.loads(replies[2]["result"]["content"][0]["text"]) if len(replies) > 2 else {}
    check.record(command, aor.get("bot", {}).get("slug") == "example" and len(tools) >= 6, f"{len(tools)} tools; aor says bot {aor.get('bot', {}).get('slug')}, device {aor.get('device')}; {stderr[-80:]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="clone this repository or path")
    parser.add_argument("--branch")
    parser.add_argument("--github-remote", default="https://github.com/Akilleez-QA/cstack", help="origin for the merge train's gh calls")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cstack-readme-") as directory:
        clone = Path(directory, "cstack")
        subprocess.run(["git", "clone", "--quiet", *(["--branch", args.branch] if args.branch else []), args.source, str(clone)], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", args.github_remote], cwd=clone, check=True)
        commands = readme_commands((clone / "README.md").read_text())
        covered = set()
        check = Check(clone, covered)
        check.plain("python3 -m venv .venv && . .venv/bin/activate")
        check.plain("pip install -r requirements.txt -r ci/requirements.txt")
        check.plain("npm ci --prefix adapters/workcell --ignore-scripts --no-audit --no-fund")
        check.plain("cp cstack.config.example.json cstack.config.json")
        check.run_status("python -B cli.py < examples/scalar-and-negative.json", "completed")
        check.plain("python -B -m unittest discover -s tests", timeout=1800)
        check.plain("bash ci/run-local.sh python links", timeout=3600)
        approve_on_tty(check, "python -B cli.py --approver < examples/ask-approval.json")
        check.run_status("python -B cli.py --approver=deny < examples/ask-approval.json", "stopped")
        request = subprocess.run([sys.executable, "-B", "-c", "import json,sys; sys.path.insert(0,'.'); from poodo_core import CapabilityRequest; d=json.load(open('examples/ask-approval.json')); print(CapabilityRequest.from_dict(d['calls'][0]['request']).sha256)"],
                                 cwd=clone, env={**check.env, "PATH": check.env["PATH"]}, capture_output=True, text=True, executable=str(clone / ".venv/bin/python"))
        (clone / "answers.json").write_text(json.dumps({request.stdout.strip(): "approve"}))
        check.run_status("python -B cli.py --approver=file:answers.json < examples/ask-approval.json", "completed")
        check.run_status("CSTACK_STUB_TRANSPORT_SCRIPT=examples/forge/saturation-stub.json python -B cli.py < examples/forge/saturation-goal.json", "completed")
        check.plain("python -B -c \"from adapters.aor_registry import load_fleet; print(load_fleet('aors/fleet.json').approver)\"", lambda out: out.strip() == "owner-via-approver")
        mcp_session(check, "python -B tools/cstack_mcp.py --aor example --device example-host --state-root /tmp/cstack-state")
        check.plain("python3 tools/merge_train.py --wip")
        check.plain("python3 tools/merge_train.py --dry-run --policy low-risk", lambda out: isinstance(json.loads(out), dict))
        missing = [command for command in commands if command not in covered and command not in {"python -B tools/pin_endoforge.py --source ENDOFORGE_CLONE --commit FULL_COMMIT"}]
    for command in missing:
        print("FAIL  no check covers README command: " + command)
    failed = [row for row in check.rows if not row["passed"]]
    print(json.dumps(dict(commands=len(check.rows), failed=len(failed), uncovered=len(missing))))
    return 1 if failed or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the real CLI on a forge goal: the real core, ledgers and IsolatePool, with a stub model transport."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
GOAL = json.loads((ROOT / "examples/forge/saturation-goal.json").read_text())
SATURATION = (ROOT / "examples/forge/saturation.ts").read_text()


def goal(**arguments):
    document = copy.deepcopy(GOAL)
    document["calls"][0]["request"]["arguments"].update(arguments)
    return document


class RepoCopy:
    """A writable copy of this checkout, to test what a changed file does. Dependencies stay linked, not copied."""
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="forge-copy-")
        self.root = Path(self._temporary.name, "cstack")
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__", "*.pyc", "cstack.config.json", "forge.sqlite", "endoforge.jsonl"))
        for modules in ROOT.glob("adapters/*/node_modules"):
            (self.root / modules.relative_to(ROOT)).symlink_to(modules)

    def edit(self, path, old, new):
        target = self.root / path
        text = target.read_text()
        if old not in text:
            raise AssertionError(f"{old!r} isn't in {path}")
        target.write_text(text.replace(old, new))

    def close(self):
        self._temporary.cleanup()


class Forge:
    def __init__(self, *sources, isolation="process", imports=("foundation_refrigeration", "foundation_template"),
                 decision_operations=None, job_timeout=120000, directory=None, transport=True, decision_ask_operations=None, root=None):
        self.root = Path(root or ROOT)
        self._temporary = None if directory else tempfile.TemporaryDirectory(prefix="forge-")
        self.directory = Path(directory or self._temporary.name)
        names = []
        for index, source in enumerate(sources):
            name = f"source-{index}.ts"
            (self.directory / name).write_text(source)
            names.append(name)
        (self.directory / "script.json").write_text(json.dumps({"responses": names}))
        config = {"endoforge": {"path": "witness.jsonl"}, "workcell": {
            "ledger": "forge.sqlite", "foundation_imports": list(imports), "isolation": isolation, "jobTimeoutMs": job_timeout,
            "decision_operations": decision_operations or {"foundation_template": ["echo_observation"]},
            **({"decision_ask_operations": decision_ask_operations} if decision_ask_operations else {}),
            **({"transport": str(self.root / "adapters/workcell/stub-transport.mjs")} if transport else {})}}
        self.config = self.directory / "config.json"
        self.config.write_text(json.dumps(config))
        self.env = {**os.environ, "CSTACK_STUB_TRANSPORT_SCRIPT": str(self.directory / "script.json")}

    def command(self, *extra):
        return [sys.executable, "-B", str(self.root / "cli.py"), "--config", str(self.config), *extra]

    def start(self, document):
        process = subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd=self.root)
        process.stdin.write(json.dumps(document).encode())
        process.stdin.close()
        return process

    def run(self, document, timeout=120):
        result = subprocess.run(self.command(), input=json.dumps(document).encode(), capture_output=True, env=self.env, cwd=self.root, timeout=timeout)
        return json.loads(result.stdout)

    def raw(self, document, *extra, env=None, timeout=120):
        return subprocess.run(self.command(*extra), input=json.dumps(document).encode(), capture_output=True, env=env or self.env, cwd=self.root, timeout=timeout)

    def witness(self):
        return [json.loads(line) for line in (self.directory / "witness.jsonl").read_text().splitlines()]

    def records(self):
        sys.path.insert(0, str(ROOT / "vendor/endoforge"))
        from core.ledger.ledger import Ledger
        return Ledger(str(self.directory / "forge.sqlite")).records()

    def receipts(self):
        return [r for r in self.records() if r["kind"] == "receipt"]

    def close(self):
        if self._temporary:
            self._temporary.cleanup()


def outcome(result):
    return [e["data"]["outcome"] for e in result["events"] if e["kind"] == "outcome"][-1]


def descendants(pid):
    found = []
    for child in subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True).stdout.split():
        found.append(int(child))
        found.extend(descendants(int(child)))
    return found


def args_of(pid):
    return subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True).stdout


def wait_for(predicate, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition not met in time")

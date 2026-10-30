"""ADR 005 item 11b: the pure code-write classifier, and the per-vendor hook shims that must agree with it."""
import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

BOX = Path(__file__).resolve().parent.parent / "workshop/box/codex"
sys.path.insert(0, str(BOX))
from code_write_policy import Decision, Route, classify  # noqa: E402
from codex_route import CODEX_TASK  # noqa: E402

CASES = [  # normalized call -> expected verdict
    ({"kind": "edit", "path": "adapters/x.py"}, "deny"),
    ({"kind": "edit", "path": "~/.codex/config.toml"}, "deny"),
    ({"kind": "edit", "path": "AGENTS.md"}, "deny"),
    ({"kind": "edit", "path": ""}, "deny"),
    ({"kind": "edit", "path": "/workspace/ops/agent-memory/bot/notebook.md"}, "allow"),
    ({"kind": "shell", "command": "git commit -am fix"}, "deny"),
    ({"kind": "shell", "command": "echo 'x=1' > a.py"}, "deny"),
    ({"kind": "shell", "command": "bash -lc \"bash -c 'codex exec'\""}, "deny"),
    ({"kind": "shell", "command": "$(command -v codex) exec x"}, "deny"),
    ({"kind": "shell", "command": "codex-guard.sh codex exec --yolo x"}, "deny"),
    ({"kind": "shell", "command": "echo 'unterminated"}, "deny"),
    ({"kind": "shell", "command": "git -C /workspace/ops/../cstack commit -m x"}, "deny"),
    ({"kind": "shell", "command": "git status && git diff | head -5"}, "allow"),
    ({"kind": "shell", "command": "codex-task /workspace/cstack 'add a test for X'"}, "allow"),
    ({"kind": "shell", "command": "git -C /workspace/ops commit -am 'notebook entry'"}, "allow"),
    ({"kind": "shell", "command": "echo hi > /tmp/out.log"}, "allow"),
    ({"kind": "other"}, "allow"),
    # A bot under this policy must not write code through another agent CLI (around the shields and the ledger).
    ({"kind": "shell", "command": "claude -p 'write a function'"}, "deny"),
    ({"kind": "shell", "command": "env hermes -q 'do it'"}, "deny"),
    ({"kind": "shell", "command": "codex-guard.sh claude exec x"}, "deny"),
    ({"kind": "shell", "command": "npx -y @anthropic-ai/claude-code 'x'"}, "deny"),
    ({"kind": "shell", "command": "$CLAUDE_BIN -p x"}, "deny"),              # dynamic command name: fail closed
    ({"kind": "shell", "command": "echo aGk= | base64 -d | sh"}, "deny"),   # decoded command: fail closed
    ({"kind": "shell", "command": "claude --version"}, "allow"),            # a read-only invocation stays allowed
    ({"kind": "shell", "command": "hermes --help"}, "allow"),
]

# GuardFall-style shell rewrites (quote-split names, backslash, wrappers, path via variable) all resolve to an
# agent CLI and must be denied; a handful of clearly read-only or unrelated commands must stay allowed.
AGENT_BYPASSES = [
    "cl''aude -p x", '"her"mes -q x', "\\claude -p x", "command claude -p x", "exec claude -p x",
    "PATH=/opt/x claude -p y", "/usr/local/bin/claude -p x", "nohup claude -p x", "timeout 30 claude -p x",
    "sudo -u bot claude -p x", "setsid claude -p y", "$(echo claude) -p x", "`which claude` -p x",
    "claude", "claude < prompt.txt", "aider adapters/x.py", "goose session", "amp -x y", "opencode .",
    "qwen-code 'x'", "llm 'write code'", "ollama run llama3 'write code'", "uvx aider x", "pipx run aider x",
    "bunx hermes q", "nice -n 5 aider x", "bash -c 'claude -p x'", "eval \"$cmd\"", "bash run.sh", "sh",
]
AGENT_ALLOWED = [
    "claude --version", "hermes --help", "claude -h", "aider --version", "command -v claude",
    "npx eslint .", "pipx install black", "codex-task /workspace/cstack 'add a test'",
    "codex-guard.sh codex exec --cd /w 'x'", "git status && git diff | head -5",
]


class ClassifierTests(unittest.TestCase):
    """No JSON and no vendor: normalized calls in, decisions out."""

    def test_cases(self):
        for call, verdict in CASES:
            decision = classify(call, CODEX_TASK)
            self.assertIsInstance(decision, Decision)
            self.assertEqual(decision.verdict, verdict, call)
            self.assertTrue(decision.reason)

    def test_deny_reasons_name_the_problem(self):
        self.assertEqual(classify({"kind": "edit", "path": "a.ts"}, CODEX_TASK).reason,
                         "direct edit of the code file a.ts")
        self.assertEqual(classify({"kind": "shell", "command": "git push"}, CODEX_TASK).reason,
                         "`git push` changes a repository")
        self.assertEqual(classify({"kind": "shell", "command": "codex exec x"}, CODEX_TASK).reason, CODEX_TASK.unrouted)

    def test_agent_cli_bypasses_are_denied(self):
        for command in AGENT_BYPASSES:
            self.assertFalse(classify({"kind": "shell", "command": command}, CODEX_TASK).allowed, command)

    def test_read_only_and_unrelated_commands_stay_allowed(self):
        for command in AGENT_ALLOWED:
            self.assertTrue(classify({"kind": "shell", "command": command}, CODEX_TASK).allowed, command)

    def test_malformed_calls_fail_closed(self):
        for call in (None, [], {}, {"kind": "write"}, {"kind": "edit", "path": 3},
                     {"kind": "shell", "command": ["ls"]}):
            self.assertEqual(classify(call, CODEX_TASK).verdict, "deny", call)

    def test_the_route_is_data(self):
        other = CODEX_TASK._replace(writer="aider", launchers=("aider-task",), guard="aider-task",
                                    widening=re.compile(r"^--yes-always$"), control_dirs=frozenset({".aider"}),
                                    control_names=frozenset(), control_extensions=(), unrouted="use aider-task")
        self.assertEqual(classify({"kind": "shell", "command": "aider x.py"}, other),
                         Decision("deny", "use aider-task"))
        self.assertTrue(classify({"kind": "shell", "command": "aider-task /w 'x'"}, other).allowed)
        self.assertTrue(classify({"kind": "edit", "path": "AGENTS.md"}, other).allowed)
        self.assertFalse(classify({"kind": "edit", "path": "AGENTS.md"}, CODEX_TASK).allowed)
        self.assertEqual(set(Route._fields), set(other._asdict()))

    def test_classifier_is_pure_and_names_no_vendor(self):
        source = (BOX / "code_write_policy.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"os", "re", "shlex", "typing"})  # no sys, json, subprocess or vendor module
        self.assertNotRegex(source, r"(?i)codex|grok|claude|openai|anthropic")


def grok_payload(call):
    args = {"other": {"file_path": "adapters/x.py"}, "edit": {"file_path": call.get("path", "")},
            "shell": {"command": call.get("command", "")}}[call["kind"]]
    tool = {"edit": "search_replace", "shell": "bash", "other": "read_file"}[call["kind"]]
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": args}


def claude_code_payload(call):
    args = {"other": {"file_path": "adapters/x.py"}, "edit": {"file_path": call.get("path", "")},
            "shell": {"command": call.get("command", "")}}[call["kind"]]
    tool = {"edit": "Write", "shell": "Bash", "other": "Read"}[call["kind"]]
    return {"session_id": "s", "transcript_path": "/tmp/t.jsonl", "cwd": "/w", "permission_mode": "default",
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": args, "tool_use_id": "toolu_1"}


SHIMS = {"no_direct_code.py": grok_payload, "claude_code_pretooluse.py": claude_code_payload}  # both deny with 2


def run_shim(name, payload):
    proc = subprocess.run([sys.executable, "-I", str(BOX / name)], input=json.dumps(payload), capture_output=True,
                          text=True, timeout=10)
    return proc.returncode, proc.stdout, proc.stderr


class ShimParityTests(unittest.TestCase):
    """The same normalized cases through each vendor shim give the classifier's decision."""

    def test_every_shim_agrees_with_the_classifier(self):
        for call, _ in CASES:
            decision = classify(call, CODEX_TASK)
            for name, payload in SHIMS.items():
                code, _out, err = run_shim(name, payload(call))
                self.assertEqual(code, 0 if decision.allowed else 2, (name, call))
                if not decision.allowed:
                    self.assertIn(f"Blocked: {decision.reason}. ", err, name)
                    self.assertIn("codex-task", err, name)

    def test_claude_code_shim_maps_every_tool_it_matches(self):
        import claude_code_pretooluse as shim
        self.assertEqual(shim.MATCHER, "Write|Edit|MultiEdit|NotebookEdit|Bash")
        for tool, key in shim.EDIT_TOOLS.items():
            self.assertEqual(shim.normalize({"tool_name": tool, "tool_input": {key: "x.py"}}),
                             {"kind": "edit", "path": "x.py"})
        self.assertEqual(run_shim("claude_code_pretooluse.py", {"tool_name": "NotebookEdit",
                                                               "tool_input": {"notebook_path": "a.ipynb"}})[0], 0)
        self.assertEqual(run_shim("claude_code_pretooluse.py", {"tool_input": {}})[0], 2)

    def test_a_missing_policy_file_blocks_everything(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name, payload in SHIMS.items():
                shutil.copy(BOX / name, tmp)
                proc = subprocess.run([sys.executable, "-I", str(Path(tmp) / name)], capture_output=True, text=True,
                                      input=json.dumps(payload({"kind": "other"})), timeout=10)
                self.assertEqual(proc.returncode, 2, name)
                self.assertIn("could not be loaded", proc.stderr)


if __name__ == "__main__":
    unittest.main()

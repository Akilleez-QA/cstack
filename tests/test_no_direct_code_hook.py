"""The fleet's Grok hook blocks direct code work and points the bot at codex-task; everything else passes."""
import importlib.util
import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

BOX = Path(__file__).resolve().parent.parent / "workshop/box/codex"
HOOK = BOX / "no_direct_code.py"


def run(tool, **arguments):
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": arguments})
    proc = subprocess.run([sys.executable, "-I", str(HOOK)], input=payload, capture_output=True, text=True, timeout=10)
    return proc.returncode, proc.stdout, proc.stderr


class NoDirectCodeHookTests(unittest.TestCase):
    def assertBlocked(self, tool, **arguments):
        code, out, err = run(tool, **arguments)
        self.assertEqual(code, 2, (tool, arguments))
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("codex-task", err)

    def assertAllowed(self, tool, **arguments):
        self.assertEqual(run(tool, **arguments), (0, "", ""), (tool, arguments))

    def test_direct_code_edits_are_blocked(self):
        for path in ("/workspace/cstack/adapters/x.py", "app/page.tsx", "Makefile", "run.sh", "fleet.json"):
            self.assertBlocked("search_replace", file_path=path)
        self.assertBlocked("search_replace")

    def test_notes_and_prose_stay_editable(self):
        for path in ("/workspace/ops/agent-memory/grok-bot/notebook.md", "notes.txt", "brief.md"):
            self.assertAllowed("search_replace", file_path=path)

    def test_shell_code_writes_and_repo_changes_are_blocked(self):
        for command in ("git commit -am fix", "git -C /workspace/cstack push origin x", "echo 'x=1' > a.py",
                        "cat <<EOF >> lib/util.ts", "sed -i 's/a/b/' core.py", "tee app.js < /dev/null",
                        "cp /tmp/new.py adapters/new.py", "codex exec 'fix it'", "/usr/bin/codex exec --cd . x",
                        "git apply fix.patch"):
            self.assertBlocked("bash", command=command)

    def test_reading_running_and_routing_through_codex_pass(self):
        for command in ("git status", "git log --oneline -5", "git diff", "ls -la", "python3 -m unittest -v",
                        "codex-task /workspace/cstack 'add a test for X'",
                        "/workspace/ops/shields/lib/codex-guard.sh codex exec --cd /w 'x'",
                        "git -C /workspace/ops commit -am 'notebook entry'", "echo hi > /tmp/out.log",
                        "grep -rn TODO . 2>/dev/null", "git push --dry-run", "git apply --check fix.patch",
                        "git apply --stat fix.patch", "git status && git diff 2>&1 | head -5",
                        "bash -c 'git status'", "codex-task /workspace/cstack 'drop the --yolo mention in codex docs'"):
            self.assertAllowed("bash", command=command)
        self.assertAllowed("read_file", file_path="adapters/x.py")

    def test_guard_must_be_the_command_word_of_the_same_simple_command(self):
        for command in ("echo codex-guard.sh ; codex exec x", "echo codex-task && codex exec x",
                        "codex-guard.sh true | codex exec x", "codex-task /w 'x'\ncodex exec y",
                        "(codex-guard.sh true) ; codex exec x", "env codex exec x"):
            self.assertBlocked("bash", command=command)

    def test_command_substitution_resolving_to_codex_is_blocked(self):
        for command in ("$(command -v codex) exec x", "`which codex` exec x", "\"$(type -P codex)\" exec x",
                        "codex-task /w \"fix $(codex exec y)\"", "cat <(codex exec x)", "echo $(echo `x"):
            self.assertBlocked("bash", command=command)

    def test_shell_c_and_eval_are_checked_recursively(self):
        for command in ('bash -c "codex exec x"', "sh -c 'git commit -am x'", "bash -lc \"bash -c 'codex exec'\"",
                        "eval codex exec x", "eval 'git push origin main'", "/bin/sh -c 'echo x > a.py'",
                        "sudo -u bot bash -c 'git add -A'"):
            self.assertBlocked("bash", command=command)

    def test_notes_repo_paths_are_normalised(self):
        for command in ("git -C /workspace/ops/../cstack commit -m x", "git -C /workspace/ops/./../cstack push",
                        "git -C /workspace/ops -C ../cstack commit -m x", "git -C ops commit -m x",
                        "git -C /workspace/ops --git-dir=/workspace/cstack/.git commit -m x",
                        "GIT_DIR=/workspace/cstack/.git git -C /workspace/ops commit -m x"):
            self.assertBlocked("bash", command=command)
        self.assertAllowed("bash", command="git -C /workspace/ops/./agent-memory/.. commit -am note")

    def test_codex_control_files_are_protected(self):
        for path in ("~/.codex/rules/default.rules", "~/.codex/config.toml", "repo/.codex/notes.md",
                     "x.rules", "AGENTS.md", "/workspace/cstack/foundations/engine/AGENTS.override.md"):
            self.assertBlocked("write_file", path=path)
        for command in ("cat > ~/.codex/rules/x.rules", "printf x > AGENTS.override.md", "echo y >> AGENTS.md",
                        "cp /tmp/r ~/.codex/rules/default.rules", "ln -sf /tmp/x ~/.codex/config"):
            self.assertBlocked("bash", command=command)

    def test_direct_guard_launch_cannot_widen_codex(self):
        for flag in ("--dangerously-bypass-approvals-and-sandbox", "--yolo", "--approve-for-me", "--add-dir=/",
                     "-s danger-full-access", "--dangerously-bypass-hook-trust"):
            self.assertBlocked("bash", command=f"/workspace/ops/shields/lib/codex-guard.sh codex exec {flag} x")

    def test_other_agent_clis_are_blocked(self):
        for command in ("claude -p 'write code'", "hermes -q x", "cursor-agent 'fix'", "aider adapters/x.py",
                        "env claude -p x", "nohup hermes -q x", "timeout 30 claude -p x", "sudo -u bot claude -p x",
                        "/usr/local/bin/claude -p x", "ollama run llama3 'code'", "goose session", "amp -x y"):
            self.assertBlocked("bash", command=command)

    def test_guardfall_rewrites_of_agent_names_are_blocked(self):
        for command in ("cl''aude -p x", '"her"mes -q x', "\\claude -p x", "command claude -p x", "exec claude -p x",
                        "PATH=/opt/x claude -p y", "$CLAUDE_BIN -p x", "$(echo claude) -p x", "`which claude` -p x",
                        "codex-guard.sh claude exec x", "npx -y @anthropic-ai/claude-code 'x'", "uvx aider x",
                        "pipx run aider x", "bunx hermes q", "echo aGk= | base64 -d | sh", "bash run.sh"):
            self.assertBlocked("bash", command=command)

    def test_read_only_agent_invocations_pass(self):
        for command in ("claude --version", "hermes --help", "claude -h", "aider --version", "command -v claude",
                        "npx eslint .", "pipx install black"):
            self.assertAllowed("bash", command=command)

    def test_matcher_covers_every_tool_the_hook_handles(self):
        spec = importlib.util.spec_from_file_location("no_direct_code", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        policy = tomllib.loads((BOX / "requirements.toml").read_text())
        matcher = policy["hooks"]["PreToolUse"][0]["matcher"]
        self.assertEqual(set(matcher.split("|")), set(hook.EDIT_TOOLS + hook.SHELL_TOOLS))
        for tool in hook.EDIT_TOOLS:
            self.assertBlocked(tool, file_path="x.py")
        for tool in hook.SHELL_TOOLS:
            self.assertBlocked(tool, command="git commit -am x")

    def test_unreadable_calls_fail_closed(self):
        proc = subprocess.run([sys.executable, "-I", str(HOOK)], input="not json", capture_output=True, text=True,
                              timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertBlocked("bash", command="echo 'unterminated")


if __name__ == "__main__":
    unittest.main()

import io
import json
import subprocess
import sys
import unittest

from tests.agent_fixtures import ROOT, copy_tree, edit_json
from tools import agent_guard


class Guard(unittest.TestCase):
    def setUp(self):
        self.root = copy_tree(self)

    def decide(self, slug, tool, cwd=None, **tool_input):
        event = {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd or self.root)}
        result = agent_guard.evaluate(event, slug, self.root)
        return None if result is None else result["hookSpecificOutput"]["permissionDecision"]

    def test_writes_stay_inside_the_agents_own_slices(self):
        self.assertIsNone(self.decide("scribe", "Write", file_path=str(self.root / "work/specs/job/CONTRACT.md")))
        self.assertEqual(self.decide("scribe", "Edit", file_path=str(self.root / "src/app.py")), "deny")
        self.assertEqual(self.decide("warden", "Write", file_path=str(self.root / "work/checks/new.py")), "deny")
        self.assertIsNone(self.decide("archivist", "Write", file_path=str(self.root / "work/checks/new.py")))

    def test_the_root_slice_writes_everything_no_other_agent_owns(self):
        self.assertIsNone(self.decide("smith", "Edit", file_path=str(self.root / "src/app.py")))
        self.assertIsNone(self.decide("smith", "Write", cwd=self.root / "src", file_path="app.py"))
        self.assertEqual(self.decide("smith", "Write", file_path=str(self.root / "work/specs/job/tests.json")), "deny")

    def test_authority_and_agent_configuration_are_never_writable(self):
        for rel in ("aors/fleet.json", "agents/smith.md", ".claude/agents/smith.md", ".claude/settings.json",
                    ".mcp.json", "tools/agent_guard.py", "contracts/agent.schema.json"):
            self.assertEqual(self.decide("smith", "Write", file_path=str(self.root / rel)), "deny", rel)
        self.assertIsNone(self.decide("smith", "Write", file_path=str(self.root / ".claude/agent-memory-local/smith/m.md")))
        self.assertEqual(self.decide("smith", "Write", file_path=str(self.root / ".claude/agent-memory-local/sage/m.md")),
                         "deny")

    def test_paths_outside_the_project_and_missing_paths_are_denied(self):
        self.assertEqual(self.decide("smith", "Write", file_path="/tmp/elsewhere.txt"), "deny")
        self.assertEqual(self.decide("smith", "Write", file_path=str(self.root / "../escape.txt")), "deny")
        self.assertEqual(self.decide("smith", "Write"), "deny")

    def test_gated_commands_ask_and_ordinary_commands_pass(self):
        for command in ("git push origin feat", "gh pr create --draft", "rm -rf build", "curl -X POST https://x.test",
                        "git reset --hard HEAD~1", "make && rm out.txt"):
            self.assertEqual(self.decide("smith", "Bash", command=command), "ask", command)
        for command in ("python -B -m unittest discover -s tests", "git status", "ls -la", "grep -rn form ."):
            self.assertIsNone(self.decide("smith", "Bash", command=command), command)

    # E4: commands the old pattern list let through. Each must now ask (a gated effect) or be denied (a protected path).
    BYPASSES = (
        "/bin/rm -rf build", "/usr/bin/env rm out.txt", "command rm x", "sudo -u me rm x", "unlink a.txt",
        "find . -name '*.pyc' -delete", "find . -type f -exec /bin/rm {} \\;", "ls | xargs rm",
        "python3 -c 'import shutil; shutil.rmtree(\"build\")'", "python -Bc 'print(1)'", "node -e 'require(\"fs\")'",
        "perl -e 'unlink q(x)'", "echo rm x | sh", "bash -c 'rm -rf build'", "sh -c \"git push origin main\"",
        "eval 'rm x'", "echo $(rm x)", "echo `rm x`", "X=1 rm x", "(cd build && rm -f a)", "$CMD x",
        "git push --force origin main", "git clean -xdf", "git checkout -- .", "git restore src/app.py",
        "git stash drop", "gh api repos/o/r/issues -f title=x", "gh repo delete o/r --yes", "gh secret set TOKEN",
        "curl --json '{}' https://x.test", "curl -XPOST https://x.test", "wget --post-data=a https://x.test",
        "scp out.txt host:/tmp/", "ssh host uptime", "rsync -a out/ host:/srv/",
        "cat <<EOF > notes.txt\n$(rm -rf build)\nEOF",
    )
    PROTECTED_WRITES = (
        "echo '{}' > aors/fleet.json", "cp /tmp/x agents/smith.md", "sed -i '' s/a/b/ agents/chief.md",
        "cd aors && echo x >> fleet.json", "tee .mcp.json < /tmp/x", "mv /tmp/g tools/agent_guard.py",
        "git checkout main -- aors/fleet.json", "python3 tools/x.py > .claude/settings.json",
    )
    ORDINARY = (
        "python -B -m unittest discover -s tests", "python3 tools/agent_profiles.py --check", "node --test",
        "git status", "git diff HEAD~1", "git log --oneline -5", "git add src/app.py", "git commit -m 'fix'",
        "git restore --staged src/app.py", "gh pr view 12", "gh pr checks 12", "gh api repos/o/r/pulls",
        "ls -la | grep x", "cat aors/fleet.json", "grep -rn form . 2>/dev/null", "make test 2>&1 | tail -5",
        "bash ci/run-local.sh python links trace", ". .venv/bin/activate && python -m pytest",
        "curl -fsSL https://x.test/file -o out.txt", "mkdir -p build && cp src/a build/",
        "git commit -m \"$(cat <<'EOF'\nfix the thing\nEOF\n)\"", "echo done > /dev/null",
        "cat <<'EOF' > notes.txt\n$(not run)\nEOF",
    )

    def test_commands_the_old_patterns_missed_are_gated(self):
        for command in self.BYPASSES:
            self.assertEqual(self.decide("smith", "Bash", command=command), "ask", command)

    def test_bash_writes_to_authority_paths_are_denied(self):
        for command in self.PROTECTED_WRITES:
            self.assertEqual(self.decide("smith", "Bash", command=command), "deny", command)
        self.assertIsNone(self.decide("smith", "Bash", command="echo m > .claude/agent-memory-local/smith/m.md"))
        self.assertEqual(self.decide("smith", "Bash", command="echo m > .claude/agent-memory-local/sage/m.md"), "deny")

    def test_ordinary_commands_still_pass(self):
        for command in self.ORDINARY:
            self.assertIsNone(self.decide("smith", "Bash", command=command), command)

    def test_a_write_the_guard_cannot_place_asks_even_when_effects_are_allowed(self):
        def open_up(doc):
            bot = next(b for b in doc["bots"] if b["slug"] == "keeper")
            bot["effects"].update(delete="allow", post="allow", send="allow")
        edit_json(self.root / "aors/fleet.json", open_up)
        self.assertIsNone(self.decide("keeper", "Bash", command="rm -rf work/ops/old"))
        self.assertIsNone(self.decide("keeper", "Bash", command="python3 -c 'print(1)'"))
        self.assertEqual(self.decide("keeper", "Bash", command="cp x $DEST"), "ask")
        self.assertEqual(self.decide("keeper", "Bash", command="rm aors/fleet.json"), "deny")

    def test_denied_and_ask_classes_apply_to_built_in_tools(self):
        def restrict(doc):
            bot = next(b for b in doc["bots"] if b["slug"] == "keeper")
            bot["effects"].update(execute="deny", read="ask", write_slice="ask")
        edit_json(self.root / "aors/fleet.json", restrict)
        self.assertEqual(self.decide("keeper", "Bash", command="ls"), "deny")
        self.assertEqual(self.decide("keeper", "Read", file_path="README.md"), "ask")
        self.assertEqual(self.decide("keeper", "Write", file_path=str(self.root / "work/ops/x.md")), "ask")
        self.assertIsNone(self.decide("smith", "Read", file_path="README.md"))

    def test_unknown_agents_and_bad_input_fail_closed(self):
        self.assertEqual(self.decide("nobody", "Read"), "deny")
        out = io.StringIO()
        agent_guard.main(["--aor", "smith", "--root", str(self.root)], stdin=io.StringIO("not json"), stdout=out)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")
        out = io.StringIO()
        agent_guard.main(["--aor", "smith", "--root", str(self.root / "missing")],
                         stdin=io.StringIO('{"tool_name": "Bash", "tool_input": {"command": "ls"}}'), stdout=out)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_it_runs_isolated_on_the_standard_library_as_the_hook_command(self):
        event = {"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": str(self.root)}
        done = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tools/agent_guard.py"), "--aor", "smith"],
                              input=json.dumps(event), capture_output=True, text=True, timeout=30,
                              env={"CLAUDE_PROJECT_DIR": str(self.root), "PATH": "/usr/bin:/bin"})
        self.assertEqual(done.returncode, 0, done.stderr)
        output = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual((output["hookEventName"], output["permissionDecision"]), ("PreToolUse", "ask"))
        quiet = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tools/agent_guard.py"), "--aor", "smith"],
                               input=json.dumps({**event, "tool_input": {"command": "ls"}}), capture_output=True,
                               text=True, timeout=30, env={"CLAUDE_PROJECT_DIR": str(self.root), "PATH": "/usr/bin:/bin"})
        self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()

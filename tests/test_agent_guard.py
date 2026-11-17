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

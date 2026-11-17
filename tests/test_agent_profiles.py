import contextlib
import io
import json
import os
import unittest
from unittest import mock

from tests.agent_fixtures import ROOT, STARTERS, copy_tree, edit_front, edit_json
from tools import agent_profiles as gen

CLAUDE_CODE_FIELDS = {"name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
                      "skills", "mcpServers", "hooks", "memory", "background", "isolation", "effort", "color",
                      "initialPrompt"}


def frontmatter(text):
    head = text.split("---\n")[1]
    keys, values = [], {}
    for line in head.splitlines():
        if not line.startswith(" "):
            key, _, value = line.partition(":")
            keys.append(key)
            if value.strip():
                values[key] = json.loads(value)
    return keys, values


class Generator(unittest.TestCase):
    def setUp(self):
        self.files, self.problems = gen.build(ROOT)

    def test_the_committed_output_is_current_and_check_passes(self):
        self.assertEqual(self.problems, [])
        self.assertEqual(sorted(self.files), [f".claude/agents/{s}.md" for s in STARTERS])
        self.assertEqual(gen.stale(self.files, ROOT), [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gen.main(["--check"]), 0)
        self.assertIn("9 agents up to date", out.getvalue())

    def test_output_uses_only_documented_claude_code_fields_and_is_deterministic(self):
        for rel, text in self.files.items():
            keys, values = frontmatter(text)
            self.assertLessEqual(set(keys), CLAUDE_CODE_FIELDS, rel)
            self.assertEqual(values["name"], rel.split("/")[-1][:-3])
            self.assertEqual(values["permissionMode"], "default")
            self.assertIn(gen.MARKER, text)
            self.assertNotIn("mcpInheritance", text)
        self.assertEqual(gen.build(ROOT)[0], self.files)
        self.assertFalse(any(rel.startswith(".agent/") for rel in self.files))

    def test_each_agent_gets_its_own_server_inline_and_the_guard_hook(self):
        for slug in STARTERS:
            text = self.files[f".claude/agents/{slug}.md"]
            self.assertIn(f'  - {{"cstack-{slug}": {{"type": "stdio", "command": "sh"', text)
            self.assertIn(f'tools/cstack_mcp.py\\" --aor {slug}', text)
            self.assertIn(f'tools/agent_guard.py\\" --aor {slug}"', text)
            for other in STARTERS:
                if other != slug:
                    self.assertNotIn(f"cstack-{other}", " ".join(frontmatter(text)[1]["tools"]))
        smith = frontmatter(self.files[".claude/agents/smith.md"])[1]["tools"]
        self.assertIn("mcp__endoforge__*", smith)
        self.assertIn("--fleet-mail", self.files[".claude/agents/smith.md"])
        self.assertNotIn("--fleet-mail", self.files[".claude/agents/sage.md"])

    def test_mcp_allow_and_deny_lists_and_delegation_map_to_tools(self):
        chief = frontmatter(self.files[".claude/agents/chief.md"])[1]["tools"]
        self.assertIn("mcp__cstack-chief__ledger", chief)
        self.assertNotIn("mcp__cstack-chief__*", chief)
        self.assertNotIn("mcp__cstack-chief__execute", chief)
        self.assertIn("Agent(scribe, oracle, sage, smith, warden, lab, keeper, archivist)", chief)
        self.assertFalse(any(t.startswith("Agent") for t in frontmatter(self.files[".claude/agents/warden.md"])[1]["tools"]))
        tree = copy_tree(self)
        edit_front(tree / "agents/warden.md", lambda d: d["mcp_servers"][1].update(deny=["build"]))
        files, _ = gen.build(tree)
        self.assertEqual(frontmatter(files[".claude/agents/warden.md"])[1]["disallowedTools"], ["mcp__endoforge__build"])

    def test_built_in_tools_follow_the_aor_effects(self):
        tree = copy_tree(self)

        def lock_down(doc):
            bot = next(b for b in doc["bots"] if b["slug"] == "keeper")
            bot["effects"].update(execute="deny", write_slice="deny", read="ask")
            bot["slices"] = []
        edit_json(tree / "aors/fleet.json", lock_down)
        edit_json(tree / "agents/org.json", lambda d: d.update(
            artifacts=[a for a in d["artifacts"] if a["name"] != "pin_change"]))
        edit_front(tree / "agents/keeper.md", lambda d: d["handoff"].update(returns=["health_report"]))
        edit_front(tree / "agents/warden.md", lambda d: d["handoff"]["accepts"].remove("pin_change"))
        files, problems = gen.build(tree)
        self.assertEqual(problems, [])
        keys, values = frontmatter(files[".claude/agents/keeper.md"])
        self.assertNotIn("Bash", values["tools"])
        self.assertNotIn("Write", values["tools"])
        self.assertIn("Read", values["tools"])
        self.assertIn('matcher: "Read|Grep|Glob|WebFetch|WebSearch|Edit|Write|NotebookEdit|Bash"',
                      files[".claude/agents/keeper.md"])


class Check(unittest.TestCase):
    def test_drift_and_unmarked_extra_files_fail_and_write_removes_only_its_own(self):
        tree = copy_tree(self)
        files, problems = gen.build(tree)
        self.assertEqual(problems, [])
        gen.write(files, tree)
        self.assertEqual(gen.stale(files, tree), [])
        (tree / ".claude/agents/sage.md").write_text("edited by hand\n")
        (tree / ".claude/agents/mine.md").write_text("---\nname: mine\n---\n")
        (tree / ".claude/agents/old.md").write_text(gen.MARKER)
        self.assertEqual(gen.stale(files, tree), [".claude/agents/sage.md", ".claude/agents/mine.md (not generated)",
                                                  ".claude/agents/old.md (not generated)"])
        changed = gen.write(files, tree)
        self.assertEqual(changed, [".claude/agents/sage.md", ".claude/agents/old.md (removed)"])
        self.assertTrue((tree / ".claude/agents/mine.md").exists())

    def test_a_field_with_no_declared_disposition_fails(self):
        definitions = gen.load_definitions(ROOT / "agents")
        fields = {k: v for k, v in gen.FIELDS["claude-project"].items() if k != "routines"}
        with mock.patch.dict(gen.FIELDS, {"claude-project": fields}):
            found = gen.field_problems(definitions, "claude-project")
        self.assertIn("claude-project: field 'routines' has no declared disposition, so it would be dropped silently",
                      found)
        self.assertIn("keeper: field 'routines' is not declared for claude-project", found)

    def test_the_plugin_target_and_a_plugin_root_fail_because_they_drop_the_wiring(self):
        _, problems = gen.build(ROOT, "claude-plugin")
        for field in ("mcpServers", "hooks", "permissionMode"):
            self.assertIn(f"smith: target claude-plugin would drop wiring field '{field}'", problems)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gen.main(["--check", "--target", "claude-plugin"]), 1)
        tree = copy_tree(self)
        (tree / ".claude-plugin").mkdir()
        self.assertIn("this repository is a plugin root; plugin subagents drop mcpServers, hooks and permissionMode",
                      gen.build(tree)[1])

    def test_unsupported_fields_are_declared_in_the_agent_instructions(self):
        files, _ = gen.build(ROOT)
        self.assertIn("## Not fully honoured by this engine\n- `routines`", files[".claude/agents/keeper.md"])
        self.assertIn("different_model_preferred cannot be expressed", files[".claude/agents/warden.md"])
        self.assertIn("(`30 6 * * *`, paused)", files[".claude/agents/keeper.md"])

    def test_writes_outside_the_repository_are_refused(self):
        tree = copy_tree(self)
        outside = copy_tree(self)
        (tree / ".claude").mkdir()
        os.symlink(outside, tree / ".claude/agents")
        files, _ = gen.build(tree)
        with self.assertRaisesRegex(SystemExit, "outside the repository"):
            gen.write(files, tree)


if __name__ == "__main__":
    unittest.main()

import json
import re
import unittest

from jsonschema import Draft202012Validator

from adapters.aor_registry import GATED, load_fleet, parse_fleet
from tests.agent_fixtures import ROOT, STARTERS, copy_tree, edit_front, edit_json
from tools import agent_profiles as gen


def problems(tree):
    definitions = gen.load_definitions(tree / "agents")
    return gen.organization_problems(definitions, gen.load_org(tree / "agents/org.json"),
                                     load_fleet(tree / "aors/fleet.json"))


class Schemas(unittest.TestCase):
    def test_both_schemas_are_valid_draft_2020_12(self):
        for path in (gen.AGENT_SCHEMA, gen.ORG_SCHEMA):
            Draft202012Validator.check_schema(json.loads(path.read_text()))

    def test_slug_follows_agent_skills_naming(self):
        slug = Draft202012Validator(json.loads(gen.AGENT_SCHEMA.read_text())["$defs"]["slug"])
        for good in ("smith", "home-ops", "a" * 64):
            self.assertTrue(slug.is_valid(good), good)
        for bad in ("Smith", "-smith", "smith-", "two--hyphens", "a" * 65, "under_score"):
            self.assertFalse(slug.is_valid(bad), bad)

    def test_a_routine_that_is_not_paused_or_an_unknown_field_is_refused(self):
        tree = copy_tree(self)
        edit_front(tree / "agents/keeper.md", lambda d: d["routines"][0].update(paused=False))
        with self.assertRaisesRegex(gen.DefinitionError, "keeper.md: routines/0/paused"):
            gen.load_definitions(tree / "agents")
        edit_front(tree / "agents/keeper.md", lambda d: (d["routines"][0].update(paused=True), d.update(grants=["x"])))
        with self.assertRaisesRegex(gen.DefinitionError, "Additional properties"):
            gen.load_definitions(tree / "agents")


class StarterAgents(unittest.TestCase):
    def setUp(self):
        self.defs = gen.load_definitions(ROOT / "agents")
        self.org = gen.load_org(ROOT / "agents/org.json")
        self.artifacts = {a["name"]: a for a in self.org["artifacts"]}
        self.fleet = load_fleet(ROOT / "aors/fleet.json")

    def front(self, slug):
        return self.defs[slug][0]

    def test_the_nine_starters_validate_and_the_organization_is_consistent(self):
        self.assertEqual(tuple(sorted(self.defs)), STARTERS)
        self.assertEqual(gen.organization_problems(self.defs, self.org, self.fleet), [])

    def test_each_starter_has_its_own_full_access_aor_with_gated_effects_at_ask(self):
        for slug in STARTERS:
            bot = self.fleet.bot(slug)
            self.assertEqual(bot.id, self.front(slug)["id"])
            for effect in ("read", "write_slice", "execute", "config"):
                self.assertEqual(bot.effects.of(effect), "allow")
            for effect in GATED:
                self.assertEqual(bot.effects.of(effect), "ask")
        self.assertEqual(self.fleet.bot("example").effects.of("write_slice"), "deny")

    def test_each_starter_wields_its_tools(self):
        servers = {slug: {s["name"] for s in self.front(slug)["mcp_servers"]} for slug in STARTERS}
        for slug in STARTERS:
            self.assertIn(f"cstack-{slug}", servers[slug])
        self.assertIn("endoforge", servers["smith"])
        self.assertIn("foundations", servers["sage"])
        self.assertIn("poodo", servers["oracle"])
        self.assertIn("poodo", self.front("oracle")["skills"])

    def test_scribe_writes_the_spec_and_smith_only_builds_from_it(self):
        self.assertEqual(self.artifacts["spec"]["writer"], "scribe")
        self.assertIn("spec", self.front("smith")["handoff"]["accepts"])
        self.assertNotIn("spec", self.front("smith")["handoff"]["returns"])
        self.assertEqual(self.artifacts["candidate"]["writer"], "smith")
        self.assertEqual(self.artifacts["intent"]["writer"], "chief")

    def test_warden_verifies_independently_and_never_writes_what_it_runs(self):
        warden = self.front("warden")
        self.assertEqual(set(warden["independence"]), {"fresh_context", "different_model_preferred"})
        self.assertEqual(warden["handoff"]["returns"], ["verdict"])
        self.assertEqual(self.artifacts["check"]["writer"], "archivist")
        self.assertIn("warden", self.artifacts["check"]["readers"])
        for name in ("precommit", "result"):
            self.assertEqual(self.artifacts[name]["writer"], "lab")
            self.assertIn("warden", self.artifacts[name]["readers"])

    def test_owner_only_steps_are_listed_and_chief_is_off_the_approval_path(self):
        ids = {s["id"] for s in self.org["owner_only"]}
        self.assertTrue({"go_confirm", "approvals", "budget_raise", "approved_values", "frozen_records"} <= ids)
        chief = self.front("chief")
        own = next(s for s in chief["mcp_servers"] if s["name"] == "cstack-chief")
        self.assertNotIn("decide", own["allow"])
        self.assertNotIn("execute", own["allow"])
        self.assertIn("not on the approval path", self.defs["chief"][1])
        self.assertEqual(chief["reports_to"], "owner")

    def test_every_agent_keeps_twenty_options_and_the_research_gate_and_oracle_names_the_test_oracle(self):
        for slug in STARTERS:
            poodo = self.front(slug)["poodo"]
            self.assertEqual((poodo["options"], poodo["research_gate"]), (20, "required"), slug)
        self.assertEqual(self.front("oracle")["poodo"]["effort"], "thorough")
        self.assertIn("twenty", self.defs["chief"][1])
        self.assertIn("test oracle", self.front("oracle")["description"])
        self.assertIn("test oracle", self.defs["oracle"][1])

    def test_a_definition_that_lowers_the_option_count_or_skips_research_is_refused(self):
        for change in ({"options": 5}, {"research_gate": "optional"}, {"depth": "quick"}):
            tree = copy_tree(self)
            edit_front(tree / "agents/smith.md", lambda d: d["poodo"].update(change))
            with self.assertRaises(gen.DefinitionError, msg=change):
                gen.load_definitions(tree / "agents")

    def test_the_practice_states_the_twenty_option_rule_and_why(self):
        practice = (ROOT / "agents/PRACTICE.md").read_text()
        for phrase in ("exactly twenty materially distinct options", "long tail", "local minimum",
                       "tools/check_options.py", "never skip the twenty options"):
            self.assertIn(phrase, practice)

    def test_concurrency_policy_routes_through_chief_with_no_broadcast(self):
        policy = self.org["policy"]
        self.assertLessEqual(policy["max_active_per_task"], 4)
        self.assertEqual((policy["route_via"], policy["broadcast"], policy["live_instances_per_bot"]),
                         ("chief", False, 1))
        self.assertIn("LedgerStoreClaim", " ".join(policy["notes"]))

    def test_the_definitions_hold_no_contact_details(self):
        email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
        for path in [*(ROOT / "agents").rglob("*.md"), ROOT / "agents/org.json"]:
            self.assertIsNone(email.search(path.read_text()), path)
            self.assertNotIn("http", path.read_text(), path)


class OrganizationChecks(unittest.TestCase):
    def assertProblem(self, tree, text):
        found = problems(tree)
        self.assertTrue(any(text in p for p in found), found)

    def test_returning_an_artifact_another_agent_writes_is_refused(self):
        tree = copy_tree(self)
        edit_front(tree / "agents/smith.md", lambda d: d["handoff"]["returns"].append("spec"))
        self.assertProblem(tree, "smith: returns 'spec', whose single writer is scribe")

    def test_accepting_an_artifact_that_does_not_list_the_agent_is_refused(self):
        tree = copy_tree(self)
        edit_front(tree / "agents/keeper.md", lambda d: d["handoff"]["accepts"].append("candidate"))
        self.assertProblem(tree, "keeper: accepts 'candidate', which does not list it as a reader")

    def test_an_unknown_artifact_and_a_writer_that_does_not_return_its_artifact_are_refused(self):
        tree = copy_tree(self)
        edit_front(tree / "agents/lab.md", lambda d: d["handoff"].update(returns=["precommit", "rumour"]))
        self.assertProblem(tree, "lab: returns unknown artifact 'rumour'")
        self.assertProblem(tree, "artifact result: its writer lab does not return it")

    def test_a_named_reader_must_accept_the_artifact(self):
        tree = copy_tree(self)
        edit_json(tree / "agents/org.json", lambda d: next(a for a in d["artifacts"] if a["name"] == "spec")["readers"].append("keeper"))
        self.assertProblem(tree, "artifact spec: reader keeper does not accept it")

    def test_a_file_artifact_must_live_in_its_writers_slice(self):
        tree = copy_tree(self)
        edit_json(tree / "agents/org.json", lambda d: next(a for a in d["artifacts"] if a["name"] == "spec")["transport"].update(slice="work/ops"))
        self.assertProblem(tree, "artifact spec: slice work/ops is not in scribe's AOR slices")

    def test_identity_wiring_and_delegation_must_match_the_registry(self):
        tree = copy_tree(self)
        edit_front(tree / "agents/sage.md", lambda d: d.update(id="0000a0ff"))
        edit_front(tree / "agents/smith.md", lambda d: d.update(mcp_servers=[{"name": "endoforge"}]))
        edit_front(tree / "agents/lab.md", lambda d: d.update(max_depth=0))
        edit_front(tree / "agents/keeper.md", lambda d: d["mcp_servers"].append({"name": "cstack-chief"}))
        edit_front(tree / "agents/scribe.md", lambda d: d.update(reports_to="owner"))
        self.assertProblem(tree, "sage: id 0000a0ff differs from the AOR id 0000a004")
        self.assertProblem(tree, "smith: must be wired to its own cstack-smith MCP server")
        self.assertProblem(tree, "lab: max_depth must be 0 exactly when may_delegate_to is empty")
        self.assertProblem(tree, "keeper: MCP server 'cstack-chief' is neither its own cstack server nor a shared one")
        self.assertProblem(tree, "scribe: reports_to 'owner' differs from the AOR's 'chief'")

    def test_an_agent_without_an_aor_is_refused(self):
        tree = copy_tree(self)
        edit_json(tree / "aors/fleet.json", lambda d: d.update(bots=[b for b in d["bots"] if b["slug"] != "keeper"]))
        self.assertProblem(tree, "keeper: AOR 'keeper' is not in aors/fleet.json")


class Templates(unittest.TestCase):
    TEMPLATES = ("assistant", "domain-specialist", "home-ops", "money", "research", "security")

    def test_every_template_has_a_suggested_aor_and_a_file(self):
        org = gen.load_org(ROOT / "agents/org.json")
        self.assertEqual(tuple(sorted(org["templates"])), self.TEMPLATES)
        self.assertEqual(tuple(sorted(p.stem for p in (ROOT / "agents/templates").glob("*.md"))), self.TEMPLATES)

    def test_every_template_produces_an_equally_wired_agent(self):
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                tree = copy_tree(self)
                slug = f"my-{template}"
                entry = gen.new_agent(tree, template, slug, "My Helper", "Synthetic Domain")
                edit_json(tree / "aors/fleet.json", lambda d: d["bots"].append(entry))
                for effect in GATED:
                    self.assertEqual(entry["effects"][effect], "ask")
                parse_fleet(json.loads((tree / "aors/fleet.json").read_text()))
                files, found = gen.build(tree)
                self.assertEqual(found, [])
                text = files[f".claude/agents/{slug}.md"]
                self.assertIn(f'"cstack-{slug}"', text)
                self.assertIn(f"agent_guard.py\\\" --aor {slug}", text)
                self.assertNotRegex(text.replace("mcp__", ""), r"__[A-Z]+__")
                if template == "domain-specialist":
                    self.assertIn('"foundations"', text)
                    self.assertIn("Synthetic Domain", text)

    def test_new_agent_refuses_bad_input(self):
        tree = copy_tree(self)
        for args, message in (((tree, "money", "Bad_Slug", "X"), "Refusing slug"),
                              ((tree, "money", "owner", "X"), "Refusing slug"),
                              ((tree, "nope", "fine", "X"), "Unknown template"),
                              ((tree, "money", "fine", 'Quote"Name'), "Use letters"),
                              ((tree, "domain-specialist", "fine", "X"), "needs --foundation"),
                              ((tree, "money", "chief", "X"), "already exists")):
            with self.subTest(args=args[1:]), self.assertRaisesRegex(SystemExit, message):
                gen.new_agent(*args)


if __name__ == "__main__":
    unittest.main()

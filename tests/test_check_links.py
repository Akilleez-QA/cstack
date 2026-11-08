"""tools/check_links.py: the maps' named paths exist; branch names, external paths and templates are not paths."""
import importlib.util
import pathlib
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent.parent / 'tools' / 'check_links.py'
SPEC = importlib.util.spec_from_file_location('check_links', TOOL)
links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(links)

AGENTS = """# map
Run `python3 tools/real.py --flag` and read [the docs](docs/guide.md#top) and `docs/`.
Slugs come from `ops/agent-roles/notebook-slugs.tsv`.
Branches look like `example-agent/20261025-sentinel-import`; the repo is `your-org/cstack`; see `rounds/rNN/x.md`.
External: `/workspace/ops/x.sh`, `~/.cache/y`, `$HOME/z`, `~/LOCAL LLM/a b.txt`, `<owner>/assets-manifest.d/<n>.tsv`.
A label is display text: [`old/name.md`](docs/guide.md). A broken link: [gone](docs/gone.md).
"""
AREA = "Area paths resolve from the area root: `tools/area.mjs`, and from here: `notes.md`, `sub/x.md`.\n"


class CheckLinksTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        for f in ('tools/real.py', 'docs/guide.md', 'forge/endoforge/tools/area.mjs', 'forge/endoforge/docs/sub/x.md'):
            (self.root / f).parent.mkdir(parents=True, exist_ok=True)
            (self.root / f).write_text('x')
        (self.root / 'AGENTS.md').write_text(AGENTS)
        (self.root / 'forge/endoforge/docs/MAP.md').write_text(AREA)
        self.allow = self.root / 'allow.txt'
        self.allow.write_text('# comment\nrounds/rNN/*  # per-round template\n')

    def test_broken_paths_are_found_and_nothing_else(self):
        r = links.check(self.root, self.allow)
        self.assertEqual([(b['file'], b['line'], b['path']) for b in r['broken']],
                         [('AGENTS.md', 3, 'ops/agent-roles/notebook-slugs.tsv'), ('AGENTS.md', 6, 'docs/gone.md')])
        self.assertEqual(r['unused_allowlist'], [])

    def test_an_allowlist_entry_that_excuses_nothing_is_stale(self):
        self.allow.write_text('rounds/rNN/*  # template\ntools/real.py  # exists, so needless\nnope/*  # matches nothing\n')
        self.assertEqual(links.check(self.root, self.allow)['unused_allowlist'], ['tools/real.py', 'nope/*'])

    def test_an_allowlist_entry_needs_a_reason(self):
        self.allow.write_text('rounds/rNN/*\n')
        with self.assertRaises(SystemExit):
            links.check(self.root, self.allow)

    def test_the_readme_and_every_document_under_docs_are_maps(self):
        root = TOOL.parent.parent
        scanned = {p.relative_to(root).as_posix() for p in links.maps(root)}
        expected = {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", "NOTICE.md", "aors/README.md", "adapters/memory/README.md"}
        expected |= {p.relative_to(root).as_posix() for p in (root / "docs").rglob("*.md")}
        self.assertLessEqual(expected, scanned)
        self.assertFalse([p for p in scanned if "node_modules" in p])

    def test_the_repo_maps_are_clean(self):
        root = TOOL.parent.parent
        targets = []
        docs = ([root / "AGENTS.md"] if (root / "AGENTS.md").is_file() else [])
        docs += list((root / "contracts").glob("*.md"))
        docs += list((root / "workspace").rglob("README.md"))
        docs += list((root / "forge/endoforge/docs").glob("*.md"))
        for doc in docs:
            bases = links.roots_for(doc, root)
            for line in doc.read_text(encoding="utf-8").splitlines():
                for kind, raw in links.candidates(line):
                    token = links.clean(raw)
                    if token and not links.external(token) and not links.templated(token) and links.is_path(token, kind, bases):
                        targets.append(token)
        self.assertTrue(targets)
        result = links.check()
        self.assertGreaterEqual(result["checked"], len(targets))
        self.assertEqual((result["broken"], result["unused_allowlist"]), ([], []))


if __name__ == '__main__':
    unittest.main()

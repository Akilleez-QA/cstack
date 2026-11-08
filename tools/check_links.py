#!/usr/bin/env python3
"""Check that the repo's maps name paths that exist.

Scans the root README, AGENTS, CONTRIBUTING, CHANGELOG and NOTICE, every document under docs/, contracts/*.md, the
adapters/*/ and aors/ READMEs, examples/workflows/**/README.md and forge/endoforge/docs/*.md for
  - markdown links `[text](target)` that are not URLs or pure anchors, and
  - backticked repo-relative paths, including path tokens inside backticked commands,
and fails when a named path exists nowhere it could mean.

A backticked token counts as a path when it has a `/` and either ends in a file extension or starts with a directory
that exists, so branch names (`example-agent/20261025-x`) and repo slugs (`your-org/cstack`) are not paths.
Absolute (`/workspace/...`), home (`~/...`) and variable (`$HOME/...`) paths are external and never checked; nor are
templates (`<n>`), globs, or bare file names. A path resolves against the document's folder or any folder above it up
to the repo root, because area manuals name paths from their own area root (`forge/endoforge/docs` says `tools/job`).

Deliberately external relative paths (box paths written without /workspace, user-unit paths) are listed with a reason
in ci/link-allowlist.txt: one `<glob>  # reason` per line. An entry that excuses no missing path fails (it matches
nothing, or what it matches now exists), so the list stays short and true.

  python3 tools/check_links.py            # exit 1 and list each broken reference as file:line: path
  python3 tools/check_links.py --json     # the same as JSON
"""
import argparse, fnmatch, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAPS = ['README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'NOTICE.md', 'docs/**/*.md', 'contracts/*.md',
        'adapters/*/README.md', 'aors/README.md', 'examples/workflows/**/README.md', 'forge/endoforge/docs/*.md']
ALLOWLIST = ROOT / 'ci' / 'link-allowlist.txt'

LINK = re.compile(r'(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
TICKS = re.compile(r'`([^`\n]+)`')
PATHISH = re.compile(r'[A-Za-z0-9_.@+-][A-Za-z0-9_./@+-]*')
EXT = re.compile(r'\.[A-Za-z][A-Za-z0-9]{0,6}$')


def maps(root):
    out = set()
    for pattern in MAPS:
        out.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(out)


def roots_for(doc, root):
    """The document's folder and every folder above it, up to and including the repo root."""
    d, out = doc.parent, []
    while True:
        out.append(d)
        if d == root:
            return out
        d = d.parent


def clean(token):
    token = token.strip().strip('\'"').rstrip('.,;:)')
    token = re.sub(r'#.*$', '', token)          # anchors
    token = re.sub(r':\d+(-\d+)?$', '', token)  # file:line
    return token.rstrip('/') if len(token) > 1 else token


def external(token):
    return token.startswith(('/', '~', '$', '-')) or '://' in token or token.startswith(('mailto:', '#'))


def templated(token):
    return any(c in token for c in '<>*?{}[]|=,') or '...' in token or '…' in token


def candidates(line):
    """(kind, token) pairs on one line: markdown link targets and backticked path tokens. A link's label is display
    text (`[`mononoke/STUDY.md`](studies/mononoke/STUDY.md)`), and a span that starts with an external path is one
    path even with spaces in it (`~/LOCAL LLM/x.txt`), so neither is scanned for tokens."""
    for m in LINK.finditer(line):
        yield 'link', m.group(1)
    for m in TICKS.finditer(LINK.sub(' ', line)):
        span = m.group(1).strip()
        if external(span):
            continue
        for raw in span.split():
            yield 'tick', raw


def is_path(token, kind, bases):
    if kind == 'link':
        return True
    if '/' not in token or not PATHISH.fullmatch(token):
        return False
    first = token.split('/', 1)[0]
    return bool(EXT.search(token)) or any((b / first).is_dir() for b in bases)


def load_allowlist(path):
    entries = []
    if path.exists():
        for n, raw in enumerate(path.read_text().splitlines(), 1):
            glob, _, reason = raw.partition('#')
            glob = glob.strip()
            if glob:
                if not reason.strip():
                    raise SystemExit(f'{path}:{n}: allowlist entry {glob!r} needs a `# reason`')
                entries.append(glob)
    return entries


def check(root=ROOT, allowlist=None):
    allow = load_allowlist(ALLOWLIST if allowlist is None else allowlist)
    used, broken, checked = set(), [], 0
    for doc in maps(root):
        bases = roots_for(doc, root)
        for n, line in enumerate(doc.read_text(encoding='utf-8').splitlines(), 1):
            for kind, raw in candidates(line):
                token = clean(raw)
                if not token or external(token) or templated(token) or not is_path(token, kind, bases):
                    continue
                checked += 1
                if any((b / token).exists() for b in bases):
                    continue
                hit = [g for g in allow if fnmatch.fnmatch(token, g)]
                if hit:
                    used.update(hit); continue
                broken.append({'file': str(doc.relative_to(root)), 'line': n, 'path': token})
    unused = [g for g in allow if g not in used]
    return {'checked': checked, 'broken': broken, 'unused_allowlist': unused}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    r = check()
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        for b in r['broken']:
            print(f"{b['file']}:{b['line']}: {b['path']}")
        for g in r['unused_allowlist']:
            print(f'ci/link-allowlist.txt: {g!r} excuses no missing path; remove it')
        print(f"check_links: {r['checked']} paths checked, {len(r['broken'])} broken, "
              f"{len(r['unused_allowlist'])} stale allowlist entries", file=sys.stderr)
    return 1 if r['broken'] or r['unused_allowlist'] else 0


if __name__ == '__main__':
    sys.exit(main())

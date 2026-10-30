#!/usr/bin/env python3
"""Merge train for the cstack monorepo .

Merges open PRs in dependency order: roots first (base = main), then retargets each merged PR's children to main and
merges them in a later pass. Squash merges only; never deletes branches; never force-pushes; never merges a PR whose
body lists no local checks (CI is down, so the listed checks are the evidence).

  python3 tools/merge_train.py --dry-run                # what would merge now
  python3 tools/merge_train.py                          # merge everything in scope (all policy)
  python3 tools/merge_train.py --policy low-risk        # the daily train: low-risk paths only
  python3 tools/merge_train.py --wip                    # open PRs per lane against the WIP limit (10)

Scope: coordinator/* branches, plus worker/* branches whose files are all in the iteration paths below.
Platform-core paths (poodo_core, adapters, contracts, tools, tests, workspace, examples/interface, parts-wall/oss) stay with
Coordinator review and are never merged by this train.

Other mergers (the Coordinator bot, the owner) work the same queue under the same account, so every PR's state is
re-read just before the train acts on it, and an error on one PR is recorded and skipped rather than ending the run.
One train runs at a time (a lock in ~/.cache); stdout carries only the JSON summary, progress goes to stderr.
"""
import argparse, collections, fcntl, fnmatch, json, os, re, subprocess, sys, time

LOCK = os.path.expanduser('~/.cache/cstack-merge-train.lock')

ITERATION = ['examples/*', 'docs/*']
CORE = ['poodo_core/*', 'adapters/*', 'contracts/*', 'tools/*', 'tests/*', 'bootstrap.py', 'cli.py',
        'extensions/*', 'vendor/*', '.github/*']
LOW_RISK = ['docs/*', '*.md']
NEVER_AUTO = ['contracts/*']
WIP_LIMIT = 10


def gh(*a, check=True):
    r = subprocess.run(['gh', *a], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"gh {' '.join(a)}: {r.stderr.strip()}")
    return r.stdout


def match(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def pr_detail(n, cache):
    if n not in cache:
        d = json.loads(gh('pr', 'view', str(n), '--json', 'files,body,mergeable,mergeStateStatus,baseRefName,headRefName,state,isDraft'))
        cache[n] = d
    return cache[n]


def in_scope(p, files):
    head = p['headRefName']
    if any(match(f, CORE) for f in files) and not head.startswith('coordinator/'):
        return False
    if head.startswith('coordinator/'):
        return not any(match(f, ['poodo_core/*', 'adapters/*', 'contracts/*', 'examples/interface/*']) for f in files)
    if head.startswith('worker/'):
        return bool(files) and all(match(f, ITERATION) for f in files)
    return False


def has_checks(body):
    """A checks section (any heading style) with at least one recorded result."""
    b = body or ''
    return bool(re.search(r'checks?\b', b, re.I) and re.search(r'→|->|\bPASS(ED)?\b|\bpassed\b|\bok\b|0 error', b, re.I))


def superseded(p, all_heads):
    """The Coordinator bot re-slices big PRs as `<head>-v2` or `<number>-splitN`; never merge an original twice."""
    head, n = p['headRefName'], str(p['number'])
    return any(h == head + '-v2' or re.search(rf'/\d{{8}}-{n}-split', h) for h in all_heads)


def low_risk(files):
    return all(match(f, LOW_RISK) for f in files) and not any(match(f, NEVER_AUTO) for f in files)


def view(n):
    return json.loads(gh('pr', 'view', str(n), '--json', 'mergeable,mergeStateStatus,state,baseRefName'))


def wait_mergeable(n, tries=12):
    for _ in range(tries):
        d = view(n)
        if d['state'] != 'OPEN' or d['mergeable'] != 'UNKNOWN':
            return d
        time.sleep(5)
    return d


def wip():
    prs = json.loads(gh('pr', 'list', '--state', 'open', '--limit', '300', '--json', 'number,headRefName'))
    lanes = collections.Counter()
    for p in prs:
        h = p['headRefName']
        m = re.match(r'(coordinator|worker|coord|example-agent|sample)/\d{8}-([a-z0-9]+)', h)
        lanes[(m.group(1) + ':' + m.group(2)) if m else h.split('/')[0]] += 1
    for lane, n in lanes.most_common():
        print(f"{n:3d}  {lane}{'   OVER WIP LIMIT' if n > WIP_LIMIT else ''}")
    return lanes


def branch_slugs(root=None):
    """Fleet bot slugs plus lanes and aliases (aors/branch-slugs.json); empty when the roster is missing."""
    root = root or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    try:
        with open(os.path.join(root, 'aors', 'fleet.json')) as fh:
            known = {b['slug'] for b in json.load(fh).get('bots', []) if b.get('slug')}
        with open(os.path.join(root, 'aors', 'branch-slugs.json')) as fh:
            extra = json.load(fh)
        return known | set(extra.get('lanes', [])) | set(extra.get('aliases', {}))
    except (OSError, ValueError):
        return set()


def consider(p, heads, all_heads, cache, a):
    """Decide on one open PR and act on it. Returns ('merged' | 'retargeted' | 'skip', reason)."""
    n = p['number']
    d = pr_detail(n, cache)
    files = [f['path'] for f in d.get('files', [])]
    slug = (p.get('headRefName') or '').split('/')[0]
    known = branch_slugs()
    if known and slug not in known:
        # a branch must be named for a fleet bot or lane (AGENTS.md rule 3): `null/...` reached GitHub on 2026-10-27
        return 'skip', f"unknown bot slug '{slug}' (aors/fleet.json, aors/branch-slugs.json)"
    if d.get('isDraft'):
        # a draft is not offered for merge (the 2026-10-27 dry run listed "[draft, paused] ... do not merge yet" as merged)
        return 'skip', 'draft'
    if not in_scope(p, files):
        return 'skip', 'out of scope (platform core or other bot)'
    if superseded(p, all_heads):
        return 'skip', 'superseded by a Coordinator re-slice'
    if p['baseRefName'] != 'main':
        if p['baseRefName'] in heads:
            return 'skip', f"stacked on #{heads[p['baseRefName']]}"
        # parent merged or gone: retarget to main, unless another merger already moved or closed it
        if not a.dry_run:
            cur = view(n)
            if cur['state'] != 'OPEN':
                return 'skip', f"{cur['state'].lower()} by another merger"
            if cur['baseRefName'] != 'main':
                gh('pr', 'edit', str(n), '--base', 'main')
            cache.pop(n, None)
        return 'retargeted', ''
    if not has_checks(d.get('body')):
        return 'skip', 'no local checks listed'
    if a.policy == 'low-risk' and not low_risk(files):
        return 'skip', 'not low-risk (needs review)'
    st = wait_mergeable(n) if not a.dry_run else d
    if st.get('state') != 'OPEN':
        return 'skip', f"{st.get('state', '?').lower()} by another merger"
    if st.get('mergeable') == 'CONFLICTING' or st.get('mergeStateStatus') == 'DIRTY':
        return 'skip', 'conflicts with main'
    if st.get('mergeable') != 'MERGEABLE':
        return 'skip', f"mergeable={st.get('mergeable')} state={st.get('mergeStateStatus')}"
    if a.dry_run:
        return 'merged', ''
    r = subprocess.run(['gh', 'pr', 'merge', str(n), '--squash'], capture_output=True, text=True)
    if r.returncode:
        return 'skip', 'merge failed: ' + r.stderr.strip()[:160]
    return 'merged', ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--policy', choices=['all', 'low-risk'], default='all')
    ap.add_argument('--wip', action='store_true')
    ap.add_argument('--max-passes', type=int, default=12)
    a = ap.parse_args()
    if a.wip:
        wip(); return 0
    if not a.dry_run:
        os.makedirs(os.path.dirname(LOCK), exist_ok=True)
        lock = open(LOCK, 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f'another merge train holds {LOCK}; not starting a second one', file=sys.stderr)
            return 0
    cache, merged, skipped, retargeted = {}, [], {}, []
    all_heads = {p['headRefName'] for p in json.loads(gh('pr', 'list', '--state', 'all', '--limit', '500', '--json', 'headRefName'))}
    try:
        for npass in range(a.max_passes):
            prs = json.loads(gh('pr', 'list', '--state', 'open', '--limit', '300', '--json', 'number,headRefName,baseRefName'))
            heads = {p['headRefName']: p['number'] for p in prs}
            progress = False
            for p in sorted(prs, key=lambda p: p['number']):
                n = p['number']
                try:
                    act, why = consider(p, heads, all_heads, cache, a)
                except (RuntimeError, ValueError, KeyError) as e:  # one bad PR must not stop the train
                    act, why = 'skip', f'error: {str(e)[:200]}'
                if act == 'skip':
                    skipped[n] = why; continue
                (merged if act == 'merged' else retargeted).append(n); skipped.pop(n, None)
                if a.dry_run:
                    progress = progress or act == 'retargeted'; continue
                progress = True
                print(f"{act} #{n} {p['headRefName']}", file=sys.stderr, flush=True)
            if a.dry_run or not progress:
                break
    finally:
        print(json.dumps({'merged': merged, 'retargeted': retargeted,
                          'skipped': {str(k): v for k, v in sorted(skipped.items())}}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())

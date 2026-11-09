#!/usr/bin/env python3
"""Check bidirectional traceability between requirements, design, tests and the verification matrix.

Reads docs/requirements/requirements.md, docs/verification/verification-matrix.md and
docs/architecture/architecture.md, and the test tree under tests/. Fails when
  - a requirement has no matrix row (untraced),
  - a requirement's rows name no test and it is not in the matrix's "Untested requirement gaps" table (untested),
  - a gap is listed for a requirement that has a test (stale gap),
  - a matrix row names a test file, class or method that does not exist,
  - a tests/**/test_*.py file is neither named by a row nor classified in "Tests without a requirement",
  - a requirement lacks its Derivation, Allocated to, Verification or Status field, or a derivation path is missing,
  - a requirement's "Allocated to" component and the design's component table disagree, in either direction,
  - a Markdown link in a control document points to a missing file or a missing heading.

  python3 tools/check_trace.py            # summary on stderr, each failure on stdout, exit 1 on any failure
  python3 tools/check_trace.py --json     # the full result as JSON
"""
import argparse, ast, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRS = 'docs/requirements/requirements.md'
VM = 'docs/verification/verification-matrix.md'
SDD = 'docs/architecture/architecture.md'
CONTROL = ['docs/README.md', 'docs/plan/*.md', 'docs/requirements/*.md', 'docs/architecture/*.md', 'docs/icd/*.md',
           'docs/data/*.md', 'docs/verification/*.md', 'docs/verification/reports/*.md',
           'docs/configuration/*.md', 'docs/releases/*.md', 'docs/assurance/*.md', 'docs/guides/SUM-MAP.md',
           'docs/standards/*.md']
FIELDS = ('Derivation', 'Allocated to', 'Verification', 'Status')

REQ_HEAD = re.compile(r'^### (CS-REQ-\d{3})\b')
REQ_ID = re.compile(r'CS-REQ-\d{3}')
COMPONENT = re.compile(r'SDD-C\d+')
TEST_REF = re.compile(r'`(tests/[\w/]+\.py)(?:::(\w+)(?:\.(\w+))?)?`')
TICK = re.compile(r'`([^`\s]+)`')
LINK = re.compile(r'(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)')
HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
FENCE = re.compile(r'^\s*(```|~~~)')


def read(root, rel):
    path = root / rel
    return path.read_text(encoding='utf-8') if path.is_file() else ''


def section(text, title):
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            inside = line[3:].strip().lower() == title.lower()
            continue
        if inside:
            out.append(line)
    return out


def rows(lines):
    for line in lines:
        if line.startswith('|') and not re.match(r'^\|[\s:|-]+\|?$', line):
            yield [c.strip() for c in line.strip().strip('|').split('|')]


def requirements(text):
    reqs, current = {}, None
    for line in text.splitlines():
        m = REQ_HEAD.match(line)
        if m:
            current = reqs.setdefault(m.group(1), {'fields': {}})
            continue
        if line.startswith('#'):
            current = None
            continue
        if current is not None:
            f = re.match(r'^- (Derivation|Allocated to|Verification|Status):\s*(.*)$', line)
            if f:
                current['fields'][f.group(1)] = f.group(2)
    return reqs


def matrix(text):
    traced, gaps, classified = {}, [], set()
    for cells in rows(section(text, 'Requirement to test')):
        if REQ_ID.fullmatch(cells[0]):
            refs = [m.groups() for m in TEST_REF.finditer(' '.join(cells[2:3]))]
            traced.setdefault(cells[0], []).extend(refs)
    for cells in rows(section(text, 'Untested requirement gaps')):
        if REQ_ID.fullmatch(cells[0]):
            gaps.append(cells[0])
    for cells in rows(section(text, 'Tests without a requirement')):
        classified.update(TICK.findall(cells[0]))
    return traced, gaps, classified


def design(text):
    comps = {}
    for cells in rows(section(text, '4. Decomposition and allocation')):
        if COMPONENT.fullmatch(cells[0]):
            comps[cells[0]] = {'requirements': set(REQ_ID.findall(cells[-1])),
                               'infrastructure': 'infrastructure' in cells[-1].lower()}
    return comps


def test_index(root):
    index = {}
    for path in sorted((root / 'tests').rglob('test_*.py')):
        classes = {}
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.ClassDef):
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                classes[node.name] = (bases, methods)
        index[path.relative_to(root).as_posix()] = classes
    return index


def has_method(classes, name, method, seen=()):
    if name not in classes or name in seen:
        return False
    bases, methods = classes[name]
    return method in methods or any(has_method(classes, b, method, seen + (name,)) for b in bases)


def resolve(index, file, cls, method):
    if file not in index:
        return 'no such test file'
    classes = index[file]
    if cls and cls not in classes:
        return 'no such class'
    if method and not has_method(classes, cls, method):
        return 'no such method'
    return None


def slug(heading):
    text = re.sub(r'[^\w\- ]', '', heading.strip().lower())
    return text.replace(' ', '-')


def anchors(text):
    seen, out, fenced = {}, set(), False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        m = None if fenced else HEADING.match(line)
        if m:
            base = slug(m.group(2))
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.add(base if n == 0 else f'{base}-{n}')
    return out


def control_documents(root):
    found = set()
    for pattern in CONTROL:
        found.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(found)


def dead_links(root):
    dead, cache = [], {}
    for doc in control_documents(root):
        text, fenced = doc.read_text(encoding='utf-8'), False
        for n, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for target in LINK.findall(line):
                if '://' in target or target.startswith('mailto:'):
                    continue
                path, _, anchor = target.partition('#')
                dest = (doc.parent / path).resolve() if path else doc
                if not dest.exists():
                    dead.append({'file': doc.relative_to(root).as_posix(), 'line': n, 'target': target}); continue
                if anchor and dest.suffix == '.md' and dest.is_file():
                    if dest not in cache:
                        cache[dest] = anchors(dest.read_text(encoding='utf-8'))
                    if anchor not in cache[dest]:
                        dead.append({'file': doc.relative_to(root).as_posix(), 'line': n, 'target': target})
    return dead


def check(root=ROOT):
    root = pathlib.Path(root)
    reqs = requirements(read(root, SRS))
    traced, gaps, classified = matrix(read(root, VM))
    comps = design(read(root, SDD))
    index = test_index(root)

    result = {'requirements': len(reqs), 'untraced': [], 'untested': [], 'stale_gaps': [], 'missing_tests': [],
              'unclassified_tests': [], 'fields': [], 'allocation': [], 'dead_links': [], 'gaps': []}
    referenced = set()
    for rid, req in sorted(reqs.items()):
        for field in FIELDS:
            if not req['fields'].get(field):
                result['fields'].append({'requirement': rid, 'missing': field})
        for token in TICK.findall(req['fields'].get('Derivation', '')):
            if '/' in token and not (root / token.rstrip('/')).exists():
                result['fields'].append({'requirement': rid, 'path': token})
        if req['fields'].get('Status', '').startswith('Deleted'):
            continue
        refs = traced.get(rid)
        if refs is None:
            result['untraced'].append(rid)
        elif not refs:
            (result['gaps'] if rid in gaps else result['untested']).append(rid)
        elif rid in gaps:
            result['stale_gaps'].append(rid)
        alloc = COMPONENT.findall(req['fields'].get('Allocated to', ''))
        for comp in alloc:
            if comp not in comps or rid not in comps[comp]['requirements']:
                result['allocation'].append({'requirement': rid, 'component': comp, 'problem': 'design does not list it'})
        if req['fields'].get('Allocated to') and not alloc:
            result['allocation'].append({'requirement': rid, 'component': None, 'problem': 'no SDD component named'})
    for rid, refs in sorted(traced.items()):
        if rid not in reqs:
            result['untraced'].append(rid)
        for file, cls, method in refs:
            referenced.add(file)
            problem = resolve(index, file, cls, method)
            if problem:
                ref = file + (f'::{cls}' if cls else '') + (f'.{method}' if method else '')
                result['missing_tests'].append({'requirement': rid, 'ref': ref, 'problem': problem})
    for comp, info in sorted(comps.items()):
        for rid in sorted(info['requirements']):
            if rid not in reqs or comp not in COMPONENT.findall(reqs[rid]['fields'].get('Allocated to', '')):
                result['allocation'].append({'requirement': rid, 'component': comp, 'problem': 'requirement not allocated here'})
        if not info['requirements'] and not info['infrastructure']:
            result['allocation'].append({'requirement': None, 'component': comp, 'problem': 'no requirements and not infrastructure'})
    result['unclassified_tests'] = sorted(f for f in index if f not in referenced and f not in classified)
    result['dead_links'] = dead_links(root)
    result['traced_test_files'] = len(referenced & set(index))
    result['test_files'] = len(index)
    return result


def failures(result):
    out = []
    out += [f'untraced requirement: {r}' for r in result['untraced']]
    out += [f'requirement with no test and no gap entry: {r}' for r in result['untested']]
    out += [f'gap listed but the requirement has a test: {r}' for r in result['stale_gaps']]
    out += [f"{m['requirement']}: {m['ref']}: {m['problem']}" for m in result['missing_tests']]
    out += [f'test file neither traced nor classified: {f}' for f in result['unclassified_tests']]
    out += [f"{m['requirement']}: " + (f"missing field {m['missing']}" if 'missing' in m else f"derivation path missing: {m['path']}")
            for m in result['fields']]
    out += [f"allocation: {m['requirement']} / {m['component']}: {m['problem']}" for m in result['allocation']]
    out += [f"{d['file']}:{d['line']}: dead link {d['target']}" for d in result['dead_links']]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--root', default=str(ROOT))
    a = ap.parse_args(argv)
    result = check(pathlib.Path(a.root))
    bad = failures(result)
    if a.json:
        print(json.dumps(result, indent=1))
    else:
        for line in bad:
            print(line)
    print(f"check_trace: {result['requirements']} requirements, {result['requirements'] - len(result['gaps']) - len(result['untested']) - len(result['untraced'])} with tests, "
          f"{len(result['gaps'])} listed gaps; {result['traced_test_files']}/{result['test_files']} test files traced; "
          f"{len(bad)} failures", file=sys.stderr)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

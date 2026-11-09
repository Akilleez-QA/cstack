#!/usr/bin/env python3
"""Generate the test report (STR) and version description (VDD) for a baseline or tag.

Runs each suite through `bash ci/run-local.sh <suite>`, records its exit status, duration, output digest and
unittest totals, then writes docs/verification/reports/STR-<label>.md and docs/releases/VDD-<label>.md from that
run, git, the CHANGELOG, tools/check_trace.py and (when `gh` is available) GitHub issue and PR queries.
Nothing in either file is typed by hand; rerun this tool to refresh them.

  python3 -B tools/gen_release_docs.py --label baseline                   # all suites, then write both files
  python3 -B tools/gen_release_docs.py --label v0.1.0 --suites python links trace
"""
import argparse, datetime, hashlib, importlib.util, json, os, pathlib, platform, re, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('check_trace', ROOT / 'tools' / 'check_trace.py')
check_trace = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_trace)

SUITES = ('python', 'links', 'trace', 'refrigeration', 'gitleaks', 'trufflehog')
MANIFESTS = ('EXPORT-MANIFEST.json', 'vendor/foundation-math-v014/SOURCE-MANIFEST.json',
             'vendor/foundation-engine-v020/SOURCE-MANIFEST.json', 'vendor/endoforge/SOURCE-MANIFEST.json',
             'foundations/template/SOURCE-MANIFEST.json', 'foundations/refrigeration/SOURCE-MANIFEST.json',
             'foundations/robotics/SOURCE-MANIFEST.json', 'foundations/film/SOURCE-MANIFEST.json',
             'contracts/SOURCE-PINS.json', 'contracts/ADAPTERS.json')
CONTROL = ('docs/plan/software-management-plan.md', 'docs/plan/compliance-matrix.md',
           'docs/requirements/requirements.md', 'docs/architecture/architecture.md', 'docs/data/data-dictionary.md',
           'docs/verification/test-plan.md', 'docs/verification/verification-matrix.md',
           'docs/configuration/configuration-management.md', 'docs/assurance/assurance-record.md',
           'docs/icd/icd-foundations.md', 'docs/icd/icd-endoforge.md', 'docs/icd/icd-endoforge-pin.md',
           'docs/icd/icd-poodo.md')
RAN = re.compile(r'^Ran (\d+) tests? in ([\d.]+)s$')
STATUS = re.compile(r'^(OK|FAILED)(?: \((.*)\))?$')


def sh(*argv, check=False):
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f'{" ".join(argv)} failed: {r.stderr.strip()}')
    return r.stdout.strip()


def python_runs():
    names = ['root', 'root -O']
    for domain in sorted((ROOT / 'foundations').iterdir()):
        if (domain / 'tests').is_dir():
            names += [f'{domain.relative_to(ROOT)}', f'{domain.relative_to(ROOT)} -O']
    return names


def unittest_totals(text):
    out, pending = [], None
    for line in text.splitlines():
        m = RAN.match(line.strip())
        if m:
            pending = int(m.group(1)); continue
        s = STATUS.match(line.strip())
        if s and pending is not None:
            extra = dict(kv.split('=') for kv in s.group(2).split(', ')) if s.group(2) else {}
            out.append({'ran': pending, 'status': s.group(1), 'skipped': int(extra.get('skipped', 0)),
                        'failures': int(extra.get('failures', 0)), 'errors': int(extra.get('errors', 0))})
            pending = None
    return out


def run_suite(suite, python):
    start = time.monotonic()
    r = subprocess.run(['bash', 'ci/run-local.sh', suite], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'PYTHON': python})
    text = r.stdout + r.stderr
    return {'suite': suite, 'exit': r.returncode, 'seconds': round(time.monotonic() - start, 1),
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'totals': unittest_totals(text),
            'tail': [l for l in text.splitlines() if l.startswith(('check_links:', 'check_trace:'))]}


def gh_json(*args):
    if not shutil.which('gh'):
        return None
    r = subprocess.run(['gh', *args], cwd=ROOT, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def sloc():
    counts = {}
    for name in sh('git', 'ls-files').splitlines():
        if name.startswith(('vendor/', 'foundations/', 'reasoning/', 'TODELETE/')):
            continue
        ext = pathlib.Path(name).suffix or '(none)'
        if ext in ('.py', '.mjs', '.ts', '.sh', '.md', '.json'):
            try:
                counts[ext] = counts.get(ext, 0) + sum(1 for _ in open(ROOT / name, encoding='utf-8'))
            except (OSError, UnicodeDecodeError):
                pass
    return counts


def changelog_unreleased():
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(r'^## \[?Unreleased\]?.*?$(.*?)(?=^## |\Z)', text, re.M | re.S)
    return [l[2:].strip() for l in (m.group(1) if m else '').splitlines() if l.startswith('- ')]


def header(doc_id, title, label, commit, today):
    return f"""# Cstack {title} {label}

| Field | Value |
|---|---|
| Document ID | {doc_id} |
| Version | 1.0 |
| Status | Baselined (generated) |
| Owner | Akilleez-QA |
| Date | {today} |
| Baseline commit | {commit} |
| Applies to | cstack {'main at baseline commit' if label == 'baseline' else label} |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Generated by `python3 -B tools/gen_release_docs.py --label {label}`. Do not edit by hand.
"""


def write_str(label, commit, runs, trace, issues, prs, today, python):
    names = python_runs()
    lines = [header(f'CSTACK-STR-{label}', 'software test report', label, commit, today)]
    failed = [r['suite'] for r in runs if r['exit']]
    total = [t for r in runs for t in r['totals']]
    lines.append('## 1. Summary\n')
    lines.append(f"- Conclusion: {'all suites passed' if not failed else 'FAILED: ' + ', '.join(failed)}.")
    lines.append(f"- Remaining deficiencies: {len(trace['gaps'])} requirement(s) without an automated test "
                 f"({', '.join(trace['gaps']) or 'none'}); skipped tests are listed below and are not verification.")
    lines.append('- Test-environment impact: one Linux workstation, not the GitHub runner; CI repeats `python links trace` and the secret scan on ubuntu-latest.\n')
    lines.append('## 2. Test log\n')
    lines.append('| Item | Value |\n|---|---|')
    lines.append(f'| Commit | `{commit}` |')
    lines.append(f'| Date | {today} |')
    lines.append(f"| Environment | {platform.system()} {platform.machine()}, Python {sh(python, '-c', 'import platform; print(platform.python_version())')}, Node {sh('node', '--version') if shutil.which('node') else 'absent'} |")
    lines.append('| Run by | Operator, local `bash ci/run-local.sh <suite>` per suite |\n')
    lines.append('## 3. Results\n')
    lines.append('| Suite | Exit | Seconds | Output SHA-256 | Detail |\n|---|---|---|---|---|')
    for r in runs:
        if r['suite'] == 'python':
            detail = '; '.join(f"{n}: {t['ran']} run, {t['skipped']} skipped, {t['status']}"
                               for n, t in zip(names, r['totals']))
        elif r['totals']:
            detail = '; '.join(f"{t['ran']} run, {t['skipped']} skipped, {t['status']}" for t in r['totals'])
        else:
            detail = '; '.join(r['tail']) or ('clean' if not r['exit'] else 'see output')
        lines.append(f"| {r['suite']} | {r['exit']} | {r['seconds']} | `{r['sha256'][:16]}` | {detail} |")
    lines.append('\nRequirement-level results: every requirement mapped in the [verification matrix](../verification-matrix.md) '
                 'to tests that ran in the `python` suite above passed when that suite exited 0. Skipped tests verify nothing.\n')
    lines.append('## 4. Problems and deviations\n')
    lines.append('| Item | Description | Disposition |\n|---|---|---|')
    skipped = sum(t['skipped'] for t in total)
    lines.append(f'| Skips | {skipped} skipped tests across all runs (optional SDKs or external clones absent) | Accepted; not counted as verified |')
    for f in failed:
        lines.append(f'| {f} | Suite exited nonzero | Open |')
    lines.append('')
    lines.append('## 5. Metrics\n')
    lines.append('| Measure | Value | Source |\n|---|---|---|')
    root = next((r['totals'][0] for r in runs if r['suite'] == 'python' and r['totals']), None)
    if root:
        lines.append(f"| Root tests run / skipped / failed+errors | {root['ran']} / {root['skipped']} / {root['failures'] + root['errors']} | `ci/run-local.sh python`, first run |")
    lines.append(f"| Tests run, all runs | {sum(t['ran'] for t in total)} | sum of `Ran N tests` lines |")
    lines.append(f"| Requirements total / with tests / listed gaps / TBD | {trace['requirements']} / {trace['requirements'] - len(trace['gaps'])} / {len(trace['gaps'])} / 0 | `tools/check_trace.py` |")
    lines.append(f"| Test files traced | {trace['traced_test_files']} / {trace['test_files']} | `tools/check_trace.py` |")
    if issues is not None:
        lines.append(f"| Issues open / closed | {sum(1 for i in issues if i['state'] == 'OPEN')} / {sum(1 for i in issues if i['state'] == 'CLOSED')} | `gh issue list --state all` |")
    else:
        lines.append('| Issues | not queried (`gh` unavailable) | - |')
    if prs is not None:
        reviewed = sum(1 for p in prs if p.get('reviews'))
        lines.append(f"| PRs merged / with recorded reviews | {len(prs)} / {reviewed} | `gh pr list --state merged --limit 1000` |")
    lines.append('| Static-analysis findings | No linter is configured; secret scans: gitleaks and TruffleHog exits above | `ci/run-local.sh gitleaks trufflehog` |')
    lines.append('| Coverage | Not measured; no coverage tool in `ci/requirements.txt` | - |')
    for ext, n in sorted(sloc().items()):
        lines.append(f'| Lines in tracked `{ext}` files (excluding vendored trees) | {n} | `git ls-files` |')
    lines.append('\n## 6. Rationale for decisions\n')
    lines.append('Skipped tests are accepted because each skip names a missing optional dependency (TypeScript MCP SDK, an EndoForge clone). They are not counted as verification.\n')
    out = ROOT / 'docs/verification/reports' / f'STR-{label}.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out


def write_vdd(label, commit, runs, issues, today):
    tags = sh('git', 'tag', '--sort=-creatordate').splitlines()
    prev = next((t for t in tags if t != label), None)
    rng = f'{prev}..{commit}' if prev else commit
    merges = sh('git', 'log', '--merges', '--format=%h %s', rng).splitlines()
    lines = [header(f'CSTACK-VDD-{label}', 'version description', label, commit, today).replace('../../plan', '../plan')]
    lines.append('## 1. Identification\n')
    lines.append('| Item | Value |\n|---|---|')
    lines.append('| Name | cstack (code name Mjölnir) |')
    lines.append(f"| Version / tag | {label if label in tags else label + ' (no tag; main at the commit below)'} |")
    lines.append(f'| Commit | `{commit}` |')
    lines.append(f"| Previous tag | {prev or 'none'} |")
    lines.append(f"| Commit date | {sh('git', 'log', '-1', '--format=%cs', commit)} |\n")
    lines.append('## 2. Contents\n')
    lines.append('The whole repository tree at the commit. Vendored components and their pins are listed in '
                 '[configuration management](../configuration/configuration-management.md) and `contracts/SOURCE-PINS.json`. '
                 'No packages or binaries are built or published.\n')
    lines.append('## 3. Build and install\n')
    lines.append('```sh\ngit clone https://github.com/Akilleez-QA/cstack.git && cd cstack\n'
                 f'git checkout {commit}\npython3 -m venv .venv && . .venv/bin/activate\n'
                 'pip install -r requirements.txt -r ci/requirements.txt\n'
                 'npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund\n'
                 'bash ci/run-local.sh python links trace\n```\n')
    lines.append('## 4. Integrity\n')
    lines.append('| Manifest | SHA-256 |\n|---|---|')
    for m in MANIFESTS:
        p = ROOT / m
        if p.is_file():
            lines.append(f'| `{m}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
    lines.append(f"| Tree object | `{sh('git', 'rev-parse', commit + '^{tree}')}` |\n")
    lines.append('## 5. Changes since previous tag\n')
    lines.append(f"{len(merges)} merge commits in `{rng}`{' (whole history; no earlier tag)' if not prev else ''}. "
                 'Latest ten:\n')
    lines += [f'- {m}' for m in merges[:10]]
    unreleased = changelog_unreleased()
    lines.append(f'\nCHANGELOG "Unreleased" section: {len(unreleased)} entries; see [CHANGELOG](../../CHANGELOG.md).\n')
    lines.append('## 6. Open problems and workarounds\n')
    open_issues = [i for i in (issues or []) if i['state'] == 'OPEN']
    if issues is None:
        lines.append('Not queried (`gh` unavailable).\n')
    elif not open_issues:
        lines.append('No open GitHub issues at generation time (`gh issue list --state open`).\n')
    else:
        lines.append('| Issue | Title |\n|---|---|')
        lines += [f"| #{i['number']} | {i['title']} |" for i in open_issues]
        lines.append('')
    lines.append('## 7. Documentation baseline\n')
    lines.append('| Document | Baseline commit in its header |\n|---|---|')
    for d in CONTROL:
        p = ROOT / d
        m = re.search(r'^\| Baseline commit \| (\S+) \|', p.read_text(encoding='utf-8'), re.M) if p.is_file() else None
        lines.append(f"| `{d}` | `{m.group(1) if m else 'missing'}` |")
    lines.append('\n## 8. Verification and scans\n')
    lines.append(f'Test report: [STR-{label}](../verification/reports/STR-{label}.md).\n')
    lines.append('| Scan | Exit |\n|---|---|')
    for r in runs:
        if r['suite'] in ('gitleaks', 'trufflehog', 'links', 'trace'):
            lines.append(f"| {r['suite']} | {r['exit']} |")
    out = ROOT / 'docs/releases' / f'VDD-{label}.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--label', required=True, help='a tag, or "baseline" for main at HEAD')
    ap.add_argument('--suites', nargs='*', default=list(SUITES))
    ap.add_argument('--python', default=sys.executable)
    a = ap.parse_args(argv)
    commit = sh('git', 'rev-parse', 'HEAD', check=True)
    today = datetime.date.today().isoformat()
    runs = [run_suite(s, a.python) for s in a.suites]
    trace = check_trace.check(ROOT)
    issues = gh_json('issue', 'list', '--state', 'all', '--limit', '1000', '--json', 'number,title,state')
    prs = gh_json('pr', 'list', '--state', 'merged', '--limit', '1000', '--json', 'number,reviews')
    for path in (write_str(a.label, commit, runs, trace, issues, prs, today, a.python),
                 write_vdd(a.label, commit, runs, issues, today)):
        print(path.relative_to(ROOT))
    print(json.dumps([{k: r[k] for k in ('suite', 'exit', 'seconds')} for r in runs]), file=sys.stderr)
    return 1 if any(r['exit'] for r in runs) else 0


if __name__ == '__main__':
    sys.exit(main())

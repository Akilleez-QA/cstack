"""One portable v0.11 aggregate: fresh checks from selected source alone.

Pinned embedded archives, not sibling trees or historical generated evidence,
supply the accepted v0.10 and claim-revision lab for clean replay.
"""
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.build_claim_ledger_release import verify, digest
from tools.claim_ledger_release_support import require, environment, unpack_base, check_lab_sources, BASE_MANIFEST_PIN
from tools.run_polynomial_witness_validation import prepare_legacy_transcript
from foundation_math_bridge.schemas import tool_definitions

ALLOWED_BASE_CHANGES = {
    'README.md', 'RELEASE-FILES.json', 'docs/PROVENANCE.md',
    'foundation_math/cli.py', 'foundation_math_bridge/__init__.py',
    'foundation_math_bridge/schemas.py', 'foundation_math_bridge/server.py',
    'tests/test_agent_bridge.py', 'tests/test_character_ring_integration.py',
    'tests/test_linear_algebra_bridge.py', 'tests/test_linear_systems_integration.py',
    'tests/test_split_bundle_integration.py', 'tests/test_portable_validation.py',
    'tools/audit_linear_systems_integration.py', 'tools/audit_polynomial_witness_integration.py',
    'tools/run_linear_algebra_validation.py', 'tools/validate_character_ring_schemas.py',
    'tools/validate_split_bundle_schemas.py',
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def preservation(root):
    require(digest(root / 'docs/BASE-V010-SOURCE-MANIFEST.json') == BASE_MANIFEST_PIN, 'base manifest pin')
    base = json.loads((root / 'docs/BASE-V010-SOURCE-MANIFEST.json').read_text())['files']
    changed = {name for name, pin in base.items() if digest(root / name) != pin}
    require(changed == ALLOWED_BASE_CHANGES, 'unexpected v0.10 changes: ' + str(sorted(changed)))
    prefixes = ('foundation_math/', 'bounded_counterexample/', 'exact_linalg/', 'exact_systems/',
                'polynomial_witness/', 'character_ring/', 'split_bundle/')
    runtime = [name for name in base if name.startswith(prefixes) and name != 'foundation_math/cli.py']
    require(all(digest(root / name) == base[name] for name in runtime), 'inherited arithmetic/runtime changed')
    original = json.loads((root / 'docs/BASE-V010-BRIDGE-TOOLS.json').read_text())['tools']
    require(len(original) == 14 and len(tool_definitions()) == 15 and tool_definitions()[:14] == original,
            'fourteen prior contracts changed')
    lab = check_lab_sources(root)
    return {'status': 'passed', 'v010_source_files_checked': len(base),
            'intentional_inherited_changes': sorted(changed),
            'inherited_math_runtime_files_unchanged': len(runtime),
            'original_fourteen_tool_definitions_unchanged': True,
            'runtime_verification_registry_unchanged': True, 'accepted_lab': lab}


def run_script(root, script, optimized=False, args=(), timeout=900):
    # Include the script directory to preserve ordinary Python script imports,
    # then the selected source root. -I ignores caller Python path customizations.
    code = ('import runpy,sys;from pathlib import Path;root=sys.argv[1];script=sys.argv[2];'
            'sys.path[:0]=[str(Path(root,script).parent),root];'
            'sys.argv=[root+"/"+script]+sys.argv[3:];runpy.run_path(sys.argv[0],run_name="__main__")')
    cmd = [sys.executable, '-I', '-B'] + (['-O'] if optimized else []) + ['-c', code, str(root), script, *args]
    p = subprocess.run(cmd, cwd=root, env=environment(), capture_output=True, text=True, timeout=timeout)
    require(p.returncode == 0, script + ' failed: ' + (p.stdout + p.stderr)[-7000:])
    return p


def run_tests(root, optimized):
    code = ('import runpy,sys;sys.path.insert(0,sys.argv[1]);'
            'sys.argv=["unittest","discover","-s","tests","-v"];runpy.run_module("unittest",run_name="__main__")')
    cmd = [sys.executable, '-I', '-B'] + (['-O'] if optimized else []) + ['-c', code, str(root)]
    p = subprocess.run(cmd, cwd=root, env=environment(), capture_output=True, text=True, timeout=600)
    require(p.returncode == 0, 'full tests failed: ' + (p.stdout + p.stderr)[-7000:])
    return p


def frozen_replays(evidence):
    with tempfile.TemporaryDirectory(prefix='fm-v011-frozen-') as td:
        base = Path(td) / 'base'
        unpack_base(ROOT, base)
        require(not (base / 'evidence').exists(), 'historical baseline evidence extracted')
        p = run_script(base, 'tools/run_split_bundle_validation.py', timeout=1800)
        baseline = json.loads(p.stdout)
        require(baseline['status'] == 'passed', 'frozen v0.10 aggregate failed')
        dump(evidence / 'v011-frozen-v010-replay.json', baseline)
    # Original independent review runner itself performs a manifest-only lab
    # extraction, author normal/-O aggregate and independent normal/-O BFS checks.
    p = run_script(ROOT, 'review/claim-revision-lab/reproduce_review.py',
                   args=(str(ROOT / 'vendor/claim-revision-lab.zip'),), timeout=900)
    lab = json.loads(p.stdout)
    require(lab['status'] == 'pass' and lab['manifest_only_extraction'], 'accepted lab clean replay failed')
    dump(evidence / 'v011-frozen-ledger-lab-replay.json', lab)
    return baseline, lab


def static_check(root):
    files = ('foundation_math/claim_ledger.py', 'foundation_math_bridge/claim_ledger_schemas.py', 'claim_revision/core.py')
    findings = []
    for name in files:
        for node in ast.walk(ast.parse((root / name).read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', '__import__', 'open'):
                findings.append(name + ': ' + node.func.id)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or '']
                for module in imports:
                    if module.split('.')[0] in ('socket', 'requests', 'urllib', 'http', 'subprocess', 'openai', 'os', 'pathlib'):
                        findings.append(name + ': ' + module)
    require(not findings, 'new runtime dynamic/network/file surface: ' + str(findings))
    return {'status': 'passed', 'files': list(files), 'findings': findings,
            'scope': 'Static surface check, not an OS sandbox or a formal proof. Adapter CLI reads bounded stdin and writes stdout.'}


def main():
    source = verify(ROOT)
    source_pin = digest(ROOT / 'SOURCE-MANIFEST.json')
    preserved = preservation(ROOT)
    evidence = ROOT / 'evidence'; evidence.mkdir(exist_ok=True)
    base, lab = frozen_replays(evidence)
    prepare_legacy_transcript(ROOT, environment())
    checks, counts = [], []
    schema = importlib.util.find_spec('jsonschema') is not None
    for optimized, mode in ((False, 'normal'), (True, 'optimized')):
        p = run_tests(ROOT, optimized)
        text = (p.stdout + p.stderr).replace(str(ROOT), '<source-root>')
        (evidence / f'v011-tests-{mode}.txt').write_text(text)
        count = re.search(r'Ran (\d+) tests', text); skipped = re.search(r'OK \(skipped=(\d+)\)', text)
        require(count is not None, 'missing full test count')
        counts.append({'optimization': int(optimized), 'run': int(count[1]), 'skipped': int(skipped[1]) if skipped else 0})
        jobs = [('fourteen-tool-differential', 'tools/audit_v010_tool_differential.py', ()),
                ('systems-lab-mutations', 'tools/audit_systems_lab.py', ()),
                ('systems-integration', 'tools/audit_linear_systems_integration.py', ()),
                ('witness-lab', 'tools/audit_polynomial_witness_lab.py', ('--output', f'evidence/v011-witness-lab-{mode}.json')),
                ('witness-integration', 'tools/audit_polynomial_witness_integration.py', ()),
                ('legacy-bridge', 'tools/audit_agent_bridge.py', ()),
                ('matrix-integration', 'tools/run_linear_algebra_validation.py', ())]
        if schema:
            jobs += [(name, script, ()) for name, script in (
                ('split-bundle-schemas', 'tools/validate_split_bundle_schemas.py'),
                ('character-schemas', 'tools/validate_character_ring_schemas.py'),
                ('system-schemas', 'tools/validate_linear_systems_schemas.py'),
                ('witness-schemas', 'tools/validate_polynomial_witness_schemas.py'),
                ('matrix-schemas', 'tools/validate_matrix_bridge_schemas.py'),
                ('legacy-schemas', 'tools/validate_bridge_schemas.py'))]
        for name, script, args in jobs:
            p = run_script(ROOT, script, optimized, args)
            path = evidence / f'v011-{name}-{mode}.txt'
            path.write_text((p.stdout + p.stderr).replace(str(ROOT), '<source-root>'))
            checks.append({'name': name, 'optimization': int(optimized), 'exit_code': 0, 'evidence': str(path.relative_to(ROOT))})
        require((ROOT / 'review/v011_review.py').is_file(), 'independent integration review is required')
        p = run_script(ROOT, 'review/v011_review.py', optimized)
        review = json.loads(p.stdout)
        require(review['status'] in ('PASS', 'pass', 'passed'), 'independent integration review failed')
        dump(evidence / f'v011-independent-review-{mode}.json', review)
        checks.append({'name': 'independent-integration-review', 'optimization': int(optimized), 'exit_code': 0})
    require(verify(ROOT) == source and digest(ROOT / 'SOURCE-MANIFEST.json') == source_pin, 'source changed during aggregate')
    static = static_check(ROOT)
    dump(evidence / 'v011-source-preservation.json', preserved)
    dump(evidence / 'v011-static-check.json', static)
    findings, scanned = [], 0
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.md', '.json', '.jsonl', '.txt') and '__pycache__' not in path.parts and path.name != 'v011-validation.json':
            scanned += 1
            for marker in ('/workspace/', '/home/', 'file://', 'codex://', 'ghp_', 'sk-proj-', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY'):
                if marker in path.read_text():
                    findings.append({'file': str(path.relative_to(ROOT)), 'marker': marker})
    require(not findings, 'privacy/portability scan failed: ' + str(findings))
    from shutil import which
    result = {'status': 'passed', 'version': '0.11.0-dev', 'source_manifest_sha256': source_pin,
              'source_files_checked': len(source['files']), 'tests': counts, 'checks': checks,
              'source_preservation': preserved, 'frozen_v010_aggregate_status': base['status'],
              'frozen_lab_author_status': lab['fresh_results']['author_aggregate']['status'],
              'frozen_lab_independent_counts_per_mode': lab['fresh_results']['independent_normal']['counts'],
              'frozen_lab_author_source_mutants': lab['fresh_results']['author_aggregate']['mutations']['source_mutants'],
              'frozen_lab_independent_source_mutants': len(lab['fresh_results']['independent_normal']['mutations']),
              'optional_schema_validation': 'passed_using_preinstalled_jsonschema' if schema else 'unavailable_no_install_attempted',
              'lean': 'unavailable_explicit_test_skip' if which('lean') is None else 'available_see_test_evidence',
              'historical_generated_evidence_required': False, 'sibling_dependencies': False,
              'source_unchanged_during_validation': True, 'privacy_scan_files': scanned, 'privacy_scan_passed': True,
              'scope': 'Bounded exact-revision dependency applicability only. Authored status and refutation reports are unverified. No theorem truth, proof acceptance, artifact authentication or runtime-goal promotion.'}
    dump(evidence / 'v011-validation.json', result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

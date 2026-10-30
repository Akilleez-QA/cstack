"""Reproduce v0.7 local validation, preservation, transcript and privacy gates.

Standard-library runtime/test suite. Optional schema tools use jsonschema only
when already installed; absence is reported, never repaired by installation.
"""
from __future__ import annotations
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math_bridge.schemas import tool_definitions

ALLOWED_INHERITED_CHANGES = {
    'README.md', 'docs/PROVENANCE.md', 'foundation_math/cli.py',
    'foundation_math_bridge/__init__.py', 'foundation_math_bridge/schemas.py',
    'foundation_math_bridge/server.py', 'tests/test_agent_bridge.py',
    'tests/test_linear_algebra_bridge.py', 'tools/run_linear_algebra_validation.py',
    'tools/validate_matrix_bridge_schemas.py', 'SOURCE-MANIFEST.json',
}
BASE_MANIFEST_HASH = 'e11e09b92c66687bf5bab2b88927ee5205e50beb1832a9a555af789e6f63e54f'
LAB_MANIFEST_HASH = '273b8c1847daf7930b3f04325791b9bac19963018e51d83972b3c633597ab45f'
V07_MANIFEST_HASH = '93892d475dd1cad0e1e5637a6fe682ee65af0846bfa0015650d088e68e5e30f3'
PORTABLE_CHANGED_FILES = {'tools/run_polynomial_witness_validation.py',
                          'docs/POLYNOMIAL-WITNESS-VALIDATION.md'}

def require(condition, label):
    if not condition:
        raise RuntimeError(label)

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def prepare_legacy_transcript(root, environment):
    """Generate the schema fixture from shipped requests, never old evidence."""
    process = subprocess.run([sys.executable, '-B', 'tools/run_bridge_validation.py'],
                             cwd=root, env=environment, capture_output=True, text=True, timeout=30)
    require(process.returncode == 0 and not process.stderr, 'legacy transcript generation failed')
    transcript = json.loads(process.stdout)
    require(transcript.get('status') == 'passed', 'legacy transcript did not pass')
    evidence = root / 'evidence'
    evidence.mkdir(exist_ok=True)
    write_json(evidence / 'bridge-transcript-validation.json', transcript)


def verify_inherited_sources(root, frozen_inventory):
    """Check every inherited source; historical generated evidence is unshipped."""
    excluded = sorted(name for name in frozen_inventory if name.startswith('evidence/'))
    baseline = {name: value for name, value in frozen_inventory.items() if name not in excluded}
    changed, retained = [], []
    for name, expected_hash in baseline.items():
        if name == 'SOURCE-MANIFEST.json':
            changed.append(name)  # A derivative manifest is intentionally distinct.
            continue
        if digest(root / name) != expected_hash:
            require(name in ALLOWED_INHERITED_CHANGES, 'unexpected inherited change: ' + name)
            changed.append(name)
        else:
            retained.append(name)
    return baseline, changed, retained, excluded


def main():
    EVIDENCE.mkdir(exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    prepare_legacy_transcript(ROOT, environment)
    checks, test_counts = [], []
    optional_schema = importlib.util.find_spec('jsonschema') is not None
    for optimized, mode in ((False, 'normal'), (True, 'optimized')):
        prefix = [sys.executable, '-B'] + (['-O'] if optimized else [])
        jobs = [
            ('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], 'txt'),
            ('witness-lab-audit', ['tools/audit_polynomial_witness_lab.py', '--output', f'evidence/v07-witness-lab-audit-{mode}.json'], 'txt'),
            ('integration-audit', ['tools/audit_polynomial_witness_integration.py'], 'json'),
            ('legacy-bridge-audit', ['tools/audit_agent_bridge.py'], 'json'),
            ('matrix-validation', ['tools/run_linear_algebra_validation.py'], 'json'),
        ]
        if optional_schema:
            jobs += [(name, [script], 'json') for name, script in [
                ('witness-schema', 'tools/validate_polynomial_witness_schemas.py'),
                ('matrix-schema', 'tools/validate_matrix_bridge_schemas.py'),
                ('legacy-schema', 'tools/validate_bridge_schemas.py')]]
        for name, tail, suffix in jobs:
            process = subprocess.run(prefix + tail, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120)
            log = EVIDENCE / f'v07-{name}-{mode}.{suffix}'
            output = process.stdout + process.stderr
            # Failed checks must never publish local machine paths in evidence.
            output = output.replace(str(ROOT), '<source-root>')
            log.write_text(output)
            require(process.returncode == 0, f'{name} {mode} failed; see {log.name}')
            checks.append({'check': name, 'optimization': int(optimized), 'exit_code': process.returncode,
                           'evidence': str(log.relative_to(ROOT))})
            if name == 'tests':
                match = re.search(r'Ran (\d+) tests', output)
                skipped = re.search(r'OK \(skipped=(\d+)\)', output)
                require(match is not None, 'missing test count')
                test_counts.append({'optimization': int(optimized), 'run': int(match[1]),
                                    'skipped': int(skipped[1]) if skipped else 0})
    # Replay each of the frozen lab's 17 JSON examples through its unchanged CLI.
    lab_reference = json.loads((ROOT / 'docs/POLYNOMIAL-WITNESS-LAB-FROZEN-FILES.json').read_text())['files']
    example_replays = []
    for relative in sorted(name for name in lab_reference if name.startswith('examples/') and name.endswith('.json')):
        path = ROOT / 'examples/polynomial-witness' / Path(relative).name
        verifying = path.name == 'valid-witness.json'
        process = subprocess.run([sys.executable, '-B', '-m', 'polynomial_witness'] + (['verify'] if verifying else []),
                                 input=path.read_bytes(), cwd=ROOT, env=environment, capture_output=True, timeout=10)
        response = json.loads(process.stdout)
        expected_status = 'error' if path.name.startswith('rejected-') else 'accepted' if verifying else 'success'
        expected_exit = 2 if expected_status == 'error' else 0
        require(process.returncode == expected_exit and response['status'] == expected_status,
                'standalone example replay failed: ' + path.name)
        example_replays.append({'example': path.name, 'status': response['status'], 'exit_code': process.returncode})
    require(len(example_replays) == 17, 'unexpected standalone example inventory')
    write_json(EVIDENCE / 'v07-standalone-example-replays.json', {'status': 'passed', 'examples': example_replays})
    sharp = subprocess.run([sys.executable, '-B', '-m', 'foundation_math', 'polynomial-witness',
                            'examples/polynomial-witness/sharp-40-trials.json'], cwd=ROOT, env=environment,
                           capture_output=True, text=True, timeout=10)
    sharp_result = json.loads(sharp.stdout)
    require(sharp.returncode == 0 and sharp_result['status'] == 'success'
            and sharp_result['construction_bound']['actual_substitution_trials'] == 40
            and sharp_result['construction_bound']['substitution_trial_bound'] == 40,
            'sharp 40-trial CLI example failed')
    write_json(EVIDENCE / 'v07-sharp-40-trials.json', sharp_result)
    wire = (ROOT / 'examples/polynomial-witness/session-requests.jsonl').read_bytes()
    transcripts = []
    for optimized in (False, True):
        prefix = [sys.executable, '-B'] + (['-O'] if optimized else [])
        process = subprocess.run(prefix + ['-m', 'foundation_math_bridge'], input=wire, cwd=ROOT,
                                 env=environment, capture_output=True, timeout=30)
        require(process.returncode == 0 and not process.stderr, 'example bridge transcript failed')
        transcripts.append(process.stdout)
    require(transcripts[0] == transcripts[1], 'example normal/optimized transcripts differ')
    responses = [json.loads(line) for line in transcripts[0].splitlines()]
    expected = ['polynomial_counterexample_constructed', 'polynomial_coefficient_identity',
                'polynomial_witness_valid', 'polynomial_witness_rejected', 'tool_error']
    require([r['result']['structuredContent']['assessment'] for r in responses[2:]] == expected,
            'unexpected example assessment branches')
    write_json(EVIDENCE / 'v07-example-transcript.json', {'status': 'passed', 'responses': responses,
        'normal_optimized_identical': True, 'request_sha256': sha256(wire).hexdigest(),
        'response_sha256': sha256(transcripts[0]).hexdigest()})
    require(digest(ROOT / 'docs/BASE-V06-SOURCE-MANIFEST.json') == BASE_MANIFEST_HASH, 'v0.6 reference manifest changed')
    require(digest(ROOT / 'docs/POLYNOMIAL-WITNESS-LAB-SOURCE-MANIFEST.json') == LAB_MANIFEST_HASH, 'lab reference manifest changed')
    frozen_inventory = json.loads((ROOT / 'docs/BASE-V06-FROZEN-FILES.json').read_text())['files']
    baseline, changed, retained, historical_evidence = verify_inherited_sources(ROOT, frozen_inventory)
    require(digest(ROOT / 'docs/BASE-V07-SOURCE-MANIFEST.json') == V07_MANIFEST_HASH,
            'original v0.7 reference manifest changed')
    v07_source = json.loads((ROOT / 'docs/BASE-V07-SOURCE-MANIFEST.json').read_text())['files']
    portable_changes = sorted(name for name, value in v07_source.items() if digest(ROOT / name) != value)
    require(set(portable_changes) == PORTABLE_CHANGED_FILES, 'unexpected portable-release source changes')
    lab = json.loads((ROOT / 'docs/POLYNOMIAL-WITNESS-LAB-FROZEN-FILES.json').read_text())['files']
    lab_runtime = [name for name in lab if name.startswith('polynomial_witness/')]
    require(len(lab_runtime) == 9, 'unexpected standalone lab runtime inventory')
    for name in lab_runtime:
        require(digest(ROOT / name) == lab[name], 'frozen witness runtime changed: ' + name)
    inherited = json.loads((ROOT / 'docs/BASE-V06-BRIDGE-TOOLS.json').read_text())['tools']
    definitions = tool_definitions()
    require(len(definitions) == 8 and definitions[:6] == inherited, 'six original tool contracts changed')
    runtime_prefixes = ('foundation_math/', 'bounded_counterexample/', 'exact_linalg/')
    pinned_backends = [name for name in baseline if name.startswith(runtime_prefixes) and name != 'foundation_math/cli.py']
    for name in pinned_backends:
        require(digest(ROOT / name) == baseline[name], 'original runtime/backend changed: ' + name)
    source_hash_checks = 0
    report_paths = [EVIDENCE / f'v07-witness-lab-audit-{mode}.json' for mode in ('normal', 'optimized')]
    report_paths += [ROOT / item['evidence'] for item in checks if item['evidence'].endswith('.json')]
    for report_path in report_paths:
        report_data = json.loads(report_path.read_text())
        for name, expected_hash in report_data.get('source_sha256', {}).items():
            require(digest(ROOT / name) == expected_hash, 'stale evidence source hash: ' + report_path.name + ': ' + name)
            source_hash_checks += 1
    # Review all generated user-facing docs/evidence for nonportable private paths;
    # generic /tmp examples and rejection-test strings are not private history.
    reviewed = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                and (p.suffix in ('.md', '.json', '.jsonl', '.txt'))]
    findings = []
    for path in reviewed:
        text = path.read_text()
        for marker in ('/workspace/', '/home/', 'file://', 'codex://', 'ghp_', 'sk-proj-', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY'):
            if marker in text:
                findings.append({'file': str(path.relative_to(ROOT)), 'marker': marker})
    require(not findings, 'privacy/portability scan failed: ' + str(findings))
    preservation = {'status': 'passed', 'inherited_files': len(baseline), 'unchanged_inherited_files': len(retained),
                    'historical_generated_evidence_not_shipped_or_checked': historical_evidence,
                    'original_v07_source_files_checked': len(v07_source),
                    'original_v07_source_changes': portable_changes,
                    'intentional_changes': changed, 'original_math_runtime_files_unchanged': len(pinned_backends),
                    'witness_lab_runtime_files_unchanged': len(lab_runtime), 'original_six_tool_definitions_unchanged': True,
                    'scope': 'Shipped source checks against frozen inventories; historical generated evidence is excluded, not claimed checked. Original external source trees are checked separately by the coordinator.'}
    write_json(EVIDENCE / 'v07-source-preservation.json', preservation)
    write_json(EVIDENCE / 'v07-privacy-check.json', {'status': 'passed', 'files_checked': len(reviewed), 'findings': findings,
               'scope': 'Portable documents and evidence scan; synthetic rejection strings and generic temporary-path examples are not personal data.'})
    files = {str(p.relative_to(ROOT)): digest(p) for p in sorted(ROOT.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts and 'evidence' not in p.relative_to(ROOT).parts
             and p.name != 'SOURCE-MANIFEST.json'}
    write_json(ROOT / 'SOURCE-MANIFEST.json', {'version': '0.7.0-dev', 'base_manifest_sha256': BASE_MANIFEST_HASH,
               'derived_from_v07_manifest_sha256': V07_MANIFEST_HASH,
               'release_variant': 'portable-validation',
               'polynomial_witness_lab_manifest_sha256': LAB_MANIFEST_HASH, 'files': files,
               'scope': 'Source, documentation, schemas and synthetic examples; generated evidence excluded to avoid self-reference.'})
    independent = json.loads((EVIDENCE / 'v07-integration-audit-normal.json').read_text())
    report = {'status': 'passed', 'tests': test_counts, 'checks': checks,
              'independent_integration_checks': independent['total_checks'],
              'independent_integration_requests': independent['synthetic_requests'],
              'total_degree_bound_audit': independent.get('total_degree_bound_audit'),
              'witness_lab_semantic_cases_per_mode': 300, 'standalone_example_replays': len(example_replays), 'original_six_tool_definitions_unchanged': True,
              'witness_lab_runtime_files_unchanged': len(lab_runtime), 'math_runtime_files_unchanged': len(pinned_backends),
              'example_transcript_normal_optimized_identical': True, 'privacy_scan_passed': True,
              'evidence_source_hashes_checked': source_hash_checks,
              'optional_schema_validation': 'passed_using_preinstalled_jsonschema' if optional_schema else 'unavailable_no_install_attempted',
              'source_manifest_sha256': digest(ROOT / 'SOURCE-MANIFEST.json'),
              'release_variant': 'portable-validation',
              'derived_from_v07_manifest_sha256': V07_MANIFEST_HASH,
              'scope': 'Local synthetic integration checks, not formal proof or runtime goal acceptance.'}
    write_json(EVIDENCE / 'v07-validation.json', report)
    print(json.dumps(report, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

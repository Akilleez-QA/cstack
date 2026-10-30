"""One portable packaging-only v0.12 aggregate, including fresh historical replay."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from baseline_snapshot import snapshot as s
from tools.build_snapshot_release import verify, digest, create_zip
from tools.snapshot_release_support import environment, preservation, require, restored_baseline, BASE_ZIP_PIN
from tools.run_polynomial_witness_validation import prepare_legacy_transcript


def run(root, script, optimized=False, args=(), timeout=1800):
    code = ('import runpy,sys;from pathlib import Path;root=sys.argv[1];script=sys.argv[2];'
            'sys.path[:0]=[str(Path(root,script).parent),root];'
            'sys.argv=[root+"/"+script]+sys.argv[3:];runpy.run_path(sys.argv[0],run_name="__main__")')
    p = subprocess.run([sys.executable, '-I', '-B'] + (['-O'] if optimized else []) +
                       ['-c', code, str(root), script, *map(str, args)], cwd=root,
                       env=environment(), capture_output=True, text=True, timeout=timeout)
    require(p.returncode == 0, script + ' failed: ' + (p.stdout + p.stderr)[-9000:])
    return p


def tests(root, mode, directory):
    code = ('import sys,unittest;sys.path[:0]=[sys.argv[1]+"/baseline_snapshot",sys.argv[1]];'
            'suite=unittest.defaultTestLoader.discover(sys.argv[2]);'
            'result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())')
    p = subprocess.run([sys.executable, '-I', '-B'] + (['-O'] if mode else []) +
                       ['-c', code, str(root), directory], cwd=root, env=environment(),
                       capture_output=True, text=True, timeout=600)
    require(p.returncode == 0, directory + ' failed: ' + (p.stdout + p.stderr)[-9000:])
    text = (p.stdout + p.stderr).replace(str(root), '<source-root>')
    count = re.search(r'Ran (\d+) tests', text)
    skipped = re.search(r'OK \(skipped=(\d+)\)', text)
    require(count is not None, 'test count missing')
    return {'optimization': int(mode), 'run': int(count[1]), 'skipped': int(skipped[1]) if skipped else 0}, text


def privacy(root, manifest):
    # Recurse through historical archives as well as current selected text. Match
    # selected documentation/data, not adversarial source-code strings.
    import io
    import zipfile
    markers = ('/workspace/', '/home/', 'file://', 'codex://', 'ghp_', 'sk-proj-', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY')
    findings, counts = [], {'text_files': 0, 'archive_files': 0}
    def scan(name, raw, depth=0):
        require(depth <= 8, 'nested archive depth')
        if name.endswith('.zip'):
            counts['archive_files'] += 1
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                require(len(z.infolist()) <= 4096, 'archive inventory cap')
                require(sum(i.file_size for i in z.infolist()) <= 64*1024*1024, 'archive uncompressed cap')
                for info in z.infolist():
                    if not info.is_dir():
                        scan(name + '!' + info.filename, z.read(info), depth+1)
        elif name.endswith(('.md', '.json', '.jsonl', '.txt')):
            counts['text_files'] += 1
            text = raw.decode('utf-8')
            for marker in markers:
                if marker in text:
                    findings.append({'file': name, 'marker': marker})
    for name in sorted([*manifest['files'], 'SOURCE-MANIFEST.json']):
        scan(name, (root / name).read_bytes())
    require(not findings, 'privacy/portability findings: ' + str(findings))
    return {'status': 'passed', **counts, 'findings': findings,
            'scope': 'Bounded selected textual-source and nested-history scan; no universal secret-detection claim.'}


def validate(root=ROOT):
    source = verify(root)
    source_pin = digest(root / 'SOURCE-MANIFEST.json')
    preserved = preservation(root)
    evidence = root / 'evidence'; evidence.mkdir(exist_ok=True)
    # Only named donors and snapshot files enter restoration. The original full
    # archive and sibling checkouts are never inputs to this release gate.
    with restored_baseline(root) as (base, archive, restoration):
        require(digest(archive) == BASE_ZIP_PIN, 'restored original ZIP pin')
        p = run(base, 'tools/build_claim_ledger_release.py', args=('--output', archive.parent / 'unchanged-builder.zip'))
        require((archive.parent / 'unchanged-builder.zip').read_bytes() == archive.read_bytes(), 'historical serializer mismatch')
        historical = json.loads(run(base, 'tools/run_claim_ledger_validation.py', bool(sys.flags.optimize)).stdout)
        require(historical['status'] == 'passed', 'fresh historical aggregate status')
        (evidence / 'v012-fresh-v011.json').write_bytes(s.canonical(historical))
        baseline = s.source_manifest((base / 'SOURCE-MANIFEST.json').read_bytes(), restoration['source_manifest_sha256'])
        require(all(digest(base / n) == pin for n, pin in baseline.items()), 'historical selected bytes changed during aggregate')
    prepare_legacy_transcript(root, environment())
    current_tests, packaging_tests, reviews = [], [], []
    for optimized, mode in ((False, 'normal'), (True, 'optimized')):
        for directory, counts in (('tests', current_tests), ('packaging_tests', packaging_tests)):
            count, log = tests(root, optimized, directory)
            counts.append(count)
            (evidence / ('v012-' + directory + '-' + mode + '.log')).write_text(log)
        review = json.loads(run(root, 'review/v012_review.py', optimized, timeout=600).stdout)
        require(review['status'] in ('PASS', 'pass', 'passed'), 'independent integration review failed')
        reviews.append(review)
        (evidence / ('v012-review-' + mode + '.json')).write_bytes(s.canonical(review))
    require(reviews[0] == reviews[1], 'independent normal/-O results differ')
    require(verify(root) == source and digest(root / 'SOURCE-MANIFEST.json') == source_pin, 'source changed during aggregate')
    result = {'status': 'passed', 'version': '0.12.0-dev', 'source_manifest_sha256': source_pin,
              'source_files_checked': len(source['files']), 'current_runtime_tests': current_tests,
              'packaging_tests': packaging_tests, 'source_preservation': preserved,
              'restoration': restoration, 'fresh_frozen_v011_aggregate_status': historical['status'],
              'fresh_frozen_v011_tests': historical['tests'],
              'historical_full_aggregate_unchanged': True, 'unchanged_historical_builder_zip_identical': True,
              'original_v011_zip_input_required': False, 'sibling_checkout_required': False,
              'generated_historical_evidence_required': False, 'independent_integration_review': reviews[0],
              'privacy': privacy(root, source), 'lean': historical['lean'],
              'python': sys.version.split()[0], 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION,
              'scope': 'Packaging integrity only; no authentication, theorem truth, proof acceptance, runtime promotion, sandbox or concurrent no-clobber claim.'}
    (evidence / 'v012-validation.json').write_bytes(s.canonical(result))
    return result


def main():
    print(s.canonical(validate()).decode(), end='')


if __name__ == '__main__':
    main()

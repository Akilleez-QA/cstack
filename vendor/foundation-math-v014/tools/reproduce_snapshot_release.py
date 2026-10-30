"""Selected-only normal/-O delivery gate and measured snapshot/full-ZIP comparison."""
import argparse
from pathlib import Path
import json
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from baseline_snapshot import snapshot as s
from tools.build_snapshot_release import create_zip, verify, digest
from tools.snapshot_release_support import require, restored_baseline, BASE_ZIP_BYTES
from tools.run_snapshot_validation import run


def measure(root, work):
    """Actual current selected bytes, same fixed serializer; no synthetic fixture."""
    manifest = verify(root)
    all_files = {name: (root / name).read_bytes() for name in [*manifest['files'], 'SOURCE-MANIFEST.json']}
    snapshot = {name: data for name, data in all_files.items() if name.startswith('snapshots/v011/')}
    common = {name: data for name, data in all_files.items() if name not in snapshot}
    # Comparison assemblies intentionally retain the SAME manifest, selection,
    # code and docs. They are not alternative valid releases. Only the historical
    # payload representation changes, isolating storage overhead without a hash
    # cycle through this generated receipt or rewriting selection metadata.
    with restored_baseline(root) as (_, archive, _):
        full = {**common, 'vendor/foundation-math-v011-source.zip': archive.read_bytes()}
    results = {}
    for label, files in [('common-payload', common), ('actual-snapshot-release', all_files),
                         ('counterfactual-full-baseline', full), ('snapshot-only', snapshot)]:
        hashed, size = s.create_zip(work / (label + '.zip'), files)
        results[label] = {'bytes': size, 'sha256': hashed}
    actual = results['actual-snapshot-release']['bytes']
    common_bytes = results['common-payload']['bytes']
    full_bytes = results['counterfactual-full-baseline']['bytes']
    require(actual < full_bytes, 'no actual packaging saving')
    return {'status': 'passed', 'archives': results,
            'snapshot_incremental_outer_zip_bytes': actual-common_bytes,
            'full_baseline_incremental_outer_zip_bytes': full_bytes-common_bytes,
            'outer_zip_bytes_saved': full_bytes-actual,
            'snapshot_raw_bytes': sum(map(len, snapshot.values())),
            'original_v011_archive_bytes': BASE_ZIP_BYTES,
            'actual_v012_total_growth_over_v011_bytes': actual-BASE_ZIP_BYTES,
            'counterfactual_total_growth_over_v011_bytes': full_bytes-BASE_ZIP_BYTES,
            'measurement_basis': 'Actual final v0.12 selected bytes. Same serializer and all non-snapshot members held fixed, including release metadata. Counterfactual assemblies are measurement-only, not valid releases.',
            'synthetic_fixture_measurement_reused': False, 'future_growth_claim': False, 'timing_claim': False}


def reproduce(root=ROOT):
    source = verify(root); before = digest(root / 'SOURCE-MANIFEST.json')
    with tempfile.TemporaryDirectory(prefix='fm-v012-delivery-') as td:
        temp = Path(td)
        a, b = temp / 'one.zip', temp / 'two.zip'
        receipt = create_zip(a, root); create_zip(b, root)
        require(a.read_bytes() == b.read_bytes(), 'deterministic build differs')
        clean = temp / 'selected-only'; clean.mkdir()
        with zipfile.ZipFile(a) as z:
            require(z.namelist() == sorted([*source['files'], 'SOURCE-MANIFEST.json']), 'selected archive exact inventory')
            for info in z.infolist():
                require(info.date_time == (2026, 1, 1, 0, 0, 0) and info.create_system == 3 and
                        info.external_attr == 0o100644 << 16 and info.compress_type == zipfile.ZIP_DEFLATED,
                        'ZIP serializer metadata changed')
                s.name(info.filename)
                target = clean / info.filename; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(info))
        require(not (clean / 'evidence').exists(), 'historical generated evidence shipped')
        require(not (clean / 'vendor/foundation-math-v011-source.zip').exists(), 'full original ZIP shipped')
        require(verify(clean) == source, 'delivery source verification failed')
        # Each entry mode rebuilds and runs the exact historical aggregate fresh,
        # current runtime normal/-O, packaging normal/-O and independent review.
        normal = json.loads(run(clean, 'tools/run_snapshot_validation.py', timeout=2400).stdout)
        optimized = json.loads(run(clean, 'tools/run_snapshot_validation.py', True, timeout=2400).stdout)
        require(normal == optimized, 'delivery aggregate normal/-O mismatch')
        require(verify(clean) == source, 'selected-only sources changed')
        rebuilt = temp / 'rebuilt.zip'; create_zip(rebuilt, clean)
        require(a.read_bytes() == rebuilt.read_bytes(), 'selected-only ZIP rebuild differs')
        measurements = measure(clean, temp)
        require(measurements['archives']['actual-snapshot-release']['sha256'] == receipt['sha256'], 'measurement not actual release bytes')
        fault = clean / 'baseline_snapshot/snapshot.py'; raw = fault.read_bytes()
        fault.write_bytes(raw + b'\n# drift control\n')
        rejected = False
        try:
            verify(clean)
        except (RuntimeError, s.SnapshotError):
            rejected = True
        finally:
            fault.write_bytes(raw)
        require(rejected, 'source drift accepted'); verify(clean)
    require(verify(root) == source and digest(root / 'SOURCE-MANIFEST.json') == before, 'source changed during delivery gate')
    return {'status': 'PASS', 'archive': receipt, 'manifest_only_delivery': True,
            'normal_optimized_aggregate_identical': True, 'selected_only_zip_rebuild_identical': True,
            'original_v011_zip_input_required': False, 'sibling_checkout_required': False,
            'generated_outer_evidence_shipped': False, 'source_drift_rejected': True,
            'byte_measurements': measurements, 'aggregate': normal,
            'scope': 'Packaging integrity only; no authenticity, proof, truth, runtime promotion or long-chain growth claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = reproduce()
    if args.output:
        args.output.write_bytes(s.canonical(result))
    print(s.canonical(result).decode(), end='')


if __name__ == '__main__':
    main()

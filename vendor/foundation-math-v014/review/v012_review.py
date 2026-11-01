"""Independent v0.12 packaging integration checks, portable and optimization-safe.

Run from a selected delivery, or supply --root for a separate read-only candidate.
Only temporary copies are mutated. No full historical aggregate is repeated here:
the current aggregate owns that gate. Hashes establish integrity, not authenticity.
"""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256, shake_256
from pathlib import Path
from unittest.mock import patch
import argparse
import ast
import io
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
import zlib

sys.dont_write_bytecode = True
BASE_MANIFEST = '438bc999e2a3577a4c8525a5b990a7346bd4d0dd9f1b400d596661d7a465e6a4'
BASE_ARCHIVE = '530d9794c083801d6d0acb6273980bdf1d4d7d59aeeb500945d0d5a11a31f741'
LAB_MANIFEST = '55991f10d519cdcc1e10389f60d178bc12fa82174615a390f059047a34350a1b'
LAB_ARCHIVE = 'afe15b921ac5049604d9e6255e4acf4e3f2a76eac1d30a4b694be1e078737d4b'
RECIPE = '0d8a5780fbad9df5811021c3b658f57a2aa696779d4a1d256612cb821bf22ef6'
BASE_BYTES = 5524169
MANIFEST = 'SOURCE-MANIFEST.json'
LIMITS = {'file_bytes': 8388608, 'manifest_bytes': 1048576, 'recipe_bytes': 2097152,
          'source_files': 2048, 'input_reads': 8192, 'input_bytes': 67108864,
          'output_files': 4096, 'output_bytes': 67108864, 'snapshot_bytes': 33554432,
          'path_bytes': 240, 'path_depth': 16}
COUNTS = Counter()
CONTROLS = []


class ReviewFailure(Exception):
    pass


def need(ok, label):
    COUNTS['explicit_checks'] += 1
    if not ok:
        raise ReviewFailure(label)


def H(raw):
    return sha256(raw).hexdigest()


def C(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()


def strict(raw):
    def pairs(values):
        obj = {}
        for k, v in values:
            if k in obj:
                raise ReviewFailure('duplicate JSON key')
            obj[k] = v
        return obj
    def floating(v):
        x = float(v)
        if not math.isfinite(x):
            raise ReviewFailure('nonfinite float')
        return x
    def constant(v):
        raise ReviewFailure('nonfinite constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=floating, parse_constant=constant)


def archive(files):
    """Reviewer serializer: no calls to a release or snapshot builder."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, raw, compresslevel=9)
    return stream.getvalue()


def populate(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


@contextmanager
def replace(path, raw):
    old = path.read_bytes()
    path.write_bytes(raw)
    try:
        yield
    finally:
        path.write_bytes(old)


def rejection(label, fn, outputs=None):
    try:
        fn()
    except (RuntimeError, ValueError, OSError, s.SnapshotError, ReviewFailure):
        CONTROLS.append(label)
    else:
        raise ReviewFailure('control unexpectedly accepted: ' + label)
    if outputs is not None:
        need(list(outputs.iterdir()) == [], 'failure leaked output/stage: ' + label)


def manifest(files):
    return C({'files': {n: H(v) for n, v in sorted(files.items())}})


def source_checks(root):
    raw = (root / MANIFEST).read_bytes()
    current = strict(raw)
    selection_raw = (root / 'RELEASE-FILES.json').read_bytes()
    selection = strict(selection_raw)
    need(C(current) == raw and C(selection) == selection_raw, 'canonical release inputs')
    need(selection['schema'] == 'foundation-math-v012-selected-files-v1', 'selection schema')
    names = selection['files']
    need(names == sorted(set(names)) and names == list(current['files']), 'selection/manifest exact inventory')
    need(MANIFEST not in names, 'manifest does not select itself')
    files = {}
    for name in names + [MANIFEST]:
        parts = Path(name).parts
        need(not Path(name).is_absolute() and '..' not in parts and '.' not in parts, 'safe selected path')
        path = root / name
        for i in range(1, len(parts)):
            need(not (root / Path(*parts[:i])).is_symlink(), 'selected parent is not link')
        st = path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'selected regular single-linked file')
        files[name] = path.read_bytes()
        if name != MANIFEST:
            need(H(files[name]) == current['files'][name], 'independent selected source pin: ' + name)
        need(not name.startswith(('evidence/', 'work/', '.git/')) and '__pycache__' not in parts and not name.endswith(('.pyc', '.pyo')), 'generated content not selected')
    base_raw = files['snapshots/v011/baseline-manifest.json']
    lab_raw = files['docs/BASELINE-SNAPSHOT-LAB-SOURCE-MANIFEST.json']
    need(H(base_raw) == BASE_MANIFEST and H(lab_raw) == LAB_MANIFEST, 'external baseline/lab pins')
    baseline, lab = strict(base_raw)['files'], strict(lab_raw)['files']
    need(len(baseline) == 380, 'baseline count')
    changed = [name for name, pin in baseline.items() if H(files[name]) != pin]
    need(changed == ['README.md', 'RELEASE-FILES.json'], 'only allowed inherited changes')
    vendors = sorted(n for n in baseline if n.startswith('vendor/'))
    need(len(vendors) == 7 and all(H(files[n]) == baseline[n] for n in vendors), 'seven historical ZIPs retained')
    need('vendor/foundation-math-v011-source.zip' not in names, 'no original full v0.11 ZIP selected')
    mapping = {'baseline_snapshot/snapshot.py': 'snapshot.py', 'packaging_tests/test_snapshot.py': 'test_snapshot.py',
               'docs/BASELINE-SNAPSHOT-LAB-CONTRACT.md': 'CONTRACT.md'}
    for new, old in mapping.items():
        need(H(files[new]) == lab[old], 'accepted lab bytes: ' + new)
    need(s.LIMITS == LIMITS and s.RECEIPT_RESERVE == 65536, 'unchanged fixed limits')
    tree = ast.parse(files['baseline_snapshot/snapshot.py'])
    literal = next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'LIMITS' for t in n.targets))
    def constant(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            return constant(node.left) * constant(node.right)
        raise ReviewFailure('nonconstant limit expression')
    need({k.value: constant(v) for k, v in zip(literal.keys, literal.values)} == LIMITS, 'fixed limit literals unchanged')
    forbidden = {'socket', 'requests', 'urllib', 'http', 'subprocess', 'openai', 'importlib'}
    imports = {n.name.split('.')[0] for v in ast.walk(tree) if isinstance(v, ast.Import) for n in v.names}
    imports |= {v.module.split('.')[0] for v in ast.walk(tree) if isinstance(v, ast.ImportFrom)}
    need(not imports & forbidden, 'snapshot has no network/process/dynamic-import dependency')
    need(not any(isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in {'eval', 'exec', 'compile', '__import__'} for v in ast.walk(tree)), 'snapshot does not evaluate content')
    recipe_raw = files['snapshots/v011/recipe.json']
    recipe = strict(recipe_raw)
    need(H(recipe_raw) == RECIPE, 'independent recipe pin')
    need(set(recipe) == {'schema', 'zip_profile', 'baseline_manifest_sha256', 'baseline_archive_sha256', 'baseline_archive_bytes', 'donor_projection_sha256', 'files'}, 'no next-manifest recipe field')
    need(H(raw) not in recipe_raw.decode(), 'no current-manifest hash cycle')
    need(recipe['baseline_manifest_sha256'] == BASE_MANIFEST and recipe['baseline_archive_sha256'] == BASE_ARCHIVE and recipe['baseline_archive_bytes'] == BASE_BYTES, 'baseline recipe identities')
    need({v['path']: v['sha256'] for v in recipe['files']} == baseline, 'exact recipe historical coverage')
    donors = {v['path']: files[v['path']] for v in recipe['files'] if v['source'] == 'donor'}
    blob_rows = [v for v in recipe['files'] if v['source'] == 'blob']
    need(len(donors) == 378 and {v['path'] for v in blob_rows} == set(changed), 'exact 378 donors and two changed sources')
    need(recipe['donor_projection_sha256'] == H(C({n: H(v) for n, v in donors.items()})), 'independent donor projection')
    snapshot_names = {'snapshots/v011/recipe.json', 'snapshots/v011/baseline-manifest.json'} | {'snapshots/v011/blobs/' + v['sha256'] for v in blob_rows}
    need(len(snapshot_names) == 4 and {n for n in names if n.startswith('snapshots/v011/')} == snapshot_names, 'exact four selected snapshot files')
    historical = dict(donors)
    for v in blob_rows:
        data = files['snapshots/v011/blobs/' + v['sha256']]
        need(len(data) == v['bytes'] and H(data) == v['sha256'], 'old-byte blob identity')
        historical[v['path']] = data
    historical[MANIFEST] = base_raw
    for row in recipe['files']:
        need(len(historical[row['path']]) == row['bytes'], 'independent recipe declared length')
    from foundation_math_bridge.schemas import tool_definitions
    definitions = tool_definitions()
    need(len(definitions) == 15 and definitions == strict(files['docs/BASE-V011-BRIDGE-TOOLS.json'])['tools'], 'all fifteen complete tool contracts unchanged')
    # The complete inherited source comparison above includes every runtime,
    # mathematics, ledger, acceptance, bridge schema, and dispatch implementation.
    pinfile = Path(__file__).with_name('V012-REVIEW-PINS.json')
    receipt = strict(pinfile.read_bytes())
    for name, pin in receipt['files'].items():
        data = Path(__file__).read_bytes() if name == 'review/v012_review.py' else files[name]
        need(H(data) == pin, 'independent integration source receipt: ' + name)
    need(receipt['baseline_manifest_sha256'] == BASE_MANIFEST and receipt['accepted_lab_manifest_sha256'] == LAB_MANIFEST, 'review receipt frozen input pins')
    required = {'tools/build_snapshot_release.py', 'tools/reproduce_snapshot_release.py', 'tools/run_snapshot_validation.py',
                'tools/snapshot_release_support.py', 'packaging_tests/test_integration.py', 'docs/BASELINE-SNAPSHOT.md',
                'docs/BASELINE-SNAPSHOT-VALIDATION.md'} | set(mapping)
    need(required <= set(names), 'integration implementation/tests/documentation selected')
    return current, files, historical, donors, {n.removeprefix('snapshots/v011/'): files[n] for n in snapshot_names}


def minimal_replay(work, donors, snapshots, historical):
    minimal = work / 'minimal'
    populate(minimal / 'inputs/donor', donors)
    populate(minimal / 'inputs/snapshot', snapshots)
    (minimal / 'outputs').mkdir()
    # The only executable module copied for the subprocess is the pinned snapshot
    # engine. Neither release helpers nor a baseline/current manifest is supplied.
    (minimal / 'engine.py').write_bytes((ROOT / 'baseline_snapshot/snapshot.py').read_bytes())
    code = r'''
import importlib.util,json,os,pathlib,sys
root=pathlib.Path(sys.argv[1]); spec=importlib.util.spec_from_file_location('engine',root/'engine.py')
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
seen=[]; blocked=[]; active=False
original=s.read_file
def read(fd,name,budget,maximum=None):
    location=pathlib.Path(os.readlink('/proc/self/fd/'+str(fd))).resolve()
    if not location.is_relative_to(root/'inputs'): raise RuntimeError('read outside minimal inputs')
    seen.append(str(location.relative_to(root))+'/'+name)
    return original(fd,name,budget,maximum)
s.read_file=read
def audit(event,args):
    if not active: return
    if event.startswith(('socket.','subprocess.','os.exec','os.spawn','os.posix_spawn')) or event == 'os.system':
        blocked.append(event); raise RuntimeError('network/process event forbidden')
    if event=='open' and isinstance(args[0],(str,bytes)):
        p=pathlib.Path(os.fsdecode(args[0]))
        if '..' in p.parts or (p.is_absolute() and not p.is_relative_to(root)):
            blocked.append('external-open'); raise RuntimeError('external read forbidden')
sys.addaudithook(audit)
active=True
with s.Workspace(root) as w:
    receipt=s.restore(w,'snapshot','donor','baseline',recipe_sha256=sys.argv[2],baseline_manifest_sha256=sys.argv[3],baseline_archive_sha256=sys.argv[4])
active=False
print(json.dumps({'receipt':receipt,'read_paths':sorted(seen),'blocked_events':blocked},sort_keys=True))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
    proc = subprocess.run([sys.executable, '-I', '-B'] + (['-O'] if sys.flags.optimize else []) + ['-c', code, str(minimal), RECIPE, BASE_MANIFEST, BASE_ARCHIVE], capture_output=True, text=True, env=env, cwd=minimal, timeout=120)
    need(proc.returncode == 0, 'audited minimal subprocess: ' + proc.stderr[-1000:])
    result = strict(proc.stdout)
    expected_reads = {'inputs/donor/' + n for n in donors} | {'inputs/snapshot/' + n for n in snapshots}
    need(set(result['read_paths']) == expected_reads and len(result['read_paths']) == 382, 'exact minimal read set')
    need(result['blocked_events'] == [], 'no external/network/process attempt')
    restored = minimal / 'outputs/baseline/restored'
    output = {p.relative_to(restored).as_posix(): p.read_bytes() for p in restored.rglob('*') if p.is_file()}
    need(output == historical and len(output) == 381, 'exact reconstructed historical inventory and bytes')
    raw_zip = (minimal / 'outputs/baseline/baseline.zip').read_bytes()
    need(H(raw_zip) == BASE_ARCHIVE and len(raw_zip) == BASE_BYTES, 'exact original baseline ZIP')
    need(raw_zip == archive(historical), 'independent historical ZIP serializer')
    CONTROLS.append('audited_minimal_378_donors_four_snapshot_files_no_external_dependencies')
    historical_output = work / 'historical-builder.zip'
    builder_code = ('import runpy,sys;root=sys.argv[1];out=sys.argv[2];sys.path.insert(0,root);'
                    'sys.argv=[root+"/tools/build_claim_ledger_release.py","--output",out];'
                    'runpy.run_path(sys.argv[0],run_name="__main__")')
    proc = subprocess.run([sys.executable, '-I', '-B'] + (['-O'] if sys.flags.optimize else []) +
                          ['-c', builder_code, str(restored), str(historical_output)], capture_output=True,
                          text=True, env=env, cwd=restored, timeout=120)
    need(proc.returncode == 0 and historical_output.read_bytes() == raw_zip, 'unchanged historical builder independently matches')
    CONTROLS.append('unchanged_historical_builder_matches_original_zip')
    return raw_zip, result['receipt']


def restore_controls(work, donors, snapshots):
    root = work / 'failures'
    populate(root / 'inputs/donor', donors); populate(root / 'inputs/snapshot', snapshots)
    outputs = root / 'outputs'; outputs.mkdir()
    kwargs = {'recipe_sha256': RECIPE, 'baseline_manifest_sha256': BASE_MANIFEST, 'baseline_archive_sha256': BASE_ARCHIVE}
    def restore(**changes):
        with s.Workspace(root) as w:
            return s.restore(w, 'snapshot', 'donor', 'result', **{**kwargs, **changes})
    def reject(label, fn=restore):
        rejection(label, fn, outputs)
    for key in kwargs:
        reject('wrong_' + key, lambda key=key: restore(**{key: '0' * 64}))
    for relative in ['inputs/snapshot/recipe.json', 'inputs/snapshot/baseline-manifest.json', 'inputs/donor/foundation_math/calculator.py', 'inputs/snapshot/' + sorted(n for n in snapshots if n.startswith('blobs/'))[0]]:
        path = root / relative
        raw = path.read_bytes()
        with replace(path, bytes([raw[0] ^ 1]) + raw[1:]):
            reject('same_size_tamper_' + relative)
        path.unlink()
        try:
            reject('missing_' + relative)
        finally:
            path.write_bytes(raw)
    missing = root / 'inputs/snapshot' / sorted(n for n in snapshots if n.startswith('blobs/'))[0]
    raw = missing.read_bytes(); missing.unlink()
    recipe = strict(snapshots['recipe.json'])
    row = next(v for v in recipe['files'] if v['sha256'] == H(raw))
    populate(root / 'inputs/donor', {row['path']: raw})
    try:
        reject('no_fallback_to_matching_donor_for_missing_blob')
    finally:
        missing.write_bytes(raw); (root / 'inputs/donor' / row['path']).unlink()
    for label, path, is_dir in [('extra_snapshot_file', root / 'inputs/snapshot/extra', False), ('extra_snapshot_directory', root / 'inputs/snapshot/extra', True)]:
        path.mkdir() if is_dir else path.write_bytes(b'extra')
        try:
            reject(label)
        finally:
            path.rmdir() if is_dir else path.unlink()
    donor = root / 'inputs/donor/foundation_math/calculator.py'; raw = donor.read_bytes()
    for kind in ('symlink', 'hardlink', 'fifo'):
        donor.unlink(); outside = root / 'outside'; outside.write_bytes(raw)
        if kind == 'symlink': donor.symlink_to(outside)
        elif kind == 'hardlink': os.link(outside, donor)
        else: os.mkfifo(donor)
        try:
            reject('reject_donor_' + kind)
        finally:
            donor.unlink(); outside.unlink(); donor.write_bytes(raw)
    parent = root / 'inputs/donor/foundation_math'; moved = root / 'moved'; parent.rename(moved); parent.symlink_to(moved, target_is_directory=True)
    try:
        reject('reject_symlink_donor_parent')
    finally:
        parent.unlink(); moved.rename(parent)
    for key, value in [('donor_projection_sha256', '0' * 64), ('baseline_archive_bytes', BASE_BYTES + 1), ('next_manifest_sha256', '0' * 64), ('zip_profile', 'unknown')]:
        obj = deepcopy(recipe); obj[key] = value; raw = C(obj)
        with replace(root / 'inputs/snapshot/recipe.json', raw):
            reject('reject_rebound_recipe_' + key, lambda raw=raw: restore(recipe_sha256=H(raw)))
    # Existing destinations are preserved, rather than erased by cleanup.
    target = outputs / 'result'
    for kind in ('file', 'empty_directory', 'symlink'):
        if kind == 'file': target.write_bytes(b'keep')
        elif kind == 'empty_directory': target.mkdir()
        else: target.symlink_to(root / 'absent')
        before = target.lstat()
        rejection('preserve_existing_output_' + kind, restore)
        need(target.lstat().st_ino == before.st_ino and len(list(outputs.iterdir())) == 1, 'existing output preserved')
        target.rmdir() if kind == 'empty_directory' else target.unlink()
    with patch.object(s, 'create_zip', side_effect=OSError('independent injected interruption')):
        reject('handled_zip_interruption_cleans_stage')
    real = s.create_zip
    def wrong_serializer(*args, **kwargs):
        digest, size = real(*args, **kwargs)
        return '0' * 64, size
    with patch.object(s, 'create_zip', side_effect=wrong_serializer):
        reject('serializer_mismatch_fails_closed_without_repin')
    with patch.object(s, 'write_tree', side_effect=OSError('independent injected interruption')):
        reject('handled_tree_interruption_cleans_stage')
    # Check the precise documented concurrent limitation, not a stronger claim.
    with s.Workspace(root) as w:
        original_rename = os.rename; before = []
        def raced(src, dst, *args, **kwargs):
            target.mkdir(); before.append(target.stat().st_ino)
            return original_rename(src, dst, *args, **kwargs)
        with patch.object(s.os, 'rename', side_effect=raced):
            with w.transaction('result') as stage:
                (stage / 'marker').write_bytes(b'published')
        need(target.stat().st_ino != before[0] and (target / 'marker').read_bytes() == b'published', 'documented empty-directory race limitation reproduced')
    shutil.rmtree(target)
    CONTROLS.append('excluded_concurrent_empty_directory_race_documented_not_claimed_safe')


def decoder_and_eligibility_controls(work):
    for value in ('1e400', '-1e400', 'NaN', 'Infinity', '-Infinity'):
        raw = ('{"files":{"x":"' + '0' * 64 + '"},"metadata":' + value + '}').encode()
        rejection('nonfinite_manifest_' + value, lambda raw=raw: s.source_manifest(raw, H(raw)))
    rejection('duplicate_nested_manifest_key', lambda: s.decode(b'{"a":{"b":1,"b":2}}', 'review'))
    for value in ('../x', '/tmp/x', 'x//y', 'x/./y', 'x/../y', 'x\\y', 'x/' , 'x' * 241):
        rejection('unsafe_path_' + value, lambda value=value: s.name(value))
    for value in (float('nan'), float('inf'), -float('inf')):
        rejection('nonfinite_canonical_output', lambda value=value: s.canonical({'x': value}))
    # Actual production limits, not lowered test limits. Deterministic pseudo-random
    # bytes give a real historical ZIP whose output would exceed the unchanged cap.
    old = {'old/' + str(i): shake_256(('old-' + str(i)).encode()).digest(7 * 1024 * 1024) for i in range(4)}
    new = {'keep/' + str(i): bytes([65 + i]) * (5 * 1024 * 1024) for i in range(3)}
    old.update(new)
    cases = [('actual_production_43mib_restored_output_overflow', old, new),
             ('actual_production_4804_restored_entries_overflow', {'/'.join('d%d_%d' % (i, j) for j in range(7)) + '/file': b'' for i in range(600)}, None)]
    for label, old, new in cases:
        if new is None: new = old
        root = work / label; (root / 'outputs').mkdir(parents=True)
        bm, dm = manifest(old), manifest(new)
        populate(root / 'inputs/base', {**old, MANIFEST: bm})
        populate(root / 'inputs/donor', {**new, MANIFEST: dm})
        zipped = archive({**old, MANIFEST: bm})
        with s.Workspace(root) as workspace:
            def build():
                return s.build(workspace, 'base', 'donor', 'snapshot', baseline_manifest_sha256=H(bm), baseline_archive_sha256=H(zipped), baseline_archive_bytes=len(zipped), donor_manifest_sha256=H(dm))
            with patch.object(s, 'create_zip', side_effect=ReviewFailure('reached serializer before eligibility rejection')) as mocked:
                rejection(label, build, root / 'outputs')
                need(mocked.call_count == 0, 'build rejects before serialization/publication')
        rows = [{'path': n, 'bytes': len(raw), 'sha256': H(raw), 'source': 'donor' if n in new else 'blob'} for n, raw in sorted(old.items())]
        replay_recipe = {'files': rows, 'baseline_archive_bytes': len(zipped)}
        rejection(label + '_shared_restore_preflight', lambda: s.replay_eligibility(replay_recipe, 100, len(bm)))
        shutil.rmtree(root)
    CONTROLS.append('build_restore_share_unchanged_actual_production_limits')


def integration_controls(root, work, files):
    clean = work / 'selected-only'; populate(clean, files)
    need(b.verify(clean) == strict(files[MANIFEST]), 'selected-only verify')
    a, again = work / 'a.zip', work / 'again.zip'
    receipt = b.create_zip(a, clean); b.create_zip(again, clean)
    need(a.read_bytes() == again.read_bytes() == archive(files), 'independent current ZIP serializer and repeated builder')
    with zipfile.ZipFile(a) as z:
        need(z.namelist() == sorted(files), 'exact selected archive inventory')
        for info in z.infolist():
            need(info.date_time == (2026, 1, 1, 0, 0, 0) and info.create_system == 3 and info.external_attr == 0o100644 << 16 and info.compress_type == zipfile.ZIP_DEFLATED and info.extra == b'' and info.comment == b'', 'fixed current ZIP profile')
    for name in ('foundation_math/claim_ledger.py', 'baseline_snapshot/snapshot.py', 'tools/build_snapshot_release.py', 'vendor/foundation-math-v010-source.zip', 'snapshots/v011/recipe.json'):
        with replace(clean / name, files[name] + b'\n'):
            rejection('integration_drift_' + name, lambda: b.verify(clean))
    for name in ('foundation_math/claim_ledger.py', 'baseline_snapshot/snapshot.py'):
        with replace(clean / name, files[name] + b'\n'):
            rejection('freeze_cannot_repin_' + name, lambda: b.freeze(clean))
    value = strict(files['SNAPSHOT-PINS.json']); value['recipe_sha256'] = '0' * 64
    with replace(clean / 'SNAPSHOT-PINS.json', C(value)):
        rejection('integration_recipe_repin_rejected', lambda: b.freeze(clean))
    for fragment in (b'1e400', b'NaN'):
        altered = files[MANIFEST].replace(b'"version": "0.12.0-dev"', b'"version": ' + fragment)
        need(altered != files[MANIFEST], 'current nonfinite control modifies input')
        with replace(clean / MANIFEST, altered):
            rejection('current_manifest_nonfinite_' + fragment.decode(), lambda: b.verify(clean))
    selection = strict(files['RELEASE-FILES.json'])
    for name in ('foundation_math/calculator.py', 'snapshots/v011/baseline-manifest.json'):
        obj = deepcopy(selection); obj['files'].remove(name)
        with replace(clean / 'RELEASE-FILES.json', C(obj)):
            rejection('selection_omission_' + name, lambda: b.freeze(clean))
    with replace(clean / 'RELEASE-FILES.json', b'{"schema":"x","schema":"y","files":[]}'):
        rejection('duplicate_selection_key', lambda: b.verify(clean))
    extra = clean / 'snapshots/v011/extra'; extra.write_bytes(b'not selected')
    try:
        rejection('unselected_snapshot_payload_rejected', lambda: b.verify(clean))
    finally:
        extra.unlink()
    destination = work / 'existing.zip'; destination.write_bytes(b'keep')
    rejection('current_builder_existing_destination', lambda: b.create_zip(destination, clean))
    need(destination.read_bytes() == b'keep', 'current destination preserved')
    links = work / 'linked-output'; links.symlink_to(work, target_is_directory=True)
    rejection('current_builder_symlink_output_parent', lambda: b.create_zip(links / 'not-created.zip', clean))
    need(not (work / 'not-created.zip').exists(), 'symlink output not written')
    need(b.verify(clean) == strict(files[MANIFEST]), 'control copy restored exactly')
    from tools import snapshot_release_support as support
    pinned = support.pins(clean)
    observed = []
    original_read = s.read_file
    def read(fd, name, budget, maximum=None):
        observed.append((name, budget, maximum))
        return original_read(fd, name, budget, maximum)
    with patch.object(support, 'pins', return_value=pinned), patch.object(s, 'read_file', side_effect=read), patch.object(s, 'restore', return_value={'status': 'precopy-only'}) as core:
        with support.restored_baseline(clean):
            pass
    need(core.call_count == 1 and len(observed) == 382, 'wrapper exact pre-copy input count')
    need(len({id(row[1]) for row in observed}) == 1, 'wrapper has one aggregate pre-copy budget')
    sizes = {row['path']: row['bytes'] for row in pinned[1]['files'] if row['source'] == 'donor'}
    blob_sizes = {'blobs/' + row['sha256']: row['bytes'] for row in pinned[1]['files'] if row['source'] == 'blob'}
    maxima = {**sizes, **blob_sizes, 'recipe.json': LIMITS['recipe_bytes'], 'baseline-manifest.json': LIMITS['manifest_bytes']}
    need(all(maxima[name] == maximum for name, _, maximum in observed), 'wrapper precharges declared-size bounded reads')
    budget = observed[0][1]
    need((budget.reads, budget.bytes) == (382, sum(len(files[name]) for name in sizes) + sum(len(v) for n, v in files.items() if n.startswith('snapshots/v011/'))), 'wrapper aggregate pre-copy accounting')
    CONTROLS.append('wrapper_shared_bounded_precopy_exact_sizes_hashes_and_accounting')
    for name in ('foundation_math/calculator.py', next(n for n in files if n.startswith('snapshots/v011/blobs/'))):
        raw = files[name]
        for label, bad in [('oversized', raw + b'x'), ('same_size_hash_drift', bytes([raw[0] ^ 1]) + raw[1:])]:
            with replace(clean / name, bad), patch.object(s, 'restore', side_effect=ReviewFailure('must reject before core restore')) as core:
                def precopy():
                    with support.restored_baseline(clean):
                        pass
                rejection('wrapper_' + label + '_' + name, precopy)
                need(core.call_count == 0, 'wrapper rejects changed input before replay')
    need(b.verify(clean) == strict(files[MANIFEST]), 'pre-copy control copy restored exactly')
    (clean / MANIFEST).unlink(); (clean / 'RELEASE-FILES.json').unlink()
    try:
        with replace(clean / 'README.md', b'not a historical donor'):
            with support.restored_baseline(clean) as (base, old_zip, _):
                need(H(old_zip.read_bytes()) == BASE_ARCHIVE and H((base / MANIFEST).read_bytes()) == BASE_MANIFEST, 'wrapper does not need next manifest or changed current metadata')
    finally:
        (clean / MANIFEST).write_bytes(files[MANIFEST]); (clean / 'RELEASE-FILES.json').write_bytes(files['RELEASE-FILES.json'])
    CONTROLS.append('wrapper_restore_without_current_manifest_selection_or_changed_readme')
    return receipt


def privacy(files, historical):
    markers = ('/workspace/', '/home/', 'file://', 'codex://', 'ghp_', 'sk-proj-', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY')
    counts = Counter(); findings = []
    def scan(name, raw, depth=0):
        need(depth <= 8, 'privacy archive depth bounded')
        if name.endswith('.zip'):
            counts['archives'] += 1
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos = z.infolist()
                need(len(infos) <= 4096 and sum(v.file_size for v in infos) <= 64 * 1024 * 1024, 'privacy archive bounded')
                for info in infos:
                    if not info.is_dir(): scan(name + '!' + info.filename, z.read(info), depth + 1)
        elif name.endswith(('.md', '.json', '.jsonl', '.txt')):
            counts['text_files'] += 1
            text = raw.decode('utf-8')
            for marker in markers:
                if marker in text: findings.append({'file': name, 'marker': marker})
    for name, raw in sorted(files.items()): scan(name, raw)
    # Include historical source payloads whose selected blobs have hash-only names.
    for name in ('README.md', 'RELEASE-FILES.json'): scan('restored-v011/' + name, historical[name])
    need(not findings, 'privacy/portability marker findings')
    return {'status': 'passed', **dict(counts), 'findings': [], 'scope': 'Bounded text and nested-archive marker scan, including decoded old-byte blobs; not universal secret detection.'}


def measurements(files, historical_zip, receipt):
    snapshot = {n: v for n, v in files.items() if n.startswith('snapshots/v011/')}
    common = {n: v for n, v in files.items() if n not in snapshot}
    assemblies = {'common-payload': common, 'actual-snapshot-release': files,
                  'counterfactual-full-baseline': {**common, 'vendor/foundation-math-v011-source.zip': historical_zip}, 'snapshot-only': snapshot}
    results = {}
    for name, members in assemblies.items():
        raw = archive(members)
        results[name] = {'bytes': len(raw), 'sha256': H(raw)}
    need(results['actual-snapshot-release']['sha256'] == receipt['sha256'], 'measurement equals actual current ZIP')
    base = results['common-payload']['bytes']; actual = results['actual-snapshot-release']['bytes']; full = results['counterfactual-full-baseline']['bytes']
    need(actual < full, 'measured snapshot saving')
    from tools.reproduce_snapshot_release import measure
    with tempfile.TemporaryDirectory(prefix='fm-v012-measure-') as td:
        author = measure(ROOT, Path(td))
    need(author['archives'] == results, 'independent versus release measurement archive equality')
    need(author['snapshot_incremental_outer_zip_bytes'] == actual - base and author['full_baseline_incremental_outer_zip_bytes'] == full - base and author['outer_zip_bytes_saved'] == full - actual, 'independent versus release incremental measurement equality')
    CONTROLS.append('independent_actual_current_payload_measurements_match_release_method')
    return {'archives': results, 'snapshot_raw_bytes': sum(map(len, snapshot.values())),
            'snapshot_incremental_outer_zip_bytes': actual - base, 'full_baseline_incremental_outer_zip_bytes': full - base,
            'outer_zip_bytes_saved': full - actual, 'actual_total_growth_over_v011_bytes': actual - BASE_BYTES,
            'all_non_snapshot_members_held_fixed': True, 'counterfactual_is_measurement_only_not_valid_release': True,
            'synthetic_fixture_measurement_reused': False, 'future_growth_claim': False, 'timing_claim': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    global ROOT, s, b
    ROOT = args.root.resolve()
    sys.path.insert(0, str(ROOT))
    from baseline_snapshot import snapshot as s
    from tools import build_snapshot_release as b
    current, files, historical, donors, snapshots = source_checks(ROOT)
    with tempfile.TemporaryDirectory(prefix='fm-v012-independent-') as td:
        work = Path(td)
        baseline_zip, restoration = minimal_replay(work, donors, snapshots, historical)
        restore_controls(work, donors, snapshots)
        decoder_and_eligibility_controls(work)
        receipt = integration_controls(ROOT, work, files)
        scan = privacy(files, historical)
        measured = measurements(files, baseline_zip, receipt)
    need(all((ROOT / n).read_bytes() == raw for n, raw in files.items()), 'candidate selected sources remained unchanged')
    result = {'status': 'PASS', 'scope': 'Independent packaging-only integration review, not authenticity, mathematical proof, runtime promotion, publication, or long-chain growth approval.',
              'source_manifest_sha256': H(files[MANIFEST]), 'selected_files_excluding_manifest': len(current['files']),
              'counts': dict(COUNTS), 'independent_controls': sorted(CONTROLS),
              'preservation': {'baseline_sources': 380, 'unchanged_sources': 378, 'changed_sources': ['README.md', 'RELEASE-FILES.json'], 'historical_vendor_archives': 7, 'unchanged_complete_tool_contracts': 15, 'all_runtime_math_ledger_acceptance_sources_unchanged': True},
              'accepted_lab': {'manifest_sha256': LAB_MANIFEST, 'archive_sha256': LAB_ARCHIVE, 'fixed_limits_unchanged': True, 'both_corrected_findings_regression_covered': True},
              'restoration': restoration, 'current_archive': receipt, 'measurements': measured, 'privacy': scan,
              'minimal_dependency_audit': 'Exactly 378 donor reads plus four snapshot files; separate process with only pinned snapshot engine, no current manifest, original baseline ZIP, sibling checkout, network or subprocess events. Audit instrumentation is not an OS sandbox.',
              'platform': {'python': sys.version.split()[0], 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION, 'supported_scope': 'Linux/POSIX trusted single-writer workspace; final empty-directory race remains excluded; no power-loss durability claim.'},
              'full_historical_aggregate': 'Owned by the current aggregate and delivery gate; not duplicated or claimed executed by this harness.'}
    print(C(result).decode(), end='')


if __name__ == '__main__':
    main()

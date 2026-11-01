"""Pinned v0.12 packaging inputs; integrity, not origin authentication or proof."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import tempfile

from baseline_snapshot import snapshot as s

BASE_MANIFEST_PIN = '438bc999e2a3577a4c8525a5b990a7346bd4d0dd9f1b400d596661d7a465e6a4'
BASE_ZIP_PIN = '530d9794c083801d6d0acb6273980bdf1d4d7d59aeeb500945d0d5a11a31f741'
BASE_ZIP_BYTES = 5524169
LAB_MANIFEST_PIN = '55991f10d519cdcc1e10389f60d178bc12fa82174615a390f059047a34350a1b'
LAB_ZIP_PIN = 'afe15b921ac5049604d9e6255e4acf4e3f2a76eac1d30a4b694be1e078737d4b'
RECIPE_PIN = '0d8a5780fbad9df5811021c3b658f57a2aa696779d4a1d256612cb821bf22ef6'
ALLOWED_BASE_CHANGES = frozenset(('README.md', 'RELEASE-FILES.json'))
SNAPSHOT = 'snapshots/v011'


def require(ok, label):
    if not ok:
        raise RuntimeError(label)


def environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ('PYTHONPATH', 'PYTHONHOME', 'SPLIT_REVIEW_ROOT'):
        env.pop(key, None)
    return env


@contextmanager
def source_fd(root):
    root = Path(root).absolute()
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current /= part
        require(not current.is_symlink() and current.is_dir(), 'source root must be real directories')
    fd = os.open(root, s.DIR_FLAGS)
    try:
        yield fd
    finally:
        os.close(fd)


def read(root, name, maximum=None):
    with source_fd(root) as fd:
        return s.read_file(fd, name, s.Budget(), maximum)


def pins(root):
    raw = read(root, 'SNAPSHOT-PINS.json')
    value = s.decode(raw, 'release pins')
    s.exact_keys(value, ('schema', 'baseline_manifest_sha256', 'baseline_archive_sha256',
                        'baseline_archive_bytes', 'lab_manifest_sha256', 'lab_archive_sha256',
                        'recipe_sha256', 'lab_source_pins'), 'release pins')
    require(raw == s.canonical(value), 'noncanonical release pins')
    require(value['schema'] == 'foundation-math-v012-snapshot-pins-v1', 'release pin schema')
    require(value['baseline_manifest_sha256'] == BASE_MANIFEST_PIN and
            value['baseline_archive_sha256'] == BASE_ZIP_PIN and value['baseline_archive_bytes'] == BASE_ZIP_BYTES,
            'baseline pins changed')
    require(value['lab_manifest_sha256'] == LAB_MANIFEST_PIN and value['lab_archive_sha256'] == LAB_ZIP_PIN,
            'accepted corrected lab pins changed')
    require(value['recipe_sha256'] == RECIPE_PIN, 'frozen integration recipe pin changed')
    expected = {'baseline_snapshot/snapshot.py': 'snapshot.py',
                'packaging_tests/test_snapshot.py': 'test_snapshot.py',
                'docs/BASELINE-SNAPSHOT-LAB-CONTRACT.md': 'CONTRACT.md'}
    lab_raw = read(root, 'docs/BASELINE-SNAPSHOT-LAB-SOURCE-MANIFEST.json', s.LIMITS['manifest_bytes'])
    lab = s.source_manifest(lab_raw, LAB_MANIFEST_PIN)
    require(value['lab_source_pins'] == {new: lab[old] for new, old in expected.items()}, 'accepted lab source pin mapping')
    for new, old in expected.items():
        require(s.digest(read(root, new)) == lab[old], 'accepted corrected lab source drift: ' + new)
    recipe = s.validate_recipe(read(root, SNAPSHOT + '/recipe.json', s.LIMITS['recipe_bytes']),
                               value['recipe_sha256'], BASE_MANIFEST_PIN, BASE_ZIP_PIN)
    raw = read(root, SNAPSHOT + '/baseline-manifest.json', s.LIMITS['manifest_bytes'])
    baseline = s.source_manifest(raw, BASE_MANIFEST_PIN)
    require({r['path']: r['sha256'] for r in recipe['files']} == baseline, 'baseline recipe coverage')
    s.replay_eligibility(recipe, len(read(root, SNAPSHOT + '/recipe.json')), len(raw))
    expected_names = {'recipe.json', 'baseline-manifest.json'} | {'blobs/' + r['sha256'] for r in recipe['files'] if r['source'] == 'blob'}
    with source_fd(root) as fd, s.directory(fd, SNAPSHOT) as snapshot_fd:
        actual, dirs = s.inventory(snapshot_fd)
        require(actual == expected_names and dirs == s.expected_dirs(expected_names), 'snapshot exact inventory')
    return value, recipe, baseline


def preservation(root):
    value, recipe, baseline = pins(root)
    changed = {name for name, pin in baseline.items() if s.digest(read(root, name)) != pin}
    require(changed == ALLOWED_BASE_CHANGES, 'unexpected baseline changes: ' + str(sorted(changed)))
    donors = {r['path'] for r in recipe['files'] if r['source'] == 'donor'}
    require(donors == set(baseline) - ALLOWED_BASE_CHANGES, 'donor projection must reuse every unchanged baseline file')
    from foundation_math_bridge.schemas import tool_definitions
    # Source equality covers the complete schemas, dispatch, arithmetic and ledger.
    require(len(tool_definitions()) == 15, 'exactly fifteen runtime tools')
    expected_tools = s.decode(read(root, 'docs/BASE-V011-BRIDGE-TOOLS.json'), 'baseline tools')['tools']
    require(tool_definitions() == expected_tools, 'all fifteen complete tool contracts unchanged')
    return {'status': 'passed', 'baseline_selected_files': len(baseline), 'unchanged_baseline_files': len(donors),
            'changed_baseline_files': sorted(changed), 'runtime_tool_count': 15,
            'all_runtime_math_ledger_acceptance_and_contract_sources_unchanged': True,
            'historical_vendor_archives_unchanged': sorted(n for n in baseline if n.startswith('vendor/'))}


@contextmanager
def restored_baseline(root):
    """Copy only explicit donor projection and snapshot files into a fresh workspace."""
    value, recipe, baseline = pins(root)
    with tempfile.TemporaryDirectory(prefix='fm-v012-baseline-') as td:
        work = Path(td)
        (work / 'inputs/donor').mkdir(parents=True)
        (work / 'inputs/snapshot').mkdir()
        (work / 'outputs').mkdir()
        names = {'recipe.json', 'baseline-manifest.json'} | {
            'blobs/' + row['sha256'] for row in recipe['files'] if row['source'] == 'blob'}
        budget = s.Budget()
        blob_sizes = {row['sha256']: row['bytes'] for row in recipe['files'] if row['source'] == 'blob'}
        copied_sizes = {}
        with source_fd(root) as fd, s.directory(fd, SNAPSHOT) as snapshot_fd:
            actual, dirs = s.inventory(snapshot_fd)
            require(actual == names and dirs == s.expected_dirs(names), 'release snapshot exact inventory')
            for name in sorted(names):
                if name == 'recipe.json':
                    maximum, expected_pin = s.LIMITS['recipe_bytes'], value['recipe_sha256']
                elif name == 'baseline-manifest.json':
                    maximum, expected_pin = s.LIMITS['manifest_bytes'], BASE_MANIFEST_PIN
                else:
                    expected_pin = name.split('/')[1]
                    maximum = blob_sizes[expected_pin]
                raw = s.read_file(snapshot_fd, name, budget, maximum)
                require(s.digest(raw) == expected_pin, 'snapshot pre-copy source drift: ' + name)
                copied_sizes[name] = len(raw)
                target = work / 'inputs/snapshot' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            for row in recipe['files']:
                if row['source'] == 'donor':
                    raw = s.read_file(fd, row['path'], budget, row['bytes'])
                    require(len(raw) == row['bytes'] and s.digest(raw) == row['sha256'], 'donor pre-copy source drift: ' + row['path'])
                    target = work / 'inputs/donor' / row['path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
        eligibility = s.replay_eligibility(recipe, copied_sizes['recipe.json'], copied_sizes['baseline-manifest.json'])
        require((budget.reads, budget.bytes) == (eligibility['input_reads'], eligibility['input_bytes']), 'pre-copy input accounting mismatch')
        require(not (work / 'inputs/donor/SOURCE-MANIFEST.json').exists(), 'donor manifest is unnecessary')
        with s.Workspace(work) as workspace:
            receipt = s.restore(workspace, 'snapshot', 'donor', 'baseline', recipe_sha256=value['recipe_sha256'],
                                baseline_manifest_sha256=BASE_MANIFEST_PIN, baseline_archive_sha256=BASE_ZIP_PIN)
        yield work / 'outputs/baseline/restored', work / 'outputs/baseline/baseline.zip', receipt

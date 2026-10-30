"""Pinned v0.13 hypothesis-scope inputs; integrity, not origin authentication or proof."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import tempfile

from baseline_snapshot import snapshot as s

BASE_MANIFEST_PIN = 'dcd1c48e50f3c384b96e7eea4a442286fc669ad71dd10e0704366632e75adf9d'
BASE_ZIP_PIN = '8aeadce5e8e343794f7716c7a1fb31e8eeb953191f7e4d52448d6459d2921814'
BASE_ZIP_BYTES = 5682102
LAB_MANIFEST_PIN = '0d7cb6249f9c94eb073d330bd8c1ae59b0440e7ce703182cc4c2ee5856c079b9'
LAB_ZIP_PIN = 'd32bf32ddf6baa1a013425d9775a2e8ddf84a8a8ceedb11615679ff21875bd79'
RECIPE_PIN = '3f33b16d89722d45e4c360fade0ae446cd6c58f454534c4b6d05d9a24afa3deb'
ALLOWED_BASE_CHANGES = frozenset(['README.md', 'RELEASE-FILES.json', 'foundation_math/cli.py', 'foundation_math_bridge/__init__.py', 'foundation_math_bridge/schemas.py', 'foundation_math_bridge/server.py', 'tests/test_agent_bridge.py', 'tests/test_character_ring_integration.py', 'tests/test_claim_revision_integration.py', 'tests/test_linear_algebra_bridge.py', 'tests/test_linear_systems_integration.py', 'tests/test_portable_validation.py', 'tests/test_split_bundle_integration.py'])
SNAPSHOT = 'snapshots/v012'


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
    raw = read(root, 'HYPOTHESIS-SCOPE-PINS.json')
    value = s.decode(raw, 'release pins')
    s.exact_keys(value, ('schema', 'baseline_manifest_sha256', 'baseline_archive_sha256',
                        'baseline_archive_bytes', 'lab_manifest_sha256', 'lab_archive_sha256',
                        'recipe_sha256', 'lab_source_pins'), 'release pins')
    require(raw == s.canonical(value), 'noncanonical release pins')
    require(value['schema'] == 'foundation-math-v013-scope-pins-v1', 'release pin schema')
    require(value['baseline_manifest_sha256'] == BASE_MANIFEST_PIN and
            value['baseline_archive_sha256'] == BASE_ZIP_PIN and value['baseline_archive_bytes'] == BASE_ZIP_BYTES,
            'baseline pins changed')
    require(value['lab_manifest_sha256'] == LAB_MANIFEST_PIN and value['lab_archive_sha256'] == LAB_ZIP_PIN,
            'accepted corrected lab pins changed')
    require(value['recipe_sha256'] == RECIPE_PIN, 'frozen integration recipe pin changed')
    expected = {'hypothesis_scope/__init__.py': 'hypothesis_scope/__init__.py', 'hypothesis_scope/__main__.py': 'hypothesis_scope/__main__.py', 'hypothesis_scope/core.py': 'hypothesis_scope/core.py', 'docs/HYPOTHESIS-SCOPE-LAB-CONTRACT.md': 'docs/CONTRACT.md', 'docs/HYPOTHESIS-SCOPE-LAB-REVIEW.md': 'docs/INDEPENDENT-REVIEW.md', 'schemas/hypothesis-scope-request.schema.json': 'schemas/request.schema.json', 'examples/hypothesis-scope/W-not-Wp.json': 'fixtures/W-not-Wp.json', 'examples/hypothesis-scope/expectations.json': 'fixtures/expectations.json', 'examples/hypothesis-scope/selected-not-full-kernel.json': 'fixtures/selected-not-full-kernel.json', 'examples/hypothesis-scope/abstract-not-embedded.json': 'fixtures/abstract-not-embedded.json', 'examples/hypothesis-scope/A-not-V.json': 'fixtures/A-not-V.json', 'examples/hypothesis-scope/exact-full-kernel.json': 'fixtures/exact-full-kernel.json', 'examples/hypothesis-scope/original-not-induced-torsion.json': 'fixtures/original-not-induced-torsion.json', 'examples/hypothesis-scope/same-endpoints-not-same-map.json': 'fixtures/same-endpoints-not-same-map.json', 'examples/hypothesis-scope/saturated-not-coherent-image.json': 'fixtures/saturated-not-coherent-image.json', 'examples/hypothesis-scope/stale-fact-pin.json': 'fixtures/stale-fact-pin.json', 'examples/hypothesis-scope/two-step-not-one-step.json': 'fixtures/two-step-not-one-step.json', 'examples/hypothesis-scope/generic-not-coherent.json': 'fixtures/generic-not-coherent.json', 'examples/hypothesis-scope/withdrawn-fact.json': 'fixtures/withdrawn-fact.json'}
    lab_raw = read(root, 'docs/HYPOTHESIS-SCOPE-LAB-SOURCE-MANIFEST.json', s.LIMITS['manifest_bytes'])
    lab = s.source_manifest(lab_raw, LAB_MANIFEST_PIN)
    require(value['lab_source_pins'] == {new: lab[old] for new, old in expected.items()}, 'accepted lab mapping')
    for new, old in expected.items():
        require(s.digest(read(root, new)) == lab[old], 'accepted lab source drift: ' + new)
    require(s.digest(read(root, 'vendor/hypothesis-scope-lab.zip')) == LAB_ZIP_PIN, 'accepted lab ZIP drift')
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
    expected_tools = s.decode(read(root, 'docs/BASE-V012-BRIDGE-TOOLS.json'), 'baseline tools')['tools']
    require(len(expected_tools) == 15 and len(tool_definitions()) == 16, 'tool inventory')
    require(tool_definitions()[:15] == expected_tools, 'all fifteen prior complete contracts unchanged')
    require(tool_definitions()[15]['name'] == 'match_hypothesis_scope', 'exactly one appended tool')
    runtime = [n for n in baseline if n.startswith(('foundation_math/', 'claim_revision/', 'character_ring/',
               'split_bundle/', 'exact_linalg/', 'exact_systems/', 'bounded_counterexample/', 'polynomial_witness/'))
               and n != 'foundation_math/cli.py']
    require(all(s.digest(read(root,n)) == baseline[n] for n in runtime), 'old math/ledger/acceptance source changed')
    return {'status': 'passed', 'baseline_selected_files': len(baseline), 'unchanged_baseline_files': len(donors),
            'changed_baseline_files': sorted(changed), 'runtime_tool_count': 16, 'prior_contracts_unchanged': 15,
            'inherited_runtime_sources_unchanged': len(runtime), 'runtime_acceptance_unchanged': True,
            'historical_vendor_archives_unchanged': sorted(n for n in baseline if n.startswith('vendor/'))}


@contextmanager
def restored_baseline(root):
    """Copy only explicit donor projection and snapshot files into a fresh workspace."""
    value, recipe, baseline = pins(root)
    with tempfile.TemporaryDirectory(prefix='fm-v013-baseline-') as td:
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


def unpack_lab(root, output):
    """Extract only pinned frozen lab members, with explicit inventory/budgets."""
    import io
    import zipfile
    raw = read(root, 'vendor/hypothesis-scope-lab.zip')
    require(s.digest(raw) == LAB_ZIP_PIN, 'accepted lab archive pin')
    manifest_raw = read(root, 'docs/HYPOTHESIS-SCOPE-LAB-SOURCE-MANIFEST.json', s.LIMITS['manifest_bytes'])
    manifest = s.source_manifest(manifest_raw, LAB_MANIFEST_PIN)
    output = Path(output); output.mkdir(exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        expected = sorted([*manifest, 'SOURCE-MANIFEST.json'])
        require([r.filename for r in rows] == expected and len(rows) <= 2048, 'lab exact archive inventory')
        require(sum(r.file_size for r in rows) <= s.LIMITS['input_bytes'], 'lab extraction byte cap')
        for row in rows:
            s.name(row.filename)
            require(row.file_size <= s.LIMITS['file_bytes'] and row.external_attr >> 16 == 0o100644,
                    'lab member type/size')
            data = archive.read(row)
            expected_pin = LAB_MANIFEST_PIN if row.filename == 'SOURCE-MANIFEST.json' else manifest[row.filename]
            require(s.digest(data) == expected_pin, 'lab selected source drift')
            path = output / row.filename; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    return output

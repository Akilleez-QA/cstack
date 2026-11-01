"""Selected-only deterministic v0.13 packaging. Freeze is not validation."""
from hashlib import sha256
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from baseline_snapshot import snapshot as s
from tools.hypothesis_scope_release_support import source_fd, require, pins, preservation

SELECTION = 'RELEASE-FILES.json'
MANIFEST = 'SOURCE-MANIFEST.json'
SCHEMA = 'foundation-math-v013-selected-files-v1'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def selected_sources(root):
    with source_fd(root) as fd:
        budget = s.Budget()
        raw = s.read_file(fd, SELECTION, budget, s.LIMITS['manifest_bytes'])
        selected = s.decode(raw, 'release selection')
        s.exact_keys(selected, ('schema', 'files'), 'selection')
        require(selected['schema'] == SCHEMA and raw == s.canonical(selected), 'noncanonical selection/schema')
        names = selected['files']; s.paths(names)
        require(SELECTION in names and 'HYPOTHESIS-SCOPE-PINS.json' in names, 'selection must select its own inputs')
        sources = {}
        for name in names:
            require(not name.startswith(('evidence/', 'work/', '.git/')) and '__pycache__' not in name.split('/'), 'generated source selected')
            require(not name.endswith(('.pyc', '.pyo')) and (not name.endswith('.zip') or name.startswith('vendor/')), 'unexpected archive/generated source')
            require(name != 'vendor/foundation-math-v011-source.zip', 'full v0.11 archive must not be embedded')
            sources[name] = s.read_file(fd, name, budget)
    value, recipe, baseline = pins(root)
    required = set(baseline) | {'HYPOTHESIS-SCOPE-PINS.json', 'vendor/hypothesis-scope-lab.zip',
               'docs/HYPOTHESIS-SCOPE-LAB-SOURCE-MANIFEST.json', 'snapshots/v012/recipe.json',
               'snapshots/v012/baseline-manifest.json'} | set(value['lab_source_pins'])
    required |= {'snapshots/v012/blobs/' + r['sha256'] for r in recipe['files'] if r['source'] == 'blob'}
    require(required <= set(names), 'release omits baseline/donor/snapshot/lab inputs')
    require('vendor/foundation-math-v012-source.zip' not in names, 'full v0.12 ZIP must not be embedded')
    preservation(root)
    return sources, value


def freeze(root=ROOT):
    sources, value = selected_sources(root)
    obj = {'version': '0.13.0-dev', 'release_variant': 'exact-authored-hypothesis-scope',
           'baseline_manifest_sha256': value['baseline_manifest_sha256'],
           'snapshot_recipe_sha256': value['recipe_sha256'],
           'accepted_lab_manifest_sha256': value['lab_manifest_sha256'],
           'files': {name: s.digest(raw) for name, raw in sources.items()},
           'scope': 'Exact caller-authored premise matching only; no truth, geometry, rule soundness, proof or runtime promotion. Fifteen prior contracts unchanged. Hashes establish integrity, not authenticity.'}
    (root / MANIFEST).write_bytes(s.canonical(obj))
    return obj


def verify(root=ROOT):
    with source_fd(root) as fd:
        raw = s.read_file(fd, MANIFEST, s.Budget(), s.LIMITS['manifest_bytes'])
    obj = s.decode(raw, 'current manifest')
    s.exact_keys(obj, ('version', 'release_variant', 'baseline_manifest_sha256', 'snapshot_recipe_sha256',
                       'accepted_lab_manifest_sha256', 'files', 'scope'), 'current manifest')
    require(raw == s.canonical(obj), 'noncanonical current manifest')
    require(obj['version'] == '0.13.0-dev' and obj['release_variant'] == 'exact-authored-hypothesis-scope', 'current manifest version/variant')
    sources, value = selected_sources(root)
    require(obj['files'] == {name: s.digest(data) for name, data in sources.items()}, 'source manifest drift/selection mismatch')
    require(obj['baseline_manifest_sha256'] == value['baseline_manifest_sha256'] and
            obj['snapshot_recipe_sha256'] == value['recipe_sha256'] and
            obj['accepted_lab_manifest_sha256'] == value['lab_manifest_sha256'], 'current manifest provenance binding')
    return obj


def create_zip(output, root=ROOT):
    obj = verify(root)
    sources, _ = selected_sources(root)
    sources[MANIFEST] = (root / MANIFEST).read_bytes()
    output = Path(output).absolute()
    # The serializer opens exclusively. Also reject every selected path and all
    # symlink parents; no claim of safety against concurrent hostile writers.
    current = Path(output.anchor)
    for part in output.parts[1:-1]:
        current /= part
        require(current.is_dir() and not current.is_symlink(), 'output parent must be real directories')
    require(output not in {(root / n).absolute() for n in sources}, 'output collides with source')
    try:
        hashed, size = s.create_zip(output, sources)
    except BaseException:
        # Do not remove an existing destination on failure. Exclusive open and
        # snapshot serialization own the output only after successful creation.
        raise
    return {'sha256': hashed, 'bytes': size, 'files': len(sources), 'source_manifest_sha256': digest(root / MANIFEST)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.freeze:
        freeze()
    print(s.canonical(create_zip(args.output)).decode(), end='')


if __name__ == '__main__':
    main()

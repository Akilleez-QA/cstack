"""Bounded, offline baseline snapshots. Hashes check bytes, not authenticity or proof.

The CLI only accepts single-component identifiers below this script's work/inputs
and work/outputs. Workspace is a trusted host capability, never recipe-controlled.
No baseline code, archive member or recipe text is executed by this module.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zipfile

SCHEMA = 'foundation-math-baseline-snapshot-v1'
ZIP_PROFILE = 'fm-v011-python-deflate9-fixed-2026-v1'
MANIFEST = 'SOURCE-MANIFEST.json'
RECEIPT_RESERVE = 65536
LIMITS = {
    'file_bytes': 8 * 1024 * 1024,
    'manifest_bytes': 1024 * 1024,
    'recipe_bytes': 2 * 1024 * 1024,
    'source_files': 2048,
    'input_reads': 8192,
    'input_bytes': 64 * 1024 * 1024,
    'output_files': 4096,
    'output_bytes': 64 * 1024 * 1024,
    'snapshot_bytes': 32 * 1024 * 1024,
    'path_bytes': 240,
    'path_depth': 16,
}
HEX = re.compile(r'[0-9a-f]{64}\Z')
IDENT = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')
PART = re.compile(r'[A-Za-z0-9_.-]+\Z')


class SnapshotError(Exception):
    """Closed failure: no fetch, donor search, repinning or fallback."""


def require(ok, message):
    if not ok:
        raise SnapshotError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def canonical(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'duplicate JSON key: ' + key)
        obj[key] = value
    return obj


def finite_float(token):
    value = float(token)
    require(math.isfinite(value), 'nonfinite JSON number after decoding')
    return value


def decode(raw, label):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_float=finite_float,
                          parse_constant=lambda value: (_ for _ in ()).throw(SnapshotError('nonfinite JSON')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SnapshotError('malformed ' + label) from exc


def exact_keys(obj, keys, label):
    require(type(obj) is dict and set(obj) == set(keys), 'unexpected ' + label + ' fields')


def pin(value):
    require(type(value) is str and HEX.fullmatch(value), 'invalid SHA-256 pin')
    return value


def integer(value, maximum, label):
    require(type(value) is int and 0 <= value <= maximum, 'invalid/budget ' + label)
    return value


def name(value):
    require(type(value) is str and value and value.isascii() and len(value) <= LIMITS['path_bytes'], 'invalid path length/type')
    parts = value.split('/')
    require(len(parts) <= LIMITS['path_depth'] and all(p not in ('', '.', '..') and PART.fullmatch(p) for p in parts), 'unsafe relative path')
    return value


def identifier(value):
    require(type(value) is str and IDENT.fullmatch(value), 'invalid workspace identifier')
    return value


def paths(values):
    require(type(values) is list and 0 < len(values) <= LIMITS['source_files'], 'source file count budget')
    for value in values:
        name(value)
    require(values == sorted(set(values)), 'unsorted/duplicate source paths')
    known = set(values)
    for value in values:
        parts = value.split('/')
        require(all('/'.join(parts[:i]) not in known for i in range(1, len(parts))), 'file/directory path collision')
    require(MANIFEST not in known, 'manifest cannot pin itself')


def source_manifest(raw, expected):
    require(digest(raw) == pin(expected), 'source manifest pin mismatch')
    obj = decode(raw, 'source manifest')
    require(type(obj) is dict and type(obj.get('files')) is dict, 'invalid source manifest')
    paths(list(obj['files']))
    for value in obj['files'].values():
        pin(value)
    return obj['files']


class Budget:
    def __init__(self):
        self.reads = 0
        self.bytes = 0

    def charge(self, size):
        self.reads += 1
        self.bytes += size
        require(self.reads <= LIMITS['input_reads'] and self.bytes <= LIMITS['input_bytes'], 'input budget exceeded')


DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


@contextmanager
def directory(root_fd, relative):
    """Traverse only rooted descriptor-relative directories; never follow symlinks."""
    name(relative)
    fd = os.dup(root_fd)
    try:
        for part in relative.split('/'):
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_file(root_fd, relative, budget, maximum=None):
    name(relative)
    maximum = LIMITS['file_bytes'] if maximum is None else maximum
    parts = relative.split('/')
    with directory(root_fd, '/'.join(parts[:-1])) if len(parts) > 1 else duplicate_dir(root_fd) as parent:
        fd = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode), 'input is not a regular file')
            require(before.st_nlink == 1, 'hard-linked input rejected')
            require(0 <= before.st_size <= maximum, 'input file byte budget')
            budget.charge(before.st_size)
            with os.fdopen(os.dup(fd), 'rb') as f:
                raw = f.read(before.st_size)
            after = os.fstat(fd)
            require(len(raw) == before.st_size and (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'input changed during read')
            return raw
        finally:
            os.close(fd)


@contextmanager
def duplicate_dir(fd):
    copy = os.dup(fd)
    try:
        yield copy
    finally:
        os.close(copy)


def inventory(fd):
    """Bounded inventory of a snapshot only; detects extra paths and symlinks."""
    files, dirs = set(), set()
    def walk(current, prefix=''):
        for entry in os.scandir(current):
            relative = prefix + entry.name
            name(relative)
            require(len(files) + len(dirs) < LIMITS['output_files'], 'snapshot inventory count budget')
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                dirs.add(relative)
                with directory(current, entry.name) as child:
                    walk(child, relative + '/')
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'snapshot nonregular entry')
                files.add(relative)
    walk(fd)
    return files, dirs


def expected_dirs(files):
    return {'/'.join(p.split('/')[:i]) for p in files for i in range(1, len(p.split('/')))}


class Workspace:
    """Trusted host creates a workspace; recipes cannot choose or escape its root."""
    def __init__(self, root):
        self.root = Path(root)
        # Require an absolute, already-created workspace with no symlink ancestors.
        require(self.root.is_absolute(), 'workspace must be an absolute trusted root')
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            require(not current.is_symlink() and current.is_dir(), 'workspace must be real directories')
        self.fd = os.open(self.root, DIR_FLAGS)
        try:
            for section in ('inputs', 'outputs'):
                with directory(self.fd, section):
                    pass
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def input(self, label):
        with directory(self.fd, 'inputs/' + identifier(label)) as fd:
            yield fd

    @contextmanager
    def transaction(self, label):
        """Publish one directory after all checks; never modify an existing target.

        Rename is atomic on this workspace filesystem. Concurrent hostile mutation
        of the trusted workspace/output parent is out of scope. Read-side path
        traversal and symlinks are still rejected with no-follow descriptors.
        """
        identifier(label)
        with directory(self.fd, 'outputs') as outputs:
            require(label not in os.listdir(outputs), 'destination already exists')
            stage_name = '.stage-' + next(tempfile._get_candidate_names())
            os.mkdir(stage_name, 0o700, dir_fd=outputs)
            stage = self.root / 'outputs' / stage_name
            try:
                yield stage
                require(label not in os.listdir(outputs), 'destination appeared before commit')
                # A directory cannot replace a nonempty directory (or any regular
                # file), even if one appears after the preceding existence check.
                os.rename(stage_name, label, src_dir_fd=outputs, dst_dir_fd=outputs)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)


def write_tree(root, files, maximum=LIMITS['output_bytes']):
    require(len(files) + len(expected_dirs(files)) <= LIMITS['output_files'] and sum(map(len, files.values())) <= maximum, 'output budget exceeded')
    for path, raw in sorted(files.items()):
        name(path)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(raw)


class BoundedWriter:
    """Stop ZIP writes before crossing the explicit output byte budget."""
    def __init__(self, file, maximum):
        self.file, self.maximum = file, maximum

    def write(self, data):
        require(self.file.tell() + len(data) <= self.maximum, 'archive output byte budget')
        return self.file.write(data)

    def tell(self):
        return self.file.tell()

    def seek(self, *args):
        return self.file.seek(*args)

    def flush(self):
        return self.file.flush()


def create_zip(path, files, maximum=None):
    """Fixed serializer matches the unchanged frozen v0.11 release builder.

    Deflate implementation differences are NOT assumed safe: the independently
    supplied expected original archive hash must match before commit.
    """
    maximum = LIMITS['output_bytes'] if maximum is None else maximum
    with path.open('xb') as file:
        with zipfile.ZipFile(BoundedWriter(file, maximum), 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for filename, raw in sorted(files.items()):
                info = zipfile.ZipInfo(filename, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                z.writestr(info, raw, compresslevel=9)
    require(path.stat().st_size <= maximum, 'archive output budget')
    return digest(path.read_bytes()), path.stat().st_size


def check_sources(fd, raw, expected, budget):
    pins = source_manifest(raw, expected)
    result = {}
    for path, expected_hash in pins.items():
        data = read_file(fd, path, budget)
        require(digest(data) == expected_hash, 'source drift: ' + path)
        result[path] = data
    return result


def build(workspace, base, donor, output, *, baseline_manifest_sha256,
          baseline_archive_sha256, baseline_archive_bytes, donor_manifest_sha256):
    """Generate one snapshot from a historical root and a selected candidate root."""
    for expected in (baseline_manifest_sha256, baseline_archive_sha256, donor_manifest_sha256):
        pin(expected)
    integer(baseline_archive_bytes, LIMITS['output_bytes'], 'archive bytes')
    budget = Budget()
    with workspace.input(base) as base_fd, workspace.input(donor) as donor_fd:
        manifest = read_file(base_fd, MANIFEST, budget, LIMITS['manifest_bytes'])
        donor_manifest = read_file(donor_fd, MANIFEST, budget, LIMITS['manifest_bytes'])
        old = check_sources(base_fd, manifest, baseline_manifest_sha256, budget)
        new = check_sources(donor_fd, donor_manifest, donor_manifest_sha256, budget)
    rows, blobs = [], {}
    for path, raw in sorted(old.items()):
        hashed = digest(raw)
        source = 'donor' if new.get(path) == raw else 'blob'
        rows.append({'path': path, 'sha256': hashed, 'bytes': len(raw), 'source': source})
        if source == 'blob':
            blobs['blobs/' + hashed] = raw
    recipe = {
        'schema': SCHEMA, 'zip_profile': ZIP_PROFILE,
        'baseline_manifest_sha256': baseline_manifest_sha256,
        'baseline_archive_sha256': baseline_archive_sha256,
        'baseline_archive_bytes': baseline_archive_bytes,
        'donor_projection_sha256': digest(canonical({r['path']: r['sha256'] for r in rows if r['source'] == 'donor'})),
        'files': rows,
    }
    recipe_raw = canonical(recipe)
    require(len(recipe_raw) <= LIMITS['recipe_bytes'], 'recipe byte budget')
    package = {'recipe.json': recipe_raw, 'baseline-manifest.json': manifest, **blobs}
    # A successful producer must satisfy the SAME fixed replay eligibility
    # checks as the consumer, before any snapshot can be published.
    validated = validate_recipe(recipe_raw, digest(recipe_raw), baseline_manifest_sha256, baseline_archive_sha256)
    eligibility = replay_eligibility(validated, len(recipe_raw), len(manifest))
    # Gate the supplied archive pin against baseline bytes before publishing any
    # recipe. This archive is temporary and not included in the snapshot.
    with workspace.transaction(output) as stage:
        archive = stage / 'checking.zip'
        actual, size = create_zip(archive, {**old, MANIFEST: manifest}, eligibility['archive_byte_budget'])
        require((actual, size) == (baseline_archive_sha256, baseline_archive_bytes), 'baseline archive identity mismatch')
        archive.unlink()
        write_tree(stage, package, LIMITS['snapshot_bytes'])
    return {
        'recipe_sha256': digest(recipe_raw),
        'baseline_manifest_sha256': baseline_manifest_sha256,
        'baseline_archive_sha256': baseline_archive_sha256,
        'baseline_archive_bytes': baseline_archive_bytes,
        'donor_manifest_sha256': donor_manifest_sha256,
        'source_files': len(rows), 'donor_files': sum(x['source'] == 'donor' for x in rows),
        'blob_files': len(blobs), 'blob_bytes': sum(map(len, blobs.values())),
        'snapshot_files': len(package), 'snapshot_raw_bytes': sum(map(len, package.values())),
        'input_reads': budget.reads, 'input_bytes': budget.bytes,
    }


def validate_recipe(raw, expected_recipe, expected_manifest, expected_archive):
    require(digest(raw) == pin(expected_recipe), 'recipe pin mismatch')
    recipe = decode(raw, 'recipe')
    exact_keys(recipe, ('schema', 'zip_profile', 'baseline_manifest_sha256', 'baseline_archive_sha256',
                       'baseline_archive_bytes', 'donor_projection_sha256', 'files'), 'recipe')
    require(raw == canonical(recipe), 'noncanonical recipe')
    require(recipe['schema'] == SCHEMA and recipe['zip_profile'] == ZIP_PROFILE, 'unsupported recipe/profile')
    require(recipe['baseline_manifest_sha256'] == pin(expected_manifest), 'baseline manifest binding')
    require(recipe['baseline_archive_sha256'] == pin(expected_archive), 'baseline archive binding')
    pin(recipe['donor_projection_sha256'])
    integer(recipe['baseline_archive_bytes'], LIMITS['output_bytes'], 'archive bytes')
    rows = recipe['files']
    require(type(rows) is list and 0 < len(rows) <= LIMITS['source_files'], 'recipe file count budget')
    blob_sizes = {}
    for row in rows:
        exact_keys(row, ('path', 'sha256', 'bytes', 'source'), 'file row')
        name(row['path']); pin(row['sha256'])
        integer(row['bytes'], LIMITS['file_bytes'], 'file bytes')
        require(type(row['source']) is str and row['source'] in ('donor', 'blob'), 'invalid source selector')
        if row['sha256'] in blob_sizes:
            require(blob_sizes[row['sha256']] == row['bytes'], 'ambiguous size for content pin')
        blob_sizes[row['sha256']] = row['bytes']
    paths([r['path'] for r in rows])
    require(recipe['donor_projection_sha256'] == digest(canonical({r['path']: r['sha256'] for r in rows if r['source'] == 'donor'})), 'donor projection binding')
    return recipe


def replay_eligibility(recipe, recipe_bytes, manifest_bytes):
    """Shared build/restore budget gate, using exact recipe inventory and sizes.

    This preflight never raises a limit. It retains the previous conservative
    manifest-byte reserve and also checks the actual manifest plus receipt reserve,
    full restored files/directories, snapshot membership, and planned input reads.
    Content hashes and actual lengths are still verified separately before commit.
    """
    integer(recipe_bytes, LIMITS['recipe_bytes'], 'recipe bytes')
    integer(manifest_bytes, LIMITS['manifest_bytes'], 'manifest bytes')
    rows = recipe['files']
    total = sum(row['bytes'] for row in rows)
    source_names = {row['path'] for row in rows} | {MANIFEST}
    restored_entries = len(source_names) + len(expected_dirs(source_names)) + 3
    require(restored_entries <= LIMITS['output_files'], 'restored output entry budget')
    require(total + recipe['baseline_archive_bytes'] + LIMITS['manifest_bytes'] <= LIMITS['output_bytes'], 'restored output byte budget')
    source_bytes = total + manifest_bytes
    archive_byte_budget = LIMITS['output_bytes'] - source_bytes - RECEIPT_RESERVE
    require(recipe['baseline_archive_bytes'] <= archive_byte_budget, 'restored source/archive/receipt byte budget')
    blob_sizes = {row['sha256']: row['bytes'] for row in rows if row['source'] == 'blob'}
    donor_rows = [row for row in rows if row['source'] == 'donor']
    snapshot_names = {'recipe.json', 'baseline-manifest.json'} | {'blobs/' + pin for pin in blob_sizes}
    snapshot_entries = len(snapshot_names) + len(expected_dirs(snapshot_names))
    require(snapshot_entries <= LIMITS['output_files'], 'snapshot inventory count budget')
    snapshot_bytes = recipe_bytes + manifest_bytes + sum(blob_sizes.values())
    require(snapshot_bytes <= LIMITS['snapshot_bytes'], 'snapshot byte budget')
    input_reads = 2 + len(donor_rows) + len(blob_sizes)
    input_bytes = snapshot_bytes + sum(row['bytes'] for row in donor_rows)
    require(input_reads <= LIMITS['input_reads'] and input_bytes <= LIMITS['input_bytes'], 'replay input budget exceeded')
    return {'archive_byte_budget': archive_byte_budget, 'restored_entries': restored_entries,
            'source_bytes': source_bytes, 'input_reads': input_reads, 'input_bytes': input_bytes}


def restore(workspace, snapshot, donor, output, *, recipe_sha256,
            baseline_manifest_sha256, baseline_archive_sha256):
    """Materialize exact historical sources plus exact original ZIP, or no output."""
    budget = Budget()
    with workspace.input(snapshot) as snapshot_fd, workspace.input(donor) as donor_fd:
        raw_recipe = read_file(snapshot_fd, 'recipe.json', budget, LIMITS['recipe_bytes'])
        recipe = validate_recipe(raw_recipe, recipe_sha256, baseline_manifest_sha256, baseline_archive_sha256)
        raw_manifest = read_file(snapshot_fd, 'baseline-manifest.json', budget, LIMITS['manifest_bytes'])
        pins = source_manifest(raw_manifest, baseline_manifest_sha256)
        require({r['path']: r['sha256'] for r in recipe['files']} == pins, 'recipe differs from baseline source manifest')
        eligibility = replay_eligibility(recipe, len(raw_recipe), len(raw_manifest))
        expected_files = {'recipe.json', 'baseline-manifest.json'} | {
            'blobs/' + r['sha256'] for r in recipe['files'] if r['source'] == 'blob'}
        actual_files, actual_dirs = inventory(snapshot_fd)
        require(actual_files == expected_files and actual_dirs == expected_dirs(expected_files), 'snapshot exact inventory mismatch')
        files, blobs = {}, {}
        for row in recipe['files']:
            path, expected = row['path'], row['sha256']
            if row['source'] == 'donor':
                raw = read_file(donor_fd, path, budget)
            else:
                # No fallback to a donor, even if matching bytes happen to exist.
                if expected not in blobs:
                    blobs[expected] = read_file(snapshot_fd, 'blobs/' + expected, budget)
                raw = blobs[expected]
            require(len(raw) == row['bytes'] and digest(raw) == expected, 'restoration content mismatch: ' + path)
            files[path] = raw
        files[MANIFEST] = raw_manifest
        require((budget.reads, budget.bytes) == (eligibility['input_reads'], eligibility['input_bytes']), 'replay input accounting mismatch')
    with workspace.transaction(output) as stage:
        write_tree(stage / 'restored', files)
        hashed, size = create_zip(stage / 'baseline.zip', files, eligibility['archive_byte_budget'])
        require((hashed, size) == (baseline_archive_sha256, recipe['baseline_archive_bytes']), 'regenerated original ZIP mismatch')
        receipt = {
            'status': 'pass', 'source_manifest_sha256': digest(raw_manifest),
            'source_files': len(files) - 1, 'source_bytes_including_manifest': sum(map(len, files.values())),
            'baseline_archive_sha256': hashed, 'baseline_archive_bytes': size,
            'recipe_sha256': recipe_sha256, 'donor_projection_sha256': recipe['donor_projection_sha256'],
            'input_reads': budget.reads, 'input_bytes': budget.bytes,
            'scope': 'Byte integrity and deterministic reconstruction only; not authenticity, proof, mathematical truth or release approval.',
        }
        encoded = canonical(receipt)
        require(len(encoded) <= RECEIPT_RESERVE, 'receipt byte reserve')
        require(sum(map(len, files.values())) + size + len(encoded) <= LIMITS['output_bytes'] and len(files) + len(expected_dirs(files)) + 3 <= LIMITS['output_files'], 'total output budget')
        write_tree(stage, {'receipt.json': encoded})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('build', 'restore'):
        p = sub.add_parser(command)
        p.add_argument('--donor', required=True)
        p.add_argument('--output', required=True)
        p.add_argument('--baseline-manifest-sha256', required=True)
        p.add_argument('--baseline-archive-sha256', required=True)
        if command == 'build':
            p.add_argument('--base', required=True)
            p.add_argument('--donor-manifest-sha256', required=True)
            p.add_argument('--baseline-archive-bytes', required=True, type=int)
        else:
            p.add_argument('--snapshot', required=True)
            p.add_argument('--recipe-sha256', required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    try:
        with Workspace(Path(__file__).absolute().parent / 'work') as workspace:
            result = (build if command == 'build' else restore)(workspace, **args)
        print(canonical(result).decode(), end='')
    except (SnapshotError, OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, 'snapshot rejected: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()

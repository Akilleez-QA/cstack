"""Adversarial bounded snapshots; unittest checks remain active under python -O."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import snapshot as s


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'inputs').mkdir()
        (self.root / 'outputs').mkdir()
        self.old = {'a.txt': b'unchanged\n', 'dir/change.txt': b'old value\n',
                    'dir/remove.txt': b'old value\n', 'empty.txt': b''}
        self.new = {'a.txt': b'unchanged\n', 'dir/change.txt': b'new value\n',
                    'empty.txt': b'', 'new.txt': b'new addition\n'}
        self.manifest = self.tree('base', self.old)
        self.donor_manifest = self.tree('donor', self.new)
        self.mpin = s.digest(self.manifest)
        self.zpin, self.zbytes = s.create_zip(self.root / 'original.zip', {**self.old, s.MANIFEST: self.manifest})
        self.workspace = s.Workspace(self.root)
        self.addCleanup(self.workspace.close)
        self.built = self.build('built')
        shutil.copytree(self.root / 'outputs/built', self.root / 'inputs/snapshot')
        self.recipe_pin = self.built['recipe_sha256']

    def tree(self, label, files):
        root = self.root / 'inputs' / label
        root.mkdir()
        s.write_tree(root, files)
        raw = s.canonical({'schema': 'test-source-v1', 'files': {k: s.digest(v) for k, v in sorted(files.items())}})
        (root / s.MANIFEST).write_bytes(raw)
        return raw

    def build(self, output, **options):
        args = dict(baseline_manifest_sha256=self.mpin, baseline_archive_sha256=self.zpin,
                    baseline_archive_bytes=self.zbytes, donor_manifest_sha256=s.digest(self.donor_manifest))
        args.update(options)
        return s.build(self.workspace, 'base', 'donor', output, **args)

    def restore(self, output='restored', **options):
        args = dict(recipe_sha256=self.recipe_pin, baseline_manifest_sha256=self.mpin, baseline_archive_sha256=self.zpin)
        args.update(options)
        return s.restore(self.workspace, 'snapshot', 'donor', output, **args)

    def recipe(self):
        return json.loads((self.root / 'inputs/snapshot/recipe.json').read_text())

    def change_recipe(self, mutate, repin=True):
        value = self.recipe()
        mutate(value)
        raw = s.canonical(value)
        (self.root / 'inputs/snapshot/recipe.json').write_bytes(raw)
        if repin:
            self.recipe_pin = s.digest(raw)

    def rejected(self, operation=None):
        with self.assertRaises((s.SnapshotError, OSError)):
            (operation or self.restore)()
        self.assertFalse((self.root / 'outputs/restored').exists())
        self.assertFalse(any(p.name.startswith('.stage-') for p in (self.root / 'outputs').iterdir()))

    def test_exact_roundtrip_and_zip(self):
        receipt = self.restore()
        restored = self.root / 'outputs/restored/restored'
        self.assertEqual((self.root / 'outputs/restored/baseline.zip').read_bytes(), (self.root / 'original.zip').read_bytes())
        self.assertEqual({p.relative_to(restored).as_posix(): p.read_bytes() for p in restored.rglob('*') if p.is_file()}, {**self.old, s.MANIFEST: self.manifest})
        self.assertEqual(receipt['source_manifest_sha256'], self.mpin)
        self.assertEqual(receipt['status'], 'pass')

    def test_blob_dedup_and_changed_removed_added(self):
        self.assertEqual(self.built['blob_files'], 1)
        self.assertEqual(self.built['blob_bytes'], len(self.old['dir/change.txt']))
        self.assertEqual(self.built['donor_files'], 2)
        self.restore()
        self.assertFalse((self.root / 'outputs/restored/restored/new.txt').exists())

    def test_deterministic_build_and_restore(self):
        again = self.build('again')
        self.assertEqual(again, self.built)
        for p in (self.root / 'outputs/built').rglob('*'):
            if p.is_file():
                self.assertEqual(p.read_bytes(), (self.root / 'outputs/again' / p.relative_to(self.root / 'outputs/built')).read_bytes())
        self.assertEqual(self.restore(), self.restore('second'))

    def test_minimal_replay_needs_no_baseline_or_donor_manifest(self):
        shutil.rmtree(self.root / 'inputs/base')
        (self.root / 'original.zip').unlink()
        (self.root / 'inputs/donor/SOURCE-MANIFEST.json').unlink()
        (self.root / 'inputs/donor/new.txt').unlink()
        (self.root / 'inputs/donor/dir/change.txt').unlink()
        self.restore()

    def test_unselected_candidate_edits_are_irrelevant_not_hidden_repin(self):
        (self.root / 'inputs/donor/new.txt').write_bytes(b'different unselected addition')
        self.restore()

    def test_tampered_recipe(self):
        self.change_recipe(lambda r: r.update(zip_profile='different'), repin=False)
        self.rejected()

    def test_missing_recipe(self):
        (self.root / 'inputs/snapshot/recipe.json').unlink()
        self.rejected()

    def test_duplicate_json_keys(self):
        raw = b'{"schema":"x","schema":"y"}'
        (self.root / 'inputs/snapshot/recipe.json').write_bytes(raw)
        self.recipe_pin = s.digest(raw)
        self.rejected()

    def test_malformed_and_nonfinite_recipe(self):
        for raw in (b'{', b'\xff', b'{"value":NaN}', b'[]', b'null', b'[' * 2000):
            with self.subTest(raw=raw[:20]):
                (self.root / 'inputs/snapshot/recipe.json').write_bytes(raw)
                self.recipe_pin = s.digest(raw)
                self.rejected()

    def test_noncanonical_recipe(self):
        raw = json.dumps(self.recipe()).encode()
        (self.root / 'inputs/snapshot/recipe.json').write_bytes(raw)
        self.recipe_pin = s.digest(raw)
        self.rejected()

    def test_unknown_recipe_field(self):
        self.change_recipe(lambda r: r.update(fallback_url='https://example.invalid'))
        self.rejected()

    def test_stale_baseline_manifest_pin(self):
        self.rejected(lambda: self.restore(baseline_manifest_sha256='0' * 64))

    def test_stale_archive_pin(self):
        self.rejected(lambda: self.restore(baseline_archive_sha256='0' * 64))

    def test_wrong_archive_size_is_atomic(self):
        self.change_recipe(lambda r: r.update(baseline_archive_bytes=r['baseline_archive_bytes'] + 1))
        self.rejected()

    def test_stale_donor_projection(self):
        self.change_recipe(lambda r: r.update(donor_projection_sha256='0' * 64))
        self.rejected()

    def test_tampered_donor(self):
        (self.root / 'inputs/donor/a.txt').write_bytes(b'wrongdata\n')
        self.rejected()

    def test_missing_donor_no_blob_fallback(self):
        (self.root / 'inputs/donor/a.txt').unlink()
        (self.root / 'inputs/snapshot/blobs' / s.digest(self.old['a.txt'])).write_bytes(self.old['a.txt'])
        self.rejected()

    def test_tampered_blob(self):
        blob = next((self.root / 'inputs/snapshot/blobs').iterdir())
        blob.write_bytes(b'bad value\n')
        self.rejected()

    def test_missing_blob_no_donor_fallback(self):
        next((self.root / 'inputs/snapshot/blobs').iterdir()).unlink()
        (self.root / 'inputs/donor/dir/change.txt').write_bytes(self.old['dir/change.txt'])
        (self.root / 'inputs/donor/dir/remove.txt').write_bytes(self.old['dir/remove.txt'])
        self.rejected()

    def test_stale_blob_name(self):
        blob = next((self.root / 'inputs/snapshot/blobs').iterdir())
        blob.rename(blob.parent / ('0' * 64))
        self.rejected()

    def test_tampered_baseline_manifest(self):
        path = self.root / 'inputs/snapshot/baseline-manifest.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.rejected()

    def test_duplicate_manifest_pin(self):
        raw = ('{"files":{"a.txt":"' + '0' * 64 + '","a.txt":"' + '1' * 64 + '"}}').encode()
        (self.root / 'inputs/snapshot/baseline-manifest.json').write_bytes(raw)
        self.mpin = s.digest(raw)
        self.change_recipe(lambda r: r.update(baseline_manifest_sha256=self.mpin))
        self.rejected()

    def test_duplicate_rows(self):
        self.change_recipe(lambda r: r['files'].append(copy.deepcopy(r['files'][0])))
        self.rejected()

    def test_ambiguous_size_same_pin(self):
        self.change_recipe(lambda r: r['files'][2].update(bytes=999))
        self.rejected()

    def test_wrong_row_pin_cannot_replace_historical_bytes(self):
        self.change_recipe(lambda r: r['files'][1].update(sha256='0' * 64))
        self.rejected()

    def test_unsafe_recipe_paths(self):
        original = (self.root / 'inputs/snapshot/recipe.json').read_bytes()
        for value in ('../escape', '/absolute', 'a/../../bad', 'a\\b', 'a//b', 'a/./b', '', 'C:/path', 'a\x00b', 'é', 'a/' * 17 + 'b'):
            with self.subTest(path=value):
                (self.root / 'inputs/snapshot/recipe.json').write_bytes(original)
                self.change_recipe(lambda r: r['files'][0].update(path=value))
                self.rejected()

    def test_path_collision(self):
        raw = s.canonical({'files': {'a': '0' * 64, 'a/b': '0' * 64}})
        with self.assertRaises(s.SnapshotError):
            s.source_manifest(raw, s.digest(raw))

    def test_boolean_or_negative_size(self):
        original = (self.root / 'inputs/snapshot/recipe.json').read_bytes()
        for value in (True, -1, 1.5, '10', 8388609):
            (self.root / 'inputs/snapshot/recipe.json').write_bytes(original)
            self.change_recipe(lambda r: r['files'][0].update(bytes=value))
            self.rejected()

    def test_extra_snapshot_file_and_directory(self):
        extra = self.root / 'inputs/snapshot/extra'
        extra.write_bytes(b'x')
        self.rejected()
        extra.unlink()
        extra.mkdir()
        self.rejected()

    def test_symlink_donor_file(self):
        target = self.root / 'inputs/donor/a.txt'
        target.unlink()
        target.symlink_to(self.root / 'inputs/base/a.txt')
        self.rejected()

    def test_symlink_donor_parent(self):
        target = self.root / 'inputs/donor'
        target.rename(self.root / 'inputs/real-donor')
        target.symlink_to(self.root / 'inputs/real-donor', target_is_directory=True)
        self.rejected()

    def test_symlink_blob(self):
        blob = next((self.root / 'inputs/snapshot/blobs').iterdir())
        blob.unlink()
        blob.symlink_to(self.root / 'inputs/base/dir/change.txt')
        self.rejected()

    def test_hardlink_donor_rejected(self):
        target = self.root / 'inputs/donor/a.txt'
        target.unlink()
        os.link(self.root / 'inputs/base/a.txt', target)
        self.rejected()

    def test_fifo_and_directory_donor_do_not_block(self):
        target = self.root / 'inputs/donor/a.txt'
        target.unlink()
        os.mkfifo(target)
        self.rejected()
        target.unlink()
        target.mkdir()
        self.rejected()

    def test_unrestricted_identifiers_rejected(self):
        for value in ('../escape', '/tmp/escape', 'A', 'a/b', '', 'a' * 65):
            with self.subTest(value=value):
                self.rejected(lambda: self.restore(output=value))

    def test_existing_nonempty_destination_preserved(self):
        target = self.root / 'outputs/restored'
        target.mkdir()
        (target / 'precious.txt').write_bytes(b'keep me')
        with self.assertRaises(s.SnapshotError):
            self.restore()
        self.assertEqual((target / 'precious.txt').read_bytes(), b'keep me')
        self.assertEqual([p.name for p in target.iterdir()], ['precious.txt'])

    def test_existing_empty_destination_also_rejected(self):
        (self.root / 'outputs/restored').mkdir()
        with self.assertRaises(s.SnapshotError):
            self.restore()

    def test_destination_symlink_preserved(self):
        (self.root / 'outputs/restored').symlink_to(self.root / 'inputs/base', target_is_directory=True)
        with self.assertRaises(s.SnapshotError):
            self.restore()
        self.assertTrue((self.root / 'outputs/restored').is_symlink())

    def test_output_appears_before_commit(self):
        real_zip = s.create_zip
        target = self.root / 'outputs/restored'
        def collision(*args, **kwargs):
            result = real_zip(*args, **kwargs)
            target.mkdir()
            (target / 'precious').write_bytes(b'keep')
            return result
        with mock.patch.object(s, 'create_zip', collision):
            with self.assertRaises(s.SnapshotError):
                self.restore()
        self.assertEqual((target / 'precious').read_bytes(), b'keep')
        self.assertFalse(any(p.name.startswith('.stage-') for p in (self.root / 'outputs').iterdir()))

    def test_write_failure_atomic(self):
        real_write = s.write_tree
        def fail(root, files, *args):
            real_write(root, files, *args)
            raise OSError('synthetic interrupted write')
        with mock.patch.object(s, 'write_tree', fail):
            self.rejected()

    def test_build_donor_manifest_stale(self):
        (self.root / 'inputs/donor/new.txt').write_bytes(b'stale candidate')
        self.rejected(lambda: self.build('restored'))

    def test_build_wrong_archive_and_source_pins_atomic(self):
        self.rejected(lambda: self.build('restored', baseline_archive_sha256='0' * 64))
        self.rejected(lambda: self.build('restored', baseline_manifest_sha256='0' * 64))

    def test_per_file_input_budget(self):
        path = self.root / 'inputs/donor/a.txt'
        with path.open('wb') as f:
            f.truncate(s.LIMITS['file_bytes'] + 1)
        self.rejected()

    def test_total_input_budget(self):
        with mock.patch.dict(s.LIMITS, {'input_bytes': 1}):
            self.rejected()

    def test_input_read_count_budget(self):
        with mock.patch.dict(s.LIMITS, {'input_reads': 1}):
            self.rejected()

    def test_recipe_metadata_budget(self):
        with mock.patch.dict(s.LIMITS, {'recipe_bytes': 1}):
            self.rejected()

    def test_source_file_count_budget(self):
        with mock.patch.dict(s.LIMITS, {'source_files': 1}):
            self.rejected()

    def test_total_output_budget(self):
        with mock.patch.dict(s.LIMITS, {'output_bytes': 1}):
            self.rejected()

    def test_snapshot_budget(self):
        with mock.patch.dict(s.LIMITS, {'snapshot_bytes': 1}):
            self.rejected()

    def test_zip_write_capped_before_byte_limit(self):
        target = self.root / 'capped.zip'
        with self.assertRaises(s.SnapshotError):
            s.create_zip(target, self.old, maximum=10)
        self.assertLessEqual(target.stat().st_size, 10)

    def test_inventory_entry_count_budget(self):
        with mock.patch.dict(s.LIMITS, {'output_files': 2}):
            self.rejected()

    def test_missing_baseline_manifest(self):
        (self.root / 'inputs/snapshot/baseline-manifest.json').unlink()
        self.rejected()

    def test_missing_row(self):
        self.change_recipe(lambda r: r['files'].pop(1))
        self.rejected()

    def test_unknown_source_type(self):
        self.change_recipe(lambda r: r['files'][1].update(source='fallback'))
        self.rejected()

    def test_lone_surrogate_path_rejected_cleanly(self):
        self.change_recipe(lambda r: r['files'][0].update(path='\ud800'))
        self.rejected()

    def test_manifest_exponent_overflow_rejected(self):
        for token in ('1e400', '-1e400', '1.7976931348623159e308'):
            with self.subTest(token=token):
                raw = ('{"files":{"a":"' + '0' * 64 +
                       '"},"metadata":{"nested":[{"value":' + token + '}]}}').encode()
                with self.assertRaisesRegex(s.SnapshotError, 'nonfinite JSON'):
                    s.source_manifest(raw, s.digest(raw))

    def test_finite_float_metadata_accepted_without_rewriting_raw(self):
        raw = ('{"files":{"a":"' + '0' * 64 +
               '"},"metadata":{"value":1e308}}').encode()
        self.assertEqual(s.source_manifest(raw, s.digest(raw)), {'a': '0' * 64})
        self.assertEqual(s.decode(raw, 'manifest')['metadata']['value'], 1e308)

    def test_build_overflow_manifest_rejected_atomically(self):
        obj = json.loads(self.manifest)
        raw = s.canonical(obj).rstrip()[:-1] + b',"metadata":{"value":1e400}}'
        (self.root / 'inputs/base/SOURCE-MANIFEST.json').write_bytes(raw)
        with self.assertRaisesRegex(s.SnapshotError, 'nonfinite JSON'):
            self.build('restored', baseline_manifest_sha256=s.digest(raw))
        self.assertFalse((self.root / 'outputs/restored').exists())
        self.assertFalse(list((self.root / 'outputs').glob('.stage-*')))

    def check_production_budget_rejection(self, old, new, reason):
        # These fixtures deliberately exceed future restore budgets, not input
        # file-count/path limits. Populate trusted test inputs directly rather
        # than using the production output writer to construct a bad input tree.
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'inputs').mkdir()
            (root / 'outputs').mkdir()
            manifests = []
            for label, files in (('base', old), ('donor', new)):
                raw = s.canonical({'files': {p: s.digest(b) for p, b in sorted(files.items())}})
                manifests.append(raw)
                for path, data in {**files, s.MANIFEST: raw}.items():
                    target = root / 'inputs' / label / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            archive_pin, archive_bytes = s.create_zip(root / 'historical.zip', {**old, s.MANIFEST: manifests[0]})
            with s.Workspace(root) as workspace:
                with self.assertRaisesRegex(s.SnapshotError, reason):
                    s.build(workspace, 'base', 'donor', 'snapshot',
                        baseline_manifest_sha256=s.digest(manifests[0]),
                        baseline_archive_sha256=archive_pin,
                        baseline_archive_bytes=archive_bytes,
                        donor_manifest_sha256=s.digest(manifests[1]))
            self.assertFalse((root / 'outputs/snapshot').exists())
            self.assertEqual(list((root / 'outputs').iterdir()), [])
            return len(old) + 1 + len(s.expected_dirs(set(old) | {s.MANIFEST})) + 3

    def test_build_rejects_actual_64mib_restore_byte_budget(self):
        from hashlib import shake_256
        old = {f'old/{i}': shake_256(('budget-regression-' + str(i)).encode()).digest(7 * 1024 * 1024)
               for i in range(4)}
        new = {f'keep/{i}': bytes([65 + i]) * (5 * 1024 * 1024) for i in range(3)}
        old.update(new)
        self.assertEqual(s.LIMITS['output_bytes'], 64 * 1024 * 1024)
        self.assertEqual(s.LIMITS['snapshot_bytes'], 32 * 1024 * 1024)
        self.check_production_budget_rejection(old, new, 'restored output byte budget')

    def test_build_rejects_actual_4096_restore_entry_budget(self):
        old = {'/'.join(f'd{i}_{j}' for j in range(7)) + '/file': b'' for i in range(600)}
        self.assertEqual(s.LIMITS['output_files'], 4096)
        entries = self.check_production_budget_rejection(old, old, 'restored output entry budget')
        self.assertEqual(entries, 4804)

    def test_build_and_restore_call_same_preflight(self):
        with mock.patch.object(s, 'replay_eligibility', wraps=s.replay_eligibility) as gate:
            self.build('shared-gate-build')
            self.restore()
        self.assertEqual(gate.call_count, 2)
        self.assertEqual(gate.call_args_list[0], gate.call_args_list[1])

    def test_actual_manifest_plus_receipt_reserve_also_checked(self):
        recipe = self.recipe()
        total = sum(row['bytes'] for row in recipe['files'])
        # The old conservative 1 MiB manifest check alone fits exactly, but the
        # actual 1 MiB manifest still needs the unchanged 65,536-byte reserve.
        cap = total + recipe['baseline_archive_bytes'] + s.LIMITS['manifest_bytes']
        with mock.patch.dict(s.LIMITS, {'output_bytes': cap}):
            with self.assertRaisesRegex(s.SnapshotError, 'source/archive/receipt'):
                s.replay_eligibility(recipe, len(s.canonical(recipe)), s.LIMITS['manifest_bytes'])
        self.assertEqual(s.RECEIPT_RESERVE, 65536)

    def test_no_runtime_assertions(self):
        import ast
        tree = ast.parse(Path(s.__file__).read_text())
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main(verbosity=2)

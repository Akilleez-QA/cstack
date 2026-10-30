"""Packaging integration tests; never mutate the selected source or frozen inputs."""
from pathlib import Path
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from baseline_snapshot import snapshot as s
from tools import build_hypothesis_scope_release as b
from tools import hypothesis_scope_release_support as r
from tools.run_snapshot_validation import privacy

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'selected'
        self.root.mkdir()
        names = json.loads((ROOT / 'RELEASE-FILES.json').read_bytes())['files']
        for name in [*names, 'SOURCE-MANIFEST.json']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())

    def test_selected_source_verified(self):
        self.assertEqual(b.verify(self.root), b.verify(ROOT))

    def test_fifteen_contracts_and_every_runtime_file_unchanged(self):
        result = r.preservation(self.root)
        self.assertEqual(result['runtime_tool_count'], 16)
        self.assertEqual(result['changed_baseline_files'], sorted(r.ALLOWED_BASE_CHANGES))
        self.assertEqual(result['unchanged_baseline_files'], 388)

    def test_snapshot_module_and_regressions_exact_accepted_sources(self):
        value, _, _ = r.pins(self.root)
        for name, pin in value['lab_source_pins'].items():
            self.assertEqual(s.digest((self.root / name).read_bytes()), pin)

    def test_restore_minimal_input_exact_original_archive(self):
        with r.restored_baseline(self.root) as (base, archive, receipt):
            self.assertEqual(s.digest(archive.read_bytes()), r.BASE_ZIP_PIN)
            self.assertEqual(archive.stat().st_size, r.BASE_ZIP_BYTES)
            self.assertEqual(len(json.loads((base / 'SOURCE-MANIFEST.json').read_bytes())['files']), 401)
            self.assertTrue((base / 'baseline_snapshot').is_dir())
            self.assertEqual(receipt['source_files'], 401)
            self.assertFalse((base.parent.parent.parent / 'inputs/donor/SOURCE-MANIFEST.json').exists())

    def test_recipe_has_no_next_manifest_hash(self):
        _, recipe, _ = r.pins(self.root)
        self.assertNotIn('donor_manifest_sha256', recipe)
        self.assertNotIn('next_manifest_sha256', recipe)
        self.assertNotIn(s.digest((self.root / 'SOURCE-MANIFEST.json').read_bytes()), json.dumps(recipe))

    def test_runtime_source_drift_rejected(self):
        p = self.root / 'foundation_math/claim_ledger.py'; p.write_bytes(p.read_bytes() + b'\n')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.verify(self.root)

    def test_accepted_implementation_drift_rejected_even_after_freeze_attempt(self):
        p = self.root / 'hypothesis_scope/core.py'; p.write_bytes(p.read_bytes() + b'\n')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.freeze(self.root)

    def test_recipe_repin_rejected(self):
        p = self.root / 'HYPOTHESIS-SCOPE-PINS.json'; value = json.loads(p.read_bytes()); value['recipe_sha256'] = '0'*64
        p.write_bytes(s.canonical(value))
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.freeze(self.root)

    def test_historical_archive_drift_rejected(self):
        p = self.root / 'vendor/foundation-math-v010-source.zip'; p.write_bytes(p.read_bytes() + b'junk')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.verify(self.root)

    def test_current_manifest_nonfinite_overflow_rejected(self):
        p = self.root / 'SOURCE-MANIFEST.json'; p.write_bytes(p.read_bytes().replace(b'"version": "0.13.0-dev"', b'"version": 1e400'))
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.verify(self.root)

    def test_selection_duplicate_keys_rejected(self):
        p = self.root / 'RELEASE-FILES.json'; p.write_bytes(b'{"schema":"x","schema":"y","files":[]}')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.verify(self.root)

    def test_missing_donor_rejected(self):
        (self.root / 'foundation_math/calculator.py').unlink()
        with self.assertRaises((RuntimeError, s.SnapshotError, OSError)):
            with r.restored_baseline(self.root):
                self.fail('missing donor accepted')

    def test_oversized_donor_rejected_before_read_or_copy(self):
        target = self.root / 'foundation_math/calculator.py'
        target.write_bytes(target.read_bytes() + b'oversized')
        with self.assertRaisesRegex(s.SnapshotError, 'input file byte budget'):
            with r.restored_baseline(self.root):
                self.fail('oversized donor reached restore')

    def test_same_length_donor_drift_rejected_before_copy(self):
        target = self.root / 'foundation_math/calculator.py'
        raw = target.read_bytes()
        target.write_bytes(b'X' + raw[1:])
        with self.assertRaisesRegex(RuntimeError, 'donor pre-copy source drift'):
            with r.restored_baseline(self.root):
                self.fail('changed donor reached restore')

    def test_missing_blob_rejected(self):
        next((self.root / 'snapshots/v012/blobs').iterdir()).unlink()
        with self.assertRaises((RuntimeError, s.SnapshotError, OSError)):
            b.verify(self.root)

    def test_extra_unselected_snapshot_blob_rejected(self):
        (self.root / 'snapshots/v012/blobs/extra').write_bytes(b'extra')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.verify(self.root)

    def test_symlink_parent_donor_rejected(self):
        folder = self.root / 'foundation_math'; moved = self.root / 'moved'; folder.rename(moved); folder.symlink_to(moved, target_is_directory=True)
        with self.assertRaises((RuntimeError, s.SnapshotError, OSError)):
            b.verify(self.root)

    def test_hardlink_source_rejected(self):
        os.link(self.root / 'foundation_math/calculator.py', self.root / 'linked')
        with self.assertRaises((RuntimeError, s.SnapshotError, OSError)):
            b.verify(self.root)

    def test_output_collision_preserved(self):
        p = Path(self.temp.name) / 'existing.zip'; p.write_bytes(b'keep')
        with self.assertRaises((RuntimeError, s.SnapshotError, OSError)):
            b.create_zip(p, self.root)
        self.assertEqual(p.read_bytes(), b'keep')

    def test_deterministic_current_archive_exact_inventory(self):
        a, c = Path(self.temp.name) / 'a.zip', Path(self.temp.name) / 'c.zip'
        b.create_zip(a, self.root); b.create_zip(c, self.root)
        self.assertEqual(a.read_bytes(), c.read_bytes())
        with zipfile.ZipFile(a) as z:
            self.assertEqual(z.namelist(), sorted([*b.verify(self.root)['files'], 'SOURCE-MANIFEST.json']))
            self.assertNotIn('vendor/foundation-math-v012-source.zip', z.namelist())

    def test_no_next_manifest_required_for_restoration(self):
        (self.root / 'SOURCE-MANIFEST.json').unlink()
        with r.restored_baseline(self.root) as (_, archive, _):
            self.assertEqual(s.digest(archive.read_bytes()), r.BASE_ZIP_PIN)

    def test_changed_current_readme_not_used_for_restoration(self):
        (self.root / 'README.md').write_text('deliberately unavailable to historical donors\n')
        (self.root / 'RELEASE-FILES.json').unlink()
        with r.restored_baseline(self.root) as (base, _, _):
            self.assertNotEqual((base / 'README.md').read_bytes(), (self.root / 'README.md').read_bytes())

    def test_accepted_lab_archive_drift_rejected(self):
        p = self.root / 'vendor/hypothesis-scope-lab.zip'
        p.write_bytes(p.read_bytes() + b'untrusted')
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.freeze(self.root)

    def test_copied_lab_contract_and_request_schema_are_fixed(self):
        for name in ('docs/HYPOTHESIS-SCOPE-LAB-CONTRACT.md', 'schemas/hypothesis-scope-request.schema.json'):
            p = self.root / name; old = p.read_bytes(); p.write_bytes(old + b'\n')
            with self.assertRaises((RuntimeError, s.SnapshotError)):
                b.freeze(self.root)
            p.write_bytes(old)

    def test_inherited_snapshot_implementation_budget_is_fixed(self):
        p = self.root / 'baseline_snapshot/snapshot.py'
        p.write_bytes(p.read_bytes().replace(b"'source_files': 2048", b"'source_files': 4096"))
        with self.assertRaises((RuntimeError, s.SnapshotError)):
            b.freeze(self.root)

    def test_schema_source_matches_frozen_lab_data(self):
        from foundation_math_bridge.hypothesis_scope_schemas import REQUEST
        self.assertEqual(REQUEST, json.loads((self.root/'schemas/hypothesis-scope-request.schema.json').read_bytes()))

    def test_no_full_immediate_baseline_or_v011_archive_selected(self):
        names = b.verify(self.root)['files']
        self.assertNotIn('vendor/foundation-math-v012-source.zip', names)
        self.assertNotIn('vendor/foundation-math-v011-source.zip', names)
        baseline = json.loads((self.root/'snapshots/v012/baseline-manifest.json').read_bytes())['files']
        for name in baseline:
            if name.startswith(('vendor/', 'snapshots/v011/')):
                self.assertEqual(s.digest((self.root/name).read_bytes()), baseline[name])


if __name__ == '__main__':
    unittest.main()

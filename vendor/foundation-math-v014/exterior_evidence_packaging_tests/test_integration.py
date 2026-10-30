"""Current packaging, drift, old-contract, fresh-policy and actual-mode regressions."""
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from baseline_snapshot import snapshot as s
from tools import build_exterior_evidence_release as b
from tools import exterior_evidence_release_support as r
from tools.exterior_evidence_validation_runner import run
from tools.v014_privacy import privacy
ROOT=Path(__file__).resolve().parents[1]

class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.root.mkdir()
        for name in [*json.loads((ROOT/'RELEASE-FILES.json').read_text())['files'],'SOURCE-MANIFEST.json']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())

    def test_current_selection_exact(self):self.assertEqual(b.verify(self.root),b.verify(ROOT))
    def test_prior_runtime_and_sixteen_contracts_preserved(self):
        report=r.preservation(self.root);self.assertEqual(report['runtime_tool_count'],19);self.assertEqual(report['prior_complete_contracts_unchanged'],16)
        self.assertEqual(report['changed_baseline_files'],sorted(r.ALLOWED_BASE_CHANGES));self.assertEqual(report['baseline_selected_files'],454)
    def test_exact_baseline_restoration(self):
        with r.restored_baseline(self.root) as (base,archive,receipt):
            self.assertEqual(s.digest(archive.read_bytes()),r.BASE_ZIP_PIN);self.assertEqual(archive.stat().st_size,r.BASE_ZIP_BYTES)
            self.assertEqual(s.digest((base/'SOURCE-MANIFEST.json').read_bytes()),r.BASE_MANIFEST_PIN);self.assertEqual(receipt['source_files'],454)
    def test_snapshot_no_manifest_cycle_or_full_archive(self):
        _,recipe,_=r.pins(self.root);self.assertNotIn('donor_manifest_sha256',recipe)
        self.assertNotIn(s.digest((self.root/'SOURCE-MANIFEST.json').read_bytes()),json.dumps(recipe))
        self.assertFalse((self.root/'vendor/foundation-math-v013-source.zip').exists())
    def test_old_acceptance_source_drift(self):
        p=self.root/'foundation_math/orchestrator.py';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises((RuntimeError,s.SnapshotError)):b.freeze(self.root)
    def test_accepted_new_lab_source_drift(self):
        for name in ('exterior_power/producer.py','exterior_power/verifier.py','validation_receipt/core.py'):
            p=self.root/name;raw=p.read_bytes();p.write_bytes(raw+b'\n')
            with self.assertRaises((RuntimeError,s.SnapshotError)):b.freeze(self.root)
            p.write_bytes(raw)
    def test_lab_archive_drift(self):
        for name in ('vendor/exterior-power-lab.zip','vendor/validation-receipt-lab.zip'):
            p=self.root/name;raw=p.read_bytes();p.write_bytes(raw+b'junk')
            with self.assertRaises((RuntimeError,s.SnapshotError)):b.freeze(self.root)
            p.write_bytes(raw)
    def test_pin_rebinding_rejected(self):
        p=self.root/'EXTERIOR-EVIDENCE-PINS.json';v=json.loads(p.read_bytes());v['recipe_sha256']='0'*64;p.write_bytes(s.canonical(v))
        with self.assertRaises((RuntimeError,s.SnapshotError)):b.freeze(self.root)
    def test_old_gate_code_drift(self):
        p=self.root/'tools/run_hypothesis_scope_validation.py';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises((RuntimeError,s.SnapshotError)):b.freeze(self.root)
    def test_snapshot_blob_drift(self):
        p=next((self.root/'snapshots/v013/blobs').iterdir());p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaises((RuntimeError,s.SnapshotError)):
            with r.restored_baseline(self.root):pass
    def test_snapshot_extra_member_rejected(self):
        (self.root/'snapshots/v013/unexpected').write_text('x')
        with self.assertRaises((RuntimeError,s.SnapshotError)):b.verify(self.root)
    def test_deterministic_zip_and_selected_inventory(self):
        one=Path(self.temp.name)/'one.zip';two=Path(self.temp.name)/'two.zip';a=b.create_zip(one,self.root);b.create_zip(two,self.root)
        self.assertEqual(one.read_bytes(),two.read_bytes());self.assertEqual(one.stat().st_size,a['bytes'])
        with zipfile.ZipFile(one) as z:self.assertEqual(z.namelist(),sorted([*b.verify(self.root)['files'],'SOURCE-MANIFEST.json']))
    def test_existing_output_untouched(self):
        out=Path(self.temp.name)/'keep.zip';out.write_bytes(b'keep')
        with self.assertRaises((OSError,RuntimeError,s.SnapshotError)):b.create_zip(out,self.root)
        self.assertEqual(out.read_bytes(),b'keep')
    def test_selected_output_collision_rejected(self):
        target=self.root/'README.md';old=target.read_bytes()
        with self.assertRaises((RuntimeError,s.SnapshotError)):b.create_zip(target,self.root)
        self.assertEqual(target.read_bytes(),old)
    def test_symlink_source_rejected(self):
        target=self.root/'README.md';raw=target.read_bytes();other=Path(self.temp.name)/'other';other.write_bytes(raw);target.unlink();target.symlink_to(other)
        with self.assertRaises((RuntimeError,s.SnapshotError,OSError)):b.verify(self.root)
    def test_lab_extraction_exact(self):
        for label,spec in r.LABS.items():
            output=r.unpack_lab(self.root,label,Path(self.temp.name)/label)
            self.assertEqual(s.digest((output/'SOURCE-MANIFEST.json').read_bytes()),spec['manifest_sha256'])
    def test_actual_modes_override_inherited_optimization(self):
        script=self.root/'probe.py';script.write_text('import json,sys;print(json.dumps({"optimization":sys.flags.optimize}))\n')
        with patch.dict(os.environ,{'PYTHONOPTIMIZE':'2','PYTHONPATH':'untrusted','PYTHONHOME':'untrusted'}):
            for mode in (False,True):self.assertEqual(json.loads(run(self.root,'probe.py',mode).stdout)['optimization'],int(mode))
    def test_failed_actual_mode_guard_is_not_pass(self):
        script=self.root/'probe.py';script.write_text('raise RuntimeError("deliberate failure")\n')
        with self.assertRaises(RuntimeError):run(self.root,'probe.py')
    def test_measurements_are_observations_not_reuse_authority(self):
        script=self.root/'probe.py';script.write_text('print("ok")\n');logs=Path(self.temp.name)/'logs';run(self.root,'probe.py',log_dir=logs)
        v=json.loads((logs/'probe.measurement.json').read_text());self.assertFalse(v['closure_certified']);self.assertFalse(v['historical_reuse_authorized'])
        self.assertEqual(v['actual_optimization'],0);self.assertGreaterEqual(v['elapsed_seconds'],0)
    def test_no_skip_or_user_command_gate_surface(self):
        import ast
        for name in ('tools/run_full_archival_replay.py','tools/run_exterior_evidence_validation.py'):
            text=(self.root/name).read_text();tree=ast.parse(text)
            self.assertNotIn('plan_validation_evidence',text);self.assertNotIn('PRIOR_PINNED_EVIDENCE_MATCHES',text)
            self.assertNotIn('--skip',text)
    def test_new_sources_privacy(self):self.assertEqual(privacy(self.root,b.verify(self.root))['findings'],[])
    def test_new_unreviewed_path_marker_rejected(self):
        manifest=b.verify(self.root);p=self.root/'README.md';p.write_text(p.read_text()+'\n/workspace/unreviewed\n')
        with self.assertRaises(RuntimeError):privacy(self.root,manifest)
    def test_provenance_exception_bound_to_exact_member_bytes(self):
        manifest=b.verify(self.root);path=self.root/'vendor/validation-receipt-lab.zip'
        with zipfile.ZipFile(path) as z:members={n:z.read(n) for n in z.namelist()}
        members['reference/PROVENANCE.json']+=b'\n'
        path.unlink()
        with zipfile.ZipFile(path,'x') as z:
            for name,data in members.items():z.writestr(name,data)
        with self.assertRaises(RuntimeError):privacy(self.root,manifest)
    def test_no_evidence_or_pycache_selected(self):
        names=b.verify(self.root)['files'];self.assertFalse(any(n.startswith('evidence/') or '__pycache__' in n for n in names))

if __name__=='__main__':unittest.main()

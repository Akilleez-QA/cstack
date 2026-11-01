"""Explicit fresh full archival v0.13 replay, preserving every original gate."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from baseline_snapshot import snapshot as s
from tools.exterior_evidence_release_support import restored_baseline,require,BASE_ZIP_PIN,BASE_MANIFEST_PIN
from tools.exterior_evidence_validation_runner import run


def replay(root=ROOT,log_dir=None):
    with restored_baseline(root) as (base,archive,restoration):
        require(s.digest(archive.read_bytes())==BASE_ZIP_PIN,'restored archive drift')
        rebuilt=archive.parent/'original-builder.zip'
        run(base,'tools/build_hypothesis_scope_release.py',args=('--output',rebuilt),log_dir=log_dir,label='v013-builder')
        require(archive.read_bytes()==rebuilt.read_bytes(),'unchanged historical builder differs')
        p=run(base,'tools/run_hypothesis_scope_validation.py',bool(sys.flags.optimize),timeout=5400,
              log_dir=log_dir,label='fresh-v013-full-aggregate')
        historical=json.loads(p.stdout);require(historical['status']=='passed','fresh historical full gate failed')
        require(historical['source_manifest_sha256']==BASE_MANIFEST_PIN,'historical report manifest mismatch')
        manifest=s.source_manifest((base/'SOURCE-MANIFEST.json').read_bytes(),BASE_MANIFEST_PIN)
        require(all(s.digest((base/n).read_bytes())==pin for n,pin in manifest.items()),'historical source drift during replay')
    return {'status':'passed','profile':'fresh_full_archival_replay','restoration':restoration,
            'unchanged_historical_builder_zip_identical':True,'fresh_frozen_v013_aggregate':historical,
            'prior_pinned_evidence_reused':False,'v013_gate_modified':False}


def main():
    if len(sys.argv)!=1:raise ValueError('No caller-provided commands or profile substitutions accepted')
    evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
    print(s.canonical(replay(ROOT,evidence)).decode(),end='')
if __name__=='__main__':main()

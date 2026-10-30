"""Selected-only normal/-O full fresh v0.14 delivery and exact measured archive bytes."""
import argparse
import json
import shutil
from pathlib import Path
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from baseline_snapshot import snapshot as s
from tools.build_exterior_evidence_release import create_zip,verify,digest
from tools.exterior_evidence_release_support import require,restored_baseline,BASE_ZIP_BYTES
from tools.exterior_evidence_validation_runner import run


def measure(root,work):
    manifest=verify(root);files={n:(root/n).read_bytes() for n in [*manifest['files'],'SOURCE-MANIFEST.json']}
    snapshot={n:d for n,d in files.items() if n.startswith('snapshots/v013/')};common={n:d for n,d in files.items() if n not in snapshot}
    with restored_baseline(root) as (_,archive,_):full={**common,'vendor/foundation-math-v013-source.zip':archive.read_bytes()}
    results={}
    for label,payload in [('common-payload',common),('actual-snapshot-release',files),('counterfactual-full-baseline',full),('snapshot-only',snapshot)]:
        pin,size=s.create_zip(work/(label+'.zip'),payload);results[label]={'bytes':size,'sha256':pin}
    actual=results['actual-snapshot-release']['bytes'];full_size=results['counterfactual-full-baseline']['bytes'];base=results['common-payload']['bytes']
    require(actual<full_size,'no measured packaging saving')
    return {'status':'passed','archives':results,'snapshot_incremental_outer_zip_bytes':actual-base,
            'full_baseline_incremental_outer_zip_bytes':full_size-base,'outer_zip_bytes_saved':full_size-actual,
            'snapshot_raw_bytes':sum(map(len,snapshot.values())),'original_v013_archive_bytes':BASE_ZIP_BYTES,
            'actual_v014_growth_over_v013_bytes':actual-BASE_ZIP_BYTES,
            'measurement_basis':'Actual final selected bytes with all non-snapshot members fixed, including source metadata. Counterfactual assemblies are measurement-only, not valid releases.',
            'synthetic_fixture_reused':False,'future_growth_claim':False,'speed_equivalence_claim':False}


def reproduce(root=ROOT):
    source=verify(root);before=digest(root/'SOURCE-MANIFEST.json');evidence=root/'evidence';evidence.mkdir(exist_ok=True)
    observations=Path(tempfile.mkdtemp(prefix='delivery-observations-',dir=evidence))
    with tempfile.TemporaryDirectory(prefix='fm-v014-delivery-') as td:
        temp=Path(td);first=temp/'first.zip';second=temp/'second.zip';receipt=create_zip(first,root);create_zip(second,root)
        require(first.read_bytes()==second.read_bytes(),'deterministic build mismatch')
        clean=temp/'selected-only';clean.mkdir()
        with zipfile.ZipFile(first) as z:
            require(z.namelist()==sorted([*source['files'],'SOURCE-MANIFEST.json']),'selected exact archive inventory')
            for info in z.infolist():
                require(info.date_time==(2026,1,1,0,0,0) and info.create_system==3 and info.external_attr==0o100644<<16 and info.compress_type==zipfile.ZIP_DEFLATED,'archive metadata')
                s.name(info.filename);target=clean/info.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info))
        require(not (clean/'evidence').exists(),'generated outer evidence selected')
        require(not (clean/'vendor/foundation-math-v013-source.zip').exists(),'full v013 archive selected')
        require(verify(clean)==source,'clean selected verification')
        reports=[]
        for mode in (False,True):
            report=json.loads(run(clean,'tools/run_exterior_evidence_validation.py',mode,timeout=9000,log_dir=observations,
                                  label='selected-full-aggregate-'+str(int(mode))).stdout)
            reports.append(report)
            # Preserve the actual per-phase observations from each entry mode.
            # These generated files are never selected source or cache authority.
            saved=observations/('selected-entry-'+str(int(mode)))
            shutil.copytree(clean/'evidence',saved)
        require(reports[0]==reports[1],'delivery semantic aggregate normal/-O mismatch')
        require(verify(clean)==source,'selected source changed')
        # Independent serializer assembly, not the current builder's function.
        rebuilt=temp/'independent-rebuilt.zip'
        files={n:(clean/n).read_bytes() for n in sorted([*source['files'],'SOURCE-MANIFEST.json'])}
        with zipfile.ZipFile(rebuilt,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,data in files.items():
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        require(first.read_bytes()==rebuilt.read_bytes(),'independent selected-only rebuild mismatch')
        measurements=measure(clean,temp)
        require(measurements['archives']['actual-snapshot-release']['sha256']==receipt['sha256'],'not actual final measured release')
        fault=clean/'exterior_power/producer.py';raw=fault.read_bytes();fault.write_bytes(raw+b'\n# drift control\n');rejected=False
        try:verify(clean)
        except (RuntimeError,s.SnapshotError):rejected=True
        finally:fault.write_bytes(raw)
        require(rejected,'source drift accepted');verify(clean)
    require(verify(root)==source and digest(root/'SOURCE-MANIFEST.json')==before,'source changed during delivery')
    return {'status':'PASS','validation_profile':'fresh_current_and_full_archival_replay','archive':receipt,
            'manifest_only_delivery':True,'normal_optimized_semantic_aggregates_identical':True,
            'actual_child_modes_verified':[0,1],'independent_selected_only_zip_rebuild_identical':True,
            'source_drift_rejected':True,'prior_pinned_evidence_reused':False,'full_v013_archive_embedded':False,
            'byte_measurements':measurements,'aggregate':reports[0],
            'scope':'Local bounded formal arithmetic and pure evidence classification only; no actual geometry, maps, proof, execution of supplied argv, skip authorization, promotion or publication.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args();result=reproduce()
    if args.output:args.output.write_bytes(s.canonical(result))
    print(s.canonical(result).decode(),end='')
if __name__=='__main__':main()

"""v0.14 full fresh aggregate. No reused-history profile or arbitrary execution plan."""
from pathlib import Path
import ast
import json
import sys
import tempfile
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from baseline_snapshot import snapshot as s
from tools.build_exterior_evidence_release import verify,digest
from tools.exterior_evidence_release_support import preservation,unpack_lab,require,environment,LABS
from tools.exterior_evidence_validation_runner import run,tests
from tools.run_polynomial_witness_validation import prepare_legacy_transcript
from tools.v014_privacy import privacy


def static_check(root):
    names=('foundation_math/validation_evidence.py','validation_receipt/core.py','foundation_math_bridge/validation_evidence_schemas.py')
    findings=[]
    for name in names:
        for node in ast.walk(ast.parse((root/name).read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('eval','exec','compile','__import__','open'):
                findings.append(name+': '+node.func.id)
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                modules=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or '']
                for module in modules:
                    if module.split('.')[0] in ('os','pathlib','socket','subprocess','requests','urllib','http','openai'):
                        findings.append(name+': '+module)
    require(not findings,'planner execution/I/O surface: '+str(findings))
    verifier=(root/'exterior_power/verifier.py').read_text();tree=ast.parse(verifier)
    imports=[node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    require(not any('producer' in x or 'fusion' in x for x in imports),'checker imports producer/fusion')
    return {'status':'passed','pure_planner_files':list(names),'findings':findings,
            'independent_checker_import_boundary':True,'scope':'Static import/call inspection, not formal verification or sandbox assurance.'}


def labs(root,evidence):
    reports={}
    with tempfile.TemporaryDirectory(prefix='fm-v014-labs-') as td:
        for label,spec in LABS.items():
            lab=unpack_lab(root,label,Path(td)/label);runs=[]
            for mode in (False,True):
                result=json.loads(run(lab,'tools/validate.py',mode,timeout=1800,log_dir=evidence,
                                      label=label+'-lab-'+str(int(mode))).stdout)
                if label=='exterior':
                    require(result['status']=='passed' and result['source_manifest_sha256']==spec['manifest_sha256'],'exterior fresh lab status/pin')
                    require(result['launcher_optimization']==int(mode),'exterior actual launcher mode')
                    stages=result['normal_and_optimized']
                    require(len(stages)==2,'exterior both modes')
                    for index,stage in enumerate(stages):
                        require(all(stage[k]['optimization']==index and stage[k]['status']=='passed' for k in ('tests','mutations')),'exterior actual nested modes')
                    normalized=[{k:{field:value for field,value in report.items() if field!='seconds'} for k,report in stage.items()} for stage in stages]
                    runs.append({'entry_optimization':int(mode),'status':'passed','normal_and_optimized':normalized})
                else:
                    require(result['status']=='PASS' and result['archive']['sha256']==spec['archive_sha256'],'receipt fresh lab status/pin')
                    require(result['deterministic_archive'] and result['selected_only_rebuild_identical'],'receipt lab deterministic selected replay')
                    require(all(x['tests']==40 and not x['skipped'] for x in result['original']+result['selected_only']),'receipt author test coverage')
                    require(all(x['independent_cases']==181 and x['semantic_mutants_killed']==17 for x in result['independent_original']+result['independent_selected_only']),'receipt independent coverage')
                    runs.append({'entry_optimization':int(mode),'status':'passed','author_tests_per_mode':40,'independent_cases_per_mode':181,
                                 'independent_mutants_per_mode':17,'selected_only_rebuild_identical':True,'author_mutations':result['source_mutations']})
            reports[label]={'manifest_sha256':spec['manifest_sha256'],'archive_sha256':spec['archive_sha256'],'fresh_runs':runs}
    return reports


def validate(root=ROOT):
    source=verify(root);source_pin=digest(root/'SOURCE-MANIFEST.json');preserved=preservation(root)
    evidence=root/'evidence';evidence.mkdir(exist_ok=True)
    # Audit the independent integration boundary before entering the long gate.
    reviews=[]
    for mode in (False,True):
        review=json.loads(run(root,'review/v014_review.py',mode,timeout=900,log_dir=evidence,label='integration-review-'+str(int(mode))).stdout)
        require(review['status'] in ('PASS','pass','passed'),'independent integration review')
        reviews.append(review)
    require(reviews[0]==reviews[1],'independent review normal/-O mismatch')
    prepare_legacy_transcript(root,environment())
    runtime=[];packaging=[];differentials=[]
    for mode in (False,True):
        runtime.append(tests(root,mode,'tests',evidence));packaging.append(tests(root,mode,'exterior_evidence_packaging_tests',evidence))
        differential=json.loads(run(root,'tools/audit_v013_tool_differential.py',mode,log_dir=evidence,label='old-tool-differential-'+str(int(mode))).stdout)
        require(differential['status']=='passed','old-tool differential');differentials.append(differential)
    require(differentials[0]==differentials[1],'old-tool differential entry modes')
    lab_reports=labs(root,evidence)
    archival=json.loads(run(root,'tools/run_full_archival_replay.py',bool(sys.flags.optimize),timeout=6000,
                            log_dir=evidence,label='fresh-full-archival').stdout)
    require(archival['status']=='passed' and not archival['prior_pinned_evidence_reused'],'fresh full historical gate')
    require(verify(root)==source and digest(root/'SOURCE-MANIFEST.json')==source_pin,'source changed during validation')
    report={'status':'passed','version':'0.14.0-dev','validation_profile':'fresh_current_and_full_archival_replay',
            'source_manifest_sha256':source_pin,'source_files_checked':len(source['files']),'source_preservation':preserved,
            'current_runtime_tests':runtime,'current_packaging_tests':packaging,'accepted_labs':lab_reports,
            'sixteen_tool_differential':differentials[0],'independent_integration_review':reviews[0],
            'archival_replay':archival,'prior_pinned_evidence_reused':False,'closure_inferred_from_traces':False,
            'speed_equivalence_claimed':False,'v013_gates_modified':False,'static_check':static_check(root),'privacy':privacy(root,source),
            'lean':archival['fresh_frozen_v013_aggregate']['lean'],'python':sys.version.split()[0],'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,
            'sibling_checkout_required':False,'original_v013_zip_input_required':False,'generated_evidence_required':False,
            'scope':'Bounded formal exterior arithmetic and pure authored-evidence classification; no geometry, maps, existence, proof, skip authority, execution of supplied argv or runtime promotion.'}
    (evidence/'v014-validation.json').write_bytes(s.canonical(report));return report


def main():
    if len(sys.argv)!=1:raise ValueError('No caller-provided commands or profile substitutions accepted')
    print(s.canonical(validate()).decode(),end='')
if __name__=='__main__':main()

"""One selected-only v0.13 aggregate: syntactic scope matching, never proof."""
import ast
import json
import re
from pathlib import Path
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from baseline_snapshot import snapshot as s
from tools.build_hypothesis_scope_release import verify, digest
from tools.hypothesis_scope_release_support import preservation, restored_baseline, unpack_lab, require, environment, LAB_ZIP_PIN
from tools.run_snapshot_validation import run, tests, privacy
from tools.run_polynomial_witness_validation import prepare_legacy_transcript


def static_check(root):
    names = ('foundation_math/hypothesis_scope.py', 'foundation_math_bridge/hypothesis_scope_schemas.py', 'hypothesis_scope/core.py')
    findings = []
    for name in names:
        for node in ast.walk(ast.parse((root/name).read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval','exec','compile','__import__','open'):
                findings.append(name + ': ' + node.func.id)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or '']
                for module in modules:
                    if module.split('.')[0] in ('socket','requests','urllib','http','subprocess','openai','os','pathlib'):
                        findings.append(name + ': ' + module)
    require(not findings, 'new execution/file/network surface: ' + str(findings))
    return {'status':'passed','files':list(names),'findings':findings,'scope':'Static surface check, not a sandbox or proof.'}


def validate(root=ROOT):
    source=verify(root); source_pin=digest(root/'SOURCE-MANIFEST.json'); preserved=preservation(root)
    evidence=root/'evidence'; evidence.mkdir(exist_ok=True)
    with restored_baseline(root) as (base, archive, restoration):
        rebuilt=archive.parent/'unchanged-v012-builder.zip'
        run(base,'tools/build_snapshot_release.py',args=('--output',rebuilt))
        require(archive.read_bytes()==rebuilt.read_bytes(),'unchanged v0.12 builder ZIP differs')
        historical=json.loads(run(base,'tools/run_snapshot_validation.py',bool(sys.flags.optimize),timeout=3600).stdout)
        require(historical['status']=='passed','fresh full v0.12 aggregate')
        (evidence/'v013-fresh-v012.json').write_bytes(s.canonical(historical))
    with tempfile.TemporaryDirectory(prefix='fm-v013-lab-') as td:
        lab=unpack_lab(root,Path(td)/'lab')
        lab_report=json.loads(run(lab,'tools/validate.py',bool(sys.flags.optimize),timeout=600).stdout)
        require(lab_report['archive_sha256']==LAB_ZIP_PIN and lab_report['selected_only_verified'] and lab_report['deterministic_zip'] and lab_report['deterministic_assets'], 'fresh frozen lab aggregate')
        lab_counts = []
        for location in ('original', 'selected_only'):
            rows = lab_report[location]
            require(len(rows) == 4, 'lab must run author and independent suites in both modes')
            for row in rows:
                count = re.search(r'Ran (\d+) tests', row['stderr'])
                require(count is not None and row['returncode'] == 0, 'lab fresh test count/result')
                independent = row['command'][0] == 'review/independent_review.py'
                require(int(count[1]) == (19 if independent else 29), 'accepted lab suite count')
                lab_counts.append({'location': location, 'optimization': int(row['optimized']),
                                   'suite': 'independent' if independent else 'author', 'run': int(count[1])})
        require({(r['location'],r['optimization'],r['suite']) for r in lab_counts} ==
                {(loc,mode,suite) for loc in ('original','selected_only') for mode in (0,1) for suite in ('author','independent')},
                'lab mode/suite coverage')
        (evidence/'v013-frozen-lab.json').write_bytes(s.canonical(lab_report))
    prepare_legacy_transcript(root,environment())
    runtime_counts=[]; packaging_counts=[]; reviews=[]; differentials=[]
    for optimized,label in ((False,'normal'),(True,'optimized')):
        for directory,counts in (('tests',runtime_counts),('scope_packaging_tests',packaging_counts)):
            count,log=tests(root,optimized,directory);counts.append(count)
            (evidence/f'v013-{directory}-{label}.log').write_text(log)
        differential=json.loads(run(root,'tools/audit_v012_tool_differential.py',optimized).stdout)
        differentials.append(differential)
        (evidence/f'v013-differential-{label}.json').write_bytes(s.canonical(differential))
        review=json.loads(run(root,'review/v013_review.py',optimized,timeout=900).stdout)
        require(review['status'] in ('PASS','pass','passed'),'independent integration review status')
        reviews.append(review);(evidence/f'v013-review-{label}.json').write_bytes(s.canonical(review))
    require(reviews[0]==reviews[1] and differentials[0]==differentials[1],'normal/-O audit/review mismatch')
    require(verify(root)==source and digest(root/'SOURCE-MANIFEST.json')==source_pin,'source changed during aggregate')
    result={'status':'passed','version':'0.13.0-dev','source_manifest_sha256':source_pin,'source_files_checked':len(source['files']),
            'current_runtime_tests':runtime_counts,'packaging_tests':packaging_counts,'source_preservation':preserved,
            'restoration':restoration,'fresh_frozen_v012_aggregate_status':historical['status'],
            'fresh_frozen_v012_runtime_tests':historical['current_runtime_tests'],
            'historical_full_aggregate_unchanged':True,'unchanged_historical_builder_zip_identical':True,
            'accepted_lab':{'manifest_sha256':lab_report['source_manifest_sha256'],'archive_sha256':LAB_ZIP_PIN,
                            'selected_only_normal_optimized':True,'fresh_suites':lab_counts,
                            'deterministic_zip':True,'deterministic_assets':True},
            'fifteen_tool_differential':differentials[0],'independent_integration_review':reviews[0],
            'static_check':static_check(root),'privacy':privacy(root,source),'lean':historical['lean'],
            'original_v012_zip_input_required':False,'sibling_checkout_required':False,'generated_evidence_required':False,
            'python':sys.version.split()[0],'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,
            'scope':'Exact caller-authored premise matching only; no fact truth, rule soundness, geometry, authentication, proof or runtime promotion.'}
    (evidence/'v013-validation.json').write_bytes(s.canonical(result));return result


def main():print(s.canonical(validate()).decode(),end='')
if __name__=='__main__':main()

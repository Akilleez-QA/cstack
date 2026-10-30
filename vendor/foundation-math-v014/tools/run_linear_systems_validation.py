"""Single portable v0.8 aggregate, run from source-only manifest extraction.

Regenerates all required evidence from shipped source/fixtures. Historical
unshipped evidence is explicitly excluded from source preservation. Never reads
sibling trees, writes source, installs dependencies, or contacts a network.
"""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from foundation_math_bridge.schemas import tool_definitions
from tools.run_polynomial_witness_validation import prepare_legacy_transcript

BASE_PIN='608d5703b313d0a2f8edf08b8dab40607ce61baf5921af44a0b8098062991214'
LAB_PIN='1159de46ea66a4b2564a906c81ab43744e316e0e58ec7ae33ebeb069575d226b'
ALLOWED_BASE_CHANGES={
    'README.md','docs/PROVENANCE.md','foundation_math/cli.py',
    'foundation_math_bridge/__init__.py','foundation_math_bridge/schemas.py','foundation_math_bridge/server.py',
    'tests/test_agent_bridge.py','tests/test_linear_algebra_bridge.py','tests/test_portable_validation.py',
    'tests/test_v07_independent_review.py','tools/run_linear_algebra_validation.py',
    'tools/audit_polynomial_witness_integration.py',
}


def require(condition,label):
    if not condition:raise RuntimeError(label)


def digest(path):return sha256(path.read_bytes()).hexdigest()


def write_json(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def check_preservation(root):
    require(digest(root/'docs/BASE-V07-PORTABLE-SOURCE-MANIFEST.json')==BASE_PIN,'base reference manifest changed')
    require(digest(root/'docs/LINEAR-SYSTEMS-LAB-SOURCE-MANIFEST.json')==LAB_PIN,'lab reference manifest changed')
    base=json.loads((root/'docs/BASE-V07-PORTABLE-SOURCE-MANIFEST.json').read_text())['files']
    changed=[name for name,h in base.items() if digest(root/name)!=h]
    require(set(changed)==ALLOWED_BASE_CHANGES,'unexpected inherited source changes: '+str(changed))
    inventory=json.loads((root/'docs/BASE-V07-PORTABLE-FROZEN-FILES.json').read_text())['files']
    excluded=sorted(name for name in inventory if name.startswith('evidence/'))
    # SOURCE-MANIFEST is intentionally replaced; all other shipped source entries
    # are checked against the pinned full base inventory as well as its manifest.
    source={name:h for name,h in inventory.items() if not name.startswith('evidence/') and name!='SOURCE-MANIFEST.json'}
    require(source==base,'base source inventory and pinned source manifest disagree')
    math=[name for name in base if name.startswith(('foundation_math/','bounded_counterexample/','exact_linalg/','polynomial_witness/')) and name!='foundation_math/cli.py']
    require(all(digest(root/name)==base[name] for name in math),'inherited math runtime changed')
    lab=json.loads((root/'docs/LINEAR-SYSTEMS-LAB-SOURCE-MANIFEST.json').read_text())['sha256']
    vendored=[name for name in lab if name.startswith(('exact_linalg/','exact_systems/'))]
    require(len(vendored)==12 and all(digest(root/name)==lab[name] for name in vendored),'accepted lab engine changed')
    fixtures=[name for name in lab if name.startswith('examples/')]
    require(all(digest(root/'examples/linear-systems'/Path(name).name)==lab[name] for name in fixtures),'lab fixture changed')
    require(digest(root/'tools/audit_systems_lab.py')==lab['tools/audit_systems.py'],'frozen lab mutation audit changed')
    inherited=json.loads((root/'docs/BASE-V07-PORTABLE-BRIDGE-TOOLS.json').read_text())['tools']
    require(len(tool_definitions())==10 and tool_definitions()[:8]==inherited,'prior eight tool definitions changed')
    return {'status':'passed','base_source_files_checked':len(base),'base_source_unchanged':len(base)-len(changed),
        'intentional_inherited_changes':sorted(changed),'inherited_math_runtime_files_unchanged':len(math),
        'accepted_lab_runtime_files_unchanged':len(vendored),'accepted_lab_examples_unchanged':len(fixtures),
        'original_eight_tool_definitions_unchanged':True,
        'lab_test_change':'test_systems.py changes only its provenance test to pinned shipped sources instead of external sibling paths.',
        'historical_generated_evidence_not_shipped_or_checked':excluded,
        'scope':'Every inherited shipped source checked; external frozen trees and historical evidence are not checked by this portable command.'}


def verify_manifest(root):
    data=json.loads((root/'SOURCE-MANIFEST.json').read_text())
    files=data['files']
    require(all(digest(root/name)==h for name,h in files.items()),'source manifest mismatch')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts
            and 'evidence' not in p.relative_to(root).parts and p.name!='SOURCE-MANIFEST.json'}
    require(actual==set(files),'unmanifested or missing source files')
    return files


def main():
    source=verify_manifest(ROOT);before=digest(ROOT/'SOURCE-MANIFEST.json')
    preservation=check_preservation(ROOT)
    EVIDENCE.mkdir(exist_ok=True)
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    # Required by the original schema validator. Generate now, never copy old evidence.
    prepare_legacy_transcript(ROOT,environment)
    checks=[];counts=[];schema=importlib.util.find_spec('jsonschema') is not None
    for optimized,mode in ((False,'normal'),(True,'optimized')):
        prefix=[sys.executable,'-B']+(['-O'] if optimized else [])
        jobs=[('tests',['-m','unittest','discover','-s','tests','-v'],'txt'),
              ('systems-lab-mutations',['tools/audit_systems_lab.py'],'json'),
              ('systems-integration',['tools/audit_linear_systems_integration.py'],'json'),
              ('witness-lab',['tools/audit_polynomial_witness_lab.py','--output',f'evidence/v08-witness-lab-audit-{mode}.json'],'txt'),
              ('witness-integration',['tools/audit_polynomial_witness_integration.py'],'json'),
              ('legacy-bridge',['tools/audit_agent_bridge.py'],'json'),
              ('matrix-integration',['tools/run_linear_algebra_validation.py'],'json')]
        if schema:
            jobs += [(name,[script],'json') for name,script in [
                ('system-schemas','tools/validate_linear_systems_schemas.py'),
                ('witness-schemas','tools/validate_polynomial_witness_schemas.py'),
                ('matrix-schemas','tools/validate_matrix_bridge_schemas.py'),
                ('legacy-schemas','tools/validate_bridge_schemas.py')]]
        for name,args,suffix in jobs:
            p=subprocess.run(prefix+args,cwd=ROOT,env=environment,capture_output=True,text=True,timeout=180)
            path=EVIDENCE/f'v08-{name}-{mode}.{suffix}'
            output=(p.stdout+p.stderr).replace(str(ROOT),'<source-root>');path.write_text(output)
            require(p.returncode==0,name+' '+mode+' failed; see '+path.name)
            checks.append({'check':name,'optimization':int(optimized),'exit_code':p.returncode,'evidence':str(path.relative_to(ROOT))})
            if name=='tests':
                count=re.search(r'Ran (\d+) tests',output);skipped=re.search(r'OK \(skipped=(\d+)\)',output)
                require(count is not None,'missing full test count')
                counts.append({'optimization':int(optimized),'run':int(count[1]),'skipped':int(skipped[1]) if skipped else 0})
    replays=[]
    for path in sorted((ROOT/'examples/linear-systems').glob('*request.json')):
        outputs=[]
        for optimized in (False,True):
            p=subprocess.run([sys.executable,'-B']+(['-O'] if optimized else [])+['-m','exact_systems'],input=path.read_bytes(),cwd=ROOT,env=environment,capture_output=True,timeout=10)
            require(p.returncode==0 and not p.stderr and json.loads(p.stdout)['ok'],'standalone fixture replay: '+path.name)
            outputs.append(p.stdout)
        require(outputs[0]==outputs[1],'standalone optimized mismatch')
        replays.append({'fixture':path.name,'normal_optimized_identical':True,'response_sha256':sha256(outputs[0]).hexdigest()})
    require(len(replays)==8,'system fixture request inventory')
    write_json(EVIDENCE/'v08-system-example-replays.json',{'status':'passed','replays':replays})
    source_hash_checks=0
    for path in EVIDENCE.glob('v08-*.json'):
        if path.name in ('v08-validation.json','v08-source-preservation.json','v08-privacy-check.json'):continue
        data=json.loads(path.read_text())
        for name,h in data.get('source_sha256',{}).items():
            require(digest(ROOT/name)==h,'stale evidence: '+path.name+': '+name);source_hash_checks+=1
    reviewed=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.md','.json','.jsonl','.txt')]
    findings=[]
    for path in reviewed:
        content=path.read_text()
        for marker in ('/workspace/','/home/','file://','codex://','ghp_','sk-proj-','BEGIN PRIVATE KEY','BEGIN RSA PRIVATE KEY'):
            if marker in content:findings.append({'file':str(path.relative_to(ROOT)),'marker':marker})
    require(not findings,'privacy/portability scan failed: '+str(findings))
    require(verify_manifest(ROOT)==source and digest(ROOT/'SOURCE-MANIFEST.json')==before,'source changed during validation')
    write_json(EVIDENCE/'v08-source-preservation.json',preservation)
    write_json(EVIDENCE/'v08-privacy-check.json',{'status':'passed','files_checked':len(reviewed),'findings':findings})
    integration=json.loads((EVIDENCE/'v08-systems-integration-normal.json').read_text())
    report={'status':'passed','version':'0.8.0-dev','source_manifest_sha256':before,
        'tests':counts,'checks':checks,'synthetic_systems_per_mode':integration['systems'],
        'integration_checks_per_mode':integration['total_checks'],'system_standalone_fixture_replays':len(replays),
        'source_hashes_in_reports_checked':source_hash_checks,'source_files_checked':len(source),
        'original_eight_tool_definitions_unchanged':True,'accepted_lab_runtime_files_unchanged':12,
        'historical_evidence_required':False,'source_unchanged_during_validation':True,'privacy_scan_passed':True,
        'optional_schema_validation':'passed_using_preinstalled_jsonschema' if schema else 'unavailable_no_install_attempted',
        'scope':'Finite synthetic software/proof-certificate testing, not formal proof, integer lattice, generic/family theorem or runtime goal acceptance.'}
    write_json(EVIDENCE/'v08-validation.json',report)
    print(json.dumps(report,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

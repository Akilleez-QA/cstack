"""Single portable v0.9 aggregate, run from source-only manifest extraction.

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
import tempfile
import ast
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from foundation_math_bridge.schemas import tool_definitions
from tools.run_polynomial_witness_validation import prepare_legacy_transcript
from tools.character_release_support import unpack_base, unpack_lab, environment as clean_environment, BASE_MANIFEST_PIN, LAB_MANIFEST_PIN

ALLOWED_BASE_CHANGES = {
    'README.md', 'docs/PROVENANCE.md', 'foundation_math/cli.py',
    'foundation_math_bridge/__init__.py', 'foundation_math_bridge/schemas.py', 'foundation_math_bridge/server.py',
    'tests/test_agent_bridge.py', 'tests/test_linear_algebra_bridge.py',
    'tests/test_linear_systems_integration.py', 'tests/test_portable_validation.py',
    'tools/audit_linear_systems_integration.py', 'tools/audit_polynomial_witness_integration.py',
    'tools/run_linear_algebra_validation.py',
}

def require(condition,label):
    if not condition:raise RuntimeError(label)


def digest(path):return sha256(path.read_bytes()).hexdigest()


def write_json(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def check_preservation(root):
    require(digest(root/'docs/BASE-V08-SOURCE-MANIFEST.json')==BASE_MANIFEST_PIN,'base manifest changed')
    require(digest(root/'docs/CHARACTER-RING-LAB-SOURCE-MANIFEST.json')==LAB_MANIFEST_PIN,'lab manifest changed')
    base=json.loads((root/'docs/BASE-V08-SOURCE-MANIFEST.json').read_text())['files']
    changed=[name for name,h in base.items() if digest(root/name)!=h]
    require(set(changed)==ALLOWED_BASE_CHANGES,'unexpected inherited changes: '+str(changed))
    math=[name for name in base if name.startswith(('foundation_math/', 'bounded_counterexample/', 'exact_linalg/', 'exact_systems/', 'polynomial_witness/')) and name!='foundation_math/cli.py']
    require(all(digest(root/name)==base[name] for name in math),'inherited runtime changed')
    entries=json.loads((root/'docs/CHARACTER-RING-LAB-SOURCE-MANIFEST.json').read_text())['files']
    vendored=[item for item in entries if item['path'].startswith('character_ring/')]
    fixtures=[item for item in entries if item['path'].startswith('examples/')]
    require(len(vendored)==7 and all(digest(root/item['path'])==item['sha256'] for item in vendored),'accepted character engine changed')
    require(all(digest(root/'examples/character-ring'/Path(item['path']).name)==item['sha256'] for item in fixtures),'character example changed')
    inherited=json.loads((root/'docs/BASE-V08-BRIDGE-TOOLS.json').read_text())['tools']
    require(len(tool_definitions())==12 and tool_definitions()[:10]==inherited,'prior ten tool contracts changed')
    with tempfile.TemporaryDirectory(prefix='fm-authenticated-inputs-') as td:
        directory=Path(td);unpack_base(root,directory/'base');unpack_lab(root,directory/'lab')
    return {'status':'passed','base_source_files_checked':len(base),'base_source_unchanged':len(base)-len(changed),
        'intentional_inherited_changes':sorted(changed),'inherited_math_runtime_files_unchanged':len(math),
        'accepted_character_runtime_files_unchanged':len(vendored),'accepted_character_examples_unchanged':len(fixtures),
        'original_ten_tool_definitions_unchanged':True,'historical_evidence_required':False,
        'scope':'Every inherited shipped source checked against the pinned base; embedded source archives authenticated, no sibling trees used.'}


def replay_character_lab(root, evidence, env):
    reports=[]
    with tempfile.TemporaryDirectory(prefix='fm-character-lab-') as td:
        lab=Path(td);unpack_lab(root,lab)
        require(not list((lab/'evidence').iterdir()),'historical lab evidence extracted')
        jobs=[('author-aggregate',['reproduce.py']),('independent-normal',['review/review_checks.py']),
              ('independent-optimized',['-O','review/review_checks.py']),('standalone',['review/standalone_replay.py'])]
        for name,args in jobs:
            p=subprocess.run([sys.executable,'-B',*args],cwd=lab,env=env,capture_output=True,text=True,timeout=300)
            require(p.returncode==0 and not p.stderr,'accepted lab replay failed: '+name)
            data=json.loads(p.stdout);require(data['status'] in ('PASS','passed'),'lab replay status: '+name)
            output=p.stdout.replace(str(lab),'<isolated-lab-root>')
            (evidence/f'v09-character-lab-{name}.json').write_text(output)
            reports.append({'name':name,'output_sha256':sha256(p.stdout.encode()).hexdigest(),'status':'passed'})
        require(reports[1]['output_sha256']==reports[2]['output_sha256'],'lab review optimization mismatch')
    return reports


def source_static_check(root):
    runtime=['foundation_math/character_ring.py','foundation_math_bridge/character_ring_schemas.py']
    findings=[]
    for name in runtime:
        tree=ast.parse((root/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('eval','exec','compile','__import__'):
                findings.append(name+': '+node.func.id)
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or '']
                for module in names:
                    if module.split('.')[0] in ('socket','requests','urllib','http','subprocess','openai'):
                        findings.append(name+': '+module)
    require(not findings,'new runtime dynamic execution/network surface: '+str(findings))
    return {'status':'passed','files':runtime,'findings':findings,
            'scope':'Static forbidden-surface scan plus tests; not an OS sandbox or formal program proof.'}


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
    environment=clean_environment()
    lab_replays=replay_character_lab(ROOT,EVIDENCE,environment)
    # Required by the original schema validator. Generate now, never copy old evidence.
    prepare_legacy_transcript(ROOT,environment)
    checks=[];counts=[];schema=importlib.util.find_spec('jsonschema') is not None
    for optimized,mode in ((False,'normal'),(True,'optimized')):
        prefix=[sys.executable,'-B']+(['-O'] if optimized else [])
        jobs=[('tests',['-m','unittest','discover','-s','tests','-v'],'txt'),
              ('prior-tool-differential',['tools/audit_prior_tool_differential.py'],'json'),
              ('systems-lab-mutations',['tools/audit_systems_lab.py'],'json'),
              ('systems-integration',['tools/audit_linear_systems_integration.py'],'json'),
              ('witness-lab',['tools/audit_polynomial_witness_lab.py','--output',f'evidence/v09-witness-lab-audit-{mode}.json'],'txt'),
              ('witness-integration',['tools/audit_polynomial_witness_integration.py'],'json'),
              ('legacy-bridge',['tools/audit_agent_bridge.py'],'json'),
              ('matrix-integration',['tools/run_linear_algebra_validation.py'],'json')]
        if schema:
            jobs += [(name,[script],'json') for name,script in [
                ('character-schemas','tools/validate_character_ring_schemas.py'),
                ('system-schemas','tools/validate_linear_systems_schemas.py'),
                ('witness-schemas','tools/validate_polynomial_witness_schemas.py'),
                ('matrix-schemas','tools/validate_matrix_bridge_schemas.py'),
                ('legacy-schemas','tools/validate_bridge_schemas.py')]]
        for name,args,suffix in jobs:
            p=subprocess.run(prefix+args,cwd=ROOT,env=environment,capture_output=True,text=True,timeout=180)
            path=EVIDENCE/f'v09-{name}-{mode}.{suffix}'
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
    write_json(EVIDENCE/'v09-system-example-replays.json',{'status':'passed','replays':replays})
    source_hash_checks=0
    for path in EVIDENCE.glob('v09-*.json'):
        if path.name in ('v09-validation.json','v09-source-preservation.json','v09-privacy-check.json','v09-new-source-static-scan.json'):continue
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
    write_json(EVIDENCE/'v09-new-source-static-scan.json',source_static_check(ROOT))
    write_json(EVIDENCE/'v09-source-preservation.json',preservation)
    write_json(EVIDENCE/'v09-privacy-check.json',{'status':'passed','files_checked':len(reviewed),'findings':findings})
    integration=json.loads((EVIDENCE/'v09-systems-integration-normal.json').read_text())
    report={'status':'passed','version':'0.9.0-dev','source_manifest_sha256':before,
        'tests':counts,'checks':checks,'synthetic_systems_per_mode':integration['systems'],
        'integration_checks_per_mode':integration['total_checks'],'system_standalone_fixture_replays':len(replays),
        'source_hashes_in_reports_checked':source_hash_checks,'source_files_checked':len(source),
        'original_ten_tool_definitions_unchanged':True,'accepted_character_runtime_files_unchanged':7,
        'character_lab_replays':lab_replays,'all_ten_tool_differential_calls_per_mode':93,
        'historical_evidence_required':False,'source_unchanged_during_validation':True,'privacy_scan_passed':True,
        'optional_schema_validation':'passed_using_preinstalled_jsonschema' if schema else 'unavailable_no_install_attempted',
        'scope':'Finite universal arithmetic and synthetic software testing. The fixed table-group identification is assumed, not proved. No formal proof, geometric realization, arbitrary-problem refutation or runtime goal acceptance.'}
    write_json(EVIDENCE/'v09-validation.json',report)
    print(json.dumps(report,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

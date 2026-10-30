"""One portable v0.10 aggregate: manifest sources alone, fresh normal/-O evidence.

Only authenticated embedded archives supply historical dependencies. The aggregate
never consults a sibling checkout, installs software, calls models or a network.
"""
from hashlib import sha256
import ast,importlib.util,json,os,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from tools.build_split_bundle_release import verify,digest
from tools.split_bundle_release_support import require,environment,unpack_base,unpack_lab,BASE_MANIFEST_PIN,LAB_SOURCE_PIN
from tools.run_polynomial_witness_validation import prepare_legacy_transcript
from foundation_math_bridge.schemas import tool_definitions
ALLOWED_BASE_CHANGES={
 'README.md','docs/PROVENANCE.md','foundation_math/cli.py',
 'foundation_math_bridge/__init__.py','foundation_math_bridge/schemas.py','foundation_math_bridge/server.py',
 'tests/test_agent_bridge.py','tests/test_character_ring_integration.py','tests/test_linear_algebra_bridge.py',
 'tests/test_linear_systems_integration.py','tests/test_portable_validation.py',
 'tools/audit_linear_systems_integration.py','tools/audit_polynomial_witness_integration.py',
 'tools/run_linear_algebra_validation.py','tools/validate_character_ring_schemas.py',
}

def preservation(root):
 require(digest(root/'docs/BASE-V09-SOURCE-MANIFEST.json')==BASE_MANIFEST_PIN,'base manifest pin')
 require(digest(root/'docs/SPLIT-BUNDLE-LAB-SOURCE-MANIFEST.json')==LAB_SOURCE_PIN,'lab source pin')
 base=json.loads((root/'docs/BASE-V09-SOURCE-MANIFEST.json').read_text())['files']
 changed={name for name,h in base.items() if digest(root/name)!=h}
 require(changed==ALLOWED_BASE_CHANGES,'unexpected v0.9 changes: '+str(sorted(changed)))
 runtime=[n for n in base if n.startswith(('foundation_math/','bounded_counterexample/','exact_linalg/','exact_systems/','polynomial_witness/','character_ring/')) and n!='foundation_math/cli.py']
 require(all(digest(root/n)==base[n] for n in runtime),'inherited math/runtime changed')
 rows=json.loads((root/'docs/SPLIT-BUNDLE-LAB-SOURCE-MANIFEST.json').read_text())['files']
 # Lab SOURCE-MANIFEST pins only its seven inherited character files. Its
 # artifact manifest pins the complete accepted lab, including split_bundle.
 artifact=json.loads((root/'docs/SPLIT-BUNDLE-LAB-ARTIFACT-MANIFEST.json').read_text())['files']
 engine=[x for x in artifact if x['path'].startswith(('split_bundle/','character_ring/'))]
 fixtures=[x for x in artifact if x['path'].startswith('examples/')]
 require(len(engine)==12,'accepted engine inventory')
 for row in engine:require(digest(root/row['path'])==row['sha256'],'accepted engine changed '+row['path'])
 for row in fixtures:require(digest(root/'examples/split-bundle'/Path(row['path']).name)==row['sha256'],'accepted fixture changed')
 original=json.loads((root/'docs/BASE-V09-BRIDGE-TOOLS.json').read_text())['tools']
 require(len(original)==12 and len(tool_definitions())==14 and tool_definitions()[:12]==original,'twelve prior contracts changed')
 return {'status':'passed','v09_source_files_checked':len(base),'intentional_inherited_changes':sorted(changed),
 'inherited_math_runtime_files_unchanged':len(runtime),'accepted_engine_files_unchanged':len(engine),
 'accepted_fixture_files_unchanged':len(fixtures),'original_twelve_tool_definitions_unchanged':True,
 'runtime_verification_registry_unchanged':True}

def run_script(root,script,optimized=False,args=(),timeout=600):
 command=[sys.executable,'-I','-B']+(['-O'] if optimized else [])+['-c',
  'import runpy,sys;root=sys.argv[1];script=sys.argv[2];sys.path.insert(0,root);sys.argv=[root+"/"+script]+sys.argv[3:];runpy.run_path(sys.argv[0],run_name="__main__")',str(root),script,*args]
 p=subprocess.run(command,cwd=root,env=environment(),capture_output=True,text=True,timeout=timeout)
 require(p.returncode==0,script+' failed: '+(p.stdout+p.stderr)[-5000:])
 return p

def run_tests(root,optimized):
 command=[sys.executable,'-I','-B']+(['-O'] if optimized else [])+['-c',
  'import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=["unittest","discover","-s","tests","-v"];runpy.run_module("unittest",run_name="__main__")',str(root)]
 p=subprocess.run(command,cwd=root,env=environment(),capture_output=True,text=True,timeout=600)
 require(p.returncode==0,'full tests failed: '+(p.stdout+p.stderr)[-7000:])
 return p

def normalized(obj):return {k:v for k,v in obj.items() if k!='python_optimized'}
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def replay_inputs(evidence):
 reports={}
 with tempfile.TemporaryDirectory(prefix='fm-v010-frozen-') as td:
  tmp=Path(td);base=tmp/'base';lab=tmp/'lab';unpack_base(ROOT,base);unpack_lab(ROOT,lab)
  require(not (base/'evidence').exists(),'historical baseline evidence extracted')
  require(not list((lab/'evidence').iterdir()),'historical lab evidence extracted')
  p=run_script(base,'tools/run_character_ring_validation.py')
  data=json.loads(p.stdout);require(data['status']=='passed','v0.9 replay failed')
  dump(evidence/'v010-frozen-v09-replay.json',data);reports['frozen_v09_aggregate']=data
  jobs=('run_tests.py','review/review_checks.py','review/adversarial_controls.py')
  reports['split_bundle_lab']={}
  for script in jobs:
   outputs=[]
   for opt in (False,True):
    p=run_script(lab,script,opt);data=json.loads(p.stdout);require(data['status']=='PASS','accepted lab failed '+script)
    outputs.append(normalized(data))
    dump(evidence/('v010-lab-'+Path(script).stem+('-optimized' if opt else '-normal')+'.json'),data)
   require(outputs[0]==outputs[1],'accepted lab normal/-O mismatch '+script)
   reports['split_bundle_lab'][script]=outputs[0]
 return reports

def static_check(root):
 files=('foundation_math/split_bundle.py','foundation_math_bridge/split_bundle_schemas.py')
 findings=[]
 for name in files:
  for node in ast.walk(ast.parse((root/name).read_text())):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('eval','exec','compile','__import__'):findings.append(name+': '+node.func.id)
   if isinstance(node,(ast.Import,ast.ImportFrom)):
    imports=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or '']
    for mod in imports:
     if mod.split('.')[0] in ('socket','requests','urllib','http','subprocess','openai'):findings.append(name+': '+mod)
 require(not findings,'new runtime dynamic/network surface '+str(findings))
 return {'status':'passed','files':list(files),'findings':findings,'scope':'Static surface check, not an OS sandbox or formal proof.'}

def main():
 source=verify(ROOT);pin=digest(ROOT/'SOURCE-MANIFEST.json');preserved=preservation(ROOT)
 evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
 replay=replay_inputs(evidence)
 prepare_legacy_transcript(ROOT,environment())
 checks=[];counts=[];schema=importlib.util.find_spec('jsonschema') is not None
 for optimized,mode in ((False,'normal'),(True,'optimized')):
  p=run_tests(ROOT,optimized);text=(p.stdout+p.stderr).replace(str(ROOT),'<source-root>')
  (evidence/f'v010-tests-{mode}.txt').write_text(text)
  m=re.search(r'Ran (\d+) tests',text);skipped=re.search(r'OK \(skipped=(\d+)\)',text)
  require(m is not None,'missing full test count');counts.append({'optimization':int(optimized),'run':int(m[1]),'skipped':int(skipped[1]) if skipped else 0})
  jobs=[('twelve-tool-differential','tools/audit_v09_tool_differential.py',()),
   ('systems-lab-mutations','tools/audit_systems_lab.py',()),
   ('systems-integration','tools/audit_linear_systems_integration.py',()),
   ('witness-lab','tools/audit_polynomial_witness_lab.py',('--output',f'evidence/v010-witness-lab-{mode}.json')),
   ('witness-integration','tools/audit_polynomial_witness_integration.py',()),
   ('legacy-bridge','tools/audit_agent_bridge.py',()),
   ('matrix-integration','tools/run_linear_algebra_validation.py',())]
  if schema:jobs += [(name,script,()) for name,script in (
   ('split-bundle-schemas','tools/validate_split_bundle_schemas.py'),
   ('character-schemas','tools/validate_character_ring_schemas.py'),
   ('system-schemas','tools/validate_linear_systems_schemas.py'),
   ('witness-schemas','tools/validate_polynomial_witness_schemas.py'),
   ('matrix-schemas','tools/validate_matrix_bridge_schemas.py'),
   ('legacy-schemas','tools/validate_bridge_schemas.py'))]
  for name,script,args in jobs:
   p=run_script(ROOT,script,optimized,args);output=(p.stdout+p.stderr).replace(str(ROOT),'<source-root>')
   path=evidence/f'v010-{name}-{mode}.txt';path.write_text(output)
   checks.append({'name':name,'optimization':int(optimized),'exit_code':0,'evidence':str(path.relative_to(ROOT))})
  require((ROOT/'review/v010_review.py').is_file(),'independent integration review is required')
  p=run_script(ROOT,'review/v010_review.py',optimized);data=json.loads(p.stdout);require(data['status'] in ('PASS','passed'),'independent integration review failed')
  dump(evidence/f'v010-independent-review-{mode}.json',data)
  checks.append({'name':'independent-integration-review','optimization':int(optimized),'exit_code':0})
 require(verify(ROOT)==source and digest(ROOT/'SOURCE-MANIFEST.json')==pin,'source changed during aggregate')
 static=static_check(ROOT);dump(evidence/'v010-source-preservation.json',preserved);dump(evidence/'v010-static-check.json',static)
 # Only human-facing text/data is scanned; scripts legitimately discuss rejected markers.
 findings=[];scanned=0
 for path in ROOT.rglob('*'):
  if path.is_file() and path.suffix in ('.md','.json','.jsonl','.txt') and '__pycache__' not in path.parts and path.name!='v010-validation.json':
   scanned+=1;contents=path.read_text()
   for marker in ('/workspace/','/home/','file://','codex://','ghp_','sk-proj-','BEGIN PRIVATE KEY','BEGIN RSA PRIVATE KEY'):
    if marker in contents:findings.append({'file':str(path.relative_to(ROOT)),'marker':marker})
 require(not findings,'privacy/portability scan failed: '+str(findings))
 # Existing actual Lean integration is explicitly skipped when binary unavailable.
 from shutil import which
 lean='unavailable_explicit_test_skip' if which('lean') is None else 'available_see_test_evidence'
 result={'status':'passed','version':'0.10.0-dev','source_manifest_sha256':pin,'source_files_checked':len(source['files']),
 'tests':counts,'checks':checks,'source_preservation':preserved,'frozen_v09_replay_status':replay['frozen_v09_aggregate']['status'],
 'lab_author_checks_per_mode':replay['split_bundle_lab']['run_tests.py']['checks'],
 'lab_independent_checks_per_mode':replay['split_bundle_lab']['review/review_checks.py']['total'],
 'lab_detected_source_mutations':replay['split_bundle_lab']['review/adversarial_controls.py']['mutation_cases'],
 'optional_schema_validation':'passed_using_preinstalled_jsonschema' if schema else 'unavailable_no_install_attempted',
 'lean':lean,'historical_generated_evidence_required':False,'sibling_dependencies':False,
 'source_unchanged_during_validation':True,'privacy_scan_files':scanned,'privacy_scan_passed':True,
 'scope':'Bounded arithmetic conditional on a supplied formal splitting and marked catalog. No actual geometric realization, chosen map rank, Lean proof or runtime-goal promotion.'}
 dump(evidence/'v010-validation.json',result);print(json.dumps(result,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

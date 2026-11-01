"""Selected-only isolated normal/-O aggregate and byte-reproducible ZIP gate."""
from hashlib import sha256
import argparse,json,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_claim_ledger_release import create_zip,verify,digest
from tools.claim_ledger_release_support import environment,require

def execute(root,optimized):
 command=[sys.executable,'-I','-B']+(['-O'] if optimized else [])+['-c',
  'import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path(sys.argv[1]+"/tools/run_claim_ledger_validation.py",run_name="__main__")',str(root)]
 p=subprocess.run(command,cwd=root,env=environment(),capture_output=True,text=True,timeout=1800)
 require(p.returncode==0,'isolated aggregate failed '+('optimized' if optimized else 'normal')+': '+(p.stdout+p.stderr)[-7000:])
 data=json.loads(p.stdout);require(data['status']=='passed','aggregate nonpassing status');return data

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
 manifest=verify(ROOT);before=digest(ROOT/'SOURCE-MANIFEST.json')
 with tempfile.TemporaryDirectory(prefix='fm-v011-delivery-') as td:
  tmp=Path(td);a=tmp/'one.zip';b=tmp/'two.zip';receipt=create_zip(a);create_zip(b)
  require(a.read_bytes()==b.read_bytes(),'ZIP rebuild differs')
  clean=tmp/'selected-only';clean.mkdir()
  with zipfile.ZipFile(a) as z:
   names=sorted(list(manifest['files'])+['SOURCE-MANIFEST.json'])
   require(z.namelist()==names,'ZIP exact selected membership')
   for info in z.infolist():
    require(info.date_time==(2026,1,1,0,0,0) and info.create_system==3 and info.external_attr==0o100644<<16 and info.compress_type==zipfile.ZIP_DEFLATED,'ZIP metadata drift')
   z.extractall(clean)
  require(not (clean/'evidence').exists(),'generated historical evidence shipped')
  require(verify(clean)==manifest,'selected-only manifest mismatch')
  normal=execute(clean,False);optimized=execute(clean,True)
  require(normal==optimized,'normal/-O aggregate result differs')
  require(verify(clean)==manifest,'selected-only source changed')
  c=tmp/'rebuilt.zip';create_zip(c,clean);require(a.read_bytes()==c.read_bytes(),'isolated ZIP rebuild differs')
  # An integrity claim must fail, not silently refresh, after source corruption.
  fault=clean/'claim_revision/core.py';original=fault.read_bytes();fault.write_bytes(original+b'\n# source drift control\n')
  rejected=False
  try:verify(clean)
  except RuntimeError:rejected=True
  finally:fault.write_bytes(original)
  require(rejected,'source drift was accepted');verify(clean)
 require(verify(ROOT)==manifest and digest(ROOT/'SOURCE-MANIFEST.json')==before,'source changed during delivery gate')
 result={'status':'PASS','archive':receipt,'manifest_only_membership':True,'generated_outer_evidence_shipped':False,'embedded_review_history_is_not_execution_evidence':True,
  'isolated_aggregate_modes':['normal','optimized'],'normal_optimized_aggregate_identical':True,
  'zip_byte_reproducible':True,'isolated_zip_rebuild_identical':True,'source_drift_rejected':True,
  'sibling_tree_required':False,'aggregate':normal,
  'scope':'Bounded dependency applicability and software review only. No proof, truth, evidence acceptance or runtime promotion.'}
 if args.output:args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()

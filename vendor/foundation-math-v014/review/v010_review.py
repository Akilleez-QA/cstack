"""Independent integration checks. Formal supplied data, never actual geometry."""
from pathlib import Path
import sys,json,copy,hashlib,builtins
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from foundation_math.split_bundle import calculate_split_bundle,check_split_bundle_certificate
from foundation_math_bridge.server import _tool_result
from foundation_math_bridge.schemas import tool_definitions
N=0
def need(x,label):
 global N
 N+=1
 if not x:raise RuntimeError(label)
def req(bundle,twists):return {'schema':'fm-split-bundle-request-v1','operation':'cohomology','bundle':bundle,'twists':twists}
def block(r,a,m=1):return {'irrep':r,'twist':a,'multiplicity':m}
def flags(r):
 for k in ('formal_proof','runtime_goal_acceptance','geometric_realization','map_rank_claim'):need(r[k] is False,k)
 for k in ('table_group_identification_assumed','supplied_splitting_assumed'):need(r[k] is True,k)
def calc(q):
 r=calculate_split_bundle(q);need(r['status']=='success','calculate success');flags(r)
 c=r['result']['certificate'];v=check_split_bundle_certificate(q,c);need(v['status']=='success','certificate success');flags(v)
 need(r['request_sha256']==v['request_sha256'],'external request binding')
 for path,pin in r['implementation']['source_sha256'].items():need(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==pin,'implementation source pin')
 return c
labels=('1','W','A','S4','D','T6','P','Wp','V');dims=(1,2,3,4,5,6,4,2,3)
for label,dim in zip(labels,dims):
 for a in range(-5,6):
  q=req([block(label,a,2)],list(range(-3,4)));c=calc(q)
  for row in c['result']['twists']:
   t=row['twist'];need(row['rank']==2*dim,'rank');need(row['degree']==2*dim*(a+t),'twisted degree')
   need(row['h0']['dimension']==2*dim*max(a+t+1,0),'H0 dimension oracle')
   need(row['h1']['dimension']==2*dim*max(-a-t-1,0),'H1 dimension oracle')
   need(row['euler']['dimension']==2*dim*(a+t+1),'Euler dimension oracle')
  bad=copy.deepcopy(c);bad['result']['twists'][0]['h0']['dimension']+=1
  r=check_split_bundle_certificate(q,bad);need(r['status']=='error','forged certificate refused');need('result' not in r,'no partial result');flags(r)
  other=copy.deepcopy(q);other['bundle'][0]['multiplicity']=3
  need(check_split_bundle_certificate(other,c)['status']=='error','external request mismatch')
for source,sd in zip(labels,dims):
 for target,td in zip(labels,dims):
  q={'schema':'fm-split-bundle-request-v1','operation':'hom','source':[block(source,-2)],'target':[block(target,-2)]};c=calc(q)
  need(c['result']['hom_character']['dimension']==sd*td,'all sheaf Hom dimension')
  need(c['result']['equivariant_hom_dimension']==int(source==target),'physical Schur labels')
q=req([block('1',-10),block('1',-8),block('V',-8)],[8]);c=calc(q);r=c['result']['twists'][0]
need(r['h0']['multiplicities']==[1,0,0,0,0,0,0,0,1],'critical H0')
need(r['h1']['multiplicities']==[1,0,0,0,0,0,0,0,0],'critical H1')
need(r['euler']['multiplicities']==[0,0,0,0,0,0,0,0,1],'critical Euler')
a=calc(req([block('1',0),block('1',-2)],[-2,0,2]))
b=calc(req([block('W',-1)],[-2,0,2]))
for x,y in zip(a['result']['twists'],b['result']['twists']):need(x['euler']==y['euler'],'Euler collision')
need(a['result']['twists'][1]['h0']!=b['result']['twists'][1]['h0'],'Euler does not identify H0')
# Fresh verifier dispatch cannot import either producer or its request contract.
old=builtins.__import__
def guarded(name,*args,**kwargs):
 if name in ('split_bundle.producer','split_bundle.contract'):raise RuntimeError('forbidden producer or contract import')
 return old(name,*args,**kwargs)
builtins.__import__=guarded
try:
 r=check_split_bundle_certificate(q,c);need(r['status']=='success','independent verify imports')
finally:builtins.__import__=old
for key in ('multiplicity','twist'):
 for value in (True,1.0,'1'):
  invalid=copy.deepcopy(q);invalid['bundle'][0][key]=value
  r=calculate_split_bundle(invalid);need(r['status']=='error','exact type guard');flags(r)
wire=_tool_result('calculate_formal_split_bundle',{'request':q});need(wire['isError'] is False,'bridge calculate');need(wire['structuredContent']['runtime_goal_acceptance'] is False,'bridge no runtime promotion')
bad=copy.deepcopy(c);bad['scope']='actual_geometry_proved';wire=_tool_result('check_formal_split_bundle_certificate',{'request':q,'certificate':bad});need(wire['isError'] is True,'bridge forged scope');need(wire['structuredContent']['assessment']=='tool_error','bridge failure not acceptance')
review_pins=json.loads((ROOT/'review/V010-REVIEW-PINS.json').read_text())
for name,pin in review_pins.items():need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==pin,'reviewed source drift')
base=json.loads((ROOT/'docs/BASE-V09-BRIDGE-TOOLS.json').read_text())['tools'];need(tool_definitions()[:12]==base,'prior twelve schemas');need(len(tool_definitions())==14,'append only tools')
basepins=json.loads((ROOT/'docs/BASE-V09-SOURCE-MANIFEST.json').read_text())['files']
for name,pin in basepins.items():
 if name.startswith(('foundation_math/','character_ring/','exact_linalg/','exact_systems/','polynomial_witness/','bounded_counterexample/')) and name!='foundation_math/cli.py':need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==pin,'unchanged previous backend/runtime')
print(json.dumps({'status':'PASS','independent_checks':N,'scope':'integration and supplied-formal arithmetic; no Lean, geometric realization or runtime promotion'},indent=2))

"""Compare all ten unchanged tool contracts and responses against pinned v0.8."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.character_release_support import environment, require, unpack_base


def main():
    def read(name):
        return json.loads((ROOT / name).read_text())
    scalar = {'domain':'Q','operation':'add','operands':[{'numerator':1,'denominator':2},{'numerator':1,'denominator':3}]}
    finite = read('examples/counterexample/false-bounded-inequality.json')
    matrix = read('examples/linear-algebra/rectangular-matrix.json')
    system = read('examples/linear-systems/consistent-system.json')
    polynomial = read('examples/polynomial-witness/false-square.json')
    cases = [
        ('exact_scalar', scalar),
        ('polynomial_identity', read('examples/polynomial/distributivity.json')),
        ('finite_box_search', finite),
        ('check_finite_box_witness', {'request':finite,'assignment':read('examples/counterexample/valid-witness.json')}),
        ('certify_rational_matrix', {'matrix':matrix}),
        ('check_rational_matrix_certificate', {'matrix':matrix,'certificate':read('examples/linear-algebra/rectangular-certificate.json')}),
        ('construct_polynomial_witness', {'request':polynomial}),
        ('check_polynomial_witness', {'request':polynomial,'witness':read('examples/polynomial-witness/false-square-witness.json')}),
        ('solve_rational_linear_system', {'system':system}),
        ('check_rational_linear_system_certificate', {'system':system,'certificate':read('examples/linear-systems/consistent-certificate.json')}),
    ]
    names=[name for name,args in cases]
    # Every old tool receives a positive fixture and malformed/missing/extra/null controls.
    fixtures=[]
    for name,args in cases:
        fixtures.extend([(name,args),(name,{}),(name,dict(args,unrequested_claim=True)),(name,None)])
        for field in args:
            bad=deepcopy(args);bad[field]=None;fixtures.append((name,bad))
    for path in sorted((ROOT/'examples/polynomial-witness').glob('*.json')):
        if 'witness' not in path.stem:
            fixtures.append(('construct_polynomial_witness',{'request':json.loads(path.read_text())}))
    for path in sorted((ROOT/'examples/linear-systems').glob('*system.json')):
        fixtures.append(('solve_rational_linear_system',{'system':json.loads(path.read_text())}))
    for path in sorted((ROOT/'examples/counterexample').glob('*.json')):
        if path.name!='valid-witness.json':fixtures.append(('finite_box_search',json.loads(path.read_text())))
    frames=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'foundation-math-jsonrpc/1'}},
            {'jsonrpc':'2.0','id':'list','method':'tools/list'}]
    frames += [{'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':n,'arguments':a}}
               for i,(n,a) in enumerate(fixtures)]
    wire=b''.join(json.dumps(f,sort_keys=True,separators=(',',':')).encode()+b'\n' for f in frames)
    reports=[]
    with tempfile.TemporaryDirectory(prefix='fm-v08-differential-') as td:
        base=Path(td);unpack_base(ROOT,base)
        for flags in ([],['-O']):
            outputs=[]
            for tree in (base,ROOT):
                p=subprocess.run([sys.executable,'-B',*flags,'-m','foundation_math_bridge'],input=wire,cwd=tree,
                                 env=environment(),capture_output=True,timeout=90)
                require(p.returncode==0 and not p.stderr,'differential bridge execution')
                rows=[json.loads(x) for x in p.stdout.splitlines()]
                require(len(rows)==len(frames),'differential response count')
                outputs.append(rows)
            old,new=outputs
            old_version=old[0]['result']['serverInfo'].pop('version')
            new_version=new[0]['result']['serverInfo'].pop('version')
            require(old[0]==new[0],'only version may differ in initialization')
            require(old_version=='0.8.0-dev' and new_version=='0.9.0-dev','release version')
            old_tools=old[1]['result']['tools'];new_tools=new[1]['result']['tools']
            require(len(old_tools)==10 and len(new_tools)==12 and new_tools[:10]==old_tools,'ten prior contracts')
            require([t['name'] for t in old_tools]==names,'all prior tools covered')
            require(old[2:]==new[2:],'prior responses differ')
            # Each original fixture really exercises its successful old tool path.
            for name,args in cases:
                i=fixtures.index((name,args));response=old[2+i]
                require('result' in response and not response['result']['isError'],'positive fixture: '+name)
            reports.append({'optimization':int(bool(flags)),'calls':len(fixtures),'all_ten_contracts_identical':True,
                            'all_prior_responses_identical':True,'response_sha256':sha256(json.dumps(old[2:],sort_keys=True).encode()).hexdigest()})
    require(reports[0]['response_sha256']==reports[1]['response_sha256'],'optimized legacy differential')
    result={'status':'passed','tools':names,'runs':reports,'scope':'Finite differential replay plus byte-preserved backends; not an exhaustive proof of program equivalence.'}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())

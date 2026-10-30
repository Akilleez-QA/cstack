"""Independent synthetic integration arithmetic oracle; no backend test helpers."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from foundation_math.linear_systems import solve_system,check_system_certificate
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL

CHECKS={}

def require(condition,label):
    CHECKS[label]=CHECKS.get(label,0)+1
    if not condition:raise RuntimeError(label)

def frac(value):
    return Fraction(value) if type(value)==int else Fraction(value['num'],value['den'])

def token(value):
    return value.numerator if value.denominator==1 else {'num':value.numerator,'den':value.denominator}

def determinant(a):
    if not a:return Fraction(1)
    return sum(((-1)**j*a[0][j]*determinant([row[:j]+row[j+1:] for row in a[1:]]) for j in range(len(a))),Fraction(0))

def rank(a,n):
    for k in range(min(len(a),n),0,-1):
        for rows in combinations(range(len(a)),k):
            for cols in combinations(range(n),k):
                if determinant([[a[i][j] for j in cols] for i in rows]):return k
    return 0

def spec(a,b,n=None):
    return {'matrix':{'domain':'Q','rows':len(a),'cols':len(a[0]) if a else (n or 0),
                      'entries':[[token(Fraction(x)) for x in row] for row in a]},'rhs':[token(Fraction(x)) for x in b]}

def oracle(system,receipt):
    require(receipt['status']=='success','success')
    for flag in ('formal_proof','runtime_goal_acceptance','family_or_generic_claim'):
        require(receipt[flag] is False,'nonpromotion')
    result=receipt['result']['verification']
    a=[[frac(x) for x in row] for row in system['matrix']['entries']];b=list(map(frac,system['rhs']))
    m,n=len(a),system['matrix']['cols'];r=rank(a,n);ra=rank([row+[b[i]] for i,row in enumerate(a)],n+1)
    require((result['outcome']=='consistent')==(r==ra),'minor_consistency')
    require((result['rows'],result['cols'],result['input_domain'])==(m,n,system['matrix']['domain']),'input_metadata')
    if result['outcome']=='consistent':
        x=list(map(frac,result['particular']));basis=[[frac(v) for v in row] for row in result['nullspace']['entries']]
        require((result['rank'],result['nullity'])==(r,n-r),'minor_rank_nullity')
        require(len(x)==n and len(basis)==n and all(len(row)==n-r for row in basis),'basis_shape')
        require(rank(basis,n-r)==n-r,'basis_independence')
        for i,row in enumerate(a):
            require(sum((row[j]*x[j] for j in range(n)),Fraction(0))==b[i],'particular')
            for k in range(n-r):require(sum((row[j]*basis[j][k] for j in range(n)),Fraction(0))==0,'kernel_membership')
        for c in (Fraction(-3,2),Fraction(0),Fraction(7,5)):
            point=[x[j]+sum((basis[j][k]*(c+k) for k in range(n-r)),Fraction(0)) for j in range(n)]
            require(all(sum((row[j]*point[j] for j in range(n)),Fraction(0))==b[i] for i,row in enumerate(a)),'affine_combinations')
    else:
        y=list(map(frac,result['left_nullvector']));require(len(y)==m,'left_witness_shape')
        require(all(sum((y[i]*a[i][j] for i in range(m)),Fraction(0))==0 for j in range(n)),'left_annihilator')
        pairing=sum((y[i]*b[i] for i in range(m)),Fraction(0))
        require(pairing!=0 and pairing==frac(result['rhs_pairing']),'nonzero_pairing')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode('ascii')


def main():
    definitions=tool_definitions();frozen=json.loads((ROOT/'docs/BASE-V07-PORTABLE-BRIDGE-TOOLS.json').read_text())['tools']
    require(len(definitions)==15 and definitions[:8]==frozen,'prior_tool_preservation')
    cases=[]
    for m,n in ((0,0),(0,3),(1,0),(2,0),(1,1),(1,2),(2,1),(2,2)):
        for values in product((-1,0,1),repeat=m*n+m):
            a=[list(values[i*n:(i+1)*n]) for i in range(m)];b=list(values[m*n:]);cases.append(spec(a,b,n))
    exhaustive=len(cases)
    rng=random.Random(80820261024)
    for sample in range(200):
        m,n=rng.randrange(5),rng.randrange(5)
        a=[[Fraction(rng.randrange(-3,4),rng.randrange(1,5)) for j in range(n)] for i in range(m)]
        if sample%3==0 and m>=2:a[-1]=[2*x for x in a[0]]
        if sample%2:
            x=[Fraction(rng.randrange(-4,5),rng.randrange(1,6)) for j in range(n)]
            b=[sum((row[j]*x[j] for j in range(n)),Fraction(0)) for row in a]
        else:b=[Fraction(rng.randrange(-4,5),rng.randrange(1,6)) for i in range(m)]
        cases.append(spec(a,b,n))
    bridge=Bridge();bridge.dispatch({'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':PROTOCOL}})
    outcomes={'consistent':0,'inconsistent':0}
    for number,system in enumerate(cases):
        receipt=solve_system(system);oracle(system,receipt)
        cert=receipt['result']['certificate'];outcomes[cert['outcome']]+=1
        check=check_system_certificate(system,cert);oracle(system,check)
        require(receipt['request_sha256']==sha256(canonical({'operation':'solve','system':system})).hexdigest(),'request_binding')
        for name,args in [('solve_rational_linear_system',{'system':system}),
                          ('check_rational_linear_system_certificate',{'system':system,'certificate':cert})]:
            response=bridge.dispatch({'jsonrpc':'2.0','id':number+1,'method':'tools/call','params':{'name':name,'arguments':args}})['result']
            require(not response['isError'],'bridge_success');oracle(system,response['structuredContent']['receipt'])
        changed=deepcopy(system)
        if system['rhs']:
            changed['rhs'][0]=token(frac(changed['rhs'][0])+1)
            rejection=check_system_certificate(changed,cert)
            require(rejection['status']=='error' and 'result' not in rejection,'external_rhs_binding')
        changed=deepcopy(cert);changed['formal_proof']=True
        require(check_system_certificate(system,changed)['status']=='error','certificate_scope_injection')
    messages=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':PROTOCOL}},
              {'jsonrpc':'2.0','id':'list','method':'tools/list'},
              {'jsonrpc':'2.0','method':'tools/call','params':{'name':'solve_rational_linear_system','arguments':{}}}]
    for name,system in [('consistent',spec([[2,1]],[1])),('inconsistent',spec([[0]],[1])),('empty',spec([],[],2))]:
        cert=solve_system(system)['result']['certificate']
        messages.append({'jsonrpc':'2.0','id':name,'method':'tools/call','params':{'name':'solve_rational_linear_system','arguments':{'system':system}}})
        messages.append({'jsonrpc':'2.0','id':name+'-check','method':'tools/call','params':{'name':'check_rational_linear_system_certificate','arguments':{'system':system,'certificate':cert}}})
    messages.append({'jsonrpc':'2.0','id':'reject','method':'tools/call','params':{'name':'check_rational_linear_system_certificate','arguments':{'system':cases[-1],'certificate':{}}}})
    wire=b'\n'.join(map(canonical,messages))+b'\n';outputs=[]
    for optimized in (False,True):
        p=subprocess.run([sys.executable,'-B']+(['-O'] if optimized else [])+['-m','foundation_math_bridge'],input=wire,cwd=ROOT,capture_output=True,timeout=20)
        require(p.returncode==0 and not p.stderr,'stdio_clean');outputs.append(p.stdout)
    require(outputs[0]==outputs[1],'stdio_optimization_equal')
    responses=[json.loads(line) for line in outputs[0].splitlines()]
    require(len(responses)==len(messages)-1,'silent_notification')
    require(responses[-1]['result']['isError'] and responses[-1]['result']['structuredContent']['assessment']=='tool_error','stdio_rejection')
    names=['foundation_math/linear_systems.py','foundation_math/cli.py','foundation_math_bridge/server.py',
           'foundation_math_bridge/schemas.py','foundation_math_bridge/linear_systems_schemas.py','tools/audit_linear_systems_integration.py']
    print(json.dumps({'status':'passed','optimization':sys.flags.optimize,'checks':CHECKS,'total_checks':sum(CHECKS.values()),
        'exhaustive_ternary_systems':exhaustive,'seeded_rational_systems':200,'systems':len(cases),'outcomes':outcomes,
        'oracle':'Independent recursive Laplace-minor ranks and direct rational products, no elimination or backend test helpers.',
        'source_sha256':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
        'stdio_requests_including_notification':len(messages),'stdio_responses':len(responses),
        'normal_optimized_transcript_identical':True,'response_sha256':sha256(outputs[0]).hexdigest(),
        'scope':'Finite synthetic integration evidence, not formal proof, arbitrary-code isolation or family/runtime promotion.'},indent=2,sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())

"""Optional preinstalled JSON Schema audit. Never install or access a network."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL
from foundation_math_bridge.linear_systems_schemas import SOLVE, CHECK
from foundation_math.linear_systems import solve_system


def main():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print(json.dumps({'status':'unavailable','reason':'No preinstalled jsonschema; no installation attempted.'})); return 2
    checks=0
    def require(condition,label):
        nonlocal checks
        checks+=1
        if not condition:raise RuntimeError(label)
    definitions={tool['name']:tool for tool in tool_definitions()}
    for tool in definitions.values():
        for key in ('inputSchema','outputSchema'):
            Draft202012Validator.check_schema(tool[key]);checks+=1
    bridge=Bridge();bridge.dispatch({'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':PROTOCOL}})
    def call(name,args):
        response=bridge.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}})
        content=response['result']['structuredContent']
        validator=Draft202012Validator(definitions[name]['outputSchema'])
        errors=list(validator.iter_errors(content))
        require(not errors,'actual output violates schema: '+('; '.join(error.message for error in errors[:2])))
        return content
    fixtures=[{'matrix':{'domain':'Z','rows':1,'cols':1,'entries':[[2]]},'rhs':[1]},
              {'matrix':{'domain':'Z','rows':2,'cols':1,'entries':[[1],[1]]},'rhs':[0,1]},
              {'matrix':{'domain':'Q','rows':1,'cols':2,'entries':[[{'num':1,'den':2},1]]},'rhs':[{'num':1,'den':3}]},
              {'matrix':{'domain':'Q','rows':0,'cols':3,'entries':[]},'rhs':[]},
              {'matrix':{'domain':'Z','rows':2,'cols':0,'entries':[[],[]]},'rhs':[0,1]},
              {'matrix':{'domain':'Z','rows':0,'cols':0,'entries':[]},'rhs':[]}]
    for system in fixtures:
        certificate=solve_system(system)['result']['certificate']
        for name in (SOLVE,CHECK):
            args={'system':system}
            if name==CHECK:args['certificate']=certificate
            inp=Draft202012Validator(definitions[name]['inputSchema'])
            out=Draft202012Validator(definitions[name]['outputSchema'])
            require(inp.is_valid(args),'good input rejected')
            actual=call(name,args)
            for field in ('path','limits','command','formal_proof','runtime_goal_acceptance'):
                require(not inp.is_valid({**args,field:True}),'extra input field accepted')
            for field in ('formal_proof','runtime_goal_acceptance'):
                forged=deepcopy(actual);forged[field]=True;require(not out.is_valid(forged),'envelope promotion')
            for field,value in [('formal_proof',True),('runtime_goal_acceptance',True),('family_or_generic_claim',True),('scope','family'),('computational_field','Z')]:
                forged=deepcopy(actual);forged['receipt'][field]=value;require(not out.is_valid(forged),'receipt promotion')
                forged=deepcopy(actual);forged['receipt']['result']['verification'][field]=value;require(not out.is_valid(forged),'verification promotion')
            forged=deepcopy(actual);forged['assessment']='tool_error';require(not out.is_valid(forged),'incorrect successful assessment')
            forged=deepcopy(actual);forged['receipt']['result']['verification']['outcome']='inconsistent' if certificate['outcome']=='consistent' else 'consistent'
            require(not out.is_valid(forged),'wrong outcome fields accepted')
            if name==SOLVE:
                forged=deepcopy(actual);forged['receipt']['result']['certificate']['outcome']='inconsistent' if certificate['outcome']=='consistent' else 'consistent'
                require(not out.is_valid(forged),'mismatched certificate branch')
            else:
                forged=deepcopy(actual);forged['receipt']['result']['certificate']=certificate
                require(not out.is_valid(forged),'check response must not carry producer certificate')
            invalid=deepcopy(args);invalid['system']['rhs']=[True]
            require(not inp.is_valid(invalid),'bool coefficient accepted')
            failed=call(name,invalid)
            require(failed['assessment']=='tool_error','invalid input not tool error')
            forged=deepcopy(failed);forged['receipt']['result']={'accepted':True};require(not out.is_valid(forged),'error carries partial acceptance')
    z=deepcopy(fixtures[0]);z['rhs']=[{'num':1,'den':2}]
    require(not Draft202012Validator(definitions[SOLVE]['inputSchema']).is_valid({'system':z}),'Z RHS fractional token accepted')
    # Shape, gcd and semantic equations remain runtime checks, not schema promises.
    malformed=deepcopy(fixtures[0]);malformed['rhs']=[]
    require(Draft202012Validator(definitions[SOLVE]['inputSchema']).is_valid({'system':malformed}),'structural schema unexpectedly enforces dependent shape')
    require(call(SOLVE,{'system':malformed})['assessment']=='tool_error','runtime shape not enforced')
    bad=deepcopy(solve_system(fixtures[0])['result']['certificate']);bad['particular']=[0]
    require(Draft202012Validator(definitions[CHECK]['inputSchema']).is_valid({'system':fixtures[0],'certificate':bad}),'structural schema unexpectedly proves equation')
    require(call(CHECK,{'system':fixtures[0],'certificate':bad})['assessment']=='tool_error','invalid equation accepted')
    names=['foundation_math_bridge/linear_systems_schemas.py','tools/validate_linear_systems_schemas.py']
    print(json.dumps({'status':'passed','checks':checks,'optimization':sys.flags.optimize,
        'dependency':'Preinstalled jsonschema only; no install or runtime dependency.',
        'source_sha256':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
        'scope':'Structural schemas and runtime semantic rejection distinguished; not a proof kernel.'},indent=2,sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())

"""Read-only local CLI; output is stdout, errors are structured stderr."""
import json,sys
from .contract import BUDGETS,DomainError,read_json

def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    try:
        if len(args)==2 and args[0]=='calculate':
            from .producer import calculate
            out=calculate(read_json(args[1],BUDGETS['request_bytes']))
        elif len(args)==3 and args[0]=='check':
            from .verifier import verify
            out=verify(read_json(args[1],BUDGETS['request_bytes']),read_json(args[2],BUDGETS['certificate_bytes']))
        else:raise DomainError('E_USAGE','Usage: python -m character_ring calculate REQUEST.json | check REQUEST.json CERTIFICATE.json')
        print(json.dumps(out,sort_keys=True,indent=2,allow_nan=False));return 0
    except Exception as e:
        # Unexpected exceptions are not reported as valid mathematical rejection.
        code=getattr(e,'code',None)
        if code is None:code='E_INTERNAL';message='Unexpected implementation failure'
        else:message=str(e)
        print(json.dumps({'status':'error','code':code,'message':message},sort_keys=True),file=sys.stderr)
        return 3 if code=='E_EXPECTATION' else 4 if code=='E_INTERNAL' else 2
if __name__=='__main__':sys.exit(main())

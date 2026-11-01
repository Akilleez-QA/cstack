"""Read-only bounded file CLI. No path is accepted inside mathematical requests."""
import json
import sys
from .contract import read_json,DomainError

def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    try:
        if len(args)==2 and args[0]=='calculate':
            from .producer import calculate
            out=calculate(read_json(args[1],65536))
        elif len(args)==3 and args[0]=='check':
            from .verifier import verify
            out=verify(read_json(args[1],65536),read_json(args[2],2097152))
        else:raise DomainError('E_USAGE','Usage: python -B -m exterior_power calculate REQUEST.json | check REQUEST.json CERTIFICATE.json')
        print(json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False));return 0
    except Exception as e:
        code=getattr(e,'code','E_INTERNAL')
        message=str(e) if code!='E_INTERNAL' else 'Unexpected implementation failure'
        print(json.dumps({'status':'error','code':code,'message':message},sort_keys=True),file=sys.stderr)
        return 4 if code=='E_INTERNAL' else 2
if __name__=='__main__':sys.exit(main())

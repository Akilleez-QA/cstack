"""python -m split_bundle calculate REQUEST | verify REQUEST CERTIFICATE"""
import argparse,json,sys
from .contract import DomainError,read_json
from .verifier import VerificationError,verify

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    c=sp.add_parser('calculate');c.add_argument('request')
    v=sp.add_parser('verify');v.add_argument('request');v.add_argument('certificate')
    args=p.parse_args()
    try:
        req=read_json(args.request,65536)
        if args.command=='calculate':
            from .producer import calculate
            out=calculate(req)
        else:out=verify(req,read_json(args.certificate,262144))
        print(json.dumps(out,sort_keys=True,indent=2));return 0
    except (ValueError,OSError) as e:
        print(json.dumps({'status':'error','code':getattr(e,'code','E_VALUE'),'message':str(e)},sort_keys=True),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

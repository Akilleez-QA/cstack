"""Formal finite exterior powers using integer fusion and pinned seed polynomials."""
from fractions import Fraction as F
from .contract import (parse_request, guard, digest, PIN, SCOPE, ASSUMPTIONS,
                       LABELS, DIMS, SIGNS, need)
from . import fusion


def sparse(m): return {s:n for s,n in zip(LABELS,m) if n}
def parity(signs):
    s=set(signs)
    return 'zero' if not s else 'even' if s=={1} else 'odd' if s=={-1} else 'mixed'

def character(m,cat):
    values=[]
    for c in range(9):
        a=b=F(0)
        for i,n in enumerate(m):
            p,q,r,s=cat['characters'][i][c]
            a+=n*F(p,q); b+=n*F(r,s)
        values.append([a.numerator,a.denominator,b.numerator,b.denominator])
    return {'multiplicities':sparse(m), 'dimension':sum(n*d for n,d in zip(m,DIMS)),
            'module_center_parity':parity(SIGNS[i] for i,n in enumerate(m) if n), 'class_values':values}

def stats(blocks):
    rank=sum(DIMS[LABELS.index(b['irrep'])]*b['multiplicity'] for b in blocks)
    degree=sum(DIMS[LABELS.index(b['irrep'])]*b['multiplicity']*b['twist'] for b in blocks)
    return {'rank':rank,'degree':degree,'determinant':{'module':{'1':1},'line_degree':degree}}

def describe_bundle(coeff,cat):
    terms=[]; rank=degree=0; signs=[]
    for d,m in sorted(coeff.items()):
        if not any(m):continue
        ch=character(m,cat); rank+=ch['dimension']; degree+=d*ch['dimension']
        ss=[SIGNS[i]*(-1 if d%2 else 1) for i,n in enumerate(m) if n]
        signs.extend(ss)
        terms.append({'line_degree':d,'character':ch,'bundle_center_parity':parity(ss)})
    return {'terms':terms,'rank':rank,'degree':degree,'bundle_center_parity':parity(signs),
            'determinant':{'module':{'1':1},'line_degree':degree}}

def h0(coeff,t,cat):
    out=fusion.ZERO
    for d,m in coeff.items():
        if d+t>=0:out=fusion.add(out,fusion.tensor(m,fusion.symmetric(d+t,cat),cat))
    return out

def calculate(request):
    req=parse_request(request);cat,seeds=fusion.load_inputs(); maximum=max(req['orders'])
    op=req['operation']
    if op=='representation':
        blocks=[{'irrep':s,'twist':0,'multiplicity':n} for s,n in req['representation'].items()]
        powers=fusion.exterior_graded(blocks,maximum,cat,seeds)
        result={'operation':op,'input_dimension':stats(blocks)['rank'],
                'powers':[{'order':k,'character':character(powers[k].get(0,fusion.ZERO),cat)} for k in req['orders']]}
    elif op=='bundle':
        powers=fusion.exterior_graded(req['bundle'],maximum,cat,seeds)
        result={'operation':op,'input':stats(req['bundle']),
                'powers':[{'order':k,'bundle':describe_bundle(powers[k],cat)} for k in req['orders']]}
    else:
        source=fusion.exterior_graded(req['source'],maximum,cat,seeds)
        target=fusion.exterior_graded(req['target'],maximum,cat,seeds)
        rows=[]
        for k in req['orders']:
            for t in req['twists']:
                a=h0(source[k],t,cat);b=h0(target[k],t,cat)
                difference=tuple(y-x for x,y in zip(a,b))
                rows.append({'order':k,'twist':t,'source_h0':character(a,cat),'target_h0':character(b,cat),
                    'target_minus_source':sparse(difference),
                    'multiplicity_test':'passes' if min(difference)>=0 else 'obstructed'})
        result={'operation':op,'source':stats(req['source']),'target':stats(req['target']),'comparisons':rows,
                'conclusion':'finite_necessary_tests_only_not_sufficient_for_any_map_or_injection'}
    certificate={'schema':'fm-exterior-certificate-v1','catalog_sha256':PIN,'request_sha256':digest(req),
                 'request':req,'result':result,'scope':SCOPE,'assumptions':ASSUMPTIONS.copy()}
    guard(certificate,2097152)
    return certificate

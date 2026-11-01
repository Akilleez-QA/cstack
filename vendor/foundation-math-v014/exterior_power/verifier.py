"""Independent mathematical checker: no producer, fusion, or seed imports.

Shares the explicit transport/schema contract, not the arithmetic implementation.
Each entire certificate is independently rebuilt from exact Adams/Newton values.
"""
from .contract import (parse_request, guard, canonical, digest, PIN, SCOPE, ASSUMPTIONS,
                       LABELS, DIMS, SIGNS, need)
from . import class_arithmetic as ca


def parity(signs):
    s=set(signs)
    if not s:return 'zero'
    if len(s)>1:return 'mixed'
    return 'even' if 1 in s else 'odd'

def sparse(m):return {LABELS[i]:n for i,n in enumerate(m) if n}
def describe(ch,rows):
    m=ca.decompose(ch,rows)
    return {'multiplicities':sparse(m),'dimension':sum(DIMS[i]*m[i] for i in range(9)),
            'module_center_parity':parity(SIGNS[i] for i,n in enumerate(m) if n),
            'class_values':[ca.encode(v) for v in ch]}

def stats(blocks):
    r=d=0
    for b in blocks:
        n=DIMS[LABELS.index(b['irrep'])]*b['multiplicity'];r+=n;d+=b['twist']*n
    return {'rank':r,'degree':d,'determinant':{'module':{'1':1},'line_degree':d}}

def describe_bundle(coeff,rows):
    terms=[];rank=degree=0;signs=[]
    for d,ch in sorted(coeff.items()):
        c=describe(ch,rows);m=ca.decompose(ch,rows)
        ss=[SIGNS[i]*(-1 if d%2 else 1) for i,n in enumerate(m) if n]
        terms.append({'line_degree':d,'character':c,'bundle_center_parity':parity(ss)})
        rank+=c['dimension'];degree+=d*c['dimension'];signs.extend(ss)
    return {'terms':terms,'rank':rank,'degree':degree,'bundle_center_parity':parity(signs),
            'determinant':{'module':{'1':1},'line_degree':degree}}

def h0(coeff,t,rows):
    answer=[ca.ZERO]*9
    for degree,ch in coeff.items():
        if degree+t>=0:
            for c in range(9):
                answer[c]=ca.add(answer[c],ca.mul(ch[c],ca.symmetric_class(degree+t,rows[1][c])))
    return tuple(answer)

def expected(request):
    req=parse_request(request); rows=ca.table();maximum=max(req['orders']);op=req['operation']
    if op=='representation':
        blocks=[{'irrep':s,'twist':0,'multiplicity':n} for s,n in req['representation'].items()]
        powers=ca.exterior_graded(blocks,maximum,rows)
        result={'operation':op,'input_dimension':stats(blocks)['rank'],
                'powers':[{'order':k,'character':describe(powers[k].get(0,(ca.ZERO,)*9),rows)} for k in req['orders']]}
    elif op=='bundle':
        powers=ca.exterior_graded(req['bundle'],maximum,rows)
        result={'operation':op,'input':stats(req['bundle']),
                'powers':[{'order':k,'bundle':describe_bundle(powers[k],rows)} for k in req['orders']]}
    else:
        source=ca.exterior_graded(req['source'],maximum,rows)
        target=ca.exterior_graded(req['target'],maximum,rows)
        tests=[]
        for k in req['orders']:
            for t in req['twists']:
                a=h0(source[k],t,rows);b=h0(target[k],t,rows)
                ma=ca.decompose(a,rows);mb=ca.decompose(b,rows)
                difference=tuple(mb[i]-ma[i] for i in range(9))
                tests.append({'order':k,'twist':t,'source_h0':describe(a,rows),'target_h0':describe(b,rows),
                    'target_minus_source':sparse(difference),
                    'multiplicity_test':'passes' if all(v>=0 for v in difference) else 'obstructed'})
        result={'operation':op,'source':stats(req['source']),'target':stats(req['target']),'comparisons':tests,
                'conclusion':'finite_necessary_tests_only_not_sufficient_for_any_map_or_injection'}
    out={'schema':'fm-exterior-certificate-v1','catalog_sha256':PIN,'request_sha256':digest(req),
         'request':req,'result':result,'scope':SCOPE,'assumptions':ASSUMPTIONS.copy()}
    guard(out,2097152)
    return out

def verify(request,certificate):
    guard(certificate,2097152)
    want=expected(request)
    need(canonical(certificate)==canonical(want),'E_CERTIFICATE','Certificate differs from independent Adams/Newton recomputation')
    return {'status':'verified','scope':SCOPE,'request_sha256':want['request_sha256'],
            'runtime_acceptance':False,'lean_proof':False,'geometric_realization':False,
            'map_existence_or_injectivity':False}

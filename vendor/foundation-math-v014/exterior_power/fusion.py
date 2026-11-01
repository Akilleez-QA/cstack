"""Integer representation-ring producer. No class/Newton arithmetic imports."""
from pathlib import Path
import hashlib
import json
from .contract import need, PIN, LABELS, DIMS

ZERO = (0,)*9
ONE = (1,)+(0,)*8

def load_inputs():
    here = Path(__file__).parent
    raw = (here/'catalog.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == PIN, 'E_CATALOG', 'Fixed catalog pin mismatch')
    c = json.loads(raw)
    seed_raw = (here/'seeds.json').read_bytes()
    need(hashlib.sha256(seed_raw).hexdigest() == '0476eb520e3f8910828b4762fac3e88e16b12ba8f35ebe782c4e357c06ff1656', 'E_CATALOG', 'Exterior seed pin mismatch')
    seeds = json.loads(seed_raw)
    return c, {label: tuple(tuple(x) for x in seeds[label]) for label in LABELS}

def add(a,b): return tuple(x+y for x,y in zip(a,b))
def scale(n,a): return tuple(n*x for x in a)
def tensor(a,b,cat):
    ans = [0]*9
    for i,x in enumerate(a):
        if not x: continue
        for j,y in enumerate(b):
            if y:
                for k,n in enumerate(cat['fusion'][i][j]): ans[k] += x*y*n
    need(all(abs(v).bit_length() <= 256 for v in ans), 'E_BUDGET', 'Fusion coefficient budget exceeded')
    return tuple(ans)

def exterior_graded(blocks, maximum, cat, seeds):
    """Multiply exact finite lambda polynomials of each repeated direct summand.

Only requested coefficients are projected; no degree support or nonzero term is
silently truncated. Multiplicity means repeated copies, not scalar lambda powers.
"""
    result = [{0:ONE}]+[{} for _ in range(maximum)]
    for b in blocks:
        factors = seeds[b['irrep']]
        for _ in range(b['multiplicity']):
            nxt = [{} for _ in range(maximum+1)]
            for i, source in enumerate(result):
                for j, rep in enumerate(factors):
                    if i+j > maximum: break
                    for degree, value in source.items():
                        d = degree+j*b['twist']
                        nxt[i+j][d] = add(nxt[i+j].get(d,ZERO), tensor(value,rep,cat))
            need(sum(map(len,nxt)) <= 8192, 'E_BUDGET', 'Intermediate degree-term budget exceeded')
            result = nxt
    return result

def symmetric(n, cat):
    need(type(n) is int and 0 <= n <= 400, 'E_BUDGET', 'Symmetric degree bound exceeded')
    a,b = ZERO,ONE
    w = (0,1,0,0,0,0,0,0,0)
    for _ in range(n): a,b = b,add(tensor(w,b,cat),scale(-1,a))
    return b

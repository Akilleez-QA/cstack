"""Exact Q(sqrt(5)) and independently evaluated Adams/Newton class functions.

No fusion table, exterior seeds, or producer imports. Power classes follow the
faithful determinant-one W trace recurrence, not character multiplication.
"""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
from .contract import DomainError, need, PIN, LABELS, DIMS, SIGNS

SIZES = (1, 1, 30, 20, 20, 12, 12, 12, 12)
ZERO = (F(0), F(0))
ONE = (F(1), F(0))

def q(a=0, b=0): return F(a), F(b)
def add(x, y): return x[0]+y[0], x[1]+y[1]
def mul(x, y): return x[0]*y[0]+5*x[1]*y[1], x[0]*y[1]+x[1]*y[0]
def scale(n, x): return n*x[0], n*x[1]
def encode(x): return [x[0].numerator, x[0].denominator, x[1].numerator, x[1].denominator]
def total(xs):
    ans = ZERO
    for x in xs: ans = add(ans, x)
    return ans

def table():
    raw = Path(__file__).with_name('catalog.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == PIN, 'E_CATALOG', 'Fixed catalog pin mismatch')
    c = json.loads(raw)
    need(tuple(c['labels']) == LABELS and tuple(c['dimensions']) == DIMS and tuple(c['center_signs']) == SIGNS,
         'E_CATALOG', 'Physical catalog metadata mismatch')
    rows = tuple(tuple((F(a,b), F(c,d)) for a,b,c,d in row) for row in c['characters'])
    for i, row in enumerate(rows):
        need(row[0] == q(DIMS[i]) and row[1] == q(DIMS[i]*SIGNS[i]), 'E_CATALOG', 'Dimension/parity mismatch')
        for j, other in enumerate(rows):
            need(inner(row, other) == q(int(i == j)), 'E_CATALOG', 'Orthogonality mismatch')
    return rows

def inner(a, b): return total(scale(F(s, 120), mul(x, y)) for s,x,y in zip(SIZES,a,b))
def combine(m, rows): return tuple(total(scale(m[i], rows[i][j]) for i in range(9)) for j in range(9))
def decompose(ch, rows):
    ans = []
    for row in rows:
        a,b = inner(ch, row)
        need(b == 0 and a.denominator == 1, 'E_CHARACTER', 'Nonintegral character decomposition')
        need(a >= 0 and a.numerator.bit_length() <= 256, 'E_CHARACTER', 'Non-genuine or oversized exterior coefficient')
        ans.append(int(a))
    need(combine(ans, rows) == tuple(ch), 'E_CHARACTER', 'Character reconstruction failed')
    return tuple(ans)

def class_powers(rows, maximum=25):
    need(type(maximum) is int and 0 <= maximum <= 25, 'E_BUDGET', 'Power bound exceeded')
    traces = rows[1]
    powers = []
    for x in traces:
        seq = [q(2)]
        if maximum: seq.append(x)
        for _ in range(2, maximum+1): seq.append(add(mul(x, seq[-1]), scale(-1, seq[-2])))
        need(all(v in traces for v in seq), 'E_CATALOG', 'Class power has unknown trace')
        powers.append(tuple(traces.index(v) for v in seq))
    return tuple(powers)

def adams(ch, k, powers):
    need(type(k) is int and 1 <= k <= 25, 'E_BUDGET', 'Adams order outside bound')
    return tuple(ch[powers[c][k]] for c in range(9))

def exterior_graded(blocks, maximum, rows=None):
    """Graded Newton identity; computes every coefficient through requested order.

Degrees are exact Laurent exponents, not a support cutoff. Above-rank values are
computed as zero by the identity rather than silently dropped.
"""
    rows = table() if rows is None else rows
    powers = class_powers(rows, maximum)
    initial = {}
    for b in blocks:
        a, i, m = b['twist'], LABELS.index(b['irrep']), b['multiplicity']
        old = initial.get(a, (ZERO,)*9)
        initial[a] = tuple(add(old[c], scale(m, rows[i][c])) for c in range(9))
    result = [{0: (ONE,)*9}]
    for n in range(1, maximum+1):
        out = {}
        for k in range(1, n+1):
            sign = F(1 if k % 2 else -1, n)
            for a, ch in initial.items():
                trace = adams(ch, k, powers)
                for d, prev in result[n-k].items():
                    degree = d+k*a
                    value = tuple(scale(sign, mul(x,y)) for x,y in zip(prev,trace))
                    old = out.get(degree, (ZERO,)*9)
                    out[degree] = tuple(add(x,y) for x,y in zip(old,value))
        out = {d: ch for d,ch in out.items() if any(v != ZERO for v in ch)}
        need(len(out) <= 8192, 'E_BUDGET', 'Intermediate degree-term budget exceeded')
        for ch in out.values():
            need(all(abs(v.numerator).bit_length() <= 256 and v.denominator.bit_length() <= 256 for x in ch for v in x),
                 'E_BUDGET', 'Exact field component budget exceeded')
        result.append(out)
    return result

def symmetric_class(n, x):
    need(type(n) is int and 0 <= n <= 400, 'E_BUDGET', 'Symmetric degree bound exceeded')
    a,b = ZERO,ONE
    for _ in range(n): a,b = b,add(mul(x,b),scale(-1,a))
    return b

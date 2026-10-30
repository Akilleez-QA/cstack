"""Finite data-only boundary. Formal representation classes, never actual maps."""
import hashlib
import json
from pathlib import Path

LABELS = ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V')
DIMS = (1, 2, 3, 4, 5, 6, 4, 2, 3)
SIGNS = (1, -1, 1, -1, 1, -1, 1, -1, 1)
PIN = '84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74'
SCOPE = 'formal_exterior_representation_and_supplied_split_bundle_arithmetic_only'
ASSUMPTIONS = {'group': 'SL2(F5) over C', 'physical_catalog': 'fixed_identification_assumed_not_proved',
    'base': 'P(W) with standard O(1) linearization', 'splitting': 'caller_supplied_formal_equivariant_direct_sum',
    'maps': 'no_actual_map_rank_injectivity_or_existence_claim', 'proof': 'not_Lean_or_runtime_acceptance'}
BUDGETS = {'rank': 24, 'order': 25, 'orders': 26, 'blocks': 12, 'absolute_twist': 16,
    'comparison_twists': 8, 'request_bytes': 65536, 'certificate_bytes': 2097152,
    'data_depth': 16, 'data_values': 180000, 'integer_bits': 512, 'string_length': 256,
    'intermediate_degree_terms': 8192, 'result_bits': 256, 'symmetric_degree': 400}

class DomainError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def need(ok, code, message):
    if not ok:
        raise DomainError(code, message)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)

def digest(obj):
    return hashlib.sha256(canonical(obj).encode('ascii')).hexdigest()

def guard(obj, limit):
    stack = [(obj, 0)]
    count = 0
    while stack:
        x, depth = stack.pop()
        count += 1
        need(depth <= 16 and count <= 180000, 'E_BUDGET', 'Data depth/value budget exceeded')
        t = type(x)
        need(t in (dict, list, str, int, type(None)), 'E_TYPE', 'Only exact JSON data types accepted')
        if t in (dict, list):
            need(len(x) + count + len(stack) <= 180000, 'E_BUDGET', 'Data value budget exceeded')
            if t is dict:
                need(all(type(k) is str and len(k) <= 256 for k in x), 'E_TYPE', 'Invalid keys')
            stack.extend((v, depth + 1) for v in (x.values() if t is dict else x))
        elif t is str:
            need(len(x) <= 256, 'E_BUDGET', 'String budget exceeded')
        elif t is int:
            need(abs(x).bit_length() <= 512, 'E_BUDGET', 'Integer budget exceeded')
    raw = canonical(obj).encode('ascii')
    need(len(raw) <= limit, 'E_BUDGET', 'Canonical byte budget exceeded')
    return raw

def load_json(raw, limit):
    need(type(raw) is bytes, 'E_TYPE', 'JSON bytes required')
    need(len(raw) <= limit, 'E_BUDGET', 'JSON byte budget exceeded')
    depth = 0
    quoted = escaped = False
    for b in raw:
        if quoted:
            if escaped: escaped = False
            elif b == 92: escaped = True
            elif b == 34: quoted = False
        elif b == 34: quoted = True
        elif b in (91, 123):
            depth += 1
            need(depth <= 16, 'E_BUDGET', 'JSON nesting budget exceeded')
        elif b in (93, 125): depth -= 1
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'E_JSON', 'Duplicate JSON key')
            out[k] = v
        return out
    def integer(s):
        need(len(s.lstrip('-')) <= 155, 'E_BUDGET', 'JSON integer digit budget exceeded')
        return int(s)
    def reject(s):
        raise DomainError('E_TYPE', 'Floats and nonfinite numbers forbidden')
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_int=integer,
                         parse_float=reject, parse_constant=reject)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as e:
        raise DomainError('E_JSON', 'Malformed JSON') from e
    guard(obj, limit)
    return obj

def read_json(path, limit):
    try:
        with Path(path).open('rb') as stream: raw = stream.read(limit + 1)
    except (OSError, ValueError) as e:
        raise DomainError('E_IO', 'Cannot read input file') from e
    return load_json(raw, limit)

def keys(x, names):
    need(type(x) is dict and set(x) == set(names), 'E_SCHEMA', 'Unexpected fields')

def integer(x, lo, hi):
    need(type(x) is int, 'E_TYPE', 'Exact integer required')
    need(lo <= x <= hi, 'E_BUDGET', 'Integer outside finite domain')

def representation(x):
    need(type(x) is dict and set(x) <= set(LABELS), 'E_SCHEMA', 'Unknown physical module label')
    for n in x.values(): integer(n, 1, 24)
    need(sum(DIMS[i] * x.get(s, 0) for i, s in enumerate(LABELS)) <= 24, 'E_BUDGET', 'Rank exceeds 24')

def bundle(x):
    need(type(x) is list and len(x) <= 12, 'E_BUDGET', 'Bundle requires at most 12 blocks')
    rank = 0
    for b in x:
        keys(b, ('irrep', 'twist', 'multiplicity'))
        need(b['irrep'] in LABELS, 'E_SCHEMA', 'Unknown physical module label')
        integer(b['twist'], -16, 16)
        integer(b['multiplicity'], 1, 24)
        rank += DIMS[LABELS.index(b['irrep'])] * b['multiplicity']
    need(rank <= 24, 'E_BUDGET', 'Rank exceeds 24')

def parse_request(x):
    wire = guard(x, 65536)
    need(type(x) is dict and x.get('schema') == 'fm-exterior-request-v1', 'E_SCHEMA', 'Unknown schema')
    op = x.get('operation')
    need(op in ('representation', 'bundle', 'wedge_h0_comparison'), 'E_SCHEMA', 'Unknown operation')
    keys(x, ('schema', 'operation', 'representation', 'orders') if op == 'representation' else
         ('schema', 'operation', 'bundle', 'orders') if op == 'bundle' else
         ('schema', 'operation', 'source', 'target', 'orders', 'twists'))
    orders = x['orders']
    need(type(orders) is list and 1 <= len(orders) <= 26, 'E_BUDGET', 'Require 1..26 explicit orders')
    for k in orders: integer(k, 0, 25)
    need(len(set(orders)) == len(orders), 'E_SCHEMA', 'Orders must be distinct')
    if op == 'representation': representation(x['representation'])
    elif op == 'bundle': bundle(x['bundle'])
    else:
        bundle(x['source']); bundle(x['target'])
        ts = x['twists']
        need(type(ts) is list and 1 <= len(ts) <= 8, 'E_BUDGET', 'Require 1..8 explicit twists')
        for t in ts: integer(t, -16, 16)
        need(len(set(ts)) == len(ts), 'E_SCHEMA', 'Twists must be distinct')
    return json.loads(wire)

#!/usr/bin/env python3
"""Reproducible read-only polynomial audit; only CLI temp files are written.

Usage: PYTHONDONTWRITEBYTECODE=1 python independent_oracle.py EXTENSION_ROOT
The oracle uses integer pairs and gcd, never Fraction or production internals.
This script reconstructs the 3,000-case inline audit and adds boundary probes.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
from foundation_math.polynomial import calculate_polynomial, calculate_polynomial_json


def require(condition, description):
    if not condition:
        raise AssertionError(description)


def rat(n, d):
    g = math.gcd(n, d)
    n //= g
    d //= g
    if d < 0:
        n, d = -n, -d
    return n, d


def plus(a, b):
    return rat(a[0] * b[1] + b[0] * a[1], a[1] * b[1])


def times(a, b):
    return rat(a[0] * b[0], a[1] * b[1])


def calc(expr):
    kind = expr['type']
    if kind == 'rational':
        c = rat(expr['numerator'], expr['denominator'])
        return {(0, 0, 0): c} if c[0] else {}
    if kind == 'variable':
        return {tuple(int(x == expr['name']) for x in 'xyz'): (1, 1)}
    a, b = map(calc, expr['operands'])
    result = {}
    if kind == 'add':
        for key in set(a) | set(b):
            result[key] = plus(a.get(key, (0, 1)), b.get(key, (0, 1)))
    else:
        for ka, ca in a.items():
            for kb, cb in b.items():
                key = tuple(x + y for x, y in zip(ka, kb))
                result[key] = plus(result.get(key, (0, 1)), times(ca, cb))
    return {key: c for key, c in result.items() if c[0]}


rng = random.Random(722)


def ast(depth):
    if depth == 0 or rng.random() < 0.3:
        if rng.random() < 0.5:
            return {'type': 'variable', 'name': rng.choice('xyz')}
        return {'type': 'rational', 'numerator': rng.randint(-300, 300),
                'denominator': rng.choice([i for i in range(-35, 36) if i])}
    return {'type': rng.choice(['add', 'multiply']),
            'operands': [ast(depth - 1), ast(depth - 1)]}


def decode(polynomial):
    return {tuple(t['exponents']): (t['coefficient']['numerator'], t['coefficient']['denominator'])
            for t in polynomial['terms']}


def encoded_pair(coefficient):
    return coefficient['numerator'], coefficient['denominator']


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


for case in range(1000):
    a, b = ast(4), ast(4)
    for operation in ['add', 'multiply', 'verify_identity']:
        request = {'domain': 'polynomial_ring', 'coefficient_field': 'Q',
                   'variables': list('xyz'), 'operation': operation, 'operands': [a, b]}
        receipt = calculate_polynomial_json(json.dumps(request))
        require(receipt['status'] == 'success', (case, receipt['error']))
        result = receipt['result']
        aa, bb = calc(a), calc(b)
        require(decode(result['left']) == aa and decode(result['right']) == bb, 'operand normalizations')
        if operation == 'verify_identity':
            difference = {key: plus(aa.get(key, (0, 1)), times((-1, 1), bb.get(key, (0, 1))))
                          for key in set(aa) | set(bb)}
            difference = {key: coefficient for key, coefficient in difference.items() if coefficient[0]}
            require(result['equal'] == (not difference), 'identity decision')
            require(decode(result['difference']) == difference, 'left-minus-right difference')
            if difference:
                witness = result['mismatch_witness']
                key = min(difference)
                require(tuple(witness['exponents']) == key, 'lexicographically first mismatch')
                require(encoded_pair(witness['coefficient']) == difference[key], 'witness sign and value')
                require(encoded_pair(witness['left_coefficient']) == aa.get(key, (0, 1)), 'witness left')
                require(encoded_pair(witness['right_coefficient']) == bb.get(key, (0, 1)), 'witness right')
            else:
                require(result['mismatch_witness'] is None, 'equal identity has no witness')
        else:
            require(decode(result['polynomial']) == calc({'type': operation, 'operands': [a, b]}),
                    'operation result')
        for key in ['input', 'request', 'result']:
            require(receipt['artifacts'][key + '_sha256'] == canonical_hash(receipt[key]), key + ' hash')
print('Independent rational-pair oracle: 3000 requests passed; witness and canonical hash checks passed.')

for raw in ['\ufeff{}', '\ud800', '"\\ud800"', '1e9999', '-1e9999', '1e-9999',
            '{"\\u0061":1,"a":2}', '{"a":NaN}', '\x00', b'\xff', b'\xef\xbb\xbf{}',
            '{"a":' + '[' * 500 + ']' * 500 + '}']:
    receipt = calculate_polynomial_json(raw)
    require(receipt['status'] == 'error' and receipt['result'] is None, 'malformed ingress rejected')
print('Adversarial Unicode, duplicate escaped keys, extreme floats, and nesting probes: structured rejection.')


def literal(n, d=1):
    return {'type': 'rational', 'numerator': n, 'denominator': d}


def req(a, b, operation='verify_identity', variables=None):
    return {'domain': 'polynomial_ring', 'coefficient_field': 'Q',
            'variables': [] if variables is None else variables,
            'operation': operation, 'operands': [a, b]}


negative = calculate_polynomial(req(literal(0), literal(3, 2)))
require(negative['status'] == 'success' and negative['result']['equal'] is False, 'false is successful computation')
require(negative['result']['mismatch_witness']['exponents'] == [], 'constant ring has empty monomial tuple')
require(encoded_pair(negative['result']['mismatch_witness']['coefficient']) == (-3, 2), 'negative witness sign')
zero = calculate_polynomial(req(literal(2, 3), literal(-2, 3), 'add'))
require(zero['result']['polynomial'] == {'terms': [], 'total_degree': None}, 'zero constant-ring semantics')
constant = calculate_polynomial(req(literal(2, 3), literal(-3, 2), 'multiply'))
require(constant['result']['polynomial'] == {
    'terms': [{'exponents': [], 'coefficient': {'numerator': -1, 'denominator': 1}}],
    'total_degree': 0}, 'nonzero constant-ring semantics')
print('Explicit negative witness, false-as-success, zero, and nonzero constant-ring probes passed.')

with tempfile.TemporaryDirectory(prefix='polynomial-audit-') as temp:
    source = Path(temp) / 'request.json'
    for request, expected_exit in [(req(literal(1), literal(1)), 0),
                                   (req(literal(0), literal(1)), 1),
                                   (req(literal(1, 0), literal(1)), 2)]:
        source.write_text(json.dumps(request), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'foundation_math', 'polynomial', str(source)],
                                cwd=ROOT, capture_output=True, text=True, check=False, timeout=20)
        require(result.returncode == expected_exit, ('CLI exit', expected_exit, result.returncode, result.stderr))
        receipt = json.loads(result.stdout)
        require(receipt['status'] == ('error' if expected_exit == 2 else 'success'), 'CLI receipt status')
print('CLI exit status probes passed: true=0, false identity=1, invalid/error=2.')

print('Reviewed source SHA-256:')
for name in ['foundation_math/polynomial.py', 'tests/test_polynomial.py', 'foundation_math/calculator.py',
             'foundation_math/cli.py', 'docs/EULER-SEQUENCE-PITFALL.md']:
    print(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name)

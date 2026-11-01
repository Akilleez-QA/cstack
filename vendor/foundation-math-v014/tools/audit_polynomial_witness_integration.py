#!/usr/bin/env python3
"""Independent v0.7 integration audit with tiny original synthetic polynomials.

Deterministic dense coefficient and original-AST oracles below do not import
backend parser/normalizer/substitution helpers. No assert-based checks, network,
installs, credentials, research data, or repository operations are used.
"""
from __future__ import annotations
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math.polynomial_witness import construct_polynomial_witness, check_polynomial_witness
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL

CHECKS = {}
BASE_PINS = (
    'f36d0f145c7704dbfdc61e5504ee5bb8a413e34748791806890c538e18715c26',
    'b61b8563638f18572c343d4d381a5e78980d8fa8172ecda89a4c382e23a66325',
    'c6804f2b38e63bf159e643c1053e941849926427f8c5fcf5d622f754246bb77d',
    '03c09cee65e35964b86f8b4af97b0e29b7fd9b6211a71830458cfe3122fba471',
    '765e34bd7cadd99097034791080ed04d456087dbce2efd1a1c3a2e6b5744742d',
    '7f5cabe7387e1d7288b26ce51c6fc12b9e2c3d7196f626ec974308475a6775db',
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def require(condition, category, detail):
    CHECKS[category] = CHECKS.get(category, 0) + 1
    if not condition:
        raise RuntimeError(category + ': ' + detail)


def q(n, d=1):
    return {'type': 'rational', 'numerator': n, 'denominator': d}


def x():
    return {'type': 'variable', 'name': 'x'}


def binary(kind, a, b):
    return {'type': kind, 'operands': [a, b]}


def expression(rng, depth):
    if depth == 0 or rng.randrange(4) == 0:
        return x() if rng.randrange(2) else q(rng.randint(-3, 3), rng.randint(1, 4))
    return binary(rng.choice(('add', 'multiply')), expression(rng, depth - 1), expression(rng, depth - 1))


def request(left, right, variables=None):
    return {'domain': 'polynomial_ring', 'coefficient_field': 'Q', 'variables': ['x'] if variables is None else variables,
            'operation': 'verify_identity', 'operands': [left, right]}


def coefficients(node):
    if node['type'] == 'rational':
        return [Fraction(node['numerator'], node['denominator'])]
    if node['type'] == 'variable':
        return [Fraction(0), Fraction(1)]
    a, b = [coefficients(n) for n in node['operands']]
    if node['type'] == 'add':
        return [(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(max(len(a), len(b)))]
    result = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, first in enumerate(a):
        for j, second in enumerate(b):
            result[i + j] += first * second
    return result


def evaluate(node, assignment):
    if node['type'] == 'rational':
        return Fraction(node['numerator'], node['denominator'])
    if node['type'] == 'variable':
        return Fraction(assignment[node['name']])
    a, b = [evaluate(n, assignment) for n in node['operands']]
    return a + b if node['type'] == 'add' else a * b


def fraction(pair):
    return Fraction(pair['numerator'], pair['denominator'])


def scope(receipt):
    require(receipt['scope'] == 'characteristic_zero_unrestricted_formal_polynomial' and
            receipt['coefficient_field'] == 'Q' and receipt['characteristic'] == 0 and
            receipt['formal_proof'] is False and receipt['runtime_goal_acceptance'] is False,
            'nonpromotion', 'scope and no acceptance')


def invoke(bridge, name, arguments):
    response = bridge.dispatch({'jsonrpc': '2.0', 'id': 'audit', 'method': 'tools/call',
                                'params': {'name': name, 'arguments': arguments}})
    require('result' in response, 'bridge', 'expected result envelope')
    result = response['result']; content = result['structuredContent']
    require(content['tool'] == name and content['formal_proof'] is False and content['runtime_goal_acceptance'] is False,
            'nonpromotion', 'bridge scope')
    require(result['isError'] == (content['receipt']['status'] == 'error'), 'bridge', 'rejected is not resource error')
    scope(content['receipt'])
    return content



def audit_total_degree_bound():
    """Exhaustive tiny sparse oracle, independent of backend normalization.

    A nonzero residual of degree D selecting a first-success coordinate a
    must lose at least a total degrees. This audit checks every specialization
    and the telescoping count, not just a final reported trace total.
    """
    monomials = [(0, 0), (1, 0), (0, 1), (2, 0), (1, 1), (0, 2)]

    def fold(kind, nodes):
        if not nodes:
            return q(1 if kind == 'multiply' else 0)
        if len(nodes) == 1:
            return nodes[0]
        mid = len(nodes) // 2
        return binary(kind, fold(kind, nodes[:mid]), fold(kind, nodes[mid:]))

    def specialize(poly, index, coordinate):
        out = {}
        for powers, coefficient in poly.items():
            key = tuple(power if j != index else 0 for j, power in enumerate(powers))
            out[key] = out.get(key, 0) + coefficient * coordinate ** powers[index]
        return {powers: coefficient for powers, coefficient in out.items() if coefficient}

    cases = sharp = strict_drops = 0
    for values in product((-1, 0, 1), repeat=len(monomials)):
        poly = {powers: coefficient for powers, coefficient in zip(monomials, values) if coefficient}
        if not poly:
            continue
        terms = []
        for powers, coefficient in poly.items():
            factors = [q(coefficient)] + [
                {'type': 'variable', 'name': name}
                for name, exponent in zip(('u', 'v'), powers) for _ in range(exponent)]
            terms.append(fold('multiply', factors))
        req = request(fold('add', terms), q(0), ['u', 'v'])
        outer = construct_polynomial_witness(req)
        require(outer['status'] == 'success', 'total_degree_bound', 'tiny nonzero construction succeeds')
        scope(outer)
        result = outer['result']; witness = result['result']['witness']
        choices = [witness['assignment'][name] for name in ('u', 'v')]
        degree = max(map(sum, poly))
        trials = result['usage']['substitution_trials']
        bound = outer['construction_bound']
        require(bound['substitution_trial_bound'] == 34 and bound['actual_substitution_trials'] == trials
                and bound['sum_chosen_coordinates'] == sum(choices)
                and bound['exact_difference_degree_recomputed'] is False
                and bound['point_checker_certifies_bound'] is False,
                'total_degree_metadata', 'conservative wrapper cap, not exact-D or point certification')
        require(trials == 2 + sum(choices), 'total_degree_bound', 'actual first-success trial identity')
        require(sum(choices) <= degree and trials <= 2 + degree, 'total_degree_bound', 'sharp telescoping bound')
        current, current_degree = poly, degree
        for index, chosen in enumerate(choices):
            for failed in range(chosen):
                require(not specialize(current, index, failed), 'total_degree_bound', 'every preceding candidate vanishes identically')
            following = specialize(current, index, chosen)
            require(bool(following), 'total_degree_bound', 'chosen residual is nonzero')
            next_degree = max(map(sum, following))
            require(next_degree <= current_degree - chosen, 'total_degree_bound', 'per-step total-degree loss')
            strict_drops += next_degree < current_degree - chosen
            current, current_degree = following, next_degree
        sharp += trials == 2 + degree
        cases += 1
    require(cases == 728 and sharp == 72 and strict_drops == 752,
            'total_degree_bound', 'exhaustive oracle inventory stable')
    return {'nonzero_bivariate_quadratics': cases, 'sharp_cases': sharp,
            'strict_extra_degree_drops': strict_drops,
            'claim': 'For successful construction of nonzero normalized p: trials = n + sum(chosen coordinates) <= n + total_degree(p).',
            'limits': 'Finite synthetic corroboration plus documented algebraic argument; not point-verifier certification or a runtime-cost bound.'}


def main():
    definitions = tool_definitions()
    require(len(definitions) == 15, 'preservation', 'fifteen tools with unchanged eight-tool prefix')
    for definition, digest in zip(definitions, BASE_PINS):
        require(sha256(canonical(definition)).hexdigest() == digest, 'preservation', definition['name'])
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}})
    rng = random.Random(2026102407)
    scenarios = []
    for i in range(96):
        left = expression(rng, 3)
        right = binary('add', q(0), deepcopy(left)) if i % 3 == 0 else expression(rng, 3)
        scenarios.append(request(left, right))
    scenarios.extend([request(q(0), q(0), []), request(q(-5, 7), q(2, 3), []),
                      request(binary('multiply', q(2, -6), x()), q(0)),
                      request(binary('multiply', x(), binary('add', x(), q(-1))), q(0))])
    identity_count = witness_count = 0
    sample_request = sample_witness = None
    for req in scenarios:
        a, b = [coefficients(n) for n in req['operands']]
        difference = [(a[i] if i < len(a) else 0) - (b[i] if i < len(b) else 0) for i in range(max(len(a), len(b)))]
        identity = not any(difference)
        content = invoke(bridge, 'construct_polynomial_witness', {'request': req})
        receipt = content['receipt']; lab = receipt['result']
        require(receipt['status'] == 'success', 'synthetic_oracle', 'construction fits tiny bounds')
        require(receipt['request_sha256'] == sha256(canonical({'operation': 'construct', 'request': req})).hexdigest(),
                'binding', 'whole construction request')
        require((lab['result']['kind'] == 'coefficient_identity') == identity, 'dense_oracle', 'exact coefficient decision')
        if identity:
            identity_count += 1
            require('construction_bound' not in receipt, 'total_degree_metadata', 'identity branch has no nonzero-degree claim')
            require(content['assessment'] == 'polynomial_coefficient_identity' and
                    lab['verification']['status'] == 'not_applicable' and 'witness' not in lab['result'],
                    'evidence_kind', 'normalization identity not fresh point proof')
            continue
        witness_count += 1
        witness = lab['result']['witness']
        bound = receipt['construction_bound']
        require(bound['variable_count'] == len(req['variables']) and bound['normalizer_total_degree_cap'] == 32
                and bound['substitution_trial_bound'] == len(req['variables']) + 32
                and bound['actual_substitution_trials'] == len(req['variables']) + sum(witness['assignment'].values())
                and bound['actual_substitution_trials'] == lab['usage']['substitution_trials']
                and bound['actual_substitution_trials'] <= bound['substitution_trial_bound']
                and bound['legacy_hard_trial_cap'] == 264
                and bound['exact_difference_degree_recomputed'] is False
                and bound['point_checker_certifies_bound'] is False,
                'total_degree_metadata', 'wrapper cap corollary labels and actual count')
        lval, rval = [evaluate(n, witness['assignment']) for n in req['operands']]
        require(lval != rval and (fraction(witness['left_value']), fraction(witness['right_value']),
                                 fraction(witness['difference_value'])) == (lval, rval, lval - rval),
                'point_oracle', 'original AST exact values')
        require(set(witness['assignment']) == set(req['variables']) and
                all(type(v) is int and 0 <= v <= 32 for v in witness['assignment'].values()),
                'point_oracle', 'declared small integer point')
        require(content['assessment'] == 'polynomial_counterexample_constructed' and
                lab['verification']['status'] == 'accepted', 'evidence_kind', 'freshly checked mismatch')
        checked = invoke(bridge, 'check_polynomial_witness', {'request': req, 'witness': witness})
        require('construction_bound' not in checked['receipt'], 'total_degree_metadata', 'fresh checking does not certify greedy bound')
        require(checked['assessment'] == 'polynomial_witness_valid' and checked['receipt']['result']['status'] == 'accepted',
                'point_oracle', 'fresh bridge replay')
        require(checked['receipt']['request_sha256'] == sha256(canonical({'operation': 'verify', 'request': req, 'witness': witness})).hexdigest(),
                'binding', 'whole verification request')
        for key in ('input_sha256', 'request_sha256'):
            forged = deepcopy(witness); forged[key] = '0' * 64
            bad = invoke(bridge, 'check_polynomial_witness', {'request': req, 'witness': forged})
            require(bad['assessment'] == 'polynomial_witness_rejected' and 'result' not in bad['receipt'],
                    'forgery', 'hash is binding, not authority')
        forged = deepcopy(witness); forged['difference_value']['numerator'] += 1
        bad = check_polynomial_witness(req, forged)
        scope(bad)
        require(bad['status'] == 'rejected' and 'result' not in bad, 'forgery', 'wrong concrete value')
        if sample_request is None:
            sample_request, sample_witness = req, witness

    # Replaying all inherited tools is covered by their frozen tests. This audit
    # pins their entire contracts and exercises only the newly appended routes.
    total_degree_bound = audit_total_degree_bound()
    schemas = {'status': 'unavailable', 'reason': 'jsonschema absent; no install attempted'}
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError:
        pass
    else:
        for definition in definitions:
            for kind in ('inputSchema', 'outputSchema'):
                Draft202012Validator.check_schema(definition[kind])
                require(True, 'schema', 'advertised schema validates')
        for definition in definitions[6:8]:
            name = definition['name']; args = {'request': sample_request}
            if name == 'check_polynomial_witness':
                args['witness'] = sample_witness
            input_validator = Draft202012Validator(definition['inputSchema'])
            output_validator = Draft202012Validator(definition['outputSchema'])
            require(input_validator.is_valid(args), 'schema', 'valid input accepted')
            actual = invoke(bridge, name, args)
            require(output_validator.is_valid(actual), 'schema', 'actual success conforms')
            for key, value in [('formal_proof', True), ('runtime_goal_acceptance', True), ('assessment', 'tool_error')]:
                forged = deepcopy(actual); forged[key] = value
                require(not output_validator.is_valid(forged), 'schema', 'promoted/misclassified envelope rejected')
            for key, value in [('formal_proof', True), ('runtime_goal_acceptance', True),
                               ('coefficient_field', 'F2'), ('characteristic', 2), ('scope', 'all_identities')]:
                forged = deepcopy(actual); forged['receipt'][key] = value
                require(not output_validator.is_valid(forged), 'schema', 'promoted source receipt rejected')
            malformed = deepcopy(args); malformed['request']['coefficient_field'] = 'F2'
            require(not input_validator.is_valid(malformed), 'schema', 'unsupported field rejected')
            failed = invoke(bridge, name, malformed)
            require(output_validator.is_valid(failed), 'schema', 'actual error conforms')
            forged = deepcopy(failed); forged['receipt']['result'] = {'accepted': True}
            require(not output_validator.is_valid(forged), 'schema', 'error cannot carry partial result')
            if name == 'check_polynomial_witness':
                forged = deepcopy(sample_witness); forged['assignment'] = {}
                rejected = invoke(bridge, name, {'request': sample_request, 'witness': forged})
                require(output_validator.is_valid(rejected), 'schema', 'actual rejection conforms')
            else:
                for key, value in [('substitution_trial_bound', 41), ('normalizer_total_degree_cap', 33),
                                   ('point_checker_certifies_bound', True), ('exact_difference_degree_recomputed', True)]:
                    forged = deepcopy(actual); forged['receipt']['construction_bound'][key] = value
                    require(not output_validator.is_valid(forged), 'schema', 'incorrect bound/certification metadata rejected')
                identity = invoke(bridge, name, {'request': request(q(0), q(0), [])})
                require(output_validator.is_valid(identity), 'schema', 'actual identity conforms')
        schemas = {'status': 'passed', 'validator': 'jsonschema', 'version': version('jsonschema'),
                   'note': 'Already installed development validator; no runtime dependency or install added.'}

    messages = [
        {'jsonrpc': '2.0', 'id': 'init', 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}},
        {'jsonrpc': '2.0', 'id': 'list', 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'construct_polynomial_witness', 'arguments': {}}},
        {'jsonrpc': '2.0', 'id': 'construct', 'method': 'tools/call', 'params': {'name': 'construct_polynomial_witness', 'arguments': {'request': sample_request}}},
        {'jsonrpc': '2.0', 'id': 'reject', 'method': 'tools/call', 'params': {'name': 'check_polynomial_witness', 'arguments': {'request': sample_request, 'witness': {}}}},
        {'jsonrpc': '2.0', 'id': 'verify', 'method': 'tools/call', 'params': {'name': 'check_polynomial_witness', 'arguments': {'request': sample_request, 'witness': sample_witness}}},
        {'jsonrpc': '2.0', 'id': 'ping', 'method': 'ping'}]
    wire = b'\n'.join(map(canonical, messages)) + b'\n'
    transcripts = []
    for optimized in (False, True):
        command = [sys.executable, '-B'] + (['-O'] if optimized else []) + ['-m', 'foundation_math_bridge']
        process = subprocess.run(command, input=wire, cwd=ROOT, capture_output=True, timeout=10)
        require(process.returncode == 0 and process.stderr == b'', 'transcript', 'clean process exit')
        transcripts.append(process.stdout)
    require(transcripts[0] == transcripts[1], 'transcript', 'normal and optimized bytes equal')
    responses = [json.loads(line) for line in transcripts[0].splitlines()]
    require([r['id'] for r in responses] == ['init', 'list', 'construct', 'reject', 'verify', 'ping'],
            'transcript', 'notification is silent and session recovers')
    names = ('foundation_math/polynomial_witness.py', 'foundation_math/cli.py', 'foundation_math_bridge/server.py',
             'foundation_math_bridge/schemas.py', 'foundation_math_bridge/polynomial_witness_schemas.py',
             'polynomial_witness/api.py', 'polynomial_witness/checker.py', 'polynomial_witness/producer.py',
             'polynomial_witness/contract.py', 'polynomial_witness/_vendor/polynomial.py',
             'polynomial_witness/_vendor/calculator.py', 'docs/POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md',
             'tests/test_v07_independent_review.py',
             'tools/audit_polynomial_witness_integration.py')
    report = {'status': 'passed', 'checks': CHECKS, 'total_checks': sum(CHECKS.values()),
              'synthetic_requests': len(scenarios), 'coefficient_identities': identity_count,
              'concrete_mismatches': witness_count, 'optimization': sys.flags.optimize,
              'python_version': sys.version.split()[0], 'schema_validation': schemas,
              'total_degree_bound_audit': total_degree_bound,
              'transcript': {'requests_including_notification': len(messages), 'responses': len(responses),
                             'normal_optimized_equal': True, 'sha256': sha256(transcripts[0]).hexdigest()},
              'scope': 'Bounded integration and synthetic exact oracles only. Not a proof kernel, authentication, exhaustive correctness proof, or runtime goal acceptance.',
              'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names}}
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

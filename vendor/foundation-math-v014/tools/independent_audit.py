#!/usr/bin/env python3
"""Independent finite-box oracle and adversarial controls, using only stdlib.

The mathematical oracle uses integer pairs and gcd, not Fraction, production
parsers, production evaluators, or production canonicalization/hash helpers.
Run: PYTHONDONTWRITEBYTECODE=1 python tools/independent_audit.py --output evidence/independent-audit.json
Repeat with python -O. A successful run establishes these bounded software
checks, not a proof kernel, an unrestricted theorem, or security certification.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bounded_counterexample import (check_witness, check_witness_json,
                                    search_counterexample, search_counterexample_json)

SEED = 20261024
RELATIONS = ("lt", "le", "eq", "ne", "ge", "gt")
SOURCES = ("bounded_counterexample/core.py", "bounded_counterexample/__init__.py",
           "bounded_counterexample/__main__.py", "bounded_counterexample/_vendor/polynomial.py",
           "bounded_counterexample/_vendor/calculator.py", "tools/independent_audit.py")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def rat(n, d=1):
    divisor = math.gcd(n, d)
    n, d = n // divisor, d // divisor
    return (-n, -d) if d < 0 else (n, d)


def plus(a, b):
    return rat(a[0] * b[1] + b[0] * a[1], a[1] * b[1])


def times(a, b):
    return rat(a[0] * b[0], a[1] * b[1])


def evaluate(expr, assignment):
    if expr["type"] == "rational":
        return rat(expr["numerator"], expr["denominator"])
    if expr["type"] == "variable":
        return assignment[expr["name"]], 1
    left, right = [evaluate(item, assignment) for item in expr["operands"]]
    return plus(left, right) if expr["type"] == "add" else times(left, right)


def compare(relation, left, right):
    delta = left[0] * right[1] - right[0] * left[1]
    return {"lt": delta < 0, "le": delta <= 0, "eq": delta == 0,
            "ne": delta != 0, "ge": delta >= 0, "gt": delta > 0}[relation]


def encode(pair):
    return {"numerator": pair[0], "denominator": pair[1]}


def predicate(pred, assignment):
    left, right = evaluate(pred["left"], assignment), evaluate(pred["right"], assignment)
    return {"relation": pred["relation"], "left": encode(left), "right": encode(right),
            "holds": compare(pred["relation"], left, right)}


def adjudicate(request, assignment):
    constraints = [predicate(item, assignment) for item in request["constraints"]]
    holds = all(item["holds"] for item in constraints)
    assertion = predicate(request["assertion"], assignment) if holds else None
    return {"constraints": constraints, "all_constraints_hold": holds, "assertion": assertion,
            "assertion_violated": assertion is not None and not assertion["holds"]}


def nodes(expr):
    return 1 + sum(nodes(item) for item in expr.get("operands", []))


def predicate_work(pred):
    return 1 + nodes(pred["left"]) + nodes(pred["right"])


def assignment_work(request, evaluation):
    return sum(map(predicate_work, request["constraints"])) + (
        predicate_work(request["assertion"]) if evaluation["all_constraints_hold"] else 0)


def points(request):
    names = request["variables"]
    ranges = [range(request["bounds"][name]["lower"], request["bounds"][name]["upper"] + 1)
              for name in names]
    return [dict(zip(names, values)) for values in itertools.product(*ranges)]


def oracle(request):
    visited = eligible = work = 0
    all_points = points(request)
    for assignment in all_points:
        evaluation = adjudicate(request, assignment)
        visited += 1
        eligible += int(evaluation["all_constraints_hold"])
        work += assignment_work(request, evaluation)
        if evaluation["assertion_violated"]:
            return {"outcome": "counterexample_found", "assignment": assignment,
                    "evaluation": evaluation}, visited, eligible, len(all_points), work
    return {"outcome": "no_counterexample_in_declared_finite_domain", "assignment": None,
            "evaluation": None}, visited, eligible, len(all_points), work


def normalized(value):
    if type(value) is dict:
        if value.get("type") == "rational":
            n, d = rat(value["numerator"], value["denominator"])
            return {"type": "rational", "numerator": n, "denominator": d}
        return {key: normalized(item) for key, item in value.items()}
    if type(value) is list:
        return [normalized(item) for item in value]
    return value


def verify_hashes(receipt, sources):
    for key in ("input", "request", "result"):
        expected = None if receipt[key] is None else digest(receipt[key])
        require(receipt["artifacts"][key + "_sha256"] == expected, key + " hash mismatch")
    assignment = receipt["supplied_assignment"]
    require(receipt["artifacts"]["assignment_sha256"] == (None if assignment is None else digest(assignment)),
            "assignment hash mismatch")
    for key, path in (("backend_source_sha256", SOURCES[0]),
                      ("parser_source_sha256", SOURCES[3]),
                      ("canonical_json_source_sha256", SOURCES[4])):
        require(receipt["artifacts"][key] == sources[path], key + " mismatch")
    evidence = copy.deepcopy(receipt)
    expected = evidence["artifacts"].pop("evidence_sha256")
    require(digest(evidence) == expected, "evidence hash mismatch")
    require(receipt["scope"]["formal_proof"] is False and receipt["scope"]["universal_proof"] is False,
            "unsupported proof promotion")


def verify_search(request, receipt, sources):
    require(receipt["status"] == "success", "unexpected error: " + str(receipt["error"]))
    result, visited, eligible, cardinality, work = oracle(request)
    require(receipt["kind"] == "bounded_counterexample_search", "search kind")
    require(receipt["result"] == result, "mathematical result mismatch")
    require(receipt["input"] == request, "original input snapshot")
    require(receipt["request"] == normalized(request), "normalized request snapshot")
    require(receipt["progress"] == {"domain_cardinality": cardinality, "visited_count": visited,
            "eligible_count": eligible, "complete": visited == cardinality, "checked_assignment_count": 0},
            "search progress mismatch")
    require(receipt["usage"]["evaluation_steps"] == work, "evaluation work mismatch")
    expected_nodes = sum(nodes(pred[key]) for pred in request["constraints"] + [request["assertion"]]
                         for key in ("left", "right"))
    require(receipt["usage"]["ast_nodes"] == expected_nodes, "node accounting mismatch")
    verify_hashes(receipt, sources)


def verify_check(request, assignment, receipt, sources):
    require(receipt["status"] == "success", "checker unexpected error: " + str(receipt["error"]))
    evaluation = adjudicate(request, assignment)
    valid = evaluation["all_constraints_hold"] and evaluation["assertion_violated"]
    reason = "counterexample_verified" if valid else (
        "assertion_not_violated" if evaluation["all_constraints_hold"] else "constraint_not_satisfied")
    require(receipt["result"] == {"valid": valid, "reason": reason, "evaluation": evaluation},
            "checker mathematical result mismatch")
    require(receipt["supplied_assignment"] == assignment, "checker assignment snapshot")
    require(receipt["progress"] == {"domain_cardinality": len(points(request)), "visited_count": 0,
            "eligible_count": 0, "complete": False, "checked_assignment_count": 1}, "checker progress mismatch")
    require(receipt["usage"]["evaluation_steps"] == assignment_work(request, evaluation), "checker work mismatch")
    verify_hashes(receipt, sources)


def literal(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def variable(name):
    return {"type": "variable", "name": name}


def binary(kind, left, right):
    return {"type": kind, "operands": [left, right]}


def pred(relation="eq", left=None, right=None):
    return {"relation": relation, "left": literal(0) if left is None else left,
            "right": literal(0) if right is None else right}


def request(variables=None, bounds=None, constraints=None, assertion=None):
    variables = ["x"] if variables is None else variables
    return {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": variables,
            "bounds": {name: {"lower": -2, "upper": 2} for name in variables} if bounds is None else bounds,
            "constraints": [] if constraints is None else constraints,
            "assertion": pred() if assertion is None else assertion}


def set_path(value, path, replacement):
    result = copy.deepcopy(value)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    return result


def random_expr(rng, variables, depth):
    if depth == 0 or rng.random() < 0.4:
        if variables and rng.random() < 0.55:
            return variable(rng.choice(variables))
        return literal(rng.randint(-7, 7), rng.choice([-7, -3, -2, -1, 1, 2, 3, 7]))
    return binary(rng.choice(("add", "multiply")), random_expr(rng, variables, depth - 1),
                  random_expr(rng, variables, depth - 1))


def generate_corpus():
    result = []
    for relation in RELATIONS:
        result.append(request(assertion=pred(relation, variable("x"), literal(0))))
        result.append(request(constraints=[pred(relation, variable("x"), literal(0))],
                              assertion=pred("gt", literal(-1, -2), variable("x"))))
        result.append(request(variables=[], assertion=pred(relation, literal(1, -2), literal(-2, 4))))
    result += [request(variables=[], assertion=pred("eq", literal(0), literal(1))),
               request(variables=[], constraints=[pred("ne")], assertion=pred("eq", literal(0), literal(1))),
               request(bounds={"x": {"lower": 2, "upper": 2}}, assertion=pred("ne", variable("x"), literal(2))),
               request(assertion=pred("lt", variable("x"), literal(2))),
               request(variables=["z", "a"], assertion=pred("le", variable("z"), variable("a")))]
    rng = random.Random(SEED)
    for index in range(360):
        variables = list("zay"[:index % 4])
        bounds = {name: {"lower": rng.randint(-2, 0), "upper": rng.randint(0, 2)} for name in variables}
        def random_predicate():
            return pred(rng.choice(RELATIONS), random_expr(rng, variables, 3), random_expr(rng, variables, 3))
        result.append(request(variables, bounds, [random_predicate() for _ in range(index % 4)], random_predicate()))
    return result


class Audit:
    def __init__(self):
        self.failures = []
        self.passed = []

    def run(self, name, action):
        try:
            action()
        except Exception as error:
            self.failures.append({"name": name, "error": type(error).__name__ + ": " + str(error)})
        else:
            self.passed.append(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    sources = source_hashes()
    audit = Audit()
    corpus = generate_corpus()
    counters = {"oracle_requests": 0, "witness_checks": 0, "malformed_requests": 0,
                "malformed_json": 0, "assignment_controls": 0, "resource_controls": 0,
                "tamper_controls": 0}
    for index, item in enumerate(corpus):
        def check_case(item=item, index=index):
            receipt = search_counterexample(item) if index % 2 else search_counterexample_json(json.dumps(item))
            verify_search(item, receipt, sources)
            counters["oracle_requests"] += 1
            candidates = points(item)
            selected = candidates if index < 40 else candidates[:1] + candidates[-1:]
            if receipt["result"]["assignment"] is not None:
                selected.append(receipt["result"]["assignment"])
            for assignment in selected:
                checked = check_witness(item, assignment) if index % 2 else check_witness_json(json.dumps(item), json.dumps(assignment))
                verify_check(item, assignment, checked, sources)
                counters["witness_checks"] += 1
        audit.run("oracle_case_" + str(index), check_case)

    def rejected_request(value, code=None):
        for receipt in (search_counterexample(value), check_witness(value, {})):
            require(receipt["status"] == "error" and receipt["result"] is None, "malformed request admitted")
            require(receipt["progress"]["complete"] is False, "error mistaken for exhaustion")
            if code is not None:
                require(receipt["error"]["code"] == code, "unexpected error category: " + str(receipt["error"]))
            verify_hashes(receipt, sources)
        counters["malformed_requests"] += 1

    base = request(assertion=pred("eq", variable("x"), literal(0)))
    malformed = [None, True, [], "x == 0", {**base, "extra": 1},
                 {key: value for key, value in base.items() if key != "bounds"}]
    for path, values in [(('domain',), ['Q', 'R', 'polynomial_ring', None, True]),
                         (('coefficient_field',), ['R', 'Z', None, 1]),
                         (('variables',), [['x', 'x'], ['X'], ['x', 'X'], ['é'], ['_x'], ['x '], ['x' * 33], ['x', 1], (), ['a'] * 9]),
                         (('bounds',), [{}, {'x': {'lower': 0, 'upper': 1}, 'y': {'lower': 0, 'upper': 1}}, []]),
                         (('bounds', 'x', 'lower'), [True, 0.0, '0', {'numerator': 0, 'denominator': 1}, 1 << 256, 3]),
                         (('constraints',), [None, (), [pred()] * 17]),
                         (('assertion', 'relation'), ['EQ', '==', 'contains', [], None]),
                         (('assertion', 'left'), [0, 'x', {'type': 'variable', 'name': 'X'}, {'type': 'power', 'base': variable('x'), 'exponent': 2}, {'type': 'add', 'operands': [literal(0)]}, {'type': 'rational', 'numerator': True, 'denominator': 1}, literal(1, 0)])]:
        malformed += [set_path(base, path, value) for value in values]
    for index, item in enumerate(malformed):
        audit.run("malformed_object_" + str(index), lambda item=item: rejected_request(item))
    cyclic = {'type': 'add', 'operands': []}
    cyclic['operands'] = [literal(0), cyclic]
    audit.run("cyclic_ast", lambda: rejected_request(set_path(base, ('assertion', 'left'), cyclic), "resource_limit"))
    class DictSubclass(dict):
        pass
    class IntSubclass(int):
        pass
    audit.run("dictionary_subclass", lambda: rejected_request(DictSubclass(base)))
    audit.run("integer_subclass", lambda: rejected_request(set_path(base, ('bounds', 'x', 'lower'), IntSubclass(-2))))

    invalid_json = ['\ufeff{}', '\ud800', '"\\ud800"', '{"a":NaN}', '{"a":Infinity}',
                    '{"a":-Infinity}', '{"\\u0061":1,"a":2}', '\x00', b'\xff', b'\xef\xbb\xbf{}',
                    '{"x":' + '[' * 1100 + ']' * 1100 + '}', '{} trailing', '', '1e9999', '-1e9999',
                    '1e-9999', '{"x":' + '9' * 1000 + '}', ' ' * 65537, 0, bytearray(b'{}')]
    valid_wire = json.dumps(base)
    invalid_json += [valid_wire.replace('"domain":', '"domain":"Q","domain":', 1),
                     valid_wire.replace('"lower": -2', '"lower": -2.0')]
    # A syntactically valid JSON value can still be an invalid assignment. The
    # checker intentionally returns success/valid:false for that distinction.
    valid_but_wrong_shape = {2, 10, 13, 14, 15, 21}
    def reject_json(value, assignment_may_parse=False):
        for receipt in (search_counterexample_json(value), check_witness_json(value, '{}')):
            require(receipt["status"] == "error" and receipt["result"] is None, "malformed transport admitted")
            verify_hashes(receipt, sources)
        receipt = check_witness_json(valid_wire, value)
        if assignment_may_parse and receipt['status'] == 'success':
            require(receipt['result']['valid'] is False and receipt['result']['evaluation'] is None,
                    'invalid-shaped JSON assignment admitted')
        else:
            require(receipt['status'] == 'error' and receipt['result'] is None, 'invalid JSON transport admitted')
        verify_hashes(receipt, sources)
        counters["malformed_json"] += 1
    for index, item in enumerate(invalid_json):
        audit.run("malformed_json_" + str(index), lambda item=item, index=index: reject_json(item, index in valid_but_wrong_shape))

    witness_request = request(assertion=pred("eq", variable("x"), literal(0)))
    bad_assignments = [{}, {'x': 1, 'y': 0}, {1: 1}, None, [], {'x': True}, {'x': 1.0}, {'x': '1'},
                       {'x': {'numerator': 1, 'denominator': 2}}, {'x': {'numerator': 1, 'denominator': 1}},
                       {'x': 1 << 256}, {'x': IntSubclass(1)}, DictSubclass(x=1), {'x': -3}, {'x': 3}]
    def reject_assignment(value):
        receipt = check_witness(witness_request, value)
        require(receipt['status'] == 'success' and receipt['result']['valid'] is False, 'invalid assignment accepted')
        require(receipt['result']['evaluation'] is None, 'invalid assignment evaluated')
        verify_hashes(receipt, sources)
        counters['assignment_controls'] += 1
    for index, assignment in enumerate(bad_assignments):
        audit.run('assignment_rejection_' + str(index), lambda assignment=assignment: reject_assignment(assignment))
    def recheck_controls():
        constrained = request(constraints=[pred('gt', variable('x'), literal(0))], assertion=pred('eq', variable('x'), literal(0)))
        require(check_witness(constrained, {'x': -1})['result']['reason'] == 'constraint_not_satisfied', 'ineligible false assertion is witness')
        require(check_witness(witness_request, {'x': 0})['result']['reason'] == 'assertion_not_violated', 'true assertion is witness')
        first = search_counterexample(witness_request)
        changed = set_path(witness_request, ('assertion', 'relation'), 'ne')
        checked = check_witness(changed, first['result']['assignment'])
        require(checked['result']['valid'] is False, 'checker trusted stale producer result')
        require(checked['artifacts']['request_sha256'] != first['artifacts']['request_sha256'], 'changed request not rebound')
        require(check_witness(witness_request, first)['result']['valid'] is False, 'receipt accepted as assignment')
        counters['assignment_controls'] += 4
    audit.run('independent_request_recheck_controls', recheck_controls)

    def success_boundary(item):
        verify_search(item, search_counterexample(item), sources)
        counters['resource_controls'] += 1
    audit.run('cardinality_10000_accepted', lambda: success_boundary(request(bounds={'x': {'lower': 0, 'upper': 9999}})))
    audit.run('cartesian_cardinality_10000_accepted', lambda: success_boundary(request(['x', 'y'], {'x': {'lower': 0, 'upper': 99}, 'y': {'lower': 0, 'upper': 99}})))
    audit.run('cardinality_10001_rejected', lambda: rejected_request(request(bounds={'x': {'lower': 0, 'upper': 10000}}), 'resource_limit'))
    audit.run('cartesian_cardinality_10100_rejected', lambda: rejected_request(request(['x', 'y'], {'x': {'lower': 0, 'upper': 99}, 'y': {'lower': 0, 'upper': 100}}), 'resource_limit'))
    audit.run('maximum_integer_singleton', lambda: success_boundary(request(bounds={'x': {'lower': (1 << 256) - 1, 'upper': (1 << 256) - 1}})))
    audit.run('minimum_integer_singleton', lambda: success_boundary(request(bounds={'x': {'lower': -((1 << 256) - 1), 'upper': -((1 << 256) - 1)}})))
    deep = variable('x')
    for _ in range(32):
        deep = binary('add', deep, literal(0))
    audit.run('expression_depth_33_rejected', lambda: rejected_request(set_path(base, ('assertion', 'left'), deep), 'resource_limit'))
    degree = variable('x')
    for _ in range(6):
        degree = binary('multiply', degree, degree)
    audit.run('syntactic_degree_64_rejected', lambda: rejected_request(set_path(base, ('assertion', 'left'), degree), 'resource_limit'))
    oversized = literal(1)
    for _ in range(9):
        oversized = binary('add', oversized, oversized)
    audit.run('aggregate_ast_nodes_rejected', lambda: rejected_request(request(constraints=[pred('eq', oversized, literal(1))], assertion=pred('eq', oversized, literal(1))), 'resource_limit'))
    def exhausted(item, checker=False):
        receipt = check_witness(item, {name: item['bounds'][name]['lower'] for name in item['variables']}) if checker else search_counterexample(item)
        require(receipt['status'] == 'error' and receipt['error']['code'] == 'resource_limit', 'resource failure not error')
        require(receipt['result'] is None and receipt['progress']['complete'] is False, 'resource failure promoted to exhaustion')
        require(receipt['usage']['evaluation_steps'] <= 250000, 'work cap exceeded')
        verify_hashes(receipt, sources)
        counters['resource_controls'] += 1
    expensive = request(bounds={'x': {'lower': 0, 'upper': 9999}}, constraints=[pred()] * 16)
    audit.run('evaluation_budget_partial_failure', lambda: exhausted(expensive))
    square = variable('x')
    for _ in range(5):
        square = binary('multiply', square, square)
    too_big = request(bounds={'x': {'lower': 1 << 255, 'upper': 1 << 255}}, assertion=pred('eq', square, square))
    audit.run('intermediate_bits_search_failure', lambda: exhausted(too_big))
    audit.run('intermediate_bits_check_failure', lambda: exhausted(too_big, True))

    def tamper_controls():
        original = search_counterexample(witness_request)
        changes = [(('result', 'outcome'), 'no_counterexample_in_declared_finite_domain'),
                   (('result', 'assignment', 'x'), 0), (('result', 'evaluation', 'assertion_violated'), False),
                   (('progress', 'complete'), True), (('progress', 'visited_count'), 5),
                   (('scope', 'universal_proof'), True), (('artifacts', 'backend_source_sha256'), '0' * 64)]
        for path, value in changes:
            forged = set_path(original, path, value)
            forged['artifacts']['result_sha256'] = digest(forged['result'])
            evidence = copy.deepcopy(forged)
            evidence['artifacts'].pop('evidence_sha256')
            forged['artifacts']['evidence_sha256'] = digest(evidence)
            try:
                verify_search(witness_request, forged, sources)
            except AssertionError:
                counters['tamper_controls'] += 1
            else:
                raise AssertionError('independent oracle accepted self-consistently rehashed tampering at ' + str(path))
    audit.run('rehashed_tamper_negative_controls', tamper_controls)
    after = source_hashes()
    audit.run('source_snapshot_stable', lambda: require(after == sources, 'source changed during the audit; rerun against stable source'))
    report = {'schema_version': '1.0', 'kind': 'independent_finite_integer_box_audit',
              'status': 'pass' if not audit.failures else 'fail', 'python_version': platform.python_version(),
              'optimized': not __debug__, 'seed': SEED, 'oracle_arithmetic': 'reduced integer pairs with gcd and cross-products',
              'production_imports': 'public API only; no production parser/evaluator/hash internals',
              'source_sha256': sources, 'corpus_sha256': digest(corpus), 'counters': counters,
              'passed_checks': len(audit.passed), 'failed_checks': len(audit.failures),
              'failures': audit.failures, 'check_names': audit.passed,
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'limitations': ['Finite deterministic and pseudorandom software tests are not exhaustive input-space validation.',
                              'No independently verified proof kernel, unrestricted theorem, external service, or HM instance experiment.',
                              'Hashes detect content changes, not authenticity; invalid nonrepresentable assignments are not necessarily retained.']}
    if args.output:
        output = args.output.resolve()
        require(output.parent == ROOT / 'evidence' and output.name.startswith('independent-audit') and output.suffix == '.json',
                'audit output must be evidence/independent-audit*.json')
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'optimized', 'counters', 'passed_checks', 'failed_checks', 'failures', 'elapsed_seconds')}, indent=2))
    return 0 if not audit.failures else 1


if __name__ == '__main__':
    raise SystemExit(main())

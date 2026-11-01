#!/usr/bin/env python3
"""Independent finite-grid oracle and adversarial API audit (standard library).

Only the test harness uses a Cartesian grid. The oracle evaluates the supplied
AST directly and obtains safe degrees structurally; it never calls a normalizer
or the production substitution algorithm. Explicit checks survive python -O.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from polynomial_witness.contract import Limits, WitnessError, strict_json
from polynomial_witness.producer import produce
from polynomial_witness.checker import verify_witness


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def q(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def v(name):
    return {"type": "variable", "name": name}


def add(a, b):
    return {"type": "add", "operands": [a, b]}


def mul(a, b):
    return {"type": "multiply", "operands": [a, b]}


def combine(kind, expressions):
    items = list(expressions)
    if not items:
        return q(0 if kind == "add" else 1)
    while len(items) > 1:
        items = [({"type": kind, "operands": items[i:i + 2]} if i + 1 < len(items)
                  else items[i]) for i in range(0, len(items), 2)]
    return items[0]


def power(base, exponent):
    return combine("multiply", [deepcopy(base) for _ in range(exponent)])


def falling(name, degree):
    return combine("multiply", [add(v(name), q(-i)) for i in range(degree)])


def request(variables, left, right=None):
    return {"domain": "polynomial_ring", "coefficient_field": "Q",
            "variables": list(variables), "operation": "verify_identity",
            "operands": [left, q(0) if right is None else right]}


def evaluate(expression, point):
    kind = expression["type"]
    if kind == "rational":
        return Fraction(expression["numerator"], expression["denominator"])
    if kind == "variable":
        return Fraction(point[expression["name"]])
    left, right = [evaluate(child, point) for child in expression["operands"]]
    return left + right if kind == "add" else left * right


def degree_bounds(expression, variables):
    kind = expression["type"]
    if kind == "rational":
        return [0] * len(variables)
    if kind == "variable":
        return [int(name == expression["name"]) for name in variables]
    a, b = [degree_bounds(child, variables) for child in expression["operands"]]
    return [max(x, y) if kind == "add" else x + y for x, y in zip(a, b)]


def request_bounds(raw):
    a, b = [degree_bounds(e, raw["variables"]) for e in raw["operands"]]
    return [max(x, y) for x, y in zip(a, b)]


def first_grid_point(raw, prefix=()):
    variables = raw["variables"]
    bounds = request_bounds(raw)
    for tail in product(*(range(d + 1) for d in bounds[len(prefix):])):
        coordinates = tuple(prefix) + tail
        point = dict(zip(variables, coordinates))
        left, right = [evaluate(e, point) for e in raw["operands"]]
        if left != right:
            return coordinates, left, right
    return None


def degree_by_differences(raw, index, prefix=()):
    """Recover an actual residual degree using only scalar finite differences.

    All other unfixed variables are sampled on a degree-sufficient grid, so a
    nonzero leading coefficient cannot vanish on every sampled tail.
    """
    variables = raw["variables"]
    bounds = request_bounds(raw)
    other = [j for j in range(len(prefix), len(variables)) if j != index]
    actual = -1
    for values in product(*(range(bounds[j] + 1) for j in other)):
        point = dict(zip(variables, prefix))
        point.update({variables[j]: value for j, value in zip(other, values)})
        differences = []
        for value in range(bounds[index] + 1):
            point[variables[index]] = value
            left, right = [evaluate(e, point) for e in raw["operands"]]
            differences.append(left - right)
        order = 0
        while differences:
            if any(differences):
                actual = max(actual, order)
            differences = [b - a for a, b in zip(differences, differences[1:])]
            order += 1
    return actual


def pair(number):
    return {"numerator": number.numerator, "denominator": number.denominator}


def count_nodes(expr):
    return 1 + sum(count_nodes(c) for c in expr.get("operands", []))


def named_cases():
    x, y = v("x"), v("y")
    return [
        ("constant_zero_empty_ring", request([], q(0))),
        ("constant_equal_empty_ring", request([], q(2, 3), q(-4, -6))),
        ("constant_unequal_empty_ring", request([], q(7, 3), q(-1, 2))),
        ("unused_declared_variables", request(["z", "x", "y"], q(5))),
        ("zero_first_candidate", request(["x"], x)),
        ("nonzero_at_zero", request(["x"], add(x, q(-1)))),
        ("univariate_all_lower_candidates_roots", request(["x"], falling("x", 7))),
        ("maximum_coordinate_degree_32", request(["x"], falling("x", 32))),
        ("maximum_eight_variables", request(["a", "b", "c", "d", "e", "f", "g", "h"], combine("multiply", [v(n) for n in "abcdefgh"]))),
        ("bivariate_root_products", request(["x", "y"], mul(falling("x", 3), falling("y", 2)))),
        ("remaining_zero_is_not_residual_zero", request(["x", "y"], mul(x, y))),
        ("degree_drop_after_substitution", request(["x", "y"], add(mul(x, power(y, 4)), y))),
        ("coalescing_cancellation", request(["x", "y"], add(add(mul(x, y), mul(q(-1), mul(x, y))), power(y, 3)))),
        ("declared_order_is_not_sorted", request(["y", "x", "unused"], add(mul(y, add(y, q(-1))), x))),
        ("original_unreduced_negative_denominator", request(["x"], add(mul(q(-6, -9), x), q(2, -4)), q(-5, -10))),
        ("distributive_identity", request(["x", "y"], mul(x, add(y, q(3))), add(mul(x, y), mul(q(3), x)))),
        ("coefficient_cancellation_identity", request(["x", "y"], add(mul(q(1, 3), mul(x, y)), mul(q(2, 6), mul(y, x))), mul(q(2, 3), mul(x, y)))),
        ("zero_factor_identity", request(["x", "y"], mul(add(x, mul(q(-1), x)), y))),
        ("rational_nonzero", request(["x", "y"], mul(q(-7, 11), mul(falling("x", 2), falling("y", 2))))),
    ]


def generated_cases(seed, count):
    rng = random.Random(seed)
    for index in range(count):
        variables = ["b", "a", "c"][:rng.randrange(4)]
        def sparse():
            terms = []
            for _ in range(rng.randrange(1, 6)):
                term = q(rng.randrange(-5, 6), rng.choice([-7, -3, 1, 2, 5]))
                for name in variables:
                    term = mul(term, power(v(name), rng.randrange(3)))
                terms.append(term)
            return combine("add", terms)
        left = sparse()
        if index % 4 == 0:
            a, b = sparse(), sparse()
            left, right = mul(left, add(a, b)), add(mul(deepcopy(left), a), mul(deepcopy(left), b))
        elif index % 4 == 1:
            right = add(deepcopy(left), mul(q(0), sparse()))
        else:
            right = sparse()
        yield f"generated_{index:03d}", request(variables, left, right)


def exhaustive_small_cases():
    monomials = [q(1), v("x"), v("y"), mul(v("x"), v("y"))]
    for index, coefficients in enumerate(product([-1, 0, 1], repeat=4)):
        expression = combine("add", [mul(q(c), deepcopy(m)) for c, m in zip(coefficients, monomials)])
        yield f"exhaustive_bilinear_{index:02d}", request(["x", "y"], expression)


def audit_case(name, raw):
    oracle = first_grid_point(raw)
    receipt = produce(raw)
    require(receipt["status"] == "success", f"{name}: producer error {receipt}")
    result = receipt["result"]
    if oracle is None:
        require(result["kind"] == "coefficient_identity", f"{name}: false nonidentity")
        require(result["equal"] is True, f"{name}: identity flag")
        return {"name": name, "kind": "coefficient_identity", "grid_bounds": request_bounds(raw)}
    expected, left, right = oracle
    require(result["kind"] == "nonzero_evaluation", f"{name}: false identity")
    witness = result["witness"]
    actual = tuple(witness["assignment"][n] for n in raw["variables"])
    require(actual == expected, f"{name}: expected lexicographic point {expected}, got {actual}")
    for key, value in [("left_value", left), ("right_value", right), ("difference_value", left - right)]:
        require(witness[key] == pair(value), f"{name}: incorrect exact {key}")
    checked = verify_witness(raw, witness)
    require(checked["status"] == "accepted", f"{name}: checker rejected {checked}")
    trace = result["construction_trace"]
    require(len(trace) == len(raw["variables"]), f"{name}: incomplete trace")
    total_trials = 0
    prefix = ()
    for j, step in enumerate(trace):
        require(step["variable"] == raw["variables"][j], f"{name}: variable order")
        require(step["chosen_value"] == actual[j], f"{name}: trace point disagreement")
        require(0 <= actual[j] <= step["current_degree"] <= step["initial_degree"] <= request_bounds(raw)[j], f"{name}: degree bounds")
        require(step["current_degree"] == degree_by_differences(raw, j, prefix), f"{name}: exact current degree")
        require(step["initial_degree"] == degree_by_differences(raw, j), f"{name}: exact initial degree")
        require(step["candidate_min"] == 0 and step["candidate_max"] == step["current_degree"], f"{name}: candidate interval")
        require([t["value"] for t in step["trials"]] == list(range(actual[j] + 1)), f"{name}: missing candidate")
        for trial in step["trials"]:
            survives = first_grid_point(raw, prefix + (trial["value"],)) is not None
            require(trial["remaining_nonzero"] is survives, f"{name}: incorrect residual-zero trace")
        total_trials += len(step["trials"])
        prefix += (actual[j],)
    current_bound = sum(t["current_degree"] + 1 for t in trace)
    initial_bound = sum(t["initial_degree"] + 1 for t in trace)
    require(total_trials == receipt["usage"]["substitution_trials"], f"{name}: trial accounting")
    require(total_trials <= current_bound <= initial_bound, f"{name}: trial bound")
    require(result["current_degree_trial_bound"] == current_bound, f"{name}: reported current bound")
    require(result["initial_degree_trial_bound"] == initial_bound, f"{name}: reported initial bound")
    return {"name": name, "kind": "nonzero_evaluation", "point": list(actual), "trials": total_trials,
            "current_degree_trial_bound": current_bound, "initial_degree_trial_bound": initial_bound,
            "grid_bounds": request_bounds(raw)}


def audit_mutations():
    raw = request(["x", "y"], mul(falling("x", 2), v("y")), q(0))
    witness = produce(raw)["result"]["witness"]
    mutations = []
    def reject(name, mutate, mutate_request=None):
        candidate, supplied = deepcopy(witness), deepcopy(raw)
        mutate(candidate)
        if mutate_request:
            mutate_request(supplied)
        result = verify_witness(supplied, candidate)
        require(result["status"] != "accepted", f"forgery accepted: {name}")
        mutations.append({"name": name, "status": result["status"]})
    reject("wrong_input_hash", lambda w: w.update(input_sha256="0" * 64))
    reject("wrong_request_hash", lambda w: w.update(request_sha256="0" * 64))
    reject("wrong_schema", lambda w: w.update(schema_version="2.0"))
    reject("ring_field", lambda w: w["ring"].update(coefficient_field="F2"))
    reject("ring_variable_order", lambda w: w["ring"].update(variables=["y", "x"]))
    reject("ring_extra_field", lambda w: w["ring"].update(relations=[]))
    reject("missing_coordinate", lambda w: w["assignment"].pop("x"))
    reject("extra_coordinate", lambda w: w["assignment"].update(z=0))
    reject("boolean_coordinate", lambda w: w["assignment"].update(y=True))
    reject("float_coordinate", lambda w: w["assignment"].update(y=1.0))
    reject("negative_coordinate", lambda w: w["assignment"].update(y=-1))
    reject("over_cap_coordinate", lambda w: w["assignment"].update(y=33))
    reject("root_coordinate", lambda w: w["assignment"].update(x=0))
    reject("changed_left_value", lambda w: w.update(left_value=pair(Fraction(99))))
    reject("changed_right_value", lambda w: w.update(right_value=pair(Fraction(99))))
    reject("changed_difference", lambda w: w.update(difference_value=pair(Fraction(99))))
    reject("zero_difference", lambda w: w.update(difference_value=pair(Fraction(0))))
    reject("unreduced_rational", lambda w: w.update(left_value={"numerator": 4, "denominator": 2}))
    reject("negative_denominator", lambda w: w.update(left_value={"numerator": -2, "denominator": -1}))
    reject("zero_denominator", lambda w: w.update(left_value={"numerator": 2, "denominator": 0}))
    reject("boolean_numerator", lambda w: w.update(left_value={"numerator": True, "denominator": 1}))
    reject("float_numerator", lambda w: w.update(left_value={"numerator": 2.0, "denominator": 1}))
    reject("extra_witness_field", lambda w: w.update(construction_trace=[]))
    reject("missing_witness_field", lambda w: w.pop("left_value"))
    reject("altered_original_request", lambda w: None, lambda r: r["operands"].__setitem__(1, q(1)))
    # A nonminimal point is intentionally valid: the certificate is semantic,
    # not a certification of construction order or trace minimality.
    alternative = deepcopy(witness)
    alternative["assignment"] = {"x": 3, "y": 2}
    left, right = [evaluate(e, alternative["assignment"]) for e in raw["operands"]]
    alternative.update(left_value=pair(left), right_value=pair(right), difference_value=pair(left - right))
    require(verify_witness(raw, alternative)["status"] == "accepted", "valid nonminimal point rejected")
    # Canonically equal rational literals still have distinct original hashes.
    first = request(["x"], mul(q(1, 2), v("x")))
    equivalent = request(["x"], mul(q(2, 4), v("x")))
    one, two = produce(first), produce(equivalent)
    require(one["request_sha256"] == two["request_sha256"], "normalized request hash instability")
    require(one["input_sha256"] != two["input_sha256"], "original-input hash failed to bind representation")
    require(verify_witness(equivalent, one["result"]["witness"])["status"] != "accepted", "cross-request witness accepted")
    return {"rejected_mutations": mutations, "valid_nonminimal_point": "accepted",
            "original_and_normalized_hash_binding": "passed"}


def audit_caps():
    checks = []
    def expect_error(name, result, code="resource_limit"):
        require(result["status"] == "error", f"{name}: expected inconclusive error, got {result}")
        require(result["error"]["code"] == code, f"{name}: wrong code {result}")
        require(result.get("result") is None, f"{name}: error carried mathematical result")
        checks.append({"name": name, "status": "error", "code": code})
    raw = request(["x"], falling("x", 4))
    base = produce(raw)
    trials = base["usage"]["substitution_trials"]
    visits = base["usage"]["substitution_term_visits"]
    for field, amount in [("max_trials", trials), ("max_substitution_term_visits", visits)]:
        require(produce(raw, replace(Limits(), **{field: amount}))["status"] == "success", f"{field}: exact cap failed")
        expect_error(field + "_one_below", produce(raw, replace(Limits(), **{field: amount - 1})))
    const = request([], q(3))
    require(produce(const, replace(Limits(), max_value_bits=2))["status"] == "success", "exact bit cap")
    expect_error("producer_value_bits", produce(const, replace(Limits(), max_value_bits=1)))
    for value in [-1, True, 265, 1.0]:
        expect_error("invalid_max_trials_" + repr(value), produce(raw, replace(Limits(), max_trials=value)), "invalid_limits")
    expect_error("invalid_limits_type", produce(raw, {}), "invalid_limits")
    expect_error("degree_cap", produce(request(["x"], power(v("x"), 33))))
    expect_error("literal_integer_bit_cap", produce(request([], q(1 << 256))))
    sum8 = combine("add", [q(1)] + [v("x" + str(i)) for i in range(8)])
    expect_error("intermediate_term_cap", produce(request(["x" + str(i) for i in range(8)], power(sum8, 4))))
    # An eventual zero does not license exceeding an intermediate cap.
    too_big = power(v("x"), 33)
    expect_error("oversize_intermediate_eventual_zero", produce(request(["x"], mul(too_big, q(0)))))
    witness = base["result"]["witness"]
    nodes = sum(count_nodes(e) for e in raw["operands"])
    require(verify_witness(raw, witness, replace(Limits(), max_evaluation_nodes=nodes))["status"] == "accepted", "exact evaluator node cap")
    expect_error("checker_node_cap", verify_witness(raw, witness, replace(Limits(), max_evaluation_nodes=nodes - 1)))
    expect_error("checker_value_bits", verify_witness(raw, witness, replace(Limits(), max_value_bits=1)))
    return checks


def audit_ingress():
    checks = []
    malformed = [
        ("duplicate_field", '{"x":1,"x":2}'),
        ("nan", '{"x":NaN}'), ("infinity", '{"x":Infinity}'),
        ("negative_infinity", '{"x":-Infinity}'),
        ("invalid_utf8", b"\xff"), ("truncated", '{"x":'),
        ("wire_bytes", " " * 262145),
        ("wire_integer", "1" + "0" * 1234),
    ]
    for name, text in malformed:
        try:
            strict_json(text)
        except WitnessError as error:
            checks.append({"name": name, "code": error.code})
        else:
            raise RuntimeError("wire ingress accepted " + name)
    base = request(["x"], v("x"))
    mutations = [
        ("duplicate_variables", lambda r: r.update(variables=["x", "x"])),
        ("unknown_variable", lambda r: r["operands"].__setitem__(0, v("z"))),
        ("extra_request_key", lambda r: r.update(extra=0)),
        ("unsupported_operation", lambda r: r.update(operation="add")),
        ("unsupported_field", lambda r: r.update(coefficient_field="F2")),
        ("boolean_literal", lambda r: r["operands"].__setitem__(1, q(True))),
        ("float_literal", lambda r: r["operands"].__setitem__(1, q(1.0))),
        ("zero_literal_denominator", lambda r: r["operands"].__setitem__(1, q(1, 0))),
        ("power_ast_not_supported", lambda r: r["operands"].__setitem__(0, {"type": "power", "base": v("x"), "exponent": 2})),
        ("executable_string", lambda r: r["operands"].__setitem__(0, "x + 1")),
    ]
    for name, mutate in mutations:
        raw = deepcopy(base)
        mutate(raw)
        result = produce(raw)
        require(result["status"] == "error" and result["result"] is None, "typed ingress accepted " + name)
        checks.append({"name": name, "code": result["error"]["code"]})
    cyclic = {"type": "add", "operands": []}
    cyclic["operands"][:] = [cyclic, q(1)]
    result = produce(request(["x"], cyclic))
    require(result["status"] == "error" and result["result"] is None, "cyclic input was not bounded")
    checks.append({"name": "cyclic_python_input", "code": result["error"]["code"]})
    return checks


def audit_checker_independence():
    import polynomial_witness._vendor.polynomial as backend
    import polynomial_witness.producer as producer_module
    raw = request(["x"], add(mul(v("x"), v("x")), q(1)))
    witness = produce(raw)["result"]["witness"]
    saved = []
    def forbidden(*args, **kwargs):
        raise RuntimeError("checker called producer or polynomial algebra")
    for module, names in [(backend, ["_normalize", "_add", "_multiply"]),
                          (producer_module, ["produce", "_substitute", "_evaluate"])]:
        for name in names:
            saved.append((module, name, getattr(module, name)))
            setattr(module, name, forbidden)
    try:
        result = verify_witness(raw, witness)
        require(result["status"] == "accepted", "checker depends on patched algebra")
    finally:
        for module, name, old in saved:
            setattr(module, name, old)
    import ast
    tree = ast.parse((ROOT / "polynomial_witness/checker.py").read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    require(not any("producer" in name for name in imports), "checker imports producer")
    return {"producer_and_normalization_disabled": "accepted", "direct_producer_import": False,
            "shared_trust": "request validator, ring/hash utilities, Fraction, Python runtime"}


def audit_scope_boundaries():
    raw = request(["x"], power(v("x"), 33))
    require(produce(raw)["status"] == "error", "degree-33 producer boundary")
    digest = sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    candidate = {"schema_version": "1.0", "input_sha256": digest, "request_sha256": digest,
                 "ring": {"kind": "commutative_polynomial_ring", "coefficient_field": "Q", "variables": ["x"]},
                 "assignment": {"x": 1}, "left_value": pair(Fraction(1)),
                 "right_value": pair(Fraction(0)), "difference_value": pair(Fraction(1))}
    require(verify_witness(raw, candidate)["status"] == "accepted", "direct evaluator should not require expansion")
    equal_raw = request(["x"], v("x"), v("x"))
    identity = produce(equal_raw)
    require(verify_witness(equal_raw, identity["result"])["status"] == "rejected", "identity receipt accepted as point certificate")
    equal_witness = {"schema_version": "1.0", "input_sha256": identity["input_sha256"],
                     "request_sha256": identity["request_sha256"], "ring": identity["ring"],
                     "assignment": {"x": 0}, "left_value": pair(Fraction(0)),
                     "right_value": pair(Fraction(0)), "difference_value": pair(Fraction(0))}
    require(verify_witness(equal_raw, equal_witness)["status"] == "rejected", "equal point accepted as mismatch")
    # Phase-specific limits deliberately do not constrain skipped phases.
    zero_limits = Limits(max_trials=0, max_substitution_term_visits=0,
                         max_evaluation_nodes=0, max_value_bits=0)
    require(produce(request([], q(3), q(3)), zero_limits)["status"] == "success", "identity incorrectly needs evaluation budget")
    require(produce(request([], q(1)), replace(Limits(), max_evaluation_nodes=0))["status"] == "success", "checker-only cap applied to producer")
    from polynomial_witness.api import construct, construct_json, verify_json
    checked = construct(request([], q(1)), replace(Limits(), max_evaluation_nodes=0))
    require(checked["status"] == "error" and checked["result"] is None, "checked API leaked an unchecked success")
    require(construct(equal_raw)["verification"]["status"] == "not_applicable", "identity falsely labeled point-verified")
    valid = request(["x"], v("x"))
    result = construct_json(json.dumps(valid))
    require(result["status"] == "success" and result["verification"]["status"] == "accepted", "JSON construction")
    envelope = {"request": valid, "witness": result["result"]["witness"]}
    require(verify_json(json.dumps(envelope))["status"] == "accepted", "JSON witness verification")
    return {"checker_accepts_without_producer_expansion": "passed",
            "identity_receipt_as_point_certificate": "rejected", "equal_point_as_mismatch": "rejected",
            "phase_specific_caps": "passed", "checked_api_fail_closed": "passed", "json_round_trip": "passed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=20261024)
    parser.add_argument("--random-cases", type=int, default=200)
    args = parser.parse_args()
    fixtures = named_cases() + list(exhaustive_small_cases()) + list(generated_cases(args.seed, args.random_cases))
    cases = [audit_case(name, raw) for name, raw in fixtures]
    report = {"status": "passed", "optimization": sys.flags.optimize, "seed": args.seed,
              "python_version": sys.version,
              "audit_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "oracle": "Direct Fraction AST evaluation on syntax-degree-bounded Cartesian grids, test only",
              "semantic_cases": cases,
              "counts": {"semantic_cases": len(cases),
                         "identities": sum(c["kind"] == "coefficient_identity" for c in cases),
                         "nonidentities": sum(c["kind"] == "nonzero_evaluation" for c in cases)},
              "mutations": audit_mutations(), "cap_checks": audit_caps(),
              "ingress_checks": audit_ingress(), "checker_independence": audit_checker_independence(),
              "scope_boundaries": audit_scope_boundaries(),
              "scope": "Finite tests and source review, not a proof-assistant certificate or exhaustive validation",
              "source_sha256": {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                                for path in sorted((ROOT / "polynomial_witness").rglob("*.py"))}}
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        destination = args.output.resolve()
        require(destination.is_relative_to(ROOT), "audit output must stay within lab")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded)
    print(json.dumps({"status": report["status"], "optimization": report["optimization"],
                      "counts": report["counts"], "output": str(args.output) if args.output else None}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Exact, resource-bounded counterexample search on explicitly finite Z boxes.

Exhaustion is not an unrestricted theorem. Witness checking is a new calculation
from the original request and assignment, not validation of a producer's verdict.
Only built-in JSON-shaped values and a fixed typed polynomial AST are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
from typing import Any, Literal, TypedDict

from ._vendor import polynomial as poly
from ._vendor.calculator import artifact_hash, canonical_json

VERSION = "0.1.1-lab"
MAX_INPUT_BYTES = 65536
MAX_DOMAIN_CARDINALITY = 10000
MAX_CONSTRAINTS = 16
MAX_EVALUATION_STEPS = 250000
MAX_VALUE_BITS = 4096
_RELATIONS = ("lt", "le", "eq", "ne", "ge", "gt")


class Bounds(TypedDict):
    lower: int
    upper: int


class Predicate(TypedDict):
    relation: Literal["lt", "le", "eq", "ne", "ge", "gt"]
    left: poly.Expression
    right: poly.Expression


class SearchRequest(TypedDict):
    domain: Literal["finite_integer_box"]
    coefficient_field: Literal["Q"]
    variables: list[str]
    bounds: dict[str, Bounds]
    constraints: list[Predicate]
    assertion: Predicate


@dataclass(frozen=True)
class _Literal:
    value: Fraction


@dataclass(frozen=True)
class _Variable:
    name: str


@dataclass(frozen=True)
class _Binary:
    operation: Literal["add", "multiply"]
    left: _Expression
    right: _Expression


_Expression = _Literal | _Variable | _Binary


@dataclass(frozen=True)
class _Predicate:
    relation: str
    left: _Expression
    right: _Expression


@dataclass(frozen=True)
class _Parsed:
    request: dict
    constraints: tuple[_Predicate, ...]
    assertion: _Predicate
    cardinality: int
    ast_nodes: int


@dataclass
class _Work:
    steps: int = 0

    def spend(self) -> None:
        if self.steps >= MAX_EVALUATION_STEPS:
            raise poly.PolynomialError("resource_limit", "exact evaluation work budget exhausted")
        self.steps += 1


def _limits() -> dict:
    return {
        "input_bytes": MAX_INPUT_BYTES,
        "variables": poly.MAX_VARIABLES,
        "constraints": MAX_CONSTRAINTS,
        "domain_cardinality": MAX_DOMAIN_CARDINALITY,
        "expression_depth": poly.MAX_EXPR_DEPTH,
        "total_ast_nodes": poly.MAX_AST_NODES,
        "syntactic_degree_upper_bound": poly.MAX_DEGREE,
        "input_integer_bits": poly.MAX_INPUT_BITS,
        "intermediate_value_bits": MAX_VALUE_BITS,
        "evaluation_steps": MAX_EVALUATION_STEPS,
    }


def _compile(expression: dict) -> tuple[_Expression, int]:
    kind = expression["type"]
    if kind == "rational":
        return _Literal(Fraction(expression["numerator"], expression["denominator"])), 0
    if kind == "variable":
        return _Variable(expression["name"]), 1
    left, left_degree = _compile(expression["operands"][0])
    right, right_degree = _compile(expression["operands"][1])
    degree = max(left_degree, right_degree) if kind == "add" else left_degree + right_degree
    if degree > poly.MAX_DEGREE:
        raise poly.PolynomialError("resource_limit", "syntactic polynomial degree upper bound exceeded")
    return _Binary(kind, left, right), degree


def _predicate(value: Any, variables: list[str], budget: poly._Budget) -> tuple[dict, _Predicate]:
    raw = poly._object(value, {"relation", "left", "right"}, "predicate")
    relation = raw["relation"]
    if type(relation) is not str or relation not in _RELATIONS:
        raise poly.PolynomialError("unsupported_relation", "relation must be lt, le, eq, ne, ge, or gt")
    left = poly._expression(raw["left"], variables, budget)
    right = poly._expression(raw["right"], variables, budget)
    left_ast, _ = _compile(left)
    right_ast, _ = _compile(right)
    return {"relation": relation, "left": left, "right": right}, _Predicate(relation, left_ast, right_ast)


def _parse(request: Any, receipt: dict) -> _Parsed:
    raw = poly._object(request, {"domain", "coefficient_field", "variables", "bounds", "constraints", "assertion"}, "search request")
    if type(raw["domain"]) is not str or raw["domain"] != "finite_integer_box":
        raise poly.PolynomialError("invalid_domain", "domain must be finite_integer_box, not Q or R")
    if type(raw["coefficient_field"]) is not str or raw["coefficient_field"] != "Q":
        raise poly.PolynomialError("unsupported_field", "only exact rational polynomial coefficients Q are supported")
    variables = raw["variables"]
    if type(variables) is not list or len(variables) > poly.MAX_VARIABLES:
        raise poly.PolynomialError("invalid_input", "variables must be a bounded JSON array of names")
    for name in variables:
        if type(name) is not str or not poly._NAME.fullmatch(name):
            raise poly.PolynomialError("invalid_variable", "variables must be case-sensitive ASCII identifiers of 1-32 characters")
    if len(set(variables)) != len(variables):
        raise poly.PolynomialError("duplicate_variable", "each variable must be declared exactly once")
    bounds = poly._object(raw["bounds"], set(variables), "bounds")
    normalized_bounds = {}
    cardinality = 1
    for name in variables:
        bound = poly._object(bounds[name], {"lower", "upper"}, "integer bounds")
        lower = poly._integer(bound["lower"], "lower bound")
        upper = poly._integer(bound["upper"], "upper bound")
        if lower > upper:
            raise poly.PolynomialError("invalid_bounds", "closed integer intervals must have lower <= upper; empty intervals are not accepted")
        cardinality *= upper - lower + 1
        normalized_bounds[name] = {"lower": lower, "upper": upper}
    receipt["domain"] = {"kind": "finite_integer_box", "variables": list(variables),
                         "bounds": normalized_bounds, "cardinality": cardinality}
    receipt["progress"]["domain_cardinality"] = cardinality
    # Retain the complete validated box even when admission or AST parsing fails.
    # Compute the complete cardinality before its admission check; never truncate.
    if cardinality > MAX_DOMAIN_CARDINALITY:
        raise poly.PolynomialError("resource_limit", "full declared box cardinality exceeds the search limit")
    if type(raw["constraints"]) is not list or len(raw["constraints"]) > MAX_CONSTRAINTS:
        raise poly.PolynomialError("invalid_input", "constraints must be a bounded JSON array")
    budget = poly._Budget()
    normalized_constraints = []
    compiled_constraints = []
    for constraint in raw["constraints"]:
        normalized, compiled = _predicate(constraint, variables, budget)
        normalized_constraints.append(normalized)
        compiled_constraints.append(compiled)
    assertion, compiled_assertion = _predicate(raw["assertion"], variables, budget)
    # Every reachable field has already been checked. Bounded depth prevents cycles.
    if len(canonical_json(raw)) > MAX_INPUT_BYTES:
        raise poly.PolynomialError("resource_limit", "canonical request exceeds the byte limit")
    normalized = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": list(variables),
                  "bounds": normalized_bounds, "constraints": normalized_constraints, "assertion": assertion}
    return _Parsed(normalized, tuple(compiled_constraints), compiled_assertion, cardinality, budget.nodes)


def _value_size(value: Fraction) -> Fraction:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_VALUE_BITS:
        raise poly.PolynomialError("resource_limit", "intermediate exact value exceeds the bit limit")
    return value


def _evaluate(expression: _Expression, assignment: dict[str, int], work: _Work) -> Fraction:
    work.spend()  # Charge visits, including literal and variable nodes.
    if isinstance(expression, _Literal):
        return expression.value
    if isinstance(expression, _Variable):
        return Fraction(assignment[expression.name])
    left = _evaluate(expression.left, assignment, work)
    right = _evaluate(expression.right, assignment, work)
    return _value_size(left + right if expression.operation == "add" else left * right)


def _compare(relation: str, left: Fraction, right: Fraction) -> bool:
    if relation == "lt":
        return left < right
    if relation == "le":
        return left <= right
    if relation == "eq":
        return left == right
    if relation == "ne":
        return left != right
    if relation == "ge":
        return left >= right
    return left > right  # Only the validated relation gt can reach this branch.


def _rational(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _evaluate_predicate(predicate: _Predicate, assignment: dict[str, int], work: _Work) -> dict:
    left = _evaluate(predicate.left, assignment, work)
    right = _evaluate(predicate.right, assignment, work)
    work.spend()  # Charge the exact comparison.
    return {"relation": predicate.relation, "left": _rational(left), "right": _rational(right),
            "holds": _compare(predicate.relation, left, right)}


def _evaluate_assignment(parsed: _Parsed, assignment: dict[str, int], work: _Work) -> dict:
    # Evaluate every constraint, not just the first failed one.
    constraints = [_evaluate_predicate(predicate, assignment, work) for predicate in parsed.constraints]
    constraints_hold = all(item["holds"] for item in constraints)
    assertion = _evaluate_predicate(parsed.assertion, assignment, work) if constraints_hold else None
    return {"constraints": constraints, "all_constraints_hold": constraints_hold,
            "assertion": assertion,
            "assertion_violated": assertion is not None and not assertion["holds"]}


def _source_hash(name: str) -> str:
    return sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()


def _receipt(kind: str) -> dict:
    return {
        "schema_version": "1.0", "kind": kind, "status": "error",
        "input": None, "request": None, "supplied_assignment": None,
        "domain": None, "result": None, "error": None,
        "progress": {"domain_cardinality": None, "visited_count": 0, "eligible_count": 0,
                     "complete": False, "checked_assignment_count": 0},
        "usage": {"ast_nodes": 0, "evaluation_steps": 0},
        "scope": {
            "evidence_level": "exact_bounded_integer_evaluation",
            "formal_proof": False, "universal_proof": False,
            "claim": "Only the declared finite Cartesian box of integers, subject to every declared constraint.",
            "quantification": "Search for a point satisfying all constraints and violating the single assertion.",
            "exhaustion_meaning": "No counterexample in this declared finite domain; no conclusion outside it.",
            "ordering": "Declared variable order; ascending integers; last coordinate varies fastest.",
            "complete_meaning": "Every point of the full declared Cartesian box was adjudicated by search.",
            "zero_variable_case": "The empty Cartesian product contains exactly one assignment, {}.",
            "rejected_assignment_capture": "Malformed, noninteger or oversized assignments are not retained or hashed; the rejection receipt does not identify their original bytes.",
            "resource_semantics": "Fixed limits include intermediates; conservative rejection is possible; errors are not exhaustion.",
            "limits": _limits(),
        },
        "backend": {"name": "typed AST + python.fractions.Fraction", "python_version": platform.python_version(),
                    "adapter_version": VERSION},
        "artifacts": {"input_sha256": None, "request_sha256": None, "assignment_sha256": None,
                      "result_sha256": None, "evidence_sha256": None,
                      "backend_source_sha256": _source_hash("core.py"),
                      "parser_source_sha256": sha256(Path(poly.__file__).read_bytes()).hexdigest(),
                      "canonical_json_source_sha256": sha256(Path(poly.__file__).with_name("calculator.py").read_bytes()).hexdigest()},
    }


def _bind(request: Any, receipt: dict) -> _Parsed:
    parsed = _parse(request, receipt)
    receipt["input"] = json.loads(canonical_json(request))
    receipt["request"] = parsed.request
    receipt["artifacts"]["input_sha256"] = artifact_hash(receipt["input"])
    receipt["artifacts"]["request_sha256"] = artifact_hash(parsed.request)
    receipt["domain"] = {"kind": "finite_integer_box", "variables": parsed.request["variables"],
                         "bounds": parsed.request["bounds"], "cardinality": parsed.cardinality}
    receipt["progress"]["domain_cardinality"] = parsed.cardinality
    receipt["usage"]["ast_nodes"] = parsed.ast_nodes
    return parsed


def _evidence_hash(receipt: dict) -> str:
    # Bind meaning, work, domain, source identities and outcomes, not just verdict.
    evidence = {key: value for key, value in receipt.items() if key != "artifacts"}
    evidence["artifacts"] = {key: value for key, value in receipt["artifacts"].items() if key != "evidence_sha256"}
    return artifact_hash(evidence)


def _finish(receipt: dict, work: _Work) -> dict:
    receipt["usage"]["evaluation_steps"] = work.steps
    try:
        if receipt["result"] is not None:
            receipt["artifacts"]["result_sha256"] = artifact_hash(receipt["result"])
        receipt["artifacts"]["evidence_sha256"] = _evidence_hash(receipt)
    except (ValueError, OverflowError, RecursionError) as error:
        # A valid bounded Fraction can still exceed a stricter host JSON integer
        # conversion limit. Final receipt serialization is part of computation:
        # discard the result and never leak an exception or promote completeness.
        # Do not change process-global integer conversion or recursion limits.
        _error(receipt, error)
        receipt["artifacts"]["evidence_sha256"] = None
        try:
            receipt["artifacts"]["evidence_sha256"] = _evidence_hash(receipt)
        except (ValueError, OverflowError, RecursionError):
            # If even bounded error metadata cannot be serialized on this host,
            # retain an explicit error with no fabricated evidence hash.
            pass
    return receipt


def _error(receipt: dict, error: Exception) -> None:
    receipt["status"] = "error"
    receipt["result"] = None
    receipt["artifacts"]["result_sha256"] = None
    receipt["progress"]["complete"] = False
    receipt["error"] = {"code": error.code, "message": str(error)} if isinstance(error, poly.PolynomialError) else {
        "code": "representation_limit", "message": "input or result exceeds supported JSON or host representation limits"}


def search_counterexample(request: SearchRequest | dict) -> dict:
    """Return a concrete finite-domain counterexample or exact bounded exhaustion.

    Unsupported input and exhausted resources return status=error, result=null.
    Hashes identify content, not authenticity or a proof of implementation correctness.
    """
    receipt = _receipt("bounded_counterexample_search")
    work = _Work()
    try:
        parsed = _bind(request, receipt)
        variables = parsed.request["variables"]
        intervals = [range(parsed.request["bounds"][name]["lower"], parsed.request["bounds"][name]["upper"] + 1)
                     for name in variables]
        for values in product(*intervals):
            assignment = dict(zip(variables, values))
            evaluation = _evaluate_assignment(parsed, assignment, work)
            receipt["progress"]["visited_count"] += 1
            receipt["progress"]["eligible_count"] += int(evaluation["all_constraints_hold"])
            if evaluation["assertion_violated"]:
                receipt["result"] = {"outcome": "counterexample_found", "assignment": assignment, "evaluation": evaluation}
                break
        else:
            receipt["result"] = {"outcome": "no_counterexample_in_declared_finite_domain", "assignment": None, "evaluation": None}
        receipt["progress"]["complete"] = receipt["progress"]["visited_count"] == parsed.cardinality
        receipt["status"] = "success"
    except (poly.PolynomialError, ValueError, OverflowError, RecursionError) as error:
        _error(receipt, error)
    return _finish(receipt, work)


def _assignment(value: Any, parsed: _Parsed) -> tuple[dict | None, str | None]:
    variables = parsed.request["variables"]
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != set(variables):
        return None, "assignment_keys_must_exactly_match_declared_variables"
    for name in variables:
        # No rational, float, bool, string or subclass coercion into an integer.
        if type(value[name]) is not int:
            return None, "assignment_values_must_be_json_integers"
        if value[name].bit_length() > poly.MAX_INPUT_BITS:
            return None, "assignment_integer_exceeds_input_bit_limit"
    assignment = {name: value[name] for name in variables}
    for name in variables:
        bounds = parsed.request["bounds"][name]
        if not bounds["lower"] <= assignment[name] <= bounds["upper"]:
            return assignment, "assignment_outside_declared_integer_bounds"
    return assignment, None


def check_witness(request: SearchRequest | dict, assignment: dict) -> dict:
    """Check the original request and supplied assignment from scratch.

    No producer receipt/verdict is accepted. A completed check returns valid=False
    for an invalid assignment, a failed constraint, or a true assertion. Malformed
    original requests or resource exhaustion remain status=error, result=null.
    This shares parser/evaluator code with search; it is independent of producer
    output, not an independently implemented proof checker.
    """
    receipt = _receipt("bounded_counterexample_witness_check")
    work = _Work()
    try:
        parsed = _bind(request, receipt)
        candidate, reason = _assignment(assignment, parsed)
        receipt["supplied_assignment"] = candidate
        if candidate is not None:
            receipt["artifacts"]["assignment_sha256"] = artifact_hash(candidate)
        if reason is not None:
            receipt["result"] = {"valid": False, "reason": reason, "evaluation": None}
        else:
            evaluation = _evaluate_assignment(parsed, candidate, work)
            receipt["progress"]["checked_assignment_count"] = 1
            valid = evaluation["all_constraints_hold"] and evaluation["assertion_violated"]
            reason = "counterexample_verified" if valid else (
                "constraint_not_satisfied" if not evaluation["all_constraints_hold"] else "assertion_not_violated")
            receipt["result"] = {"valid": valid, "reason": reason, "evaluation": evaluation}
        receipt["status"] = "success"
    except (poly.PolynomialError, ValueError, OverflowError, RecursionError) as error:
        _error(receipt, error)
    return _finish(receipt, work)


def _load_json(data: str | bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise poly.PolynomialError("invalid_json", "duplicate JSON object keys are rejected")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise poly.PolynomialError("invalid_json", "nonfinite JSON numbers are rejected")

    def bounded_integer(value: str) -> int:
        if len(value.lstrip("-")) > 78:
            raise poly.PolynomialError("resource_limit", "integer token exceeds the input bit budget")
        return poly._integer(int(value), "JSON integer")

    if type(data) not in (str, bytes):
        raise poly.PolynomialError("invalid_input", "JSON input must be text or UTF-8 bytes")
    if len(data) > MAX_INPUT_BYTES or (type(data) is str and len(data.encode("utf-8")) > MAX_INPUT_BYTES):
        raise poly.PolynomialError("resource_limit", "wire JSON exceeds the input byte limit")
    if type(data) is bytes:
        data = data.decode("utf-8")
    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant, parse_int=bounded_integer)
    except (ValueError, RecursionError) as error:
        if isinstance(error, poly.PolynomialError):
            raise
        raise poly.PolynomialError("invalid_json", "malformed JSON or unsupported nesting") from None


def search_counterexample_json(data: str | bytes) -> dict:
    """Strict JSON transport entrypoint: bounded wire bytes and duplicate rejection."""
    try:
        return search_counterexample(_load_json(data))
    except (poly.PolynomialError, ValueError, OverflowError, RecursionError) as error:
        receipt = _receipt("bounded_counterexample_search")
        _error(receipt, error)
        return _finish(receipt, _Work())


def check_witness_json(request_data: str | bytes, assignment_data: str | bytes) -> dict:
    """Strict JSON transport for the original request and a separate assignment."""
    try:
        return check_witness(_load_json(request_data), _load_json(assignment_data))
    except (poly.PolynomialError, ValueError, OverflowError, RecursionError) as error:
        receipt = _receipt("bounded_counterexample_witness_check")
        _error(receipt, error)
        return _finish(receipt, _Work())

"""Bounded exact sparse multivariate polynomials over Q, using JSON data only.

An identity is decided by a zero coefficient difference in the explicitly
declared formal polynomial ring. This is not a Lean proof or a claim about
quotients, rational functions, finite samples, or arbitrary input programs.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
from typing import Any, Literal, TypedDict, Union

from .calculator import artifact_hash, canonical_json

VERSION = "0.2.0"
MAX_INPUT_BYTES = 65536
MAX_VARIABLES = 8
MAX_EXPR_DEPTH = 32
MAX_AST_NODES = 1024
MAX_DEGREE = 32
MAX_TERMS = 256
MAX_INPUT_BITS = 256
MAX_COEFFICIENT_BITS = 2048
MAX_ARITHMETIC_STEPS = 100000
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z", re.ASCII)
_OPERATIONS = ("add", "multiply", "verify_identity")


class RationalExpr(TypedDict):
    type: Literal["rational"]
    numerator: int
    denominator: int


class VariableExpr(TypedDict):
    type: Literal["variable"]
    name: str


class BinaryExpr(TypedDict):
    type: Literal["add", "multiply"]
    operands: list["Expression"]


Expression = Union[RationalExpr, VariableExpr, BinaryExpr]


class PolynomialRequest(TypedDict):
    domain: Literal["polynomial_ring"]
    coefficient_field: Literal["Q"]
    variables: list[str]
    operation: Literal["add", "multiply", "verify_identity"]
    operands: list[Expression]


Monomial = tuple[int, ...]
Polynomial = dict[Monomial, Fraction]


class PolynomialError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class _Budget:
    nodes: int = 0
    arithmetic_steps: int = 0

    def node(self, depth: int) -> None:
        self.nodes += 1
        if depth > MAX_EXPR_DEPTH or self.nodes > MAX_AST_NODES:
            raise PolynomialError("resource_limit", "expression depth or total AST node limit exceeded")

    def spend(self, amount: int = 1) -> None:
        if self.arithmetic_steps + amount > MAX_ARITHMETIC_STEPS:
            raise PolynomialError("resource_limit", "cumulative coefficient arithmetic budget exceeded")
        self.arithmetic_steps += amount


def _object(value: Any, fields: set[str], label: str) -> dict:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != fields:
        raise PolynomialError("invalid_input", f"{label} requires exactly these fields: {', '.join(sorted(fields))}")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise PolynomialError("invalid_input", f"{label} must be a JSON integer, not a bool, float, or string")
    if value.bit_length() > MAX_INPUT_BITS:
        raise PolynomialError("resource_limit", f"{label} exceeds the {MAX_INPUT_BITS}-bit input limit")
    return value


def _expression(value: Any, variables: list[str], budget: _Budget, depth: int = 1) -> dict:
    budget.node(depth)
    if type(value) is not dict or type(value.get("type")) is not str:
        raise PolynomialError("invalid_input", "each expression must be an object with a string type")
    kind = value["type"]
    if kind == "rational":
        _object(value, {"type", "numerator", "denominator"}, "rational expression")
        numerator = _integer(value["numerator"], "numerator")
        denominator = _integer(value["denominator"], "denominator")
        if denominator == 0:
            raise PolynomialError("division_by_zero", "a rational literal denominator cannot be zero")
        coefficient = Fraction(numerator, denominator)
        return {"type": kind, "numerator": coefficient.numerator, "denominator": coefficient.denominator}
    if kind == "variable":
        _object(value, {"type", "name"}, "variable expression")
        if type(value["name"]) is not str or value["name"] not in variables:
            raise PolynomialError("unknown_variable", "variable names must exactly match a declared name; aliases are not accepted")
        return {"type": kind, "name": value["name"]}
    if kind in ("add", "multiply"):
        _object(value, {"type", "operands"}, "binary expression")
        operands = value["operands"]
        if type(operands) is not list or len(operands) != 2:
            raise PolynomialError("invalid_input", f"{kind} expressions require exactly two operands in a JSON array")
        return {"type": kind, "operands": [_expression(item, variables, budget, depth + 1) for item in operands]}
    raise PolynomialError("unsupported_expression", "allowed expression types are rational, variable, add, and multiply; no division, powers, or executable strings")


def _parse(request: Any) -> tuple[dict, _Budget]:
    raw = _object(request, {"domain", "coefficient_field", "variables", "operation", "operands"}, "polynomial request")
    if type(raw["domain"]) is not str or raw["domain"] != "polynomial_ring":
        raise PolynomialError("invalid_domain", "domain must be polynomial_ring")
    if type(raw["coefficient_field"]) is not str or raw["coefficient_field"] != "Q":
        raise PolynomialError("unsupported_field", "only the exact rational coefficient field Q is supported")
    variables = raw["variables"]
    if type(variables) is not list or len(variables) > MAX_VARIABLES:
        raise PolynomialError("invalid_input", f"variables must be a JSON array of at most {MAX_VARIABLES} names")
    for name in variables:
        if type(name) is not str or not _NAME.fullmatch(name):
            raise PolynomialError("invalid_variable", "variable names must be ASCII identifiers of 1–32 characters, starting with a letter")
    if len(set(variables)) != len(variables):
        raise PolynomialError("duplicate_variable", "each variable must be declared exactly once; aliases are not accepted")
    operation = raw["operation"]
    if type(operation) is not str or operation not in _OPERATIONS:
        raise PolynomialError("unsupported_operation", "allowed operations are add, multiply, and verify_identity")
    if type(raw["operands"]) is not list or len(raw["operands"]) != 2:
        raise PolynomialError("invalid_input", f"{operation} requires exactly two expression operands")
    budget = _Budget()
    operands = [_expression(item, variables, budget) for item in raw["operands"]]
    # Validate bounded shape and integer sizes before serialization or algebra.
    # AST parsing has produced a detached snapshot, preventing cyclic input.
    encoded = canonical_json(raw)
    if len(encoded) > MAX_INPUT_BYTES:
        raise PolynomialError("resource_limit", f"canonical input exceeds {MAX_INPUT_BYTES} bytes")
    return {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": list(variables),
            "operation": operation, "operands": operands}, budget


def _coefficient(value: Fraction) -> None:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_COEFFICIENT_BITS:
        raise PolynomialError("resource_limit", "intermediate or result coefficient exceeds its bit limit")


def _accumulate(result: Polynomial, monomial: Monomial, value: Fraction, budget: _Budget) -> None:
    budget.spend()
    coefficient = result.get(monomial, Fraction(0)) + value
    _coefficient(coefficient)
    if coefficient:
        result[monomial] = coefficient
        if len(result) > MAX_TERMS:
            raise PolynomialError("resource_limit", "intermediate or result polynomial exceeds its term limit")
    else:
        result.pop(monomial, None)


def _add(left: Polynomial, right: Polynomial, budget: _Budget, sign: int = 1) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in sorted(right.items()):
        _accumulate(result, monomial, sign * coefficient, budget)
    return result


def _multiply(left: Polynomial, right: Polynomial, budget: _Budget) -> Polynomial:
    if not left or not right:
        return {}
    degree_bound = max(map(sum, left)) + max(map(sum, right))
    if degree_bound > MAX_DEGREE:
        raise PolynomialError("resource_limit", "intermediate or result polynomial exceeds its total degree limit")
    # Charge both the product and its accumulation before constructing anything.
    if 2 * len(left) * len(right) + budget.arithmetic_steps > MAX_ARITHMETIC_STEPS:
        raise PolynomialError("resource_limit", "multiplication would exceed cumulative coefficient arithmetic budget")
    result: Polynomial = {}
    for l_monomial, l_coefficient in sorted(left.items()):
        for r_monomial, r_coefficient in sorted(right.items()):
            budget.spend()
            monomial = tuple(a + b for a, b in zip(l_monomial, r_monomial))
            coefficient = l_coefficient * r_coefficient
            _coefficient(coefficient)
            _accumulate(result, monomial, coefficient, budget)
    return result


def _normalize(expression: dict, variables: list[str], budget: _Budget) -> Polynomial:
    kind = expression["type"]
    if kind == "rational":
        coefficient = Fraction(expression["numerator"], expression["denominator"])
        return {(0,) * len(variables): coefficient} if coefficient else {}
    if kind == "variable":
        position = variables.index(expression["name"])
        return {tuple(int(index == position) for index in range(len(variables))): Fraction(1)}
    left, right = [_normalize(item, variables, budget) for item in expression["operands"]]
    return _add(left, right, budget) if kind == "add" else _multiply(left, right, budget)


def _rational(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _term(monomial: Monomial, coefficient: Fraction) -> dict:
    return {"exponents": list(monomial), "coefficient": _rational(coefficient)}


def _encoded(polynomial: Polynomial) -> dict:
    return {"terms": [_term(monomial, coefficient) for monomial, coefficient in sorted(polynomial.items())],
            "total_degree": max(map(sum, polynomial)) if polynomial else None}


def _receipt() -> dict:
    return {
        "schema_version": "1.0", "kind": "exact_polynomial_computation", "status": "error",
        "input": None, "request": None, "ring": None, "result": None, "error": None,
        "backend": {"name": "python.fractions.Fraction + canonical sparse polynomial adapter",
                    "version": platform.python_version(), "adapter_version": VERSION},
        "scope": {
            "evidence_level": "exact_polynomial_normalization", "formal_proof": False,
            "claim": "Equality means identical coefficients in the declared formal commutative polynomial ring over Q.",
            "exclusions": ["quotient rings or imposed relations", "localization or rational functions",
                           "pointwise finite evaluation tests", "analytic or domain-restricted identities",
                           "Lean or independent proof-kernel verification"],
            "variable_semantics": "Declared ordered, distinct, algebraically independent, case-sensitive ASCII names; no aliases.",
            "normal_form": "Nonzero terms in ascending lexicographic exponent-tuple order; reduced rationals with positive denominators; empty terms is zero, whose degree is null.",
            "resource_semantics": "Bounds include intermediates; conservative rejection is possible even if a final result would fit.",
            "limits": {"input_bytes": MAX_INPUT_BYTES, "variables": MAX_VARIABLES, "expression_depth": MAX_EXPR_DEPTH,
                       "total_ast_nodes": MAX_AST_NODES, "total_degree": MAX_DEGREE, "terms": MAX_TERMS,
                       "input_integer_bits": MAX_INPUT_BITS, "coefficient_bits": MAX_COEFFICIENT_BITS,
                       "coefficient_arithmetic_steps": MAX_ARITHMETIC_STEPS}},
        "artifacts": {"input_sha256": None, "request_sha256": None, "result_sha256": None,
                      "backend_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                      "canonical_json_source_sha256": sha256(Path(__file__).with_name("calculator.py").read_bytes()).hexdigest()},
    }


def _execute(request: Any, receipt: dict) -> dict:
    normalized, budget = _parse(request)
    receipt["input"] = json.loads(canonical_json(request))
    receipt["request"] = normalized
    receipt["artifacts"]["input_sha256"] = artifact_hash(receipt["input"])
    receipt["artifacts"]["request_sha256"] = artifact_hash(normalized)
    variables = normalized["variables"]
    receipt["ring"] = {"kind": "commutative_polynomial_ring", "coefficient_field": "Q", "variables": variables}
    left, right = [_normalize(expression, variables, budget) for expression in normalized["operands"]]
    operation = normalized["operation"]
    if operation == "verify_identity":
        difference = _add(left, right, budget, sign=-1)
        witness = None
        if difference:
            monomial = min(difference)
            witness = {**_term(monomial, difference[monomial]),
                       "left_coefficient": _rational(left.get(monomial, Fraction(0))),
                       "right_coefficient": _rational(right.get(monomial, Fraction(0))),
                       "meaning": "The left-minus-right coefficient of this formal monomial is nonzero."}
        result = {"operation": operation, "equal": not difference, "left": _encoded(left), "right": _encoded(right),
                  "difference": _encoded(difference), "mismatch_witness": witness}
    else:
        polynomial = _add(left, right, budget) if operation == "add" else _multiply(left, right, budget)
        result = {"operation": operation, "left": _encoded(left), "right": _encoded(right), "polynomial": _encoded(polynomial)}
    receipt["result"] = result
    receipt["artifacts"]["result_sha256"] = artifact_hash(result)
    receipt["usage"] = {"ast_nodes": budget.nodes, "coefficient_arithmetic_steps": budget.arithmetic_steps}
    receipt["status"] = "success"
    return receipt


def calculate_polynomial(request: PolynomialRequest | dict) -> dict:
    """Compute a bounded, exact JSON request. False identities are successful
    computations with equal=False, not tool errors. Replay the request to check
    an untrusted receipt; hashes provide integrity binding, not authenticity.
    """
    receipt = _receipt()
    try:
        return _execute(request, receipt)
    except PolynomialError as error:
        receipt["error"] = {"code": error.code, "message": str(error)}
    except (ValueError, OverflowError, RecursionError):
        receipt["result"] = None
        receipt["artifacts"]["result_sha256"] = None
        receipt["error"] = {"code": "representation_limit", "message": "request or result exceeds the host JSON representation limits"}
    return receipt


def calculate_polynomial_json(data: str | bytes) -> dict:
    """Strict JSON ingress with duplicate-key and nonfinite-number rejection.

    Raw wire bytes are not receipt-hashed: input_sha256 identifies canonical
    parsed input. A separate caller transport hash can bind original file bytes.
    """
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise PolynomialError("invalid_json", f"duplicate JSON object field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise PolynomialError("invalid_json", "nonfinite JSON numbers are not supported")

    def bounded_integer(value: str) -> int:
        if len(value.lstrip("-")) > 78:
            raise PolynomialError("resource_limit", "JSON integer exceeds the input bit budget")
        return _integer(int(value), "JSON integer")

    receipt = _receipt()
    try:
        if type(data) not in (str, bytes):
            raise PolynomialError("invalid_input", "JSON input must be text or UTF-8 bytes")
        if len(data) > MAX_INPUT_BYTES or (type(data) is str and len(data.encode("utf-8")) > MAX_INPUT_BYTES):
            raise PolynomialError("resource_limit", "raw JSON input exceeds the byte limit")
        if type(data) is bytes:
            data = data.decode("utf-8")
        request = json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant, parse_int=bounded_integer)
        return _execute(request, receipt)
    except PolynomialError as error:
        receipt["error"] = {"code": error.code, "message": str(error)}
    except (ValueError, OverflowError, RecursionError):
        receipt["error"] = {"code": "invalid_json", "message": "invalid JSON or unsupported host representation/nesting"}
    return receipt

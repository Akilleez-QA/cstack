"""Fixed, typed domain dispatch for the trusted local runtime.

This is not a plugin loader. Handlers define accepted structured goals and
candidate values; neither agent metadata nor a backend's success flag is a
mathematical acceptance decision. All evidence here is exact computation, not
formal proof or correspondence with a prose statement.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any, Literal, Protocol

from .calculator import calculate, canonical_json
from .polynomial import (MAX_COEFFICIENT_BITS, MAX_DEGREE, MAX_TERMS,
                         PolynomialError, calculate_polynomial,
                         validate_polynomial_request)

DomainName = Literal["Z", "Q", "polynomial_ring"]
RequiredEvidence = Literal["exact_computation", "formal_proof"]


class DomainError(ValueError):
    """A goal or candidate is outside the declared domain contract."""


def _object(value: Any, fields: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise DomainError(f"{name} requires exactly these fields: {', '.join(sorted(fields))}")
    return value


def _scalar(value: Any, domain: str) -> Fraction:
    if domain == "Z":
        data = _object(value, {"domain", "value"}, "expected integer")
        if data["domain"] != domain or type(data["value"]) is not int:
            raise DomainError("Expected an exact integer result in Z")
        return Fraction(data["value"])
    data = _object(value, {"domain", "numerator", "denominator"}, "expected rational")
    if (data["domain"] != domain or type(data["numerator"]) is not int
            or type(data["denominator"]) is not int or data["denominator"] == 0):
        raise DomainError("Expected an exact rational result in Q with nonzero denominator")
    return Fraction(data["numerator"], data["denominator"])


def _normal_form(value: Any, dimensions: int) -> None:
    """Validate canonical sparse output, not a second expression language."""
    data = _object(value, {"terms", "total_degree"}, "expected polynomial")
    terms = data["terms"]
    if type(terms) is not list or len(terms) > MAX_TERMS:
        raise DomainError("Expected a bounded list of canonical polynomial terms")
    previous: tuple[int, ...] | None = None
    degree: int | None = None
    for term in terms:
        _object(term, {"exponents", "coefficient"}, "polynomial term")
        exponents = term["exponents"]
        if (type(exponents) is not list or len(exponents) != dimensions
                or any(type(x) is not int or x < 0 for x in exponents)
                or sum(exponents) > MAX_DEGREE):
            raise DomainError("Invalid exponent tuple in expected polynomial")
        monomial = tuple(exponents)
        if previous is not None and monomial <= previous:
            raise DomainError("Polynomial terms must be unique and in lexicographic order")
        previous = monomial
        coefficient = _object(term["coefficient"], {"numerator", "denominator"}, "coefficient")
        n, d = coefficient["numerator"], coefficient["denominator"]
        if (type(n) is not int or type(d) is not int or n == 0 or d <= 0
                or max(n.bit_length(), d.bit_length()) > MAX_COEFFICIENT_BITS):
            raise DomainError("Coefficients must be bounded, nonzero reduced rational numbers")
        reduced = Fraction(n, d)
        if reduced.numerator != n or reduced.denominator != d:
            raise DomainError("Expected polynomial coefficients must be in reduced form")
        degree = max(0 if degree is None else degree, sum(exponents))
    if (data["total_degree"] is not None and type(data["total_degree"]) is not int) or data["total_degree"] != degree:
        raise DomainError("Expected total_degree must match the canonical terms (null for zero)")


class DomainHandler(Protocol):
    name: DomainName
    evidence_level: str

    def validate_goal(self, request: Any) -> None: ...
    def validate_expected(self, expected: Any, request: dict) -> None: ...
    def calculate(self, request: dict) -> dict: ...
    def accepts(self, expected: dict, result: dict, request: dict) -> bool: ...


@dataclass(frozen=True)
class ScalarDomain:
    name: Literal["Z", "Q"]
    evidence_level: str = "exact_computation"

    def validate_goal(self, request: Any) -> None:
        # Preserve scalar v1 behavior: unsupported operations get a structured
        # calculator failure rather than an implicit conversion to another domain.
        _object(request, {"domain", "operation", "operands"}, "scalar goal_request")
        if request["domain"] != self.name:
            raise DomainError("goal_request must use the declared problem domain")

    def validate_expected(self, expected: Any, request: dict) -> None:
        _scalar(expected, self.name)

    def calculate(self, request: dict) -> dict:
        return calculate(request)

    def accepts(self, expected: dict, result: dict, request: dict) -> bool:
        return _scalar(expected, self.name) == _scalar(result, self.name)


@dataclass(frozen=True)
class PolynomialDomain:
    name: Literal["polynomial_ring"] = "polynomial_ring"
    evidence_level: str = "exact_polynomial_normalization"

    def validate_goal(self, request: Any) -> None:
        try:
            # Shared backend parser validates the bounded AST without arithmetic.
            validate_polynomial_request(request)
        except PolynomialError as exc:
            raise DomainError(f"Invalid polynomial goal ({exc.code}): {exc}") from exc

    def validate_expected(self, expected: Any, request: dict) -> None:
        identity = request["operation"] == "verify_identity"
        value_field = "equal" if identity else "polynomial"
        _object(expected, {"domain", "coefficient_field", "variables", value_field}, "expected polynomial result")
        for field in ("domain", "coefficient_field", "variables"):
            if canonical_json(expected[field]) != canonical_json(request[field]):
                raise DomainError(f"Expected result {field} does not match the exact goal ring")
        if identity:
            if type(expected["equal"]) is not bool:
                raise DomainError("Expected identity equality must be a JSON boolean")
        else:
            _normal_form(expected["polynomial"], len(request["variables"]))

    def calculate(self, request: dict) -> dict:
        return calculate_polynomial(request)

    def accepts(self, expected: dict, result: dict, request: dict) -> bool:
        if request["operation"] == "verify_identity":
            # A correct prediction of a false identity is counterevidence, not
            # success for the asserted identity goal. Truthiness is insufficient.
            return result.get("equal") is True and expected["equal"] is True
        return canonical_json(expected["polynomial"]) == canonical_json(result["polynomial"])


_DOMAINS = MappingProxyType({"Z": ScalarDomain("Z"), "Q": ScalarDomain("Q"),
                            "polynomial_ring": PolynomialDomain()})


def domain_handler(name: Any) -> DomainHandler:
    if type(name) is not str or name not in _DOMAINS:
        raise DomainError("Supported runtime domains are Z, Q, and polynomial_ring over Q")
    return _DOMAINS[name]

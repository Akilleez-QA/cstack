"""Bounded typed data contract. Shared validation is not mathematical verification."""
from __future__ import annotations
from dataclasses import dataclass, fields
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from ._vendor import polynomial as backend
from ._vendor.calculator import artifact_hash, canonical_json

MAX_WIRE_BYTES = 262144
MAX_WITNESS_INTEGER_BITS = 4096

class WitnessError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

@dataclass(frozen=True)
class Limits:
    max_trials: int = 264
    max_substitution_term_visits: int = 100000
    max_evaluation_nodes: int = 4096
    max_value_bits: int = 4096

HARD_LIMITS = Limits()

def validate_limits(limits: Limits) -> Limits:
    if type(limits) is not Limits:
        raise WitnessError("invalid_limits", "limits must be a Limits value")
    for item in fields(limits):
        value, maximum = getattr(limits, item.name), getattr(HARD_LIMITS, item.name)
        if type(value) is not int or not 0 <= value <= maximum:
            raise WitnessError("invalid_limits", f"{item.name} must be an integer from 0 to {maximum}")
    return limits

def object_fields(value: Any, expected: set[str], label: str) -> dict:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != expected:
        raise WitnessError("invalid_witness", f"{label} needs exactly {', '.join(sorted(expected))}")
    return value

def parse_request(raw: Any) -> tuple[dict, dict, Any]:
    request, budget = backend._parse(raw)
    if request["operation"] != "verify_identity":
        raise WitnessError("unsupported_operation", "this lab accepts verify_identity only")
    # _parse validates depth, shape, integers and byte size before cloning/hashing.
    original = json.loads(canonical_json(raw))
    return original, request, budget

def ring_for(request: dict) -> dict:
    return {"kind": "commutative_polynomial_ring", "coefficient_field": "Q", "variables": list(request["variables"])}

def rational(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}

def checked_fraction(value: Fraction, limits: Limits) -> Fraction:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > limits.max_value_bits:
        raise WitnessError("resource_limit", "exact intermediate/result exceeds value bit budget")
    return value

def read_rational(value: Any, limits: Limits) -> Fraction:
    pair = object_fields(value, {"numerator", "denominator"}, "exact rational value")
    n, d = pair["numerator"], pair["denominator"]
    if type(n) is not int or type(d) is not int or d <= 0:
        raise WitnessError("invalid_witness", "rational values require integer numerator and positive integer denominator")
    if max(n.bit_length(), d.bit_length()) > limits.max_value_bits:
        raise WitnessError("resource_limit", "supplied rational exceeds value bit budget")
    result = Fraction(n, d)
    if (result.numerator, result.denominator) != (n, d):
        raise WitnessError("invalid_witness", "supplied rational must be reduced and canonical")
    return result

def source_hashes(*names: str) -> dict:
    root = Path(__file__).parent
    names = ("_vendor/polynomial.py", "_vendor/calculator.py", "contract.py", *names)
    return {name: sha256((root / name).read_bytes()).hexdigest() for name in names}

def strict_json(data: str | bytes) -> Any:
    if type(data) not in (str, bytes):
        raise WitnessError("invalid_json", "JSON ingress requires text or UTF-8 bytes")
    if len(data) > MAX_WIRE_BYTES:
        raise WitnessError("resource_limit", "wire input exceeds byte cap")
    if type(data) is str and len(data.encode("utf-8")) > MAX_WIRE_BYTES:
        raise WitnessError("resource_limit", "wire input exceeds byte cap")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WitnessError("invalid_json", "duplicate JSON object field")
            result[key] = value
        return result
    def integer(token):
        if len(token.lstrip("-")) > 1234:
            raise WitnessError("resource_limit", "wire integer exceeds bit cap")
        number = int(token)
        if number.bit_length() > MAX_WITNESS_INTEGER_BITS:
            raise WitnessError("resource_limit", "wire integer exceeds bit cap")
        return number
    def nonfinite(_):
        raise WitnessError("invalid_json", "nonfinite JSON tokens are forbidden")
    try:
        return json.loads(data, object_pairs_hook=unique, parse_int=integer, parse_constant=nonfinite)
    except WitnessError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise WitnessError("invalid_json", "invalid JSON or unsupported representation") from exc

def error_result(error: Exception) -> dict:
    code = getattr(error, "code", "representation_limit")
    return {"schema_version": "1.0", "status": "error", "result": None,
            "error": {"code": code, "message": str(error)},
            "conclusion": "No mathematical conclusion: rejection or resource failure is not absence of a counterexample."}

CAUGHT_ERRORS = (WitnessError, backend.PolynomialError, ValueError, OverflowError, RecursionError)

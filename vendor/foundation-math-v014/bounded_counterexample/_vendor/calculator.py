"""Exact arithmetic with explicit domains, bounded inputs, and replayable receipts.

This module never evaluates Python/source expressions. Computation evidence is
not a universal theorem, a CAS identity proof, or a Lean proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
from typing import Any, Literal, Mapping

VERSION = "0.1.0"
MAX_INPUT_BITS = 4096
MAX_RESULT_BITS = 12000  # At most 3613 decimal digits, below CPython's default cap.
MAX_EXPONENT = 10000
Domain = Literal["Z", "Q"]
Operation = Literal["add", "subtract", "multiply", "divide", "power", "negate"]
Scalar = int | Mapping[str, int]


@dataclass(frozen=True)
class CalculationRequest:
    domain: Domain
    operation: Operation
    operands: tuple[Scalar, ...]


class CalculationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> bytes:
    """Canonical within this receipt schema (not RFC 8785 for arbitrary JSON)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def artifact_hash(value: Any) -> str:
    return sha256(canonical_json(value)).hexdigest()


def _integer(value: Any, field: str) -> int:
    if type(value) is not int:  # bool is deliberately not an integer input.
        raise CalculationError("invalid_input", f"{field} must be a JSON integer, not a float, bool, or string")
    if value.bit_length() > MAX_INPUT_BITS:
        raise CalculationError("resource_limit", f"{field} exceeds {MAX_INPUT_BITS} bits")
    return value


def _scalar(value: Any, domain: str) -> Fraction:
    if type(value) is int:
        return Fraction(_integer(value, "operand"))
    if domain == "Q" and isinstance(value, Mapping):
        if set(value) != {"numerator", "denominator"}:
            raise CalculationError("invalid_input", "a rational needs exactly numerator and denominator")
        numerator = _integer(value["numerator"], "numerator")
        denominator = _integer(value["denominator"], "denominator")
        if denominator == 0:
            raise CalculationError("division_by_zero", "a rational denominator cannot be zero")
        return Fraction(numerator, denominator)
    raise CalculationError("invalid_input", "Z accepts integers; Q accepts integers or exact rational objects")


def _encoded(value: Fraction, domain: str) -> dict[str, Any]:
    if domain == "Z":
        return {"domain": "Z", "value": value.numerator}
    return {"domain": "Q", "numerator": value.numerator, "denominator": value.denominator}


def _parse(request: CalculationRequest | Mapping[str, Any]) -> tuple[str, str, list[Fraction], dict[str, Any]]:
    if isinstance(request, CalculationRequest):
        raw = {"domain": request.domain, "operation": request.operation, "operands": list(request.operands)}
    elif isinstance(request, Mapping):
        raw = dict(request)
    else:
        raise CalculationError("invalid_input", "request must be a CalculationRequest or JSON object")
    if set(raw) != {"domain", "operation", "operands"}:
        raise CalculationError("invalid_input", "request needs exactly domain, operation, and operands")
    domain, operation, operands = raw["domain"], raw["operation"], raw["operands"]
    if not isinstance(domain, str) or domain not in ("Z", "Q"):
        raise CalculationError("invalid_domain", "supported domains are Z (integers) and Q (rationals)")
    if not isinstance(operation, str) or operation not in ("add", "subtract", "multiply", "divide", "power", "negate"):
        raise CalculationError("unsupported_operation", "operation is not in the exact arithmetic allowlist")
    arity = 1 if operation == "negate" else 2
    if not isinstance(operands, (list, tuple)) or len(operands) != arity:
        raise CalculationError("invalid_input", f"{operation} requires {arity} operand(s)")
    values = [_scalar(value, domain) for value in operands]
    canonical_operands = [value.numerator if domain == "Z" else
                          {"numerator": value.numerator, "denominator": value.denominator}
                          for value in values]
    return domain, operation, values, {"domain": domain, "operation": operation, "operands": canonical_operands}


def _compute(domain: str, operation: str, values: list[Fraction]) -> Fraction:
    first = values[0]
    second = values[1] if len(values) == 2 else None
    if operation == "add":
        result = first + second
    elif operation == "subtract":
        result = first - second
    elif operation == "multiply":
        result = first * second
    elif operation == "divide":
        if second == 0:
            raise CalculationError("division_by_zero", "division by zero is undefined")
        result = first / second
    elif operation == "negate":
        result = -first
    else:
        assert second is not None
        if second.denominator != 1:
            raise CalculationError("domain_error", "power requires an integer exponent")
        exponent = second.numerator
        if abs(exponent) > MAX_EXPONENT:
            raise CalculationError("resource_limit", f"absolute exponent must be at most {MAX_EXPONENT}")
        if domain == "Z" and exponent < 0:
            raise CalculationError("domain_error", "Z power is defined here only for nonnegative integer exponents")
        if first == 0 and exponent <= 0:
            raise CalculationError("domain_error", "this tool leaves zero to zero or a negative power undefined")
        # An upper bound avoids constructing huge intermediate integers.
        bound = max(abs(first.numerator).bit_length(), first.denominator.bit_length()) * abs(exponent)
        if bound > MAX_RESULT_BITS:
            raise CalculationError("resource_limit", "power result may exceed the bit limit")
        result = first ** exponent
    if domain == "Z" and result.denominator != 1:
        raise CalculationError("domain_error", "the exact result is not an integer; explicitly request domain Q")
    if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > MAX_RESULT_BITS:
        raise CalculationError("resource_limit", "exact result exceeds the bit limit")
    return result


def calculate(request: CalculationRequest | Mapping[str, Any]) -> dict[str, Any]:
    """Return an evidence receipt; invalid requests produce structured errors.

    Successful receipts hash the normalized mathematical request, result, and
    implementation source. Hashes detect changes, not authenticity. Errors that
    cannot be represented as valid bounded input intentionally have request=null.
    """
    receipt: dict[str, Any] = {
        "schema_version": "1.0", "kind": "exact_computation", "status": "error",
        "request": None, "input": None,
        "backend": {"name": "python.fractions.Fraction", "version": platform.python_version(),
                    "adapter_version": VERSION},
        "result": None, "error": None,
        "scope": {"evidence_level": "exact_computation", "formal_proof": False,
                  "claim": "Only this explicit finite arithmetic request in its declared domain.",
                  "integer_division": "exact only; nonintegral results are domain errors",
                  "zero_to_zero": "undefined by this tool's contract",
                  "limits": {"input_bits": MAX_INPUT_BITS, "result_bits": MAX_RESULT_BITS,
                             "absolute_exponent": MAX_EXPONENT}},
        "artifacts": {"input_sha256": None, "request_sha256": None, "result_sha256": None,
                      "backend_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()},
    }
    try:
        domain, operation, values, normalized = _parse(request)
        raw = ({"domain": request.domain, "operation": request.operation, "operands": list(request.operands)}
               if isinstance(request, CalculationRequest) else dict(request))
        receipt["input"] = json.loads(canonical_json(raw))
        receipt["artifacts"]["input_sha256"] = artifact_hash(receipt["input"])
        receipt["request"] = normalized
        receipt["artifacts"]["request_sha256"] = artifact_hash(normalized)
        receipt["result"] = _encoded(_compute(domain, operation, values), domain)
        receipt["artifacts"]["result_sha256"] = artifact_hash(receipt["result"])
        receipt["status"] = "success"
    except CalculationError as error:
        receipt["error"] = {"code": error.code, "message": str(error)}
    except (ValueError, OverflowError) as error:
        # A host may lower Python's integer-to-decimal cap. Do not change that
        # process-global safety setting or leak an exception from the tool API.
        receipt["result"] = None
        receipt["artifacts"]["result_sha256"] = None
        receipt["error"] = {"code": "representation_limit", "message": "request or result exceeds host JSON integer representation limits"}
    return receipt

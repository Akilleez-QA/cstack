"""Fresh concrete-point checker. Does not import or call the witness producer.

It parses the expected original request, validates the certificate binding, and
re-evaluates that request's AST, not the producer's normalized polynomials.
No inference of polynomial identity is made from equal point evaluations.
"""
from __future__ import annotations
from fractions import Fraction
from typing import Any
from .contract import (CAUGHT_ERRORS, Limits, WitnessError, artifact_hash, checked_fraction,
                       error_result, object_fields, parse_request, rational, read_rational,
                       ring_for, source_hashes, validate_limits)
from ._vendor.polynomial import MAX_DEGREE

_FIELDS = {"schema_version", "input_sha256", "request_sha256", "ring", "assignment",
           "left_value", "right_value", "difference_value"}

def _evaluate_ast(expression: dict, assignment: dict, limits: Limits, usage: dict) -> Fraction:
    if usage["evaluation_nodes"] >= limits.max_evaluation_nodes:
        raise WitnessError("resource_limit", "AST evaluation node budget exhausted")
    usage["evaluation_nodes"] += 1
    kind = expression["type"]
    if kind == "rational":
        result = Fraction(expression["numerator"], expression["denominator"])
    elif kind == "variable":
        result = Fraction(assignment[expression["name"]])
    else:
        left = _evaluate_ast(expression["operands"][0], assignment, limits, usage)
        right = _evaluate_ast(expression["operands"][1], assignment, limits, usage)
        result = left + right if kind == "add" else left * right
    return checked_fraction(result, limits)

def verify_witness(raw_request: Any, candidate: Any, limits: Limits = Limits()) -> dict:
    """Accept only a concrete exact mismatch bound to the separately supplied input.

    Shared dependencies: typed parser, canonical hashing, Fraction arithmetic.
    Independent logic: AST point evaluation, not normalization or substitution.
    Resource/representation errors are inconclusive, not rejected mathematics.
    """
    try:
        limits = validate_limits(limits)
        original, request, _ = parse_request(raw_request)
    except CAUGHT_ERRORS as error:
        return error_result(error)
    try:
        witness = object_fields(candidate, _FIELDS, "witness")
        if type(witness["schema_version"]) is not str or witness["schema_version"] != "1.0":
            raise WitnessError("invalid_witness", "unsupported witness schema version")
        for label, expected in (("input_sha256", artifact_hash(original)), ("request_sha256", artifact_hash(request))):
            if type(witness[label]) is not str or witness[label] != expected:
                raise WitnessError("binding_mismatch", f"{label} does not bind this original request")
        ring = object_fields(witness["ring"], {"kind", "coefficient_field", "variables"}, "ring")
        if (type(ring["kind"]) is not str or type(ring["coefficient_field"]) is not str
                or type(ring["variables"]) is not list or any(type(x) is not str for x in ring["variables"])
                or ring != ring_for(request)):
            raise WitnessError("binding_mismatch", "witness ring differs from the declared formal Q-polynomial ring")
        assignment = object_fields(witness["assignment"], set(request["variables"]), "assignment")
        for name, value in assignment.items():
            if type(value) is not int or not 0 <= value <= MAX_DEGREE:
                raise WitnessError("invalid_witness", f"coordinate {name} must be an integer from 0 to {MAX_DEGREE}, not bool/float")
        expected_left = read_rational(witness["left_value"], limits)
        expected_right = read_rational(witness["right_value"], limits)
        expected_difference = read_rational(witness["difference_value"], limits)
        usage = {"evaluation_nodes": 0}
        left, right = [_evaluate_ast(expr, assignment, limits, usage) for expr in request["operands"]]
        difference = checked_fraction(left - right, limits)
        if not difference:
            raise WitnessError("not_a_counterexample", "original left and right values agree at the supplied point")
        if (left, right, difference) != (expected_left, expected_right, expected_difference):
            raise WitnessError("value_mismatch", "supplied values disagree with exact original-AST evaluation")
        return {"schema_version": "1.0", "status": "accepted", "request_sha256": artifact_hash(request),
                "input_sha256": artifact_hash(original), "ring": ring_for(request),
                "assignment": dict(assignment), "left_value": rational(left), "right_value": rational(right),
                "difference_value": rational(difference), "usage": usage,
                "source_sha256": source_hashes("checker.py"),
                "scope": {"claim": "The original requested formal identity is false at this exact integer point.",
                          "not_checked": ["producer trace", "first-choice minimality", "per-variable degree bounds", "trial-count claims"],
                          "formal_proof": False,
                          "independence": "Separate AST evaluator; shares typed parser, canonical hashing, and Fraction arithmetic with the producer."}}
    except CAUGHT_ERRORS as error:
        result = error_result(error)
        if getattr(error, "code", None) not in ("resource_limit", "invalid_limits", None):
            result["status"] = "rejected"
            result["conclusion"] = "This supplied witness was rejected; no conclusion about other candidate witnesses."
        return result

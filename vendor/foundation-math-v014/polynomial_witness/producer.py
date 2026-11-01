"""Sequential coefficient-preserving substitution, never Cartesian-grid search."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from typing import Any
from ._vendor import polynomial as backend
from .contract import (CAUGHT_ERRORS, Limits, WitnessError, artifact_hash, checked_fraction,
                       error_result, parse_request, rational, ring_for, source_hashes, validate_limits)

SCOPE = {
    "domain": "Formal commutative polynomials in the declared algebraically independent variables over Q, with no extra constraints.",
    "evidence": "Exact coefficient normalization and concrete exact integer evaluation; not a proof-assistant certificate.",
    "exclusions": ["quotient rings", "rational functions", "finite fields", "user-restricted loci or constraints", "research-instance conclusions"],
    "resource_semantics": "Phase-specific caps include intermediates in their phase; frozen normalization caps and witness substitution/evaluation caps are separate. Resource failure is inconclusive, never no witness.",
    "trace_semantics": "The construction trace is producer-reported; the separate witness checker certifies only the original request and concrete values, not trace minimality or bounds.",
}

def _substitute(poly: dict, index: int, value: int, limits: Limits, usage: dict) -> dict:
    result = {}
    for powers, coefficient in sorted(poly.items()):
        if usage["substitution_term_visits"] >= limits.max_substitution_term_visits:
            raise WitnessError("resource_limit", "substitution term-visit budget exhausted")
        usage["substitution_term_visits"] += 1
        factor = checked_fraction(Fraction(pow(value, powers[index])), limits)
        term = checked_fraction(coefficient * factor, limits)
        remaining = powers[:index] + (0,) + powers[index + 1:]
        new_value = checked_fraction(result.get(remaining, Fraction(0)) + term, limits)
        if new_value:
            result[remaining] = new_value
        else:
            result.pop(remaining, None)
    return result

def _evaluate(poly: dict, assignment: list[int], limits: Limits) -> Fraction:
    value = Fraction(0)
    for powers, coefficient in sorted(poly.items()):
        term = checked_fraction(coefficient, limits)
        for coordinate, exponent in zip(assignment, powers):
            factor = checked_fraction(Fraction(pow(coordinate, exponent)), limits)
            term = checked_fraction(term * factor, limits)
        value = checked_fraction(value + term, limits)
    return value

def produce(raw: Any, limits: Limits = Limits()) -> dict:
    """Return exact coefficient identity, or one small integer counterexample.

    Successful construction has at most sum(current_degree_j + 1) trials.
    Expanding/normalizing the input may itself exceed separate resource caps.
    """
    try:
        limits = validate_limits(limits)
        original, request, budget = parse_request(raw)
        variables = request["variables"]
        left, right = [backend._normalize(expr, variables, budget) for expr in request["operands"]]
        difference = backend._add(left, right, budget, sign=-1)
        receipt = {"schema_version": "1.0", "status": "success", "request": request,
                   "input_sha256": artifact_hash(original), "request_sha256": artifact_hash(request),
                   "ring": ring_for(request), "limits": asdict(limits), "scope": deepcopy(SCOPE),
                   "source_sha256": source_hashes("producer.py"),
                   "usage": {"normalization_ast_nodes": budget.nodes,
                             "normalization_arithmetic_steps": budget.arithmetic_steps,
                             "substitution_trials": 0, "substitution_term_visits": 0}}
        if not difference:
            receipt["result"] = {"kind": "coefficient_identity", "equal": True,
                                 "normalized_difference": {"terms": [], "total_degree": None},
                                 "conclusion": "Every coefficient of left minus right is exactly zero in the declared formal Q-polynomial ring."}
            return receipt
        current = difference
        assignment, trace = [], []
        initial_degrees = [max(power[j] for power in difference) for j in range(len(variables))]
        for j, name in enumerate(variables):
            degree = max(power[j] for power in current)
            trials = []
            for value in range(degree + 1):
                if receipt["usage"]["substitution_trials"] >= limits.max_trials:
                    raise WitnessError("resource_limit", "substitution trial budget exhausted")
                receipt["usage"]["substitution_trials"] += 1
                substituted = _substitute(current, j, value, limits, receipt["usage"])
                trials.append({"value": value, "remaining_nonzero": bool(substituted)})
                if substituted:
                    assignment.append(value)
                    trace.append({"variable": name, "initial_degree": initial_degrees[j],
                                  "current_degree": degree, "candidate_min": 0, "candidate_max": degree,
                                  "chosen_value": value, "trials": trials})
                    current = substituted
                    break
            else:
                raise WitnessError("internal_invariant", "nonzero polynomial unexpectedly vanished at all degree-plus-one candidates")
        zero = (0,) * len(variables)
        if set(current) != {zero} or not current[zero]:
            raise WitnessError("internal_invariant", "final specialization must be one nonzero constant")
        left_value, right_value = [_evaluate(poly, assignment, limits) for poly in (left, right)]
        mismatch = checked_fraction(left_value - right_value, limits)
        if mismatch != current[zero] or not mismatch:
            raise WitnessError("internal_invariant", "concrete values disagree with final nonzero specialization")
        witness = {"schema_version": "1.0", "input_sha256": receipt["input_sha256"],
                   "request_sha256": receipt["request_sha256"], "ring": ring_for(request),
                   "assignment": dict(zip(variables, assignment)),
                   "left_value": rational(left_value), "right_value": rational(right_value),
                   "difference_value": rational(mismatch)}
        receipt["result"] = {"kind": "nonzero_evaluation", "equal": False, "witness": witness,
                             "construction_trace": trace,
                             "current_degree_trial_bound": sum(item["current_degree"] + 1 for item in trace),
                             "initial_degree_trial_bound": sum(degree + 1 for degree in initial_degrees),
                             "difference_term_count": len(difference)}
        return receipt
    except CAUGHT_ERRORS as error:
        return error_result(error)

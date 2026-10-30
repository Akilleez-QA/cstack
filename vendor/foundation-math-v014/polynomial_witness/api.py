"""Checked construction API and strict JSON entrypoints."""
from __future__ import annotations
from typing import Any
from .contract import CAUGHT_ERRORS, Limits, WitnessError, error_result, object_fields, strict_json
from .producer import produce
from .checker import verify_witness

def construct(request: Any, limits: Limits = Limits()) -> dict:
    result = produce(request, limits)
    if result["status"] != "success":
        return result
    if result["result"]["kind"] == "coefficient_identity":
        result["verification"] = {"status": "not_applicable", "scope": "Exact coefficient-normalization identity, not a point witness; the concrete-point checker makes no identity claim."}
    else:
        verification = verify_witness(request, result["result"]["witness"], limits)
        if verification["status"] != "accepted":
            return {"schema_version": "1.0", "status": "error", "result": None,
                    "error": {"code": "witness_check_failed", "message": "Constructed point did not receive independent exact-AST acceptance."},
                    "verification": verification, "conclusion": "Inconclusive failure, not absence of a counterexample."}
        result["verification"] = verification
    return result

def construct_json(data: str | bytes, limits: Limits = Limits()) -> dict:
    try:
        return construct(strict_json(data), limits)
    except CAUGHT_ERRORS as error:
        return error_result(error)

def verify_json(data: str | bytes, limits: Limits = Limits()) -> dict:
    try:
        envelope = object_fields(strict_json(data), {"request", "witness"}, "check envelope")
        return verify_witness(envelope["request"], envelope["witness"], limits)
    except CAUGHT_ERRORS as error:
        return error_result(error)

"""Static JSON Schema 2020-12 tool contracts for the fixed v0.1 inventory.

Input schemas describe the closed argument shapes; the Foundation's own runtime checks remain
authoritative (this bridge is stdlib-only and does not run a schema validator). Output schemas
are tight enough that a host can validate structuredContent, but schema success alone does not
establish that a number is correct or approved.
"""
from __future__ import annotations

from copy import deepcopy

DRAFT = "https://json-schema.org/draft/2020-12/schema"
VERSION = "0.1.0"
PRESSURE_UNITS = ["kPa(a)", "kPa(g)", "psia", "psig", "bar(a)", "bar(g)"]
TEMPERATURE_UNITS = ["degC", "degF", "K", "degR"]
NUMBER = {"type": "number", "description": "Finite decimal literal; no exponent, NaN or infinity."}
TEXT = {"type": "string", "maxLength": 1024}
SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
DATE = {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}
FLUID = {"type": "string", "minLength": 1, "maxLength": 64,
         "description": "R717/R717/ammonia, CO2/R744, R134a, R290/propane, R22, R404A, R410A, R507A, R448A."}
SIDE = {"enum": ["bubble", "dew"], "description": "Required for zeotropic blends; optional for pure fluids."}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else list(required), "additionalProperties": False}


def quantity(units):
    return obj({"value": NUMBER, "unit": {"enum": list(units)}})


ATMOSPHERE = {"oneOf": [
    obj({"basis": {"const": "standard"}}),
    obj({"basis": {"const": "elevation"}, "elevation": quantity(["m", "ft"])}),
    obj({"basis": {"const": "measured"}, "pressure": quantity(["kPa(a)", "psia", "bar(a)"])})],
    "description": "Site atmosphere for gauge values. Omitted means the standard atmosphere, recorded as an assumption."}
ATMOSPHERE_OUT = obj({"basis": {"enum": ["standard", "elevation", "measured"]}, "assumed": {"type": "boolean"},
                      "elevation_m": NUMBER, "pressure": quantity(["kPa(a)"])}, ["basis", "assumed", "pressure"])

_BASIS = {"oneOf": [
    obj({"kind": {"const": "cited"}, "source": TEXT, "version": TEXT, "clause": {"type": ["string", "null"]},
         "url": TEXT, "quoted": TEXT, "retrievedOn": DATE}, ["kind", "source", "version", "clause"]),
    obj({"kind": {"const": "generated"}, "model": TEXT, "generator": TEXT, "generatedOn": DATE}),
    obj({"kind": {"const": "policy"}, "setBy": TEXT, "scope": {"enum": ["plant", "client", "expression"]},
         "reason": TEXT}),
    obj({"kind": {"const": "practice"}, "note": TEXT})]}
EVIDENCE = {**obj({"basis": _BASIS, "status": {"enum": ["CHECK", "APPROVED", "DISPUTED"]}, "approvedBy": TEXT,
                   "approvedOn": DATE, "dispute": TEXT, "freshForDays": {"type": "integer", "minimum": 1}},
                  ["basis", "status"]),
            "allOf": [
                {"if": {"properties": {"status": {"const": "APPROVED"}}},
                 "then": {"required": ["approvedBy", "approvedOn"]},
                 "else": {"not": {"anyOf": [{"required": ["approvedBy"]}, {"required": ["approvedOn"]}]}}},
                {"if": {"properties": {"status": {"const": "DISPUTED"}}},
                 "then": {"required": ["dispute"]}, "else": {"not": {"required": ["dispute"]}}}]}
EVIDENCE_ENTRY = obj({"applies_to": TEXT, "evidence": EVIDENCE})
SOURCE = obj({"projection": TEXT, "schema": TEXT, "sha256": SHA, "generator_sha256": SHA},
             ["projection", "schema", "sha256"])
BOUNDARY = obj({"observation_only": {"const": True}, "engineering_determination": {"const": False},
                "safety_determination": {"const": False}, "compliance_determination": {"const": False},
                "diagnosis": {"const": False}, "control_action": {"const": False}})
FLUID_OUT = obj({"id": TEXT, "name": TEXT, "kind": {"enum": ["pure", "zeotropic-blend"]}, "source": TEXT,
                 "edition": TEXT, "projection_schema": {"const": "refrigerant-saturation/1"},
                 "projection_sha256": SHA, "generator_sha256": SHA,
                 "range_c": {"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 2},
                 "interpolation_error_k": NUMBER})
VIEWS_P = {"type": "array", "items": quantity(PRESSURE_UNITS), "minItems": 6, "maxItems": 6}
VIEWS_T = {"type": "array", "items": quantity(TEMPERATURE_UNITS), "minItems": 4, "maxItems": 4}
STRINGS = {"type": "array", "items": TEXT}
DELTA = obj({"value_k": NUMBER, "value_degf_difference": NUMBER, "definition": TEXT,
             "relation_to_dew": {"enum": ["above", "below", "within_lookup_resolution"]},
             "relation_to_bubble": {"enum": ["above", "below", "within_lookup_resolution"]}},
            ["value_k", "value_degf_difference", "definition"])
LIMIT = obj({"id": TEXT, "value_kind": {"const": "published_limit"}, "issuer": {"enum": ["OSHA", "NIOSH", "ACGIH"]},
             "kind": TEXT, "label": TEXT, "concentration": quantity(["ppm"]),
             "mass_concentration": {"oneOf": [{"type": "null"}, quantity(["mg/m3"])]},
             "averaging": {"enum": ["TWA", "STEL", "IDLH"]},
             "legal_status": {"enum": ["enforceable", "recommended", "guideline"]}, "display": TEXT,
             "evidence": {**EVIDENCE, "properties": {**EVIDENCE["properties"], "basis": _BASIS["oneOf"][0]}}})
POLICY = obj({"value_kind": {"const": "policy_set_point"}, "label": TEXT, "concentration": quantity(["ppm"]),
              "legal_status": {"const": "not_a_legal_limit"}, "display": TEXT,
              "evidence": {**EVIDENCE, "properties": {**EVIDENCE["properties"], "basis": _BASIS["oneOf"][2]}}})
KIND_OUT = {"oneOf": [{"type": "null"}, obj({"id": TEXT, "label": TEXT, "lineage": STRINGS})]}
SERVICE_OUT = {"oneOf": [{"type": "null"}, obj({
    "code": TEXT, "name": TEXT, "family": TEXT, "phase": TEXT, "pressure": TEXT,
    "band": {"type": ["string", "null"]}, "jacketed": {"type": ["boolean", "null"]}, "origin": TEXT,
    "possible_equivalent": {"type": ["string", "null"]}},
    ["code", "name", "family", "phase", "pressure", "band", "jacketed", "origin"])]}


def _result_schemas():
    return {
        "saturation_pressure": obj({"fluid": FLUID_OUT, "side": TEXT, "temperature": quantity(["degC"]),
                                    "pressure": quantity(["kPa(a)"]), "pressure_views": VIEWS_P,
                                    "atmosphere": ATMOSPHERE_OUT}),
        "saturation_temperature": obj({"fluid": FLUID_OUT, "side": TEXT, "pressure_absolute": quantity(["kPa(a)"]),
                                       "temperature": quantity(["degC"]), "temperature_views": VIEWS_T,
                                       "atmosphere": ATMOSPHERE_OUT, "atmosphere_used": {"type": "boolean"}}),
        "convert_pressure": obj({"input": quantity(PRESSURE_UNITS), "absolute": quantity(["kPa(a)"]),
                                 "output": quantity(PRESSURE_UNITS), "atmosphere": ATMOSPHERE_OUT,
                                 "atmosphere_used": {"type": "boolean"}}),
        "convert_temperature": obj({"input": quantity(TEMPERATURE_UNITS), "canonical": quantity(["degC"]),
                                    "output": quantity(TEMPERATURE_UNITS)}),
        "check_reading_against_saturation": obj({
            "fluid": FLUID_OUT,
            "reading": obj({"pressure": quantity(PRESSURE_UNITS), "temperature": quantity(TEMPERATURE_UNITS)}),
            "pressure_absolute": quantity(["kPa(a)"]), "temperature": quantity(["degC"]),
            "saturation_at_reading_pressure": obj({"dew_temperature": quantity(["degC"]),
                                                   "bubble_temperature": quantity(["degC"])}),
            "superheat_style_delta": {**DELTA, "required": DELTA["required"] + ["relation_to_dew"]},
            "subcooling_style_delta": {**DELTA, "required": DELTA["required"] + ["relation_to_bubble"]},
            "lookup_resolution_k": NUMBER, "atmosphere": ATMOSPHERE_OUT, "atmosphere_used": {"type": "boolean"},
            "observation": TEXT, "not_determined": STRINGS}),
        "exposure_limits": obj({
            "substance": obj({"name": TEXT, "formula": TEXT, "cas": TEXT}),
            "published_limits": {"type": "array", "items": LIMIT},
            "policy_set_points": {"type": "array", "items": POLICY, "maxItems": 16},
            "gaps": {"type": "array", "items": obj({"id": TEXT, "items": STRINGS, "status": {"const": "gap"},
                                                    "reason": TEXT})},
            "scope": TEXT, "separation": TEXT}),
        "resolve_equipment_kind": {"oneOf": [
            obj({"vocabulary": {"const": "equipment_kind"}, "term": TEXT, "normalised": TEXT,
                 "resolved": {"type": "boolean"}, "kind": KIND_OUT, "alias_is_canonical_id": {"type": "boolean"},
                 "legacy_sources": STRINGS, "evidence": EVIDENCE, "note": {"type": ["string", "null"]}},
                ["vocabulary", "term", "normalised", "resolved", "kind", "evidence", "note"]),
            obj({"vocabulary": {"const": "line_service"}, "term": TEXT, "normalised": TEXT,
                 "resolved": {"type": "boolean"}, "service": SERVICE_OUT, "evidence": EVIDENCE, "note": TEXT,
                 "open_decisions": {"type": "array", "items": obj({"id": TEXT, "topic": TEXT,
                                    "status": {"const": "DISPUTED"}, "chosen": {"type": "null"}})}})]},
    }


ASSESSMENTS = {
    "saturation_pressure": ["saturation_pressure_observed"],
    "saturation_temperature": ["saturation_temperature_observed"],
    "convert_pressure": ["pressure_converted"],
    "convert_temperature": ["temperature_converted"],
    "check_reading_against_saturation": ["reading_compared_to_saturation"],
    "exposure_limits": ["exposure_limits_listed"],
    "resolve_equipment_kind": ["equipment_kind_resolved", "equipment_kind_unresolved",
                               "line_service_resolved", "line_service_unresolved"],
}


def _inputs():
    t = quantity(TEMPERATURE_UNITS)
    p = quantity(PRESSURE_UNITS)
    policy = obj({"label": {"type": "string", "minLength": 1, "maxLength": 120}, "concentration": quantity(["ppm"]),
                  "set_by": {"type": "string", "minLength": 1, "maxLength": 120,
                             "description": "Role or organisation that owns the setting; never a person's name."},
                  "scope": {"enum": ["plant", "client", "expression"]},
                  "reason": {"type": "string", "minLength": 1, "maxLength": 1024}})
    return {
        "saturation_pressure": obj({"fluid": FLUID, "temperature": t, "side": SIDE, "atmosphere": ATMOSPHERE},
                                   ["fluid", "temperature"]),
        "saturation_temperature": obj({"fluid": FLUID, "pressure": p, "side": SIDE, "atmosphere": ATMOSPHERE},
                                      ["fluid", "pressure"]),
        "convert_pressure": obj({"pressure": p, "to_unit": {"enum": PRESSURE_UNITS}, "atmosphere": ATMOSPHERE},
                                ["pressure", "to_unit"]),
        "convert_temperature": obj({"temperature": t, "to_unit": {"enum": TEMPERATURE_UNITS}}),
        "check_reading_against_saturation": obj({"fluid": FLUID, "pressure": p, "temperature": t,
                                                 "atmosphere": ATMOSPHERE}, ["fluid", "pressure", "temperature"]),
        "exposure_limits": obj({"substance": {"type": "string", "maxLength": 32,
                                              "description": "ammonia (R717, R717) only in v0.1"},
                                "issuer": {"enum": ["OSHA", "NIOSH", "ACGIH"]},
                                "policy_set_points": {"type": "array", "items": policy, "maxItems": 16}},
                               ["substance"]),
        "resolve_equipment_kind": obj({"term": {"type": "string", "minLength": 1, "maxLength": 128},
                                       "vocabulary": {"enum": ["equipment_kind", "line_service"]}}, ["term"]),
    }


DESCRIPTIONS = {
    "saturation_pressure": "Saturation pressure at a temperature from the CoolProp 8.0.0-generated table "
                           "(refrigerant-saturation/1). Blends need side bubble or dew. No extrapolation.",
    "saturation_temperature": "Saturation temperature at a pressure (absolute or gauge with a stated atmosphere) "
                              "from the generated table. Blends need side bubble or dew. No extrapolation.",
    "convert_pressure": "Convert a pressure between kPa(a), kPa(g), psia, psig, bar(a) and bar(g). Gauge values use "
                        "the stated site atmosphere (standard when omitted, recorded as an assumption).",
    "convert_temperature": "Convert an absolute temperature between degC, degF, K and degR.",
    "check_reading_against_saturation": "Compare one pressure/temperature reading with saturation at that pressure: "
                                        "superheat-style and subcooling-style deltas as an observation, never a "
                                        "diagnosis or a normal/abnormal call.",
    "exposure_limits": "Cited ammonia exposure limits (OSHA, NIOSH, ACGIH) as reference data, with caller-supplied "
                       "policy set points kept as a separate kind that is never a legal limit. ERPG is an explicit gap.",
    "resolve_equipment_kind": "Resolve a legacy equipment-kind term (or a line-service code) to the canonical "
                              "plant-taxonomy/1 entry. Unknown terms are reported unresolved, never guessed.",
}
SUFFIX = (" Every result carries its Evidence (CHECK unless approved). Observation only: not an engineering, "
          "safety or compliance determination; monitoring-only, no control. Not MCP; no formal proof or goal acceptance.")


def _output(name, result_schema):
    common = {"schema": {"const": "foundation-refrigeration-receipt/1"}, "foundation_version": {"const": VERSION},
              "tool": {"const": name}, "input_sha256": SHA, "boundary": BOUNDARY}
    success = obj({**common, "status": {"const": "success"}, "result": result_schema, "error": {"type": "null"},
                   "evidence": {"type": "array", "items": EVIDENCE_ENTRY, "minItems": 1, "maxItems": 64},
                   "data_sources": {"type": "array", "items": SOURCE, "maxItems": 8},
                   "limitations": {**STRINGS, "minItems": 3, "maxItems": 16}})
    failure = obj({**common, "status": {"const": "error"}, "result": {"type": "null"},
                   "error": obj({"code": {"type": "string", "pattern": "^[a-z_]{1,64}$"}, "message": TEXT}),
                   "evidence": {"type": "array", "maxItems": 0}, "data_sources": {"type": "array", "maxItems": 0},
                   "limitations": {**STRINGS, "minItems": 3, "maxItems": 16}})
    return {"$schema": DRAFT, **obj({
        "tool": {"const": name}, "assessment": {"enum": ASSESSMENTS[name] + ["tool_error"]},
        "formal_proof": {"const": False}, "runtime_goal_acceptance": {"const": False},
        "receipt": {"oneOf": [success, failure]}})}


def tool_definitions():
    inputs, results = _inputs(), _result_schemas()
    return [{"name": name, "description": DESCRIPTIONS[name] + SUFFIX,
             "inputSchema": {"$schema": DRAFT, **deepcopy(inputs[name])},
             "outputSchema": _output(name, deepcopy(results[name]))}
            for name in ("saturation_pressure", "saturation_temperature", "convert_pressure", "convert_temperature",
                         "check_reading_against_saturation", "exposure_limits", "resolve_equipment_kind")]

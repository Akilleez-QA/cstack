"""The fixed v0.1 tool inventory. Each tool returns (assessment, receipt); every receipt carries Evidence.

Results are observations for a person: never an engineering, safety or compliance
determination, never a diagnosis, and never a control action (monitoring-only).
Invalid input raises ToolInputError; the bridge reports it as a tool error, not a result.
"""
from __future__ import annotations

import hashlib
import json

from . import __version__, decisions, plant_model, safety_limits, thermo, units
from .evidence import EvidenceError
from .units import UnitError

RECEIPT_SCHEMA = "foundation-refrigeration-receipt/1"
TOOL_NAMES = ("saturation_pressure", "saturation_temperature", "convert_pressure", "convert_temperature",
              "check_reading_against_saturation", "exposure_limits", "resolve_equipment_kind")
BOUNDARY = {
    "observation_only": True,
    "engineering_determination": False,
    "safety_determination": False,
    "compliance_determination": False,
    "diagnosis": False,
    "control_action": False,
}
COMMON_LIMITATIONS = (
    "A tool observation is not an engineering, safety or compliance determination.",
    "Monitoring-only: nothing here operates, controls or writes to a plant.",
    "CHECK means recorded but not approved by a qualified person; silence is not approval.",
)
PLACES = 4


class ToolInputError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     allow_nan=False).encode("ascii")).hexdigest()


def _fields(args, required, optional=()):
    if type(args) is not dict:
        raise ToolInputError("invalid_arguments", "Arguments must be an object")
    keys = set(args)
    missing, extra = set(required) - keys, keys - set(required) - set(optional)
    if missing or extra:
        raise ToolInputError("invalid_arguments", "Missing fields: %s; unexpected fields: %s"
                             % (", ".join(sorted(missing)) or "none", ", ".join(sorted(extra)) or "none"))
    return args


def _ev(applies_to, evidence):
    return {"applies_to": applies_to, "evidence": evidence.to_dict() if hasattr(evidence, "to_dict") else evidence}


def _unit_evidence(keys):
    return [_ev("units: " + key, units.EVIDENCE[key]) for key in keys]


def _atmosphere(args):
    kpa, description, keys = units.read_atmosphere(args.get("atmosphere"))
    return kpa, {**description, "pressure": {"value": units.rounded(kpa, PLACES), "unit": "kPa(a)"}}, list(keys)


def _table_source(table):
    return {"projection": "refrigerant-saturation." + table.id.lower() + ".json", "schema": thermo.SCHEMA,
            "sha256": table.projection_sha256, "generator_sha256": table.generator_sha256}


def _side_label(table, side):
    return side if table.is_blend else "saturated (pure fluid: bubble equals dew)"


def saturation_pressure(args):
    _fields(args, ("fluid", "temperature"), ("side", "atmosphere"))
    table = thermo.resolve_fluid(args["fluid"])
    value, unit = units.quantity(args["temperature"], units.TEMPERATURE_UNITS, "temperature")
    t_c = units.to_celsius(value, unit)
    atm, atm_record, atm_keys = _atmosphere(args)
    kpa, side = thermo.saturation_pressure_kpa(table, t_c, args.get("side"))
    result = {"fluid": table.describe(), "side": _side_label(table, side),
              "temperature": {"value": units.rounded(t_c, 6), "unit": "degC"},
              "pressure": {"value": units.rounded(kpa, PLACES), "unit": "kPa(a)"},
              "pressure_views": units.pressure_views(kpa, atm, PLACES), "atmosphere": atm_record}
    evidence = [_ev("saturation table " + table.id, table.evidence)] + _unit_evidence(
        ["temperature_scales", "psi_definition"] + atm_keys)
    return "saturation_pressure_observed", result, evidence, [_table_source(table)], [
        "Interpolated between generated rows (ln P against 1/T); error bound covers the lookup only.",
        "Gauge views use the stated atmosphere; a different site atmosphere changes them."]


def saturation_temperature(args):
    _fields(args, ("fluid", "pressure"), ("side", "atmosphere"))
    table = thermo.resolve_fluid(args["fluid"])
    value, unit = units.quantity(args["pressure"], units.PRESSURE_UNITS, "pressure")
    atm, atm_record, atm_keys = _atmosphere(args)
    kpa = units.absolute_kpa(value, unit, atm)
    t_c, side = thermo.saturation_temperature_c(table, kpa, args.get("side"))
    result = {"fluid": table.describe(), "side": _side_label(table, side),
              "pressure_absolute": {"value": units.rounded(kpa, PLACES), "unit": "kPa(a)"},
              "temperature": {"value": units.rounded(t_c, PLACES), "unit": "degC"},
              "temperature_views": units.temperature_views(t_c, PLACES), "atmosphere": atm_record,
              "atmosphere_used": unit in units.GAUGE_UNITS}
    evidence = [_ev("saturation table " + table.id, table.evidence)] + _unit_evidence(
        ["temperature_scales", "psi_definition"] + atm_keys)
    return "saturation_temperature_observed", result, evidence, [_table_source(table)], [
        "Interpolated between generated rows (ln P against 1/T); error bound covers the lookup only."]


def convert_pressure(args):
    _fields(args, ("pressure", "to_unit"), ("atmosphere",))
    value, unit = units.quantity(args["pressure"], units.PRESSURE_UNITS, "pressure")
    if args["to_unit"] not in units.PRESSURE_UNITS:
        raise ToolInputError("invalid_unit", "to_unit must be one of " + ", ".join(units.PRESSURE_UNITS))
    atm, atm_record, atm_keys = _atmosphere(args)
    kpa = units.absolute_kpa(value, unit, atm)
    used = unit in units.GAUGE_UNITS or args["to_unit"] in units.GAUGE_UNITS
    result = {"input": {"value": value, "unit": unit},
              "absolute": {"value": units.rounded(kpa, PLACES), "unit": "kPa(a)"},
              "output": {"value": units.rounded(units.from_absolute_kpa(kpa, args["to_unit"], atm), PLACES),
                         "unit": args["to_unit"]},
              "atmosphere": atm_record, "atmosphere_used": used}
    return "pressure_converted", result, _unit_evidence(["psi_definition"] + (atm_keys if used else [])), [], [
        "A gauge value is relative to the stated atmosphere, not always the standard one."]


def convert_temperature(args):
    _fields(args, ("temperature", "to_unit"))
    value, unit = units.quantity(args["temperature"], units.TEMPERATURE_UNITS, "temperature")
    if args["to_unit"] not in units.TEMPERATURE_UNITS:
        raise ToolInputError("invalid_unit", "to_unit must be one of " + ", ".join(units.TEMPERATURE_UNITS))
    t_c = units.to_celsius(value, unit)
    result = {"input": {"value": value, "unit": unit},
              "canonical": {"value": units.rounded(t_c, 6), "unit": "degC"},
              "output": {"value": units.rounded(units.from_celsius(t_c, args["to_unit"]), PLACES),
                         "unit": args["to_unit"]}}
    return "temperature_converted", result, _unit_evidence(["temperature_scales"]), [], [
        "Absolute temperatures only; a temperature difference is not converted by this tool."]


def _relation(delta_k, resolution_k):
    if abs(delta_k) <= resolution_k:
        return "within_lookup_resolution"
    return "above" if delta_k > 0 else "below"


def _delta(k):
    return {"value_k": units.rounded(k, PLACES), "value_degf_difference": units.rounded(k * 1.8, PLACES)}


def check_reading_against_saturation(args):
    _fields(args, ("fluid", "pressure", "temperature"), ("atmosphere",))
    table = thermo.resolve_fluid(args["fluid"])
    p_value, p_unit = units.quantity(args["pressure"], units.PRESSURE_UNITS, "pressure")
    t_value, t_unit = units.quantity(args["temperature"], units.TEMPERATURE_UNITS, "temperature")
    atm, atm_record, atm_keys = _atmosphere(args)
    kpa = units.absolute_kpa(p_value, p_unit, atm)
    t_c = units.to_celsius(t_value, t_unit)
    dew_c, _ = thermo.saturation_temperature_c(table, kpa, "dew")
    bubble_c, _ = thermo.saturation_temperature_c(table, kpa, "bubble")
    resolution = table.error_k + 0.0001
    above_dew, below_bubble = t_c - dew_c, bubble_c - t_c
    result = {
        "fluid": table.describe(),
        "reading": {"pressure": {"value": p_value, "unit": p_unit}, "temperature": {"value": t_value, "unit": t_unit}},
        "pressure_absolute": {"value": units.rounded(kpa, PLACES), "unit": "kPa(a)"},
        "temperature": {"value": units.rounded(t_c, PLACES), "unit": "degC"},
        "saturation_at_reading_pressure": {
            "dew_temperature": {"value": units.rounded(dew_c, PLACES), "unit": "degC"},
            "bubble_temperature": {"value": units.rounded(bubble_c, PLACES), "unit": "degC"}},
        "superheat_style_delta": {**_delta(above_dew), "definition": "reading temperature minus dew-point "
                                  "saturation temperature at the reading pressure",
                                  "relation_to_dew": _relation(above_dew, resolution)},
        "subcooling_style_delta": {**_delta(below_bubble), "definition": "bubble-point saturation temperature "
                                   "at the reading pressure minus reading temperature",
                                   "relation_to_bubble": _relation(-below_bubble, resolution)},
        "lookup_resolution_k": units.rounded(resolution, 6),
        "atmosphere": atm_record, "atmosphere_used": p_unit in units.GAUGE_UNITS,
        "observation": "Arithmetic comparison of one supplied reading with generated saturation data. "
                       "It does not say whether the reading is normal, what causes it, or what to do.",
        "not_determined": ["normal operating range", "fault or cause", "sensor accuracy or placement",
                           "whether the pressure and temperature were taken at the same point"],
    }
    evidence = [_ev("saturation table " + table.id, table.evidence)] + _unit_evidence(
        ["temperature_scales", "psi_definition"] + atm_keys)
    return "reading_compared_to_saturation", result, evidence, [_table_source(table)], [
        "Superheat- and subcooling-style deltas are observations, never a diagnosis.",
        "No normal range is applied: the only source range found (the reference app normal-ranges.ts) is UNVERIFIED."]


_SUBSTANCES = {"ammonia": "ammonia", "r717": "ammonia", "r717": "ammonia", "r-717": "ammonia"}


def exposure_limits(args):
    _fields(args, ("substance",), ("issuer", "policy_set_points"))
    if type(args["substance"]) is not str or args["substance"].strip().lower() not in _SUBSTANCES:
        raise ToolInputError("unknown_substance", "Only ammonia (R717, R717) limits are recorded in v0.1")
    issuer = args.get("issuer")
    if issuer is not None and issuer not in safety_limits.ISSUERS:
        raise ToolInputError("invalid_issuer", "issuer must be one of " + ", ".join(safety_limits.ISSUERS))
    supplied = args.get("policy_set_points", [])
    if type(supplied) is not list or len(supplied) > 16:
        raise ToolInputError("invalid_policy", "policy_set_points must be a list of at most 16 entries")
    try:
        policies = [safety_limits.policy_set_point(item) for item in supplied]
    except safety_limits.SafetyLimitError as error:
        raise ToolInputError("invalid_policy", str(error)) from None
    limits = [x for x in safety_limits.AMMONIA_LIMITS if issuer is None or x.issuer == issuer]
    result = {"substance": safety_limits.SUBSTANCE,
              "published_limits": [x.to_dict() for x in limits],
              "policy_set_points": [x.to_dict() for x in policies],
              "gaps": [dict(g) for g in safety_limits.GAPS],
              "scope": safety_limits.SCOPE,
              "separation": "Published limits and policy set points are different kinds. A policy set point is "
                            "never a legal or published limit."}
    evidence = ([_ev("published limit " + x.id, x.evidence) for x in limits]
                + [_ev("policy set point " + x.label, x.evidence) for x in policies])
    return "exposure_limits_listed", result, evidence, [{"projection": "exposure-limits.json",
            "schema": safety_limits.SCHEMA, "sha256": safety_limits.PROJECTION_SHA256}], [
        "Reference data for a person, not an exposure assessment, respirator selection or go/no-go call.",
        "ERPG-1/2/3 are an explicit gap: no primary AIHA source was read."]


def resolve_equipment_kind(args):
    _fields(args, ("term",), ("vocabulary",))
    vocabulary = args.get("vocabulary", "equipment_kind")
    if vocabulary not in plant_model.VOCABULARIES:
        raise ToolInputError("invalid_vocabulary", "vocabulary must be equipment_kind or line_service")
    try:
        if vocabulary == "equipment_kind":
            result = plant_model.resolve_equipment_kind(args["term"])
        else:
            result = plant_model.resolve_line_service(args["term"])
            result["open_decisions"] = [
                {"id": d, "topic": decisions.open_decision(d)["topic"], "status": "DISPUTED", "chosen": None}
                for d in plant_model.LINE_SERVICE_OPEN_DECISIONS]
    except plant_model.PlantModelError as error:
        raise ToolInputError("invalid_term", str(error)) from None
    assessment = vocabulary + ("_resolved" if result["resolved"] else "_unresolved")
    evidence = [_ev(vocabulary + " " + result["normalised"], result["evidence"])]
    if vocabulary == "line_service":
        evidence += [_ev("open decision " + d, decisions.open_decision(d)["evidence"])
                     for d in plant_model.LINE_SERVICE_OPEN_DECISIONS]
    sources = [{"projection": "plant-taxonomy.json", "schema": plant_model.SCHEMA, "sha256": plant_model.PROJECTION_SHA256}]
    if vocabulary == "line_service":
        sources.append({"projection": "open-decisions.json", "schema": decisions.SCHEMA,
                        "sha256": decisions.PROJECTION_SHA256})
    return assessment, result, evidence, sources, [
        "Taxonomy and aliases are CHECK; no SME has reviewed the kind boundaries.",
        "An unresolved term is reported as unresolved, never guessed."]


_TOOLS = {"saturation_pressure": saturation_pressure, "saturation_temperature": saturation_temperature,
          "convert_pressure": convert_pressure, "convert_temperature": convert_temperature,
          "check_reading_against_saturation": check_reading_against_saturation,
          "exposure_limits": exposure_limits, "resolve_equipment_kind": resolve_equipment_kind}


def run(name, arguments):
    """Run one tool. Returns (is_error, assessment, receipt). Never raises for bad input."""
    if name not in _TOOLS:
        raise KeyError(name)
    base = {"schema": RECEIPT_SCHEMA, "foundation_version": __version__, "tool": name,
            "input_sha256": _digest(arguments), "boundary": dict(BOUNDARY)}
    try:
        assessment, result, evidence, sources, limitations = _TOOLS[name](arguments)
    except (ToolInputError, thermo.ThermoError) as error:
        return True, "tool_error", {**base, "status": "error", "result": None,
                                    "error": {"code": error.code, "message": str(error)}, "evidence": [],
                                    "data_sources": [], "limitations": list(COMMON_LIMITATIONS)}
    except (UnitError, EvidenceError) as error:
        return True, "tool_error", {**base, "status": "error", "result": None,
                                    "error": {"code": "invalid_quantity", "message": str(error)}, "evidence": [],
                                    "data_sources": [], "limitations": list(COMMON_LIMITATIONS)}
    return False, assessment, {**base, "status": "success", "result": result, "error": None, "evidence": evidence,
                               "data_sources": sources, "limitations": list(COMMON_LIMITATIONS) + limitations}

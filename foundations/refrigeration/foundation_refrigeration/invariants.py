import hashlib
import json
from pathlib import Path

from . import thermo, units


VERSION = "refrigeration-invariants/0"
RELATION_TOLERANCE = 1e-6
GOLDEN_ALLOWANCE_K = 0.001
CHECKS = ("pressure_relation", "temperature_relation", "saturation_temperature")


def _source_hashes():
    foundation = Path(units.__file__).resolve().parent
    paths = [*foundation.glob("*.py"), *foundation.joinpath("data").glob("*.json")]
    return {p.relative_to(foundation).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


SOURCE_HASHES = _source_hashes()
LIBRARY_VERSION = VERSION + ":" + hashlib.sha256(
    json.dumps(SOURCE_HASHES, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("claim requires exactly: " + ", ".join(names))


def _temperature(value):
    number, unit = units.quantity(value, units.TEMPERATURE_UNITS, "temperature")
    return units.to_celsius(number, unit)


def _pressures(values, atmosphere):
    readings = [units.quantity(value, units.PRESSURE_UNITS, "pressure") for value in values]
    gauge = any(unit in units.GAUGE_UNITS for _, unit in readings)
    if gauge and atmosphere is None:
        raise ValueError("gauge pressure requires an explicit atmosphere basis")
    if atmosphere is None:
        kpa, basis, evidence = 0.0, None, ()
    else:
        kpa, basis, evidence = units.read_atmosphere(atmosphere)
    return ([units.absolute_kpa(number, unit, kpa) for number, unit in readings],
            basis, [units.EVIDENCE[key].to_dict() for key in evidence])


def _relation(left, right, relation):
    if type(relation) is not str or relation not in ("eq", "lt", "gt"):
        raise ValueError("relation must be eq, lt or gt")
    delta = left - right
    passed = {"eq": abs(delta) <= RELATION_TOLERANCE,
              "lt": delta < -RELATION_TOLERANCE,
              "gt": delta > RELATION_TOLERANCE}[relation]
    if not passed:
        raise ValueError("canonical quantities violate " + relation)
    return {"left": left, "right": right, "relation": relation,
            "tolerance": RELATION_TOLERANCE}


def _judge(check, claim):
    if check == "pressure_relation":
        _fields(claim, ("left", "right", "relation", "atmosphere"))
        values, basis, evidence = _pressures([claim["left"], claim["right"]], claim["atmosphere"])
        return _relation(*values, claim["relation"]) | {
            "unit": "kPa(a)", "atmosphere": basis, "evidence": evidence}
    if check == "temperature_relation":
        _fields(claim, ("left", "right", "relation"))
        return _relation(_temperature(claim["left"]), _temperature(claim["right"]),
                         claim["relation"]) | {"unit": "degC"}
    _fields(claim, ("fluid", "side", "pressure", "temperature", "atmosphere"))
    table = thermo.resolve_fluid(claim["fluid"])
    pressures, basis, evidence = _pressures([claim["pressure"]], claim["atmosphere"])
    expected, side = thermo.saturation_temperature_c(table, pressures[0], claim["side"])
    actual = _temperature(claim["temperature"])
    tolerance = table.error_k + GOLDEN_ALLOWANCE_K
    if abs(actual - expected) > tolerance:
        raise ValueError("temperature differs from Foundation saturation reference")
    return {"actual": actual, "expected": expected, "unit": "degC", "tolerance": tolerance,
            "side": side, "source": table.describe(), "atmosphere": basis,
            "evidence": [table.evidence.to_dict(), *evidence]}


def evaluate(check, claim):
    result = {"check": check if type(check) is str else "invalid",
              "passed": False, "reason": "", "library_version": LIBRARY_VERSION}
    try:
        if type(check) is not str or check not in CHECKS:
            raise ValueError("unknown refrigeration invariant")
        result["measurements"] = _judge(check, claim)
        result.update(passed=True, reason="claim satisfies Foundation-backed invariant")
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        result["reason"] = str(error)
    return result

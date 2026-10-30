"""Units and the gauge basis. Ported from the bench foundation-refr src/core/units.ts draft.

Numeric semantics (declared by this Foundation, not inherited from Foundation Math): finite
decimal numbers with an explicit unit, as {"value": <number>, "unit": "<unit>"}. A bare number
is never a quantity. NaN, infinity and booleans are rejected. Arithmetic is IEEE double; results
are rounded decimals, not exact values.

Canonical storage: pressure kPa absolute, temperature degC. psia/psig/bar(g)/degF and the rest
are conversions, never storage. Gauge readings are relative to the site atmosphere, which is the
standard atmosphere only when nothing better is known.
"""
from __future__ import annotations

import math

from .evidence import CitedBasis, Evidence, PracticeBasis

STANDARD_ATMOSPHERE_KPA = 101.325
# Pound-force per square inch: 0.45359237 kg * 9.80665 m/s2 / (0.0254 m)^2, in kPa.
KPA_PER_PSI = 0.45359237 * 9.80665 / 0.0254 ** 2 / 1000.0
KPA_PER_BAR = 100.0
KELVIN_OFFSET = 273.15
METRES_PER_FOOT = 0.3048
MAX_MAGNITUDE = 1e9

PRESSURE_UNITS = ("kPa(a)", "kPa(g)", "psia", "psig", "bar(a)", "bar(g)")
TEMPERATURE_UNITS = ("degC", "degF", "K", "degR")
LENGTH_UNITS = ("m", "ft")
GAUGE_UNITS = ("kPa(g)", "psig", "bar(g)")
# ISA troposphere barometric formula is applied only inside this elevation band (metres).
ELEVATION_RANGE_M = (-500.0, 6000.0)
MEASURED_ATMOSPHERE_RANGE_KPA = (40.0, 110.0)

# No source text below was re-read for this release, so nothing is quoted and every entry is CHECK.
EVIDENCE = {
    "standard_atmosphere": Evidence(CitedBasis(
        "CGPM 10th meeting, Resolution 4 (standard atmosphere = 101 325 Pa)", "1954",
        "Resolution 4"), "CHECK"),
    "psi_definition": Evidence(CitedBasis(
        "NIST Special Publication 811, Guide for the Use of the International System of Units "
        "(pound-force per square inch from the avoirdupois pound, standard gravity and the inch)",
        "2008 edition", None), "CHECK"),
    "temperature_scales": Evidence(CitedBasis(
        "NIST Special Publication 811, Guide for the Use of the International System of Units "
        "(degC, degF, K and degR relations)", "2008 edition", None), "CHECK"),
    "isa_barometric": Evidence(CitedBasis(
        "ISO 2533 Standard Atmosphere, troposphere barometric formula as ported from the "
        "foundation-refr units.ts draft: 101.325 kPa * (1 - 2.25577e-5 * h)^5.25588",
        "1975", None), "CHECK"),
    "site_measured_atmosphere": Evidence(PracticeBasis(
        "Caller-supplied site barometric pressure; this Foundation does not verify the reading."), "CHECK"),
}


class UnitError(ValueError):
    """A quantity that cannot be read without guessing. Refused, never coerced."""


def finite_number(value, name="value"):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_MAGNITUDE:
        raise UnitError(name + " must be a finite decimal number")
    return float(value)


def quantity(value, units, name):
    """Read {"value": number, "unit": one of units}; any other shape is refused."""
    if type(value) is not dict or set(value) != {"value", "unit"}:
        raise UnitError(name + " must be {value, unit}; a bare number is not a quantity")
    if value["unit"] not in units:
        raise UnitError(name + " unit must be one of " + ", ".join(units))
    return finite_number(value["value"], name), value["unit"]


def f_to_c(f):
    return (f - 32.0) / 1.8


def c_to_f(c):
    return c * 1.8 + 32.0


def to_celsius(value, unit):
    if unit == "degC":
        c = value
    elif unit == "degF":
        c = f_to_c(value)
    elif unit == "K":
        c = value - KELVIN_OFFSET
    elif unit == "degR":
        c = (value / 1.8) - KELVIN_OFFSET
    else:
        raise UnitError("Unknown temperature unit")
    if c + KELVIN_OFFSET <= 0:
        raise UnitError("Temperature is at or below absolute zero")
    return c


def from_celsius(c, unit):
    if unit == "degC":
        return c
    if unit == "degF":
        return c_to_f(c)
    if unit == "K":
        return c + KELVIN_OFFSET
    if unit == "degR":
        return (c + KELVIN_OFFSET) * 1.8
    raise UnitError("Unknown temperature unit")


def atmosphere_at_elevation_kpa(elevation_m):
    """Barometric pressure at elevation (m), ISA troposphere model, kPa."""
    lo, hi = ELEVATION_RANGE_M
    if not lo <= elevation_m <= hi:
        raise UnitError("Elevation outside the supported %g..%g m band" % (lo, hi))
    return STANDARD_ATMOSPHERE_KPA * (1.0 - 2.25577e-5 * elevation_m) ** 5.25588


def read_atmosphere(value):
    """Resolve the site atmosphere. Returns (kPa, description dict, evidence keys).

    None means the standard atmosphere, recorded as an explicit assumption in the result.
    """
    if value is None:
        return STANDARD_ATMOSPHERE_KPA, {"basis": "standard", "assumed": True}, ("standard_atmosphere",)
    if type(value) is not dict or "basis" not in value:
        raise UnitError("atmosphere must name its basis")
    basis = value["basis"]
    if basis == "standard":
        if set(value) != {"basis"}:
            raise UnitError("Standard atmosphere takes no other fields")
        return STANDARD_ATMOSPHERE_KPA, {"basis": "standard", "assumed": False}, ("standard_atmosphere",)
    if basis == "elevation":
        if set(value) != {"basis", "elevation"}:
            raise UnitError("Elevation atmosphere needs exactly an elevation quantity")
        number, unit = quantity(value["elevation"], LENGTH_UNITS, "elevation")
        metres = number * METRES_PER_FOOT if unit == "ft" else number
        kpa = atmosphere_at_elevation_kpa(metres)
        return kpa, {"basis": "elevation", "assumed": False, "elevation_m": round(metres, 3)}, (
            "standard_atmosphere", "isa_barometric")
    if basis == "measured":
        if set(value) != {"basis", "pressure"}:
            raise UnitError("Measured atmosphere needs exactly a pressure quantity")
        number, unit = quantity(value["pressure"], ("kPa(a)", "psia", "bar(a)"), "atmosphere pressure")
        kpa = absolute_kpa(number, unit, STANDARD_ATMOSPHERE_KPA)
        lo, hi = MEASURED_ATMOSPHERE_RANGE_KPA
        if not lo <= kpa <= hi:
            raise UnitError("Measured atmosphere outside the plausible %g..%g kPa band" % (lo, hi))
        return kpa, {"basis": "measured", "assumed": False}, ("site_measured_atmosphere",)
    raise UnitError("atmosphere basis must be standard, elevation or measured")


def absolute_kpa(value, unit, atmosphere_kpa):
    """Any supported pressure unit to kPa absolute; gauge units add the supplied atmosphere."""
    if unit == "kPa(a)":
        kpa = value
    elif unit == "kPa(g)":
        kpa = value + atmosphere_kpa
    elif unit == "psia":
        kpa = value * KPA_PER_PSI
    elif unit == "psig":
        kpa = value * KPA_PER_PSI + atmosphere_kpa
    elif unit == "bar(a)":
        kpa = value * KPA_PER_BAR
    elif unit == "bar(g)":
        kpa = value * KPA_PER_BAR + atmosphere_kpa
    else:
        raise UnitError("Unknown pressure unit")
    if kpa <= 0:
        raise UnitError("Absolute pressure must be positive")
    return kpa


def from_absolute_kpa(kpa, unit, atmosphere_kpa):
    if unit == "kPa(a)":
        return kpa
    if unit == "kPa(g)":
        return kpa - atmosphere_kpa
    if unit == "psia":
        return kpa / KPA_PER_PSI
    if unit == "psig":
        return (kpa - atmosphere_kpa) / KPA_PER_PSI
    if unit == "bar(a)":
        return kpa / KPA_PER_BAR
    if unit == "bar(g)":
        return (kpa - atmosphere_kpa) / KPA_PER_BAR
    raise UnitError("Unknown pressure unit")


def rounded(value, places):
    """Round for presentation. -0.0 is normalised to 0.0 so receipts are stable."""
    out = round(value, places)
    return 0.0 if out == 0 else out


def pressure_views(kpa, atmosphere_kpa, places=4):
    return [{"value": rounded(from_absolute_kpa(kpa, unit, atmosphere_kpa), places), "unit": unit}
            for unit in PRESSURE_UNITS]


def temperature_views(c, places=4):
    return [{"value": rounded(from_celsius(c, unit), places), "unit": unit} for unit in TEMPERATURE_UNITS]

"""Saturation lookup over the generated refrigerant-saturation/1 projections (rule T-1, ADR-167).

Tables come ONLY from the the reference app generator (CoolProp 8.0.0), ported by
tools/project_saturation.py; no row is typed by hand. Lookup is linear in ln(P) against 1/T
between adjacent rows (1/T in kelvin; the generator used 1/T in rankine, which is the same
straight line scaled), and refuses to extrapolate outside the table.

Zeotropic blends have a bubble (saturated liquid, Q=0) and a dew (saturated vapour, Q=1) pressure
at each temperature, and the lookup refuses to guess which one is meant.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .evidence import evidence_from_dict
from .projection import load
from .units import KELVIN_OFFSET

SCHEMA = "refrigerant-saturation/1"
FLUID_FILES = ("r717", "co2", "r134a", "r290", "r22", "r404a", "r410a", "r507a", "r448a")
SIDES = ("bubble", "dew")
# Accepted spellings, normalised by lower-casing and removing spaces, hyphens and underscores.
FLUID_ALIASES = {
    "r717": "R717", "r717": "R717", "ammonia": "R717",
    "co2": "CO2", "r744": "CO2", "carbondioxide": "CO2",
    "r134a": "R134a", "hfc134a": "R134a",
    "r290": "R290", "propane": "R290",
    "r22": "R22", "hcfc22": "R22",
    "r404a": "R404A", "r410a": "R410A", "r507a": "R507A", "r448a": "R448A",
}


class ThermoError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SaturationTable:
    id: str
    name: str
    kind: str
    source: str
    edition: str
    min_c: float
    max_c: float
    error_k: float
    temperatures_c: tuple[float, ...]
    bubble_kpa: tuple[float, ...]
    dew_kpa: tuple[float, ...]
    evidence: object
    projection_sha256: str
    generator_sha256: str

    @property
    def is_blend(self):
        return self.kind != "pure"

    def describe(self):
        return {"id": self.id, "name": self.name, "kind": self.kind, "source": self.source,
                "edition": self.edition, "projection_schema": SCHEMA,
                "projection_sha256": self.projection_sha256, "generator_sha256": self.generator_sha256,
                "range_c": [self.min_c, self.max_c], "interpolation_error_k": self.error_k}


def _table(fid):
    data, sha = load("refrigerant-saturation." + fid + ".json", SCHEMA)
    rows = data["rows"]
    if data["units"] != ["degC", "kPa(a)", "kPa(a)", "J/kg", "J/kg"] or len(rows) < 2:
        raise ThermoError("projection_invalid", "Unexpected saturation projection layout")
    for row in rows:
        if len(row) != 5 or any(type(x) not in (int, float) or not math.isfinite(x) for x in row):
            raise ThermoError("projection_invalid", "Nonnumeric saturation row")
    temps = tuple(float(r[0]) for r in rows)
    bubble = tuple(float(r[1]) for r in rows)
    dew = tuple(float(r[2]) for r in rows)
    if not (all(a < b for a, b in zip(temps, temps[1:])) and all(a < b for a, b in zip(bubble, bubble[1:]))
            and all(a < b for a, b in zip(dew, dew[1:])) and min(bubble + dew) > 0):
        raise ThermoError("projection_invalid", "Saturation projection is not monotonic")
    return SaturationTable(data["id"], data["name"], data["kind"], data["source"], data["edition"],
                           temps[0], temps[-1], float(data["interpolation"]["error_k"]), temps, bubble, dew,
                           evidence_from_dict(data["evidence"]), sha, data["generator"]["sha256"])


TABLES = {t.id: t for t in (_table(fid) for fid in FLUID_FILES)}


def resolve_fluid(name):
    if type(name) is not str or len(name) > 64:
        raise ThermoError("unknown_fluid", "Fluid must be a short name")
    key = "".join(ch for ch in name.lower() if ch not in " -_()")
    if key not in FLUID_ALIASES:
        raise ThermoError("unknown_fluid", "No generated table for this fluid; supported: " + ", ".join(TABLES))
    return TABLES[FLUID_ALIASES[key]]


def _side(table, side):
    if side is None:
        if table.is_blend:
            raise ThermoError("side_required", table.id + " is a zeotropic blend: give side bubble or dew")
        return "bubble"
    if side not in SIDES:
        raise ThermoError("invalid_side", "side must be bubble or dew")
    return side


def _x(t_c):
    return 1.0 / (t_c + KELVIN_OFFSET)


def saturation_pressure_kpa(table, t_c, side=None):
    """Saturation pressure, kPa(a), at t_c degC. No extrapolation."""
    side = _side(table, side)
    if not table.min_c <= t_c <= table.max_c:
        raise ThermoError("outside_table_range", "Temperature outside the generated table range %.4f..%.4f degC"
                          % (table.min_c, table.max_c))
    ps = table.bubble_kpa if side == "bubble" else table.dew_kpa
    ts = table.temperatures_c
    for i in range(len(ts) - 1):
        if t_c == ts[i]:
            return ps[i], side  # A generated row is returned exactly, never re-derived.
        if ts[i] <= t_c <= ts[i + 1]:
            if t_c == ts[i + 1]:
                return ps[i + 1], side
            x0, x1, x = _x(ts[i]), _x(ts[i + 1]), _x(t_c)
            y0, y1 = math.log(ps[i]), math.log(ps[i + 1])
            return math.exp(y0 + (y1 - y0) * (x - x0) / (x1 - x0)), side
    raise ThermoError("outside_table_range", "Temperature outside the generated table range")


def saturation_temperature_c(table, p_kpa, side=None):
    """Saturation temperature, degC, at p_kpa kPa(a). No extrapolation."""
    side = _side(table, side)
    ps = table.bubble_kpa if side == "bubble" else table.dew_kpa
    if not ps[0] <= p_kpa <= ps[-1]:
        raise ThermoError("outside_table_range", "Pressure outside the generated %s range %.4f..%.4f kPa(a)"
                          % (side, ps[0], ps[-1]))
    ts = table.temperatures_c
    y = math.log(p_kpa)
    for i in range(len(ps) - 1):
        if p_kpa == ps[i]:
            return ts[i], side
        if ps[i] <= p_kpa <= ps[i + 1]:
            if p_kpa == ps[i + 1]:
                return ts[i + 1], side
            y0, y1 = math.log(ps[i]), math.log(ps[i + 1])
            x0, x1 = _x(ts[i]), _x(ts[i + 1])
            return 1.0 / (x0 + (x1 - x0) * (y - y0) / (y1 - y0)) - KELVIN_OFFSET, side
    raise ThermoError("outside_table_range", "Pressure outside the generated table range")

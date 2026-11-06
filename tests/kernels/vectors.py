"""Differential vectors for the in-workcell Foundation kernels. The pinned Python Foundation is the reference."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLUIDS = ("NH3", "R717", "ammonia", "r-744", "CO2", "R134a", "propane", "R22", "R404A", "R410A", "R507A", "R448A", "water", 7)
TEMPERATURE_UNITS = ("degC", "degF", "K", "degR", "furlong")
PRESSURE_UNITS = ("kPa(a)", "kPa(g)", "psia", "psig", "bar(a)", "bar(g)", "atm")


def _text(value):
    return json.dumps(value, separators=(",", ":"))


def refrigeration_vectors():
    out = []
    add = lambda tool, args: out.append((tool, _text(args)))
    temps = [-75.5, -60, -40.25, -33.34, -20, -10, -10.0, 0, 0.5, 7.125, 25, 30.03125, 50, 99.99, 150, 400]
    for fluid in FLUIDS:
        for t in temps:
            for side in (None, "bubble", "dew", "wet"):
                args = {"fluid": fluid, "temperature": {"value": t, "unit": "degC"}}
                if side:
                    args["side"] = side
                add("saturation_pressure", args)
        for p in (0.5, 40, 101.325, 290.5, 1000, 2500.75, 9000):
            for unit in ("kPa(a)", "psia", "bar(a)", "kPa(g)", "psig", "bar(g)"):
                add("saturation_temperature", {"fluid": fluid, "pressure": {"value": p / (100 if "bar" in unit else 1), "unit": unit},
                                               "side": "dew"})
                add("check_reading_against_saturation", {"fluid": fluid, "pressure": {"value": p, "unit": unit},
                                                         "temperature": {"value": -5.5, "unit": "degC"}})
    for atmosphere in (None, {"basis": "standard"}, {"basis": "standard", "x": 1}, {"basis": "elevation", "elevation": {"value": 1500, "unit": "m"}},
                       {"basis": "elevation", "elevation": {"value": 5000, "unit": "ft"}}, {"basis": "elevation", "elevation": {"value": 9000, "unit": "m"}},
                       {"basis": "measured", "pressure": {"value": 95.5, "unit": "kPa(a)"}}, {"basis": "measured", "pressure": {"value": 14.2, "unit": "psia"}},
                       {"basis": "measured", "pressure": {"value": 20, "unit": "kPa(a)"}}, {"basis": "other"}, "standard"):
        extra = {} if atmosphere is None else {"atmosphere": atmosphere}
        add("saturation_pressure", {"fluid": "NH3", "temperature": {"value": -10, "unit": "degC"}, **extra})
        add("saturation_temperature", {"fluid": "CO2", "pressure": {"value": 1000, "unit": "kPa(g)"}, **extra})
        for to_unit in PRESSURE_UNITS:
            for unit in PRESSURE_UNITS:
                add("convert_pressure", {"pressure": {"value": 123.456, "unit": unit}, "to_unit": to_unit, **extra})
    for unit in TEMPERATURE_UNITS:
        for to_unit in TEMPERATURE_UNITS:
            for value in (-500, -273.15, -40, 0, 0.03125, 32, 100, 459.67, 1e9, 2e9):
                add("convert_temperature", {"temperature": {"value": value, "unit": unit}, "to_unit": to_unit})
    for bad in ({}, {"fluid": "NH3"}, {"fluid": "NH3", "temperature": 5}, {"fluid": "NH3", "temperature": {"value": True, "unit": "degC"}},
                {"fluid": "NH3", "temperature": {"value": "5", "unit": "degC"}}, {"fluid": "NH3", "temperature": {"value": 1, "unit": 2}},
                {"fluid": "NH3", "temperature": {"value": 1, "unit": "degC"}, "extra": 1}, [], "text", None):
        add("saturation_pressure", bad)
    for substance in ("ammonia", " NH3 ", "R-717", "r717", "propane", 5):
        for issuer in (None, "OSHA", "NIOSH", "ACGIH", "AIHA"):
            args = {"substance": substance}
            if issuer:
                args["issuer"] = issuer
            add("exposure_limits", args)
    point = {"label": "site alarm", "concentration": {"value": 10, "unit": "ppm"}, "set_by": "plant manager", "scope": "plant", "reason": "site rule"}
    for policy in (point, {**point, "concentration": {"value": 12.5, "unit": "ppm"}}, {**point, "label": "OSHA PEL"}, {**point, "scope": "world"},
                   {**point, "concentration": {"value": -1, "unit": "ppm"}}, {"label": "x"}, {**point, "set_by": " "}, {**point, "reason": ""}, {**point, "label": "  "}):
        add("exposure_limits", {"substance": "ammonia", "policy_set_points": [policy]})
    add("exposure_limits", {"substance": "ammonia", "policy_set_points": "x"})
    taxonomy = json.loads((ROOT / "foundations/refrigeration/foundation_refrigeration/data/plant-taxonomy.json").read_text())["data"]
    terms = list(taxonomy["aliases"]) + [k["id"] for k in taxonomy["kinds"]] + ["Screw Compressor", " RACK ", "no such thing", "", "   ", "a_b c", 5, "x" * 200]
    for term in terms:
        add("resolve_equipment_kind", {"term": term})
    for code in [row["code"] for row in taxonomy["line_services"]] + ["hsd ", "?", "nope", "", "x" * 40, 3]:
        add("resolve_equipment_kind", {"term": code, "vocabulary": "line_service"})
    add("resolve_equipment_kind", {"term": "valve", "vocabulary": "other"})
    return out


def template_vectors():
    out = [("echo_observation", _text({"observation": text})) for text in ("a", "fixture reading 7", "x" * 256, "x" * 257, "", 5, None)]
    return out + [("echo_observation", _text({})), ("echo_observation", _text({"observation": "a", "b": 1}))]


def reference(foundation, vectors):
    if foundation == "foundation_refrigeration":
        from foundation_refrigeration.tools import run
    else:
        from foundation_template.tools import run
    rows = []
    for tool, text in vectors:
        failed, assessment, receipt = run(tool, json.loads(text))
        rows.append({"tool": tool, "arguments": text, "failed": failed, "assessment": assessment, "receipt": receipt})
    return rows

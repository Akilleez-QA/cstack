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
    out = [("echo_observation", _text({"observation": text})) for text in ("a", "fixture reading 7", "x" * 256, "x" * 257, "", 5, None, "C:\\users", "\t")]
    out += [("echo_observation", text) for text in ("[]", '["observation"]', "5", "null", '"observation"', '{"observation":"\\u0041"}', '{"__proto__":"x"}', '{"observation":"a","observation":"b"}')]
    return out + [("echo_observation", _text({})), ("echo_observation", _text({"observation": "a", "b": 1}))]


QUANTITY = '{"fluid":"NH3","temperature":{"value":%s,"unit":"degC"}}'


def lexical_vectors():
    """Exact text, because JSON.parse hides what these do: signs, exponents, long numbers, duplicate keys, escapes, odd names."""
    texts = [QUANTITY % v for v in ("-0", "-0.0", "1E1", "1e400", "-1e400", "1.0e-5", "0.00001", "1e22", "1.5e16", "10000000000000000", "1e308", "9" * 450, "-" + "9" * 450, "9" * 5000)]
    texts += ['{"fluid":"NH3","fluid":"CO2","temperature":{"value":1,"unit":"degC"}}', '{"fluid":"NH3","temperature":{"value":1,"value":2,"unit":"degC"}}',
              '{"__proto__":1,"fluid":"NH3","temperature":{"value":1,"unit":"degC"}}', '{"fluid":"NH3","temperature":{"value":1,"unit":"degC"},"constructor":1}',
              '{"fluid":"N\\u0048","temperature":{"value":1,"unit":"degC"}}', '{"fluid":"NH\\u0033","temperature":{"value":1,"unit":"degC"}}', '{"fluid":"C:\\\\users","temperature":{"value":1,"unit":"degC"}}',
              ' { "fluid" : "NH3" , "temperature" : { "unit" : "degC" , "value" : 1 } } ', '{"a":[' + "9" * 450 + '],"fluid":"NH3"}', '[1,2,' + "3" * 500 + "]",
              "NaN", "Infinity", QUANTITY % "NaN", '{"":1}', '{"a\\"b":1,"a\\\\b":2,"a/b":3,"a\\/c":4}', '{"\\b":1,"\\t":"\\n"}', '{"\\u007f":1}', '"text"', "5", "null", "true", "[]", "{}", "[[[[1]]]]", "not json"]
    return [("saturation_pressure", text) for text in texts]


def units_vectors():
    out = []
    add = lambda tool, args: out.append((tool, _text(args)))
    readings = {"degC": [-40.5, -10, 0, 25.25], "degF": [-40, 0, 20, 95, 212.5], "K": [233.15, 273.15, 300.5], "degR": [419.67, 491.67, 540.25]}
    atmospheres = [None, {"basis": "standard"}, {"basis": "elevation", "elevation": {"value": 1500, "unit": "m"}}, {"basis": "elevation", "elevation": {"value": 5280.5, "unit": "ft"}},
                   {"basis": "measured", "pressure": {"value": 95.5, "unit": "kPa(a)"}}]
    for fluid in ("NH3", "CO2", "R134a", "R404A", "R448A"):
        for side in ("bubble", "dew"):
            for unit, values in readings.items():
                for value in values:
                    add("saturation_pressure", {"fluid": fluid, "temperature": {"value": value, "unit": unit}, "side": side})
            for unit, value in (("kPa(a)", 290.5), ("kPa(g)", 188.25), ("psia", 42.125), ("psig", 27.5), ("bar(a)", 2.905), ("bar(g)", 1.88)):
                for atmosphere in atmospheres:
                    add("saturation_temperature", {"fluid": fluid, "pressure": {"value": value, "unit": unit}, "side": side, **({"atmosphere": atmosphere} if atmosphere else {})})
        for unit, value in (("kPa(a)", 290.5), ("psig", 27.5), ("bar(g)", 1.88)):
            for t_unit, values in readings.items():
                for t in values:
                    for atmosphere in atmospheres[:3]:
                        add("check_reading_against_saturation", {"fluid": fluid, "pressure": {"value": value, "unit": unit}, "temperature": {"value": t, "unit": t_unit}, **({"atmosphere": atmosphere} if atmosphere else {})})
    return out


def boundary_vectors(count, seed=7):
    """Temperatures within two units in the last place of a rounding boundary: the worst case for libm differences."""
    import math
    import random
    from foundation_refrigeration import thermo
    rng, out = random.Random(seed), []
    for _ in range(count):
        table = thermo.TABLES[rng.choice(("NH3", "CO2", "R134a", "R290", "R22"))]
        start = rng.uniform(table.min_c + .1, min(table.max_c - .1, 60))
        pressure, _unused = thermo.saturation_pressure_kpa(table, start, "bubble")
        target = (math.floor(pressure * 1e4) + .5) / 1e4
        low, high = max(start - 1, table.min_c), min(start + 1, table.max_c)
        for _step in range(80):
            middle = (low + high) / 2
            if thermo.saturation_pressure_kpa(table, middle, "bubble")[0] < target:
                low = middle
            else:
                high = middle
        for step in (-2, -1, 0, 1, 2):
            value = low
            for _nudge in range(abs(step)):
                value = math.nextafter(value, math.inf if step > 0 else -math.inf)
            out.append(("saturation_pressure", json.dumps({"fluid": table.id, "temperature": {"value": value, "unit": "degC"}})))
    return out


def reference(foundation, vectors):
    if foundation == "foundation_refrigeration":
        from foundation_refrigeration.tools import run
    else:
        from foundation_template.tools import run
    rows = []
    for tool, text in vectors:
        try:
            failed, assessment, receipt = run(tool, json.loads(text))
        except Exception as error:
            rows.append({"tool": tool, "arguments": text, "python_exception": type(error).__name__})
            continue
        rows.append({"tool": tool, "arguments": text, "failed": failed, "assessment": assessment, "receipt": receipt})
    return rows

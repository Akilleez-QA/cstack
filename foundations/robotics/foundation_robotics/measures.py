import math
import re

MEASURE_LIMIT = 10 ** 12
COORD_LIMIT = 10 ** 9
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}\Z")
VERDICTS = ("thresholds_met", "thresholds_not_met", "not_scored")
STANDARD_GRAVITY = 9806.65
UP_AXES = {"y": 1, "z": 2}


class ToolInputError(ValueError):
    pass


def exact(value, name, required, optional=()):
    if type(value) is not dict:
        raise ToolInputError(f"{name} must be an object")
    keys = set(value)
    missing, extra = set(required) - keys, keys - set(required) - set(optional)
    if missing or extra:
        raise ToolInputError(f"{name} fields: missing {sorted(missing)}, unexpected {sorted(extra)}")
    return value


def integer(value, name, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ToolInputError(f"{name} must be an integer from {lo} to {hi}")
    return value


def measure(value, name):
    return integer(value, name, -MEASURE_LIMIT, MEASURE_LIMIT)


def positive(value, name, hi=MEASURE_LIMIT):
    return integer(value, name, 1, hi)


def choice(value, name, options):
    if type(value) is not str or value not in options:
        raise ToolInputError(f"{name} must be one of {sorted(options)}")
    return value


def identifier(value, name):
    if type(value) is not str or ID.fullmatch(value) is None:
        raise ToolInputError(f"{name} must match {ID.pattern}")
    return value


def array(value, name, min_items, max_items):
    if type(value) is not list or not min_items <= len(value) <= max_items:
        raise ToolInputError(f"{name} must be a list of {min_items} to {max_items} items")
    return value


def vec3(value, name, limit=COORD_LIMIT):
    return [integer(v, f"{name}[{i}]", -limit, limit) for i, v in enumerate(array(value, name, 3, 3))]


def unique_ids(items, name):
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        raise ToolInputError(f"{name} must not repeat an id")
    return ids


def gravity(arguments):
    if "gravity_mm_s2" in arguments:
        return float(positive(arguments["gravity_mm_s2"], "gravity_mm_s2", 10 ** 6)), "caller"
    return STANDARD_GRAVITY, "standard"


def up_axis(arguments):
    return UP_AXES[choice(arguments.get("up_axis", "y"), "up_axis", UP_AXES)]


def ground(point, up):
    return tuple(point[i] for i in range(3) if i != up)


def rnd(x):
    if x is None:
        return None
    if not math.isfinite(x):
        raise ToolInputError("a derived value is not finite; check the inputs")
    value = min(MEASURE_LIMIT, int(math.floor(abs(x) + 0.5)))
    return value if x >= 0 else -value


def check(name, value, lo=None, hi=None):
    if value is None:
        status = "not_measured"
    else:
        status = "pass" if (lo is None or value >= lo) and (hi is None or value <= hi) else "fail"
    return {"check": name, "value": value, "min": lo, "max": hi, "status": status}


def verdict(checks):
    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        return "thresholds_not_met"
    return "not_scored" if "not_measured" in statuses or not checks else "thresholds_met"


def thresholds(arguments, defaults):
    supplied = exact(arguments.get("thresholds", {}), "thresholds", (), tuple(defaults))
    values, sources = {}, {}
    for key, default in defaults.items():
        if key in supplied:
            values[key], sources[key] = measure(supplied[key], f"thresholds.{key}"), "caller"
        else:
            values[key], sources[key] = default, "default"
    return values, sources


def percentile(values, share):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]

"""The numeric profile and the shared checks every Film tool uses.

Every measure crosses the wire as a bounded integer in milli-units of its natural unit: a share or ratio in per-mille
(0.508 -> 508), a time in milliseconds, a level in milli-dB or milli-LU (-16.9 LUFS -> -16900), a sharpness score in
thousandths (223.214 -> 223214). Producers scale with round(value * 1000). Arithmetic here is exact integer arithmetic;
the only rounding is half away from zero in div_round, applied once per derived value.

A check is {"check", "value", "min", "max", "status"}: it passes when min <= value <= max (a None bound is open), it
fails otherwise, and it is "not_measured" when the value is None. A verdict is never "met" while any check is
unmeasured (unknown is reported as not scored, never as a number).
"""
import re

MEASURE_LIMIT = 10 ** 12          # |milli-units|; a raw value of up to 1e9 in its unit
MS_LIMIT = 86_400_000             # one day in milliseconds
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}\Z")
METRIC = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
VERDICTS = ("thresholds_met", "thresholds_not_met", "not_scored")


class ToolInputError(ValueError):
    pass


def exact(value, name, required, optional=()):
    """A closed object: every required key, optional keys only from the list, nothing else."""
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


def permille(value, name):
    return integer(value, name, 0, 1000)


def ms(value, name):
    return integer(value, name, 0, MS_LIMIT)


def identifier(value, name, pattern=ID):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ToolInputError(f"{name} must match {pattern.pattern}")
    return value


def array(value, name, min_items, max_items):
    if type(value) is not list or not min_items <= len(value) <= max_items:
        raise ToolInputError(f"{name} must be a list of {min_items} to {max_items} items")
    return value


def identifiers(value, name, max_items, *, min_items=0, unique=True):
    items = [identifier(v, f"{name}[{i}]") for i, v in enumerate(array(value, name, min_items, max_items))]
    if unique and len(set(items)) != len(items):
        raise ToolInputError(f"{name} must not repeat an id")
    return items


def div_round(numerator, denominator):
    """numerator / denominator rounded half away from zero; denominator > 0."""
    quotient, remainder = divmod(abs(numerator), denominator)
    quotient += 2 * remainder >= denominator
    return quotient if numerator >= 0 else -quotient


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

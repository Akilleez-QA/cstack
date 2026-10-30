"""scale_timing: how long things take for a body of a given size, from dynamic similarity.

Under gravity, geometrically similar bodies move alike when their Froude number v^2 / (g L) is equal (Alexander and
Jayes 1983). So times scale with sqrt(L / g), speeds with sqrt(g L), and accelerations not at all: a 6 m giant swings
its legs about sqrt(3.4) = 1.85 times slower than a 1.75 m person and walks about 1.85 times faster. Mass does not
enter the kinematics; it enters strength: muscle force grows with area (L^2) and weight with volume (L^3), so
strength-to-weight falls as 1/L (the square-cube law), and a large body reads as heavy because it cannot accelerate
its limbs as sharply relative to g.
"""
import math

from .measures import ToolInputError, array, exact, gravity, identifier, integer, positive, rnd, unique_ids
from .sources import default


def leg_length(arguments):
    """Hip height in mm: the caller's, or the height times Winter's greater-trochanter ratio."""
    if ("leg_length_mm" in arguments) == ("height_mm" in arguments):
        raise ToolInputError("give exactly one of leg_length_mm and height_mm")
    if "leg_length_mm" in arguments:
        return float(positive(arguments["leg_length_mm"], "leg_length_mm", 10 ** 7)), "caller"
    height = positive(arguments["height_mm"], "height_mm", 10 ** 7)
    return height * default("anthropometry", "hip_height_per_height") / 1000, "winter_hip_height"


def reference_leg():
    return default("anthropometry", "reference_height_mm") * default("anthropometry", "hip_height_per_height") / 1000


def predicted_stride(leg, froude):
    """Alexander (1976): stride (one full cycle) = coefficient * leg * Froude^exponent."""
    k = default("scale", "stride_coefficient") / 1000
    n = default("scale", "stride_exponent") / 1000
    return k * leg * froude ** n


def walk_at(leg, g, froude):
    speed = math.sqrt(froude * g * leg)
    stride = predicted_stride(leg, froude)
    cycle = stride / speed
    return {"froude_permille": rnd(froude * 1000), "speed_mm_s": rnd(speed), "stride_mm": rnd(stride),
            "step_mm": rnd(stride / 2), "cycle_ms": rnd(cycle * 1000), "step_ms": rnd(cycle * 500),
            "cadence_milli_steps_per_min": rnd(2 / cycle * 60 * 1000)}


def scale_timing(arguments):
    exact(arguments, "arguments", (), ("height_mm", "leg_length_mm", "gravity_mm_s2", "froude_permille",
                                       "appendages", "drop_heights_mm"))
    leg, leg_source = leg_length(arguments)
    g, g_source = gravity(arguments)
    table = arguments.get("froude_permille", default("scale", "walk_froude_table"))
    table = [integer(f, f"froude_permille[{i}]", 1, 5000) for i, f in enumerate(array(table, "froude_permille", 1, 8))]
    appendages = array(arguments.get("appendages", []), "appendages", 0, 16)
    for i, item in enumerate(appendages):
        exact(item, f"appendages[{i}]", ("id", "length_mm"))
        identifier(item["id"], f"appendages[{i}].id")
        positive(item["length_mm"], f"appendages[{i}].length_mm", 10 ** 7)
    unique_ids(appendages, "appendages")
    drops = [positive(h, f"drop_heights_mm[{i}]", 10 ** 7)
             for i, h in enumerate(array(arguments.get("drop_heights_mm", []), "drop_heights_mm", 0, 16))]

    s = leg / reference_leg()
    rod = lambda length: 2 * math.pi * math.sqrt(2 * length / (3 * g)) * 1000  # noqa: E731  uniform rod, ms
    result = {
        "leg_length_mm": rnd(leg), "leg_source": leg_source, "gravity_mm_s2": rnd(g), "gravity_source": g_source,
        "reference_leg_mm": rnd(reference_leg()),
        "factors": {"length_permille": rnd(s * 1000), "time_permille": rnd(math.sqrt(s) * 1000),
                    "speed_permille": rnd(math.sqrt(s) * 1000), "acceleration_permille": 1000,
                    "strength_to_weight_permille": rnd(1000 / s)},
        "walk": [walk_at(leg, g, f / 1000) for f in table],
        "limits": {"walk_run_froude_permille": default("gait", "froude_max"),
                   "walk_run_speed_mm_s": rnd(math.sqrt(default("gait", "froude_max") / 1000 * g * leg)),
                   "max_walk_speed_mm_s": rnd(math.sqrt(g * leg))},
        "leg_swing_period_ms": rnd(rod(leg)),
        "appendages": [{"id": a["id"], "length_mm": a["length_mm"], "period_ms": rnd(rod(a["length_mm"]))}
                       for a in appendages],
        "drops": [{"height_mm": h, "fall_ms": rnd(math.sqrt(2 * h / g) * 1000)} for h in drops],
    }
    return "timing_estimated", result

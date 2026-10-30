"""squash_check: does squash and stretch keep the volume?

Flesh, clay and a filled sack are close to incompressible, so a body squashed along one axis bulges along the other
two; that constant volume is what makes squash and stretch read as mass rather than as a rubber sheet (Thomas and
Johnston 1981; Lasseter 1987). For scale factors sx, sy, sz the volume ratio is sx sy sz, and squashing by s along
one axis keeps the volume when the other two scale by 1 / sqrt(s).
"""
import math

from .measures import array, check, choice, exact, integer, rnd, thresholds, verdict
from .sources import defaults

THRESHOLDS = ("volume_error_max",)
MAX_FRAMES = 1000


def squash_check(arguments):
    exact(arguments, "arguments", ("frames",), ("axis", "thresholds"))
    limits, sources = thresholds(arguments, defaults("squash", THRESHOLDS))
    axis = "xyz".index(choice(arguments.get("axis", "y"), "axis", ("x", "y", "z")))
    rows = []
    for i, frame in enumerate(array(arguments["frames"], "frames", 1, MAX_FRAMES)):
        exact(frame, f"frames[{i}]", ("scale_permille",))
        s = [integer(v, f"frames[{i}].scale_permille[{k}]", 1, 10 ** 6) / 1000
             for k, v in enumerate(array(frame["scale_permille"], f"frames[{i}].scale_permille", 3, 3))]
        volume = s[0] * s[1] * s[2]
        rows.append({"volume_permille": rnd(volume * 1000),
                     "conserving_lateral_permille": rnd(1000 / math.sqrt(s[axis]))})
    worst = max(range(len(rows)), key=lambda k: abs(rows[k]["volume_permille"] - 1000))
    error = abs(rows[worst]["volume_permille"] - 1000)
    checks = [check("volume_error_permille", error, 0, limits["volume_error_max"])]
    return verdict(checks), {"verdict": verdict(checks), "checks": checks, "worst_frame": worst, "frames": rows,
                             "thresholds": limits, "threshold_sources": sources}

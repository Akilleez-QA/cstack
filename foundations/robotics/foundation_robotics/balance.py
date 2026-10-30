"""balance_check: could this body hold, make or stop this motion without falling?

- Static balance: the centre of mass (COM) projects inside the support polygon (the convex hull of the contact
  points on the ground).
- Dynamic balance: the zero-moment point (ZMP) lies inside the support polygon on every supported frame. With the
  COM at height z above the ground and accelerations from the frames, x_zmp = x - z x'' / (z'' + g) (Vukobratovic and
  Borovac 2004; the cart-table model of Kajita et al. 2003). A ZMP outside the polygon is a motion the feet cannot
  push for: the body would tip about the polygon edge. This neglects the rate of change of angular momentum about
  the COM (arm swing, a spinning torso), so it is a lower bound on what is needed, not the whole story.
- Stopping: a body can stop without another step only when its capture point x + x' / sqrt(g / z) (Pratt et al.
  2006; Hof et al. 2005's extrapolated COM) is inside the polygon.
- Flight: with no support the COM falls at g, whatever the limbs do (Newton).
Velocity and acceleration come from a least-squares quadratic over a window of frames (Savitzky-Golay), because
positions arrive rounded to whole millimetres.
Distances are signed: positive inside the polygon, negative outside. Point and line contacts have no inside.
"""
import math

from .measures import (ToolInputError, array, check, choice, exact, gravity, ground, rnd, positive, thresholds,
                       up_axis, vec3, verdict)
from .sources import defaults

THRESHOLDS = ("margin_mm", "flight_gravity_error_max", "derivative_window_ms")
MAX_FRAMES = 400
MAX_CONTACTS = 16


def hull(points):
    """Counter-clockwise convex hull (Andrew's monotone chain); collinear points dropped."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])  # noqa: E731
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _segment_distance(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    length2 = ab[0] ** 2 + ab[1] ** 2
    t = 0 if length2 == 0 else max(0, min(1, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / length2))
    return math.dist(p, (a[0] + t * ab[0], a[1] + t * ab[1]))


def signed_distance(p, polygon):
    """Positive inside a counter-clockwise convex polygon, negative outside; degenerate polygons have no inside."""
    if len(polygon) == 1:
        return -math.dist(p, polygon[0])
    edges = list(zip(polygon, polygon[1:] + polygon[:1])) if len(polygon) > 2 else [(polygon[0], polygon[1])]
    nearest = min(_segment_distance(p, a, b) for a, b in edges)
    if len(polygon) == 2:
        return -nearest
    inside = all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0 for a, b in edges)
    return nearest if inside else -nearest


def balance_check(arguments):
    exact(arguments, "arguments", ("fps_milli", "frames"), ("mode", "up_axis", "gravity_mm_s2", "thresholds"))
    fps = positive(arguments["fps_milli"], "fps_milli", 10 ** 6) / 1000
    mode = choice(arguments.get("mode", "dynamic"), "mode", ("static", "dynamic", "stop"))
    up = up_axis(arguments)
    g, g_source = gravity(arguments)
    limits, sources = thresholds(arguments, defaults("balance", THRESHOLDS))
    frames = array(arguments["frames"], "frames", 1, MAX_FRAMES)
    com, support = [], []
    for i, frame in enumerate(frames):
        exact(frame, f"frames[{i}]", ("com_mm", "support_mm"))
        com.append(vec3(frame["com_mm"], f"frames[{i}].com_mm"))
        contacts = array(frame["support_mm"], f"frames[{i}].support_mm", 0, MAX_CONTACTS)
        support.append([vec3(p, f"frames[{i}].support_mm[{j}]") for j, p in enumerate(contacts)])

    # Savitzky-Golay: a least-squares quadratic over 2m + 1 frames. A plain central difference turns the +/-0.5 mm
    # rounding of integer positions into 0.7 x fps^2 mm/s^2 of noise (630 at 30 fps), far too noisy for a ZMP.
    m = max(1, round(limits["derivative_window_ms"] / 2000 * fps))
    k2 = sum(k * k for k in range(-m, m + 1))
    k4 = sum(k ** 4 for k in range(-m, m + 1))
    n = 2 * m + 1

    def deriv(i, order):
        window = [com[i + k] for k in range(-m, m + 1)]
        if order == 1:
            return [sum(k * w[c] for k, w in zip(range(-m, m + 1), window)) / k2 * fps for c in range(3)]
        return [2 * sum((k * k - k2 / n) * w[c] for k, w in zip(range(-m, m + 1), window)) / (k4 - k2 * k2 / n)
                * fps * fps for c in range(3)]

    rows, worst = [], {}
    for i in range(len(frames)):
        polygon = hull([ground(p, up) for p in support[i]])
        floor = sum(p[up] for p in support[i]) / len(support[i]) if support[i] else None
        row = {"frame": i, "contacts": len(support[i]), "com_margin_mm": None, "zmp_margin_mm": None,
               "capture_margin_mm": None, "flight_gravity_error_permille": None}
        interior = m <= i < len(frames) - m
        if polygon:
            row["com_margin_mm"] = rnd(signed_distance(ground(com[i], up), polygon))
            height = com[i][up] - floor
            if height <= 0:
                raise ToolInputError(f"frames[{i}]: the COM must be above its support")
            if interior:
                acc, vel = deriv(i, 2), deriv(i, 1)
                if acc[up] + g <= 0:
                    raise ToolInputError(f"frames[{i}]: the COM accelerates down faster than g while supported")
                zmp = [c - height * a / (acc[up] + g) for c, a in zip(ground(com[i], up), ground(acc, up))]
                row["zmp_margin_mm"] = rnd(signed_distance(zmp, polygon))
                omega = math.sqrt(g / height)
                capture = [c + v / omega for c, v in zip(ground(com[i], up), ground(vel, up))]
                row["capture_margin_mm"] = rnd(signed_distance(capture, polygon))
        elif interior:
            row["flight_gravity_error_permille"] = rnd(abs(deriv(i, 2)[up] + g) / g * 1000)
        rows.append(row)

    def lowest(key, subset=rows):
        values = [r for r in subset if r[key] is not None]
        if not values:
            return None, None
        r = min(values, key=lambda x: x[key])
        return r[key], r["frame"]

    supported = [r for r in rows if r["contacts"]]
    checks = []
    if mode == "static" and supported:
        worst["com_margin_mm"] = lowest("com_margin_mm", supported)
        checks.append(check("com_margin_mm", worst["com_margin_mm"][0], limits["margin_mm"]))
    if mode in ("dynamic", "stop") and supported:
        worst["zmp_margin_mm"] = lowest("zmp_margin_mm", supported)
        checks.append(check("zmp_margin_mm", worst["zmp_margin_mm"][0], limits["margin_mm"]))
    if mode == "stop":
        last = rows[-1 - m] if len(rows) > 2 * m else None  # the last frame with a full derivative window
        checks.append(check("final_capture_margin_mm", last and last["capture_margin_mm"], limits["margin_mm"]))
    flight = [r["flight_gravity_error_permille"] for r in rows if r["flight_gravity_error_permille"] is not None]
    if flight:
        checks.append(check("flight_gravity_error_permille", max(flight), 0, limits["flight_gravity_error_max"]))
    if not checks:
        raise ToolInputError("nothing to judge: no supported frame and no interior flight frame")
    failing = [r["frame"] for r in rows if any(
        r[k] is not None and r[k] < limits["margin_mm"] for k in (("com_margin_mm",) if mode == "static"
                                                                   else ("zmp_margin_mm",)))
        or (r["flight_gravity_error_permille"] or 0) > limits["flight_gravity_error_max"]]
    return verdict(checks), {"verdict": verdict(checks), "mode": mode, "gravity_mm_s2": rnd(g),
                             "gravity_source": g_source, "checks": checks,
                             "worst": {k: {"value": v[0], "frame": v[1]} for k, v in worst.items()},
                             "first_failing_frame": failing[0] if failing else None, "frames": rows,
                             "thresholds": limits, "threshold_sources": sources}

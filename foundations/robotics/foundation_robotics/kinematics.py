import math

from .measures import (COORD_LIMIT, ToolInputError, array, check, choice, exact, identifier, integer, rnd, thresholds,
                       unique_ids, vec3, verdict)
from .sources import defaults

THRESHOLDS = ("tolerance_mm", "singular_ratio_min")
MAX_JOINTS = 16
MAX_POSES = 200


def _unit(v, name):
    norm = math.sqrt(sum(c * c for c in v))
    if norm == 0:
        raise ToolInputError(f"{name} must not be zero")
    return [c / norm for c in v]


def _rodrigues(w, theta):
    c, s, k = math.cos(theta), math.sin(theta), 1 - math.cos(theta)
    x, y, z = w
    return [[c + x * x * k, x * y * k - z * s, x * z * k + y * s],
            [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
            [z * x * k - y * s, z * y * k + x * s, c + z * z * k]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(r, v):
    return [sum(r[i][k] * v[k] for k in range(3)) for i in range(3)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def eigen_symmetric(m):
    a = [row[:] for row in m]
    for _ in range(50):
        off = sum(a[i][j] ** 2 for i in range(3) for j in range(3) if i != j)
        if off < 1e-18 * max(1.0, sum(a[i][i] ** 2 for i in range(3))):
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if a[p][q] == 0:
                continue
            phi = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
            c, s = math.cos(phi), math.sin(phi)
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    return sorted((a[i][i] for i in range(3)), reverse=True)


def forward(joints, tip, q):
    rotation = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    translation = [0.0, 0.0, 0.0]
    points, axes = [], []
    for joint, value in zip(joints, q):
        point = [_apply(rotation, joint["home"])[i] + translation[i] for i in range(3)]
        axis = _apply(rotation, joint["axis"])
        points.append(point)
        axes.append(axis)
        if joint["type"] == "revolute":
            r = _rodrigues(joint["axis"], value)
            shift = [joint["home"][i] - _apply(r, joint["home"])[i] for i in range(3)]
            translation = [_apply(rotation, shift)[i] + translation[i] for i in range(3)]
            rotation = _mul(rotation, r)
        else:
            translation = [translation[i] + _apply(rotation, [c * value for c in joint["axis"]])[i] for i in range(3)]
    end = [_apply(rotation, tip)[i] + translation[i] for i in range(3)]
    columns = [_cross(a, [end[k] - p[k] for k in range(3)]) if j["type"] == "revolute" else a
               for j, a, p in zip(joints, axes, points)]
    return end, columns


def ik_check(arguments):
    exact(arguments, "arguments", ("joints", "tip_mm", "poses"), ("thresholds",))
    limits, sources = thresholds(arguments, defaults("ik", THRESHOLDS))
    joints, home = [], [0.0, 0.0, 0.0]
    for i, joint in enumerate(array(arguments["joints"], "joints", 1, MAX_JOINTS)):
        exact(joint, f"joints[{i}]", ("id", "type", "axis", "origin_mm", "min", "max"))
        identifier(joint["id"], f"joints[{i}].id")
        kind = choice(joint["type"], f"joints[{i}].type", ("revolute", "prismatic"))
        origin = vec3(joint["origin_mm"], f"joints[{i}].origin_mm")
        lo, hi = integer(joint["min"], f"joints[{i}].min", -COORD_LIMIT, COORD_LIMIT), integer(
            joint["max"], f"joints[{i}].max", -COORD_LIMIT, COORD_LIMIT)
        if lo > hi:
            raise ToolInputError(f"joints[{i}]: min must not exceed max")
        home = [home[k] + origin[k] for k in range(3)]
        joints.append({"id": joint["id"], "type": kind, "axis": _unit(vec3(joint["axis"], f"joints[{i}].axis"),
                       f"joints[{i}].axis"), "origin": origin, "home": home, "min": lo, "max": hi})
    unique_ids(joints, "joints")
    tip = vec3(arguments["tip_mm"], "tip_mm")
    tip_home = [home[k] + tip[k] for k in range(3)]
    base = joints[0]["home"]
    reach = (sum(math.sqrt(sum(c * c for c in j["origin"])) for j in joints[1:]) + math.sqrt(sum(c * c for c in tip))
             + sum(max(abs(j["min"]), abs(j["max"])) for j in joints if j["type"] == "prismatic"))
    mixed = len({j["type"] for j in joints}) > 1
    rows, checks = [], []
    for p, pose in enumerate(array(arguments["poses"], "poses", 1, MAX_POSES)):
        exact(pose, f"poses[{p}]", ("q",), ("target_mm",))
        q = [integer(v, f"poses[{p}].q[{i}]", -COORD_LIMIT, COORD_LIMIT)
             for i, v in enumerate(array(pose["q"], f"poses[{p}].q", len(joints), len(joints)))]
        values = [v / 1000 if j["type"] == "revolute" else float(v) for j, v in zip(joints, q)]
        end, columns = forward(joints, tip_home, values)
        limit_margin = min(min(v - j["min"], j["max"] - v) for j, v in zip(joints, q))
        outside = [j["id"] for j, v in zip(joints, q) if not j["min"] <= v <= j["max"]]
        jjt = [[sum(c[a] * c[b] for c in columns) for b in range(3)] for a in range(3)]
        rank = min(3, len(joints))
        sigma = [math.sqrt(max(0.0, e)) for e in eigen_symmetric(jjt)][:rank]
        ratio = rnd(sigma[-1] / sigma[0] * 1000) if sigma[0] > 0 else 0
        row = {"pose": p, "tip_mm": [rnd(c) for c in end], "limit_margin": limit_margin, "outside_limits": outside,
               "singular_values": [rnd(s) for s in sigma], "singular_ratio_permille": ratio,
               "target_distance_mm": None, "reach_margin_mm": None, "error_mm": None}
        if "target_mm" in pose:
            target = vec3(pose["target_mm"], f"poses[{p}].target_mm")
            row["target_distance_mm"] = rnd(math.dist(target, base))
            row["reach_margin_mm"] = rnd(reach - math.dist(target, base))
            row["error_mm"] = rnd(math.dist(target, end))
        rows.append(row)
    worst = lambda key: min((r[key] for r in rows if r[key] is not None), default=None)
    checks.append(check("limit_margin", worst("limit_margin"), 0))
    checks.append(check("singular_ratio_permille", worst("singular_ratio_permille"), limits["singular_ratio_min"]))
    if any(r["reach_margin_mm"] is not None for r in rows):
        checks.append(check("reach_margin_mm", worst("reach_margin_mm"), 0))
        checks.append(check("error_mm", max(r["error_mm"] for r in rows if r["error_mm"] is not None), 0,
                            limits["tolerance_mm"]))
    failing = [r["pose"] for r in rows if r["outside_limits"] or r["singular_ratio_permille"] < limits[
        "singular_ratio_min"] or (r["error_mm"] or 0) > limits["tolerance_mm"] or (r["reach_margin_mm"] or 0) < 0]
    return verdict(checks), {"verdict": verdict(checks), "reach_mm": rnd(reach), "base_mm": [rnd(c) for c in base],
                             "mixed_joint_types": mixed, "checks": checks, "poses": rows,
                             "first_failing_pose": failing[0] if failing else None,
                             "thresholds": limits, "threshold_sources": sources}

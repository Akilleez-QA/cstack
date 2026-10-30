"""gait_check: is this walk (or run, or stand) one a body of this size could make?

The checks are first principles, each a relation that real legged gaits obey:
- Froude number v^2 / (g L) in the walking band: below a stroll a walk reads as slow motion; above about 0.5 people
  run (Alexander 1989; Kram et al. 1997).
- Stride against Alexander's (1976) relation for the same Froude number: long strides at a slow cadence are the
  slow-motion look.
- Kinematic identity: root speed equals stride over cycle time, or a planted foot must slide.
- Duty factor: in a walk each foot is down for at least half the cycle (double support); in a run, less.
- Foot slide: a planted foot does not move (Kovar et al. 2002). The allowance scales with sqrt(leg) so a giant is
  judged like a person.
- Left/right step-time symmetry.
Foot tracks are world-space positions per frame (after root motion) with a contact flag; for an in-place loop, add the
root travel before calling.
"""
import math

from .measures import (ToolInputError, array, check, choice, exact, gravity, ground, identifier, integer, percentile,
                       positive, rnd, thresholds, unique_ids, up_axis, vec3, verdict)
from .scale import leg_length, predicted_stride, reference_leg, walk_at
from .sources import defaults

THRESHOLDS = ("froude_min", "froude_max", "stride_ratio_min", "stride_ratio_max", "duty_walk_min", "slide_mean_mm_s",
              "kinematic_mismatch_max", "step_time_asymmetry_max")
MAX_FRAMES = 1200


def _mean(values):
    return sum(values) / len(values) if values else None


def _track(foot, name, fps, up):
    track = exact(foot["track"], f"{name}.track", ("positions_mm", "contact"))
    positions = [vec3(p, f"{name}.track.positions_mm[{i}]")
                 for i, p in enumerate(array(track["positions_mm"], f"{name}.track.positions_mm", 2, MAX_FRAMES))]
    contact = [integer(c, f"{name}.track.contact[{i}]", 0, 1)
               for i, c in enumerate(array(track["contact"], f"{name}.track.contact", 2, MAX_FRAMES))]
    if len(contact) != len(positions):
        raise ToolInputError(f"{name}.track: contact and positions_mm must have one entry per frame")
    dt = 1000 / fps  # s per frame, fps in milli-fps
    slides = [math.dist(ground(positions[i], up), ground(positions[i + 1], up)) / dt
              for i in range(len(contact) - 1) if contact[i] and contact[i + 1]]
    strikes = [i for i in range(1, len(contact)) if contact[i] and not contact[i - 1]]
    stances = []
    for s in strikes:
        end = s
        while end < len(contact) and contact[end]:
            end += 1
        if end < len(contact):
            stances.append((end - s) * dt)
    cycle = _mean([(b - a) * dt for a, b in zip(strikes, strikes[1:])])
    stride = _mean([math.dist(ground(positions[a], up), ground(positions[b], up))
                    for a, b in zip(strikes, strikes[1:])])
    return {"contact_frames": sum(contact), "strikes": len(strikes), "strike_times": [s * dt for s in strikes],
            "cycle": cycle, "stance": _mean(stances), "stride": stride,
            "slide": (_mean(slides), percentile(slides, 0.95), max(slides)) if slides else (None, None, None)}


def _asymmetry(a, b):
    """|mean a->b step time - mean b->a step time| / their mean, from two feet's strike times."""
    events = sorted([(t, 0) for t in a] + [(t, 1) for t in b])
    steps = {(0, 1): [], (1, 0): []}
    for (t0, f0), (t1, f1) in zip(events, events[1:]):
        if f0 != f1:
            steps[(f0, f1)].append(t1 - t0)
    m1, m2 = _mean(steps[(0, 1)]), _mean(steps[(1, 0)])
    return None if m1 is None or m2 is None else abs(m1 - m2) / ((m1 + m2) / 2)


def gait_check(arguments):
    exact(arguments, "arguments", ("speed_mm_s",), ("leg_length_mm", "height_mm", "stride_mm", "cycle_ms", "feet",
                                                   "fps_milli", "up_axis", "gait", "gravity_mm_s2", "thresholds"))
    leg, leg_source = leg_length(arguments)
    g, _ = gravity(arguments)
    up = up_axis(arguments)
    gait = choice(arguments.get("gait", "walk"), "gait", ("walk", "run", "stand"))
    speed = integer(arguments["speed_mm_s"], "speed_mm_s", 0, 10 ** 6)
    limits, sources = thresholds(arguments, defaults("gait", THRESHOLDS))
    feet = array(arguments.get("feet", []), "feet", 0, 4)
    for i, foot in enumerate(feet):
        exact(foot, f"feet[{i}]", ("id",), ("stance_ms", "slide_mean_mm_s", "track"))
        identifier(foot["id"], f"feet[{i}].id")
    unique_ids(feet, "feet")
    fps = None
    if any("track" in f for f in feet):
        if "fps_milli" not in arguments:
            raise ToolInputError("fps_milli is required with foot tracks")
        fps = positive(arguments["fps_milli"], "fps_milli", 10 ** 6)

    tracks = {f["id"]: _track(f, f"feet[{i}]", fps, up) for i, f in enumerate(feet) if "track" in f}
    track_cycles = [t["cycle"] for t in tracks.values() if t["cycle"] is not None]
    track_strides = [t["stride"] for t in tracks.values() if t["stride"] is not None]
    cycle, cycle_source = None, None
    if "cycle_ms" in arguments:
        cycle, cycle_source = positive(arguments["cycle_ms"], "cycle_ms", 10 ** 7) / 1000, "caller"
    elif track_cycles:
        cycle, cycle_source = _mean(track_cycles), "track"
    stride, stride_source = None, None
    if "stride_mm" in arguments:
        stride, stride_source = float(positive(arguments["stride_mm"], "stride_mm", 10 ** 7)), "caller"
    elif track_strides:
        stride, stride_source = _mean(track_strides), "track"
    elif cycle is not None and speed:
        stride, stride_source = speed * cycle, "speed_x_cycle"
    if cycle is None and stride is not None and speed:
        cycle, cycle_source = stride / speed, "stride_over_speed"

    froude = speed ** 2 / (g * leg)
    checks, measured = [], {"froude_permille": rnd(froude * 1000), "stride_mm": rnd(stride),
                            "cycle_ms": rnd(None if cycle is None else cycle * 1000)}
    if gait == "walk":
        checks.append(check("froude_permille", measured["froude_permille"], limits["froude_min"], limits["froude_max"]))
    if gait != "stand":
        predicted = predicted_stride(leg, froude) if speed else None
        ratio = rnd(stride / predicted * 1000) if stride is not None and predicted else None
        measured.update(predicted_stride_mm=rnd(predicted), stride_ratio_permille=ratio)
        checks.append(check("stride_ratio_permille", ratio, limits["stride_ratio_min"], limits["stride_ratio_max"]))
        if stride_source in ("caller", "track") and cycle_source in ("caller", "track") and stride:
            mismatch = rnd(abs(speed * cycle - stride) / stride * 1000)
            measured["kinematic_mismatch_permille"] = mismatch
            checks.append(check("kinematic_mismatch_permille", mismatch, 0, limits["kinematic_mismatch_max"]))

    slide_limit = limits["slide_mean_mm_s"] * math.sqrt(leg / reference_leg())
    measured["slide_limit_mm_s"] = rnd(slide_limit)
    rows = []
    for foot in feet:
        t = tracks.get(foot["id"], {})
        slide = t.get("slide", (None, None, None))
        if "slide_mean_mm_s" in foot:
            slide = (integer(foot["slide_mean_mm_s"], f"feet.{foot['id']}.slide_mean_mm_s", 0, 10 ** 7), None, None)
        stance = (positive(foot["stance_ms"], f"feet.{foot['id']}.stance_ms", 10 ** 7) / 1000 if "stance_ms" in foot
                  else t.get("stance"))
        duty = rnd(stance / cycle * 1000) if stance is not None and cycle else None
        rows.append({"id": foot["id"], "contact_frames": t.get("contact_frames"), "strikes": t.get("strikes"),
                     "cycle_ms": rnd(None if t.get("cycle") is None else t["cycle"] * 1000),
                     "stance_ms": rnd(None if stance is None else stance * 1000), "duty_permille": duty,
                     "stride_mm": rnd(t.get("stride")), "slide_mean_mm_s": rnd(slide[0]),
                     "slide_p95_mm_s": rnd(slide[1]), "slide_max_mm_s": rnd(slide[2])})
        if gait == "walk":
            checks.append(check(f"duty_permille:{foot['id']}", duty, limits["duty_walk_min"], 1000))
        elif gait == "run":
            checks.append(check(f"duty_permille:{foot['id']}", duty, 0, limits["duty_walk_min"] - 1))
        checks.append(check(f"slide_mean_mm_s:{foot['id']}", rnd(slide[0]), 0, rnd(slide_limit)))
    if len(tracks) == 2 and gait != "stand":
        a, b = (t["strike_times"] for t in tracks.values())
        asym = _asymmetry(a, b)
        measured["step_time_asymmetry_permille"] = rnd(None if asym is None else asym * 1000)
        checks.append(check("step_time_asymmetry_permille", measured["step_time_asymmetry_permille"], 0,
                            limits["step_time_asymmetry_max"]))
    if not checks:
        raise ToolInputError("nothing to judge: a stand needs feet with tracks or slide_mean_mm_s")
    expected = {"at_this_speed": walk_at(leg, g, froude) if speed else None,
                "preferred": walk_at(leg, g, 0.25)}
    return verdict(checks), {"verdict": verdict(checks), "gait": gait, "leg_length_mm": rnd(leg),
                             "leg_source": leg_source, "stride_source": stride_source, "cycle_source": cycle_source,
                             "measured": measured, "checks": checks, "feet": rows, "expected": expected,
                             "thresholds": limits, "threshold_sources": sources}

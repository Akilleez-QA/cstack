"""mechanism_check: does this machine move the way its geometry forces it to?

Kinds, each a constraint a real mechanism cannot break (Norton 2012):
- gear_train: meshing gears have equal pitch-line speed, so omega_driven = omega_driver x N_driver / N_driven, with
  the sense reversed by an external mesh or a crossed belt. Screw-compressor rotors are a gear pair whose teeth are
  lobes: a 4-lobe male drives a 6-lobe female at 4/6 of its speed, the other way (Stosic et al. 2005). Gears listed
  together in a shaft turn as one.
- gear_mesh: two meshing members keep their phase. theta_driven + k theta_driver (k = N_driver / N_driven, sign by
  mesh) is constant modulo one tooth pitch of the driven member; any drift is teeth passing through each other.
- slider_crank: the slider sits at x = r cos(theta) + sqrt(l^2 - (r sin(theta) - e)^2) from the crank axis along its
  line (offset e); it assembles for a full turn only when l > r + |e|.
- four_bar: the Grashof condition s + l <= p + q decides whether a link can turn fully; the output angle follows
  from the input angle by the loop-closure (Freudenstein) equation, on the open or the crossed branch.
- rotor_strobe: a rotor with n blades sampled at a frame rate is seen at its true speed only below half a blade
  pitch per frame (Shannon 1949); faster, it aliases (the wagon-wheel effect: it crawls, stops or turns backwards)
  unless the shutter's motion blur smears each blade over at least a pitch. With no shutter_permille the renderer is
  taken to have no motion blur (a real-time render); a 180 degree film shutter is 500.
"""
import math

from .measures import (ToolInputError, array, check, choice, exact, identifier, integer, measure, positive, rnd,
                       thresholds, verdict)
from .sources import defaults

THRESHOLDS = ("speed_error_max", "mesh_phase_max", "slider_error_max_mm", "four_bar_error_max_mrad",
              "strobe_blur_min")
KINDS = ("gear_train", "gear_mesh", "slider_crank", "four_bar", "rotor_strobe")
MESH_SIGN = {"external": -1, "internal": 1, "belt": 1, "crossed_belt": -1}
MAX_FRAMES = 1000
TAU = 2 * math.pi


def _wrap(angle):
    """An angle in (-pi, pi]."""
    return angle - TAU * math.floor((angle + math.pi) / TAU)


def _gear_train(a, limits):
    exact(a, "arguments", ("kind", "input", "input_speed_mrad_s", "stages"), ("shafts", "measured_speeds_mrad_s",
                                                                            "thresholds"))
    speeds = {identifier(a["input"], "input"): float(measure(a["input_speed_mrad_s"], "input_speed_mrad_s"))}
    shafts = [[identifier(g, f"shafts[{i}][{j}]") for j, g in enumerate(array(s, f"shafts[{i}]", 2, 8))]
              for i, s in enumerate(array(a.get("shafts", []), "shafts", 0, 16))]

    def couple():
        for shaft in shafts:
            known = [speeds[g] for g in shaft if g in speeds]
            if known:
                speeds.update({g: known[0] for g in shaft})
    couple()
    stages = []
    for i, stage in enumerate(array(a["stages"], "stages", 1, 16)):
        exact(stage, f"stages[{i}]", ("driver", "driven", "driver_teeth", "driven_teeth", "mesh"))
        driver, driven = identifier(stage["driver"], f"stages[{i}].driver"), identifier(stage["driven"],
                                                                                         f"stages[{i}].driven")
        n1 = integer(stage["driver_teeth"], f"stages[{i}].driver_teeth", 1, 10 ** 5)
        n2 = integer(stage["driven_teeth"], f"stages[{i}].driven_teeth", 1, 10 ** 5)
        sign = MESH_SIGN[choice(stage["mesh"], f"stages[{i}].mesh", MESH_SIGN)]
        if driver not in speeds:
            raise ToolInputError(f"stages[{i}]: driver {driver} is not driven by the input or an earlier stage")
        if driven in speeds:
            raise ToolInputError(f"stages[{i}]: {driven} is already driven")
        speeds[driven] = speeds[driver] * sign * n1 / n2
        couple()
        stages.append({"driver": driver, "driven": driven, "ratio_permille": rnd(sign * n1 / n2 * 1000)})
    measured = a.get("measured_speeds_mrad_s", {})
    if type(measured) is not dict or len(measured) > 32:
        raise ToolInputError("measured_speeds_mrad_s must be an object of up to 32 gear ids")
    checks, gears = [], []
    for gear, speed in speeds.items():
        row = {"id": gear, "speed_mrad_s": rnd(speed), "measured_mrad_s": None, "error_permille": None}
        if gear in measured:
            value = measure(measured[gear], f"measured_speeds_mrad_s.{gear}")
            row["measured_mrad_s"] = value
            row["error_permille"] = rnd(abs(value - speed) / abs(speed) * 1000) if speed else (0 if value == 0
                                                                                                else 1000)
            checks.append(check(f"speed_error_permille:{gear}", row["error_permille"], 0, limits["speed_error_max"]))
        gears.append(row)
    unknown = set(measured) - set(speeds)
    if unknown:
        raise ToolInputError(f"measured_speeds_mrad_s names gears not in the train: {sorted(unknown)}")
    return checks, {"gears": gears, "stages": stages}


def _gear_mesh(a, limits):
    exact(a, "arguments", ("kind", "driver_teeth", "driven_teeth", "mesh", "frames"), ("thresholds",))
    n1 = integer(a["driver_teeth"], "driver_teeth", 1, 10 ** 5)
    n2 = integer(a["driven_teeth"], "driven_teeth", 1, 10 ** 5)
    sign = MESH_SIGN[choice(a["mesh"], "mesh", MESH_SIGN)]
    pitch = TAU / n2
    phases = []
    for i, frame in enumerate(array(a["frames"], "frames", 2, MAX_FRAMES)):
        exact(frame, f"frames[{i}]", ("driver_mrad", "driven_mrad"))
        phi = measure(frame["driven_mrad"], f"frames[{i}].driven_mrad") / 1000 - sign * n1 / n2 * measure(
            frame["driver_mrad"], f"frames[{i}].driver_mrad") / 1000
        phases.append(phi * TAU / pitch)  # one driven pitch maps to a full turn, so the mean is circular
    mean = math.atan2(sum(math.sin(p) for p in phases), sum(math.cos(p) for p in phases))
    drift = [abs(_wrap(p - mean)) / TAU * 1000 for p in phases]  # per-mille of a pitch
    worst = max(range(len(drift)), key=drift.__getitem__)
    return [check("phase_drift_permille_pitch", rnd(drift[worst]), 0, limits["mesh_phase_max"])], {
        "speed_ratio_permille": rnd(sign * n1 / n2 * 1000), "driven_pitch_mrad": rnd(pitch * 1000),
        "worst_frame": worst, "phase_drift_permille_pitch": [rnd(d) for d in drift]}


def _slider_crank(a, limits):
    exact(a, "arguments", ("kind", "crank_mm", "rod_mm"), ("offset_mm", "frames", "thresholds"))
    r, l = positive(a["crank_mm"], "crank_mm", 10 ** 7), positive(a["rod_mm"], "rod_mm", 10 ** 7)
    e = measure(a.get("offset_mm", 0), "offset_mm")
    checks = [check("rod_minus_crank_and_offset_mm", l - r - abs(e), 1)]
    rows = []
    for i, frame in enumerate(array(a.get("frames", []), "frames", 0, MAX_FRAMES)):
        exact(frame, f"frames[{i}]", ("crank_mrad", "slider_mm"))
        theta = measure(frame["crank_mrad"], f"frames[{i}].crank_mrad") / 1000
        inside = l * l - (r * math.sin(theta) - e) ** 2
        expected = r * math.cos(theta) + math.sqrt(inside) if inside >= 0 else None
        value = measure(frame["slider_mm"], f"frames[{i}].slider_mm")
        rows.append({"expected_mm": rnd(expected),
                     "error_mm": None if expected is None else rnd(abs(value - expected))})
    if rows:
        errors = [r_["error_mm"] for r_ in rows]
        checks.append(check("slider_error_mm", None if None in errors else max(errors), 0,
                            limits["slider_error_max_mm"]))
    far, near = math.sqrt((l + r) ** 2 - e * e), math.sqrt(max(0, (l - r) ** 2 - e * e))
    return checks, {"stroke_mm": rnd(far - near), "top_dead_centre_mm": rnd(far), "bottom_dead_centre_mm": rnd(near),
                    "frames": rows}


def four_bar_output(d, a, b, c, theta2, branch):
    """Output angle theta4 (rad) of a four-bar with ground d, input a, coupler b, output c (Norton eq. 4.10)."""
    k1, k2, k3 = d / a, d / c, (a * a - b * b + c * c + d * d) / (2 * a * c)
    big_a = math.cos(theta2) - k1 - k2 * math.cos(theta2) + k3
    big_b = -2 * math.sin(theta2)
    big_c = k1 - (k2 + 1) * math.cos(theta2) + k3
    disc = big_b * big_b - 4 * big_a * big_c
    if disc < 0:
        return None
    root = math.sqrt(disc) * (-1 if branch == "open" else 1)
    return 2 * math.atan2(-big_b + root, 2 * big_a)


def _four_bar(a, limits):
    exact(a, "arguments", ("kind", "ground_mm", "input_mm", "coupler_mm", "output_mm"), ("branch", "frames",
                                                                                       "input_full_turn", "thresholds"))
    d, i_, b, c = (positive(a[k], k, 10 ** 7) for k in ("ground_mm", "input_mm", "coupler_mm", "output_mm"))
    branch = choice(a.get("branch", "open"), "branch", ("open", "crossed"))
    lengths = sorted([d, i_, b, c])
    grashof = lengths[0] + lengths[3] - lengths[1] - lengths[2]  # <= 0: some link turns fully
    shortest = {d: "ground", i_: "input", b: "coupler", c: "output"}[lengths[0]] if grashof < 0 else None
    kind = ("non_grashof_triple_rocker" if grashof > 0 else "change_point" if grashof == 0 else
            {"input": "crank_rocker", "output": "rocker_crank", "ground": "double_crank",
             "coupler": "double_rocker"}[shortest])
    checks, rows = [], []
    full_turn = a.get("input_full_turn", False)
    if type(full_turn) is not bool:
        raise ToolInputError("input_full_turn must be true or false")
    if full_turn:
        # the input is a crank only when Grashof holds and the shortest link is the input or the ground
        checks.append(check("input_is_crank", int(grashof < 0 and shortest in ("input", "ground")), 1, 1))
    for k, frame in enumerate(array(a.get("frames", []), "frames", 0, MAX_FRAMES)):
        exact(frame, f"frames[{k}]", ("input_mrad", "output_mrad"))
        expected = four_bar_output(d, i_, b, c, measure(frame["input_mrad"], f"frames[{k}].input_mrad") / 1000, branch)
        value = measure(frame["output_mrad"], f"frames[{k}].output_mrad") / 1000
        rows.append({"expected_mrad": rnd(None if expected is None else _wrap(expected) * 1000),
                     "error_mrad": None if expected is None else rnd(abs(_wrap(value - expected)) * 1000)})
    if rows:
        errors = [r["error_mrad"] for r in rows]
        checks.append(check("output_error_mrad", None if None in errors else max(errors), 0,
                            limits["four_bar_error_max_mrad"]))
    return checks, {"grashof_mm": grashof, "classification": kind, "branch": branch, "frames": rows}


def _rotor_strobe(a, limits):
    exact(a, "arguments", ("kind", "blades", "speed_mrad_s", "fps_milli"), ("shutter_permille", "thresholds"))
    n = integer(a["blades"], "blades", 1, 1000)
    omega = measure(a["speed_mrad_s"], "speed_mrad_s") / 1000
    fps = positive(a["fps_milli"], "fps_milli", 10 ** 6) / 1000
    shutter = integer(a.get("shutter_permille", 0), "shutter_permille", 0, 1000) / 1000  # no blur unless stated
    pitch = TAU / n
    step = omega / fps
    apparent = step - pitch * math.floor(step / pitch + 0.5)  # aliased into [-pitch/2, pitch/2)
    blur = abs(step) * shutter / pitch * 1000  # per-mille of a pitch smeared per exposure
    aliased = abs(step) >= pitch / 2
    reads = ("true_motion" if not aliased else "smeared_disc" if blur >= limits["strobe_blur_min"] else
             "stationary" if abs(apparent) < pitch * 0.02 else
             "backwards" if apparent * step < 0 else "slowed")
    per_frame = rnd(abs(step) / pitch * 1000)
    # Below half a pitch per frame the motion reads true; above it, only a full smear of blur hides the alias.
    checks = [check("pitch_per_frame_permille", per_frame, 0, 499) if not aliased else
              check("blur_permille_pitch", rnd(blur), limits["strobe_blur_min"])]
    return checks, {"reads_as": reads, "pitch_per_frame_permille": per_frame, "step_per_frame_mrad": rnd(step * 1000),
                    "apparent_step_mrad": rnd(apparent * 1000), "blade_pitch_mrad": rnd(pitch * 1000),
                    "blur_permille_pitch": rnd(blur), "max_true_speed_mrad_s": rnd(pitch / 2 * fps * 1000)}


def mechanism_check(arguments):
    if type(arguments) is not dict:
        raise ToolInputError("arguments must be an object")
    kind = choice(arguments.get("kind"), "kind", KINDS)
    limits, sources = thresholds(arguments, defaults("mechanism", THRESHOLDS))
    checks, detail = {"gear_train": _gear_train, "gear_mesh": _gear_mesh, "slider_crank": _slider_crank,
                      "four_bar": _four_bar, "rotor_strobe": _rotor_strobe}[kind](arguments, limits)
    if not checks:
        raise ToolInputError("nothing to judge: supply measured speeds or frames")
    return verdict(checks), {"verdict": verdict(checks), "kind": kind, "checks": checks, "detail": detail,
                             "thresholds": limits, "threshold_sources": sources}

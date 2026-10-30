"""Static JSON Schema 2020-12 tool contracts, in TOOL_NAMES order (foundation_robotics/tools.py).

The bridge is stdlib-only and does not run a validator; each tool's own argument checks are authoritative.
The host validates every structuredContent against outputSchema, so it is kept tight. Every number is an integer
in milli-SI units (foundation_robotics/measures.py): mm, ms, mrad, mm/s, mrad/s, milli-fps, per-mille.
"""
from copy import deepcopy

DRAFT = "https://json-schema.org/draft/2020-12/schema"
TEXT = {"type": "string", "maxLength": 1024}
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9:_.\\-]{0,63}$"}
METRIC = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,31}$"}
MEASURE = {"type": "integer", "minimum": -10 ** 12, "maximum": 10 ** 12}
COORD = {"type": "integer", "minimum": -10 ** 9, "maximum": 10 ** 9}
NULL = {"type": "null"}
VERDICTS = ["thresholds_met", "thresholds_not_met", "not_scored"]


def count(maximum, minimum=0):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def nullable(schema):
    return {"anyOf": [NULL, schema]}


def array(items, minimum, maximum, **extra):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum, **extra}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else list(required), "additionalProperties": False}


def mapping(keys, values, maximum, minimum=0):
    return {"type": "object", "propertyNames": keys, "additionalProperties": values, "minProperties": minimum,
            "maxProperties": maximum}


def enum(*values):
    return {"enum": list(values)}


OPT = nullable(MEASURE)
VEC3 = array(COORD, 3, 3)
OUT_VEC3 = array(MEASURE, 3, 3)
BOUNDARY = obj({"observation_only": {"const": True}, "acceptance_decision": {"const": False},
                "control_action": {"const": False}})
EVIDENCE_ENTRY = obj({"applies_to": TEXT, "evidence": obj({
    "basis": obj({"kind": enum("cited", "derived", "caller"), "source": TEXT, "note": TEXT}),
    "status": enum("CHECK", "RECORDED")})})
CHECK = obj({"check": {"type": "string", "maxLength": 96}, "value": OPT, "min": OPT, "max": OPT,
             "status": enum("pass", "fail", "not_measured")})
CHECKS = array(CHECK, 1, 32)
THRESHOLDS_IN = mapping(METRIC, MEASURE, 8)
THRESHOLDS_OUT = {"thresholds": mapping(METRIC, MEASURE, 8, 1),
                  "threshold_sources": mapping(METRIC, enum("default", "caller"), 8, 1)}
VERDICT = {"enum": VERDICTS}
GRAVITY = count(10 ** 6, 1)
FPS = count(10 ** 6, 1)
UP = enum("y", "z")
LEG = {"leg_length_mm": count(10 ** 7, 1), "height_mm": count(10 ** 7, 1)}


def output(assessments, result):
    receipt = obj({"tool": TEXT, "version": TEXT, "status": enum("ok", "error"),
                   "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "boundary": BOUNDARY,
                   "result": {"oneOf": [NULL, result]}, "error": {"type": ["string", "null"]},
                   "evidence": array(EVIDENCE_ENTRY, 1, 16)})
    return {"$schema": DRAFT, **obj({"tool": TEXT, "assessment": {"enum": [*assessments, "tool_error"]},
                                     "formal_proof": {"const": False}, "runtime_goal_acceptance": {"const": False},
                                     "receipt": receipt})}


def inputs(properties, required=()):
    return {"$schema": DRAFT, **obj(properties, required)}


def judged(properties):
    """A judged result: the verdict, its checks and the thresholds it used, plus the tool's own fields."""
    return obj({"verdict": VERDICT, **properties, "checks": CHECKS, **THRESHOLDS_OUT})


# scale_timing
WALK = obj({k: MEASURE for k in ("froude_permille", "speed_mm_s", "stride_mm", "step_mm", "cycle_ms", "step_ms",
                                 "cadence_milli_steps_per_min")})
SCALE_IN = inputs({**LEG, "gravity_mm_s2": GRAVITY, "froude_permille": array(count(5000, 1), 1, 8),
                   "appendages": array(obj({"id": ID, "length_mm": count(10 ** 7, 1)}), 0, 16),
                   "drop_heights_mm": array(count(10 ** 7, 1), 0, 16)})
SCALE_OUT = obj({
    "leg_length_mm": MEASURE, "leg_source": enum("caller", "winter_hip_height"), "gravity_mm_s2": MEASURE,
    "gravity_source": enum("caller", "standard"), "reference_leg_mm": MEASURE,
    "factors": obj({k: MEASURE for k in ("length_permille", "time_permille", "speed_permille",
                                         "acceleration_permille", "strength_to_weight_permille")}),
    "walk": array(WALK, 1, 8),
    "limits": obj({k: MEASURE for k in ("walk_run_froude_permille", "walk_run_speed_mm_s", "max_walk_speed_mm_s")}),
    "leg_swing_period_ms": MEASURE,
    "appendages": array(obj({"id": ID, "length_mm": MEASURE, "period_ms": MEASURE}), 0, 16),
    "drops": array(obj({"height_mm": MEASURE, "fall_ms": MEASURE}), 0, 16)})

# gait_check
TRACK = obj({"positions_mm": array(VEC3, 2, 1200), "contact": array(count(1), 2, 1200)})
FOOT_IN = obj({"id": ID, "stance_ms": count(10 ** 7, 1), "slide_mean_mm_s": count(10 ** 7), "track": TRACK},
              ["id"])
GAIT_IN = inputs({**LEG, "speed_mm_s": count(10 ** 6), "stride_mm": count(10 ** 7, 1), "cycle_ms": count(10 ** 7, 1),
                  "feet": array(FOOT_IN, 0, 4), "fps_milli": FPS, "up_axis": UP, "gait": enum("walk", "run", "stand"),
                  "gravity_mm_s2": GRAVITY, "thresholds": THRESHOLDS_IN}, ["speed_mm_s"])
FOOT_OUT = obj({"id": ID, **{k: OPT for k in ("contact_frames", "strikes", "cycle_ms", "stance_ms", "duty_permille",
                                               "stride_mm", "slide_mean_mm_s", "slide_p95_mm_s", "slide_max_mm_s")}})
GAIT_OUT = judged({"gait": enum("walk", "run", "stand"), "leg_length_mm": MEASURE,
                   "leg_source": enum("caller", "winter_hip_height"),
                   "stride_source": nullable(enum("caller", "track", "speed_x_cycle")),
                   "cycle_source": nullable(enum("caller", "track", "stride_over_speed")),
                   "measured": mapping(METRIC, OPT, 16),
                   "feet": array(FOOT_OUT, 0, 4),
                   "expected": obj({"at_this_speed": nullable(WALK), "preferred": WALK})})

# balance_check
BALANCE_IN = inputs({"fps_milli": FPS, "frames": array(obj({"com_mm": VEC3, "support_mm": array(VEC3, 0, 16)}), 1, 400),
                     "mode": enum("static", "dynamic", "stop"), "up_axis": UP, "gravity_mm_s2": GRAVITY,
                     "thresholds": THRESHOLDS_IN}, ["fps_milli", "frames"])
BALANCE_OUT = judged({
    "mode": enum("static", "dynamic", "stop"), "gravity_mm_s2": MEASURE, "gravity_source": enum("caller", "standard"),
    "worst": mapping(METRIC, obj({"value": OPT, "frame": nullable(count(400))}), 4),
    "first_failing_frame": nullable(count(400)),
    "frames": array(obj({"frame": count(400), "contacts": count(16), **{k: OPT for k in (
        "com_margin_mm", "zmp_margin_mm", "capture_margin_mm", "flight_gravity_error_permille")}}), 1, 400)})

# ik_check
JOINT = obj({"id": ID, "type": enum("revolute", "prismatic"), "axis": VEC3, "origin_mm": VEC3, "min": COORD,
             "max": COORD})
IK_IN = inputs({"joints": array(JOINT, 1, 16), "tip_mm": VEC3,
                "poses": array(obj({"q": array(COORD, 1, 16), "target_mm": VEC3}, ["q"]), 1, 200),
                "thresholds": THRESHOLDS_IN}, ["joints", "tip_mm", "poses"])
IK_OUT = judged({
    "reach_mm": MEASURE, "base_mm": OUT_VEC3, "mixed_joint_types": {"type": "boolean"},
    "poses": array(obj({"pose": count(200), "tip_mm": OUT_VEC3, "limit_margin": MEASURE,
                        "outside_limits": array(ID, 0, 16), "singular_values": array(MEASURE, 1, 3),
                        "singular_ratio_permille": MEASURE, "target_distance_mm": OPT, "reach_margin_mm": OPT,
                        "error_mm": OPT}), 1, 200),
    "first_failing_pose": nullable(count(200))})

# mechanism_check
MESH = enum("external", "internal", "belt", "crossed_belt")
FRAMES = 1000


def kind(name, properties, required):
    return obj({"kind": {"const": name}, **properties, "thresholds": THRESHOLDS_IN}, ["kind", *required])


MECHANISM_IN = {"$schema": DRAFT, "oneOf": [
    kind("gear_train", {"input": ID, "input_speed_mrad_s": MEASURE,
                        "stages": array(obj({"driver": ID, "driven": ID, "driver_teeth": count(10 ** 5, 1),
                                             "driven_teeth": count(10 ** 5, 1), "mesh": MESH}), 1, 16),
                        "shafts": array(array(ID, 2, 8), 0, 16), "measured_speeds_mrad_s": mapping(ID, MEASURE, 32)},
         ["input", "input_speed_mrad_s", "stages"]),
    kind("gear_mesh", {"driver_teeth": count(10 ** 5, 1), "driven_teeth": count(10 ** 5, 1), "mesh": MESH,
                       "frames": array(obj({"driver_mrad": MEASURE, "driven_mrad": MEASURE}), 2, FRAMES)},
         ["driver_teeth", "driven_teeth", "mesh", "frames"]),
    kind("slider_crank", {"crank_mm": count(10 ** 7, 1), "rod_mm": count(10 ** 7, 1), "offset_mm": MEASURE,
                          "frames": array(obj({"crank_mrad": MEASURE, "slider_mm": MEASURE}), 0, FRAMES)},
         ["crank_mm", "rod_mm"]),
    kind("four_bar", {**{k: count(10 ** 7, 1) for k in ("ground_mm", "input_mm", "coupler_mm", "output_mm")},
                      "branch": enum("open", "crossed"), "input_full_turn": {"type": "boolean"},
                      "frames": array(obj({"input_mrad": MEASURE, "output_mrad": MEASURE}), 0, FRAMES)},
         ["ground_mm", "input_mm", "coupler_mm", "output_mm"]),
    kind("rotor_strobe", {"blades": count(1000, 1), "speed_mrad_s": MEASURE, "fps_milli": FPS,
                          "shutter_permille": count(1000)}, ["blades", "speed_mrad_s", "fps_milli"])]}
DETAIL = [
    obj({"gears": array(obj({"id": ID, "speed_mrad_s": MEASURE, "measured_mrad_s": OPT, "error_permille": OPT}),
                        2, 160),
         "stages": array(obj({"driver": ID, "driven": ID, "ratio_permille": MEASURE}), 1, 16)}),
    obj({"speed_ratio_permille": MEASURE, "driven_pitch_mrad": MEASURE, "worst_frame": count(FRAMES),
         "phase_drift_permille_pitch": array(MEASURE, 2, FRAMES)}),
    obj({"stroke_mm": MEASURE, "top_dead_centre_mm": MEASURE, "bottom_dead_centre_mm": MEASURE,
         "frames": array(obj({"expected_mm": OPT, "error_mm": OPT}), 0, FRAMES)}),
    obj({"grashof_mm": MEASURE, "classification": enum("crank_rocker", "rocker_crank", "double_crank", "double_rocker",
                                                       "change_point", "non_grashof_triple_rocker"),
         "branch": enum("open", "crossed"),
         "frames": array(obj({"expected_mrad": OPT, "error_mrad": OPT}), 0, FRAMES)}),
    obj({"reads_as": enum("true_motion", "smeared_disc", "stationary", "backwards", "slowed"),
         **{k: MEASURE for k in ("pitch_per_frame_permille", "step_per_frame_mrad", "apparent_step_mrad",
                                 "blade_pitch_mrad", "blur_permille_pitch", "max_true_speed_mrad_s")}})]
MECHANISM_OUT = judged({"kind": enum("gear_train", "gear_mesh", "slider_crank", "four_bar", "rotor_strobe"),
                        "detail": {"anyOf": DETAIL}})

# squash_check
SQUASH_IN = inputs({"frames": array(obj({"scale_permille": array(count(10 ** 6, 1), 3, 3)}), 1, 1000),
                    "axis": enum("x", "y", "z"), "thresholds": THRESHOLDS_IN}, ["frames"])
SQUASH_OUT = judged({"worst_frame": count(1000),
                     "frames": array(obj({"volume_permille": MEASURE, "conserving_lateral_permille": MEASURE}),
                                     1, 1000)})

_DESCRIBED = (
    ("scale_timing", "Expected timing for a body of this size under gravity (dynamic similarity): time, speed and "
     "strength factors against a reference adult, walking speed, stride and cadence at chosen Froude numbers, leg and "
     "appendage swing periods, fall times.", SCALE_IN, ["timing_estimated"], SCALE_OUT),
    ("gait_check", "Judge a walk, run or stand: Froude band, stride against Alexander's relation, speed = stride / "
     "cycle, duty factor, foot slide scaled to leg length, and left/right step symmetry.", GAIT_IN, VERDICTS,
     GAIT_OUT),
    ("balance_check", "Judge balance per frame: COM over the support polygon (static), ZMP inside it (dynamic), "
     "capture point inside it at the end (stop), and free fall at g in flight.", BALANCE_IN, VERDICTS, BALANCE_OUT),
    ("ik_check", "Judge a joint chain per pose by forward kinematics: joint limits, reach, tip error against a "
     "target, and distance from singularity (Jacobian singular-value ratio).", IK_IN, VERDICTS, IK_OUT),
    ("mechanism_check", "Judge a machine's motion against its geometry: gear-train speed ratios and senses, mesh "
     "phase lock, slider-crank position, four-bar Grashof class and output angle, rotor strobing at the frame rate.",
     MECHANISM_IN, VERDICTS, MECHANISM_OUT),
    ("squash_check", "Judge squash and stretch for constant volume per frame, with the side scale that would keep "
     "it.", SQUASH_IN, VERDICTS, SQUASH_OUT),
)


def tool_definitions():
    return deepcopy([{"name": name, "description": text, "inputSchema": schema_in,
                      "outputSchema": output(assessments, schema_out)}
                     for name, text, schema_in, assessments, schema_out in _DESCRIBED])

"""The fixed Robotics inventory. run(name, arguments) returns (failed, assessment, receipt), Evidence on every receipt.

Every tool is a read-only observation and a pure function of the caller's numbers: no file paths, no commands, no
network, no writes. A verdict compares the supplied motion with first-principles relations and stated thresholds. It
is not acceptance of an animation: that stays a person's call (I11, I12), so the receipt boundary says
acceptance_decision is false.

Evidence: basis kind "cited" (a named textbook, paper or standard), "derived" (computed here from the caller's input)
or "caller" (a threshold the caller supplied). Status "CHECK" marks a threshold whose calibration is still pending;
"RECORDED" marks a physical law, a measured ratio from a cited source, or a value computed from the input.
"""
import hashlib
import json

from . import __version__
from .balance import balance_check
from .gait import gait_check
from .kinematics import ik_check
from .measures import ToolInputError
from .mechanisms import mechanism_check
from .scale import scale_timing
from .sources import SOURCES, status
from .squash import squash_check

TOOL_NAMES = ("scale_timing", "gait_check", "balance_check", "ik_check", "mechanism_check", "squash_check")
# Every receipt carries this exact boundary; the host adapter refuses a receipt without it.
BOUNDARY = {"observation_only": True, "acceptance_decision": False, "control_action": False}


def input_sha256(arguments):
    """Digest of the exact arguments; the host recomputes it to bind the receipt to its request."""
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     allow_nan=False).encode("ascii")).hexdigest()


def evidence(applies_to, kind, source, note, state):
    return {"applies_to": applies_to, "evidence": {"basis": {"kind": kind, "source": source, "note": note},
                                                   "status": state}}


def cited(applies_to, key, note, state="RECORDED"):
    return evidence(applies_to, "cited", SOURCES[key], note, state)


def derived(applies_to, note):
    return evidence(applies_to, "derived", "the caller's numbers", note, "RECORDED")


def threshold_evidence(section, result, note):
    """One entry for the thresholds: CHECK while any default in use is CHECK; caller values are the caller's."""
    entries = []
    defaulted = [k for k, s in result["threshold_sources"].items() if s == "default"]
    if defaulted:
        state = "CHECK" if any(status(section, k) == "CHECK" for k in defaulted) else "RECORDED"
        entries.append(cited("result.thresholds", "calibration", note + " Defaults in use: " + ", ".join(defaulted)
                             + ".", state))
    supplied = [k for k, s in result["threshold_sources"].items() if s == "caller"]
    if supplied:
        entries.append(evidence("result.thresholds", "caller", "the caller's input",
                                "Thresholds supplied by the caller: " + ", ".join(supplied) + ".", "CHECK"))
    return entries


def _scale(arguments):
    assessment, result = scale_timing(arguments)
    entries = [
        cited("result.factors", "alexander_jayes_1983", "Dynamic similarity: at equal Froude number, times scale with "
              "sqrt(L / g), speeds with sqrt(g L), accelerations not at all."),
        cited("result.walk", "alexander_1976", "Stride = 2.3 L Froude^0.3, fitted across animals with scatter. On "
              "the approved alex walk the measured stride was 1.23 times this prediction, so read it as the centre "
              "of a band (gait_check judges the band).", "CHECK"),
        cited("result.limits", "kram_1997", "People change from walking to running near Froude 0.5; an inverted-"
              "pendulum walk cannot exceed Froude 1 (the body would leave the ground)."),
        cited("result.leg_swing_period_ms", "pendulum", "The passive swing of a uniform leg about the hip. A driven "
              "leg swings faster; use it as the scaling reference for swing and follow-through, not as a target."),
        cited("result.factors.strength_to_weight_permille", "haldane", "Strength over weight falls as 1 / L under "
              "geometric similarity: a big body cannot snap its limbs about as sharply relative to g."),
    ]
    if result["leg_source"] == "winter_hip_height":
        entries.append(cited("result.leg_length_mm", "winter", "Hip height from standing height (0.530 H) for an "
                             "adult of human proportions; give leg_length_mm for other builds."))
    if result["gravity_source"] == "caller":
        entries.append(evidence("arguments.gravity_mm_s2", "caller", "the caller's input", "Gravity supplied by the "
                                "caller.", "CHECK"))
    return assessment, result, entries


def _gait(arguments):
    assessment, result = gait_check(arguments)
    entries = [
        derived("result.measured", "Froude number, stride over Alexander's prediction, kinematic mismatch and step "
                "asymmetry from the caller's speed, stride, cycle and foot tracks; this Foundation never sees a clip."),
        cited("result.checks", "alexander_1989", "Walking needs double support (duty factor at least 0.5) and gives "
              "way to running near Froude 0.5 (Kram et al. 1997 confirmed the 0.5 transition under reduced gravity)."),
        cited("result.checks", "alexander_1976", "Over-striding for the Froude number at a slow cadence is the "
              "slow-motion signature: the rejected generated walk measured 2.09 times the predicted stride, the "
              "approved loop 1.23.", "CHECK"),
        cited("result.feet", "kovar_2002", "Footskate: a foot in contact must not move on the ground. The allowance "
              "is the calibrated human limit scaled by sqrt(leg / reference leg) (dynamic similarity)."),
    ]
    return assessment, result, entries + threshold_evidence(
        "gait", result, "Calibrated on the approved alex walk loop (pass) and four rejected walks (fail): two "
        "slow-motion generated walks and two raw retargets with foot slide. Not yet calibrated on quadrupeds, runs or "
        "giants judged by a person (I3).")


def _balance(arguments):
    assessment, result = balance_check(arguments)
    entries = [
        derived("result.frames", "COM velocity and acceleration by central differences of the supplied frames; "
                "support polygons as convex hulls of the supplied contact points."),
        cited("result.checks", "zmp", "The ZMP must lie inside the support polygon; the cart-table formula neglects "
              "the rate of change of angular momentum about the COM, so a pass is necessary, not sufficient."),
        cited("result.frames", "capture_point", "A body stops without stepping only if its capture point is inside "
              "the support polygon."),
        cited("result.checks", "newton", "Frames with no support must fall at g."),
    ]
    return assessment, result, entries + threshold_evidence(
        "balance", result, "Margins and the flight tolerance are not yet calibrated on captured motion; the suite "
        "tries them on constructed standing, leaning, swaying and falling cases only (I3).")


def _ik(arguments):
    assessment, result = ik_check(arguments)
    entries = [
        cited("result.poses", "lynch_park", "Forward kinematics as a product of exponentials and the positional "
              "geometric Jacobian, both computed from the supplied chain."),
        cited("result.checks", "yoshikawa", "Singular values of the Jacobian: their ratio measures how far the pose "
              "is from a singularity, where IK needs unbounded joint speed and pops."
              + (" This chain mixes revolute and prismatic joints, so the ratio mixes units." if
                 result["mixed_joint_types"] else ""), "CHECK"),
    ]
    return assessment, result, entries + threshold_evidence(
        "ik", result, "The tolerance and the singularity ratio are tried on constructed two-link legs (bent knee "
        "passes, straight knee, out-of-reach target and limit violation fail), not on character rigs (I3).")


def _mechanism(arguments):
    assessment, result = mechanism_check(arguments)
    source = {"gear_train": "stosic", "rotor_strobe": "shannon"}.get(result["kind"], "norton")
    notes = {"gear_train": "Equal pitch-line speed at every mesh; screw rotors mesh like gears with lobes as teeth.",
             "gear_mesh": "Meshing members keep their phase modulo one tooth pitch.",
             "slider_crank": "Closed-form slider position from crank angle, rod length and offset.",
             "four_bar": "Grashof classification and the loop-closure output angle.",
             "rotor_strobe": "Sampled at the frame rate, rotation reads true only below half a blade pitch per frame."}
    entries = [cited("result.detail", source, notes[result["kind"]])]
    if source != "norton":
        entries.append(cited("result.detail", "norton", "Gear-train and mechanism kinematics."))
    return assessment, result, entries + threshold_evidence(
        "mechanism", result, "Tolerances are tried on constructed exact and perturbed mechanisms only (I3).")


def _squash(arguments):
    assessment, result = squash_check(arguments)
    return assessment, result, [
        cited("result.frames", "thomas_johnston", "Squash and stretch keeps the volume: scale x times y times z stays "
              "1; conserving_lateral_permille is the side scale that would.")] + threshold_evidence(
        "squash", result, "The tolerance is a starting value tried on constructed cases and a synthetic squeeze "
        "(+8.6 % volume), not yet judged by a person (I3).")


TOOLS = {"scale_timing": _scale, "gait_check": _gait, "balance_check": _balance, "ik_check": _ik,
         "mechanism_check": _mechanism, "squash_check": _squash}


def run(name, arguments):
    try:
        assessment, result, entries = TOOLS[name](arguments)
        failed, status_, error = False, "ok", None
    except ToolInputError as problem:
        assessment, result, failed, status_, error = "tool_error", None, True, "error", str(problem)[:1024]
        entries = [evidence("error", "derived", "Foundation Robotics argument check", "The request was refused "
                            "before anything was judged.", "RECORDED")]
    return failed, assessment, {"tool": name, "version": __version__, "status": status_,
                                "input_sha256": input_sha256(arguments), "boundary": dict(BOUNDARY),
                                "result": result, "error": error, "evidence": entries}

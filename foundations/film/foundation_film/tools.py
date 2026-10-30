import hashlib
import json

from . import __version__
from .audio import audio_gate
from .cinema import cinematic_gate, reference_bands
from .cues import cue_vocabulary_check
from .drift import drift_verdict
from .look import look_gate
from .measures import ToolInputError

TOOL_NAMES = ("cinematic_gate", "reference_bands", "audio_gate", "drift_verdict", "cue_vocabulary_check", "look_gate")
BOUNDARY = {"observation_only": True, "acceptance_decision": False, "control_action": False}
PLAYBOOK = "forge/endoforge/docs/PLAYBOOK-film.md"
PRODUCERS = "forge/endoforge/tools/film/"


def input_sha256(arguments):
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     allow_nan=False).encode("ascii")).hexdigest()


def evidence(applies_to, kind, source, note, status):
    return {"applies_to": applies_to, "evidence": {"basis": {"kind": kind, "source": source, "note": note},
                                                   "status": status}}


def _derived(applies_to, note):
    return evidence(applies_to, "derived", "the caller's measures", note, "RECORDED")


def _caller(applies_to, note):
    return evidence(applies_to, "caller", "the caller's input", note, "CHECK")


def _cinematic(arguments):
    assessment, result = cinematic_gate(arguments)
    entries = [_derived("result.segments", "Duration-weighted means of the supplied per-shot measures (filmstats.py "
                        "shots.json); this Foundation never sees the film. Being inside the reference bands is a "
                        "measured proxy for cinematic quality, not the outcome (I12, I16).")]
    if result["rule_source"] == "caller":
        entries.append(_caller("result.rules", "Rules supplied by the caller; their calibration is the caller's."))
    else:
        entries.append(evidence("result.rules", "cited", PRODUCERS + "filmgate.py (default rules); " + PLAYBOOK,
                                "filmgate.py's default rules, first used on the 2026-10-26 reference run against "
                                "bands from its CG shots. Not yet calibrated on known-good and known-bad films (I3).",
                                "CHECK"))
    if "bands" in arguments:
        entries.append(_caller("arguments.bands", "Reference bands supplied by the caller; expected to come from "
                               "reference_bands over the whole reference (I16)."))
    return assessment, result, entries


def _bands(arguments):
    assessment, result = reference_bands(arguments)
    return assessment, result, [
        _derived("result.bands", "Lower duration-weighted percentile per metric: the first value, in ascending order, "
                 "at which cumulative screen time reaches 25, 50 or 75 % of the total. moving_share is the screen-time "
                 "share of shots whose camera is not static."),
        evidence("result.bands", "cited", PRODUCERS + "filmstats.py; " + PLAYBOOK,
                 "The same method reproduces the duration band of the 2026-10-26 reference bands exactly (7.0, 14.67, "
                 "23.71 s over 41 shots). Which shots form a reference subset (for example CG shots only) is the "
                 "caller's choice.", "RECORDED")]


def _audio(arguments):
    assessment, result = audio_gate(arguments)
    entries = [_derived("result.checks", "Measured values from the caller (EBU R128 loudness and true peak, stem levels "
                        "from audiostats.py, AudioSet classes from audiotags.py, per-line WER) against the contract."),
               evidence("result.contract", "cited", PLAYBOOK + " (the mix gate)",
                        "Mix contract learned on the 2026-10-26 reference run: -16 +/- 1 LUFS, <= -1 dBTP, voice 12-15 dB "
                        "over the bed, a hit on >= 80 % of cuts, Speech and Music heard and no Sine wave, WER <= 5 % per "
                        "line. The reference measured -16.9 LUFS, a bed about 14 dB under the voice and a hit on 78 % of "
                        "cuts; the rejected cut read as sine wave at -34 LUFS.", "CHECK")]
    if result["contract_overrides"]:
        entries.append(_caller("arguments.contract", "Contract values overridden by the caller: "
                               + ", ".join(result["contract_overrides"]) + "."))
    return assessment, result, entries


def _drift(arguments):
    assessment, result = drift_verdict(arguments)
    entries = [_derived("result.metrics", "Per-frame control-fidelity measures from the caller (driftgate.py); the gate "
                        "is the worst frame, never the clip mean."),
               evidence("result.gate", "cited", PLAYBOOK + " (drift gate, I20)",
                        "An unconditioned image-to-video pilot measured edge F1/mask IoU 0.98/0.84 at frame 0 and "
                        "0.08/0.0 at frame 90: a clip mean would have hidden the collapse.", "RECORDED")]
    if "driftgate_default" in result["threshold_sources"].values():
        entries.append(evidence("result.thresholds", "cited", PRODUCERS + "driftgate.py (defaults)",
                                "Starting thresholds edge F1 >= 0.45, mask IoU >= 0.60. Calibration pending: the control "
                                "renders must pass with margin, an unconditioned clip must fail early, and perturbed "
                                "passes must fail on the matching metric. The 2026-10-26 control bake-off clips failed "
                                "from frame 0 (edge F1 mean 0.21-0.56), so edge extraction and thresholds are "
                                "calibrated together.", "CHECK"))
    if "caller" in result["threshold_sources"].values():
        entries.append(_caller("arguments.thresholds", "Thresholds supplied by the caller."))
    return assessment, result, entries


def _cues(arguments):
    assessment, result = cue_vocabulary_check(arguments)
    return assessment, result, [
        _derived("result", "Set and order comparison of the supplied ids, aliases and marker times."),
        evidence("result.checks", "cited", "AGENTS.md I18; " + PLAYBOOK + " (lessons 66-67)",
                 "Shared vocabulary is contract: every id two lanes must agree on is frozen before either lane starts "
                 "and checked statically before any render.", "RECORDED")]


def _look(arguments):
    assessment, result = look_gate(arguments)
    entries = [_derived("result.frames", "Per-frame look measures from the caller (lookgate.py, frame against its "
                        "approved target), each against its threshold; every frame must pass every check."),
               evidence("result.role", "cited", PLAYBOOK + " (the look gate; the prep-stage decision)",
                        "A rejection alarm, not acceptance: thresholds_met means the frame was not rejected. The client "
                        "stays the acceptance authority and judges moving proofs, not stills or metrics (I11, I12). "
                        "Structure is drift_verdict's question; this one asks only whether the look could be right.",
                        "RECORDED")]
    if "lookgate_default" in result["threshold_sources"].values():
        entries.append(evidence("result.thresholds", "cited", PRODUCERS + "lookgate.py (defaults)",
                                "Calibrated as an alarm on the 2026-10-26 reference run only: the concept frame against "
                                "itself, re-encoded copies and a restyled keyframe pass (detail 0.99); all 14 rendered "
                                "beats fail (11 on detail at 0.065-0.433 of the target, the end card at 2.37, b1 and b10 "
                                "on palette and chroma) and unconditioned generated clips fail (detail 0.16-0.29). Not "
                                "yet calibrated on other films or looks (I3).", "CHECK"))
    if "caller" in result["threshold_sources"].values():
        entries.append(_caller("arguments.thresholds", "Thresholds supplied by the caller."))
    return assessment, result, entries


TOOLS = {"cinematic_gate": _cinematic, "reference_bands": _bands, "audio_gate": _audio, "drift_verdict": _drift,
         "cue_vocabulary_check": _cues, "look_gate": _look}


def run(name, arguments):
    try:
        assessment, result, entries = TOOLS[name](arguments)
        failed, status, error = False, "ok", None
    except ToolInputError as problem:
        assessment, result, failed, status, error = "tool_error", None, True, "error", str(problem)[:1024]
        entries = [evidence("error", "derived", "Foundation Film argument check", "The request was refused before "
                            "anything was judged.", "RECORDED")]
    return failed, assessment, {"tool": name, "version": __version__, "status": status,
                                "input_sha256": input_sha256(arguments), "boundary": dict(BOUNDARY),
                                "result": result, "error": error, "evidence": entries}

"""look_gate: does each frame look like its approved target (a concept frame or an approved keyframe)?

A rejection alarm, not acceptance. drift_verdict asks "is it in the right place"; this asks "could this look right".
Input is forge/endoforge/tools/film/lookgate.py's metrics per frame, frame against target, scaled to milli-units:
  palette_ab    mean earth mover's distance of the CIE Lab a and b histograms (milli-Lab units, lower is closer)
  palette_L     earth mover's distance of the L histograms (milli-L)
  median_L      |median L difference| (milli-L, lightness 0..100)
  range_L       |p5..p95 L contrast-range difference| (milli-L)
  clip_white    near-white (L > 97) share, frame minus target, floored at 0 (per-mille)
  clip_black    near-black (L < 3) share, frame minus target, floored at 0 (per-mille)
  detail_ratio  Laplacian energy per pixel, frame / target (per-mille): flat renders score far below 1
  chroma_ratio  mean chroma, frame / target (per-mille)
A null metric was not measured on that frame. Every frame must pass every check (the producer's own rule).

Defaults are lookgate.py's, calibrated as an alarm on the 2026-10-26 reference run: the concept frame against itself,
re-encoded copies and a restyled keyframe pass (detail 0.99); all 14 rendered beats fail (most on detail, as low as
0.065) and unconditioned generated clips fail (detail 0.16-0.29). Passing is "not rejected"; the client, on moving
proofs, stays the acceptance authority.
"""
from .measures import ToolInputError, array, check, exact, identifier, integer, verdict

METRICS = ("palette_ab", "palette_L", "median_L", "range_L", "clip_white", "clip_black", "detail_ratio",
           "chroma_ratio")
# (metric, min threshold key, max threshold key); the keys and defaults are lookgate.py's T, in milli-units.
CHECKS = (("palette_ab", None, "palette_ab"), ("palette_L", None, "palette_L"), ("median_L", None, "median_L"),
          ("range_L", None, "range_L"), ("clip_white", None, "clip_white"), ("clip_black", None, "clip_black"),
          ("detail_ratio", "detail_min", "detail_max"), ("chroma_ratio", "chroma_min", "chroma_max"))
DEFAULTS = {"palette_ab": 6000, "palette_L": 8000, "median_L": 10000, "range_L": 15000, "clip_white": 40,
            "clip_black": 80, "detail_min": 550, "detail_max": 1800, "chroma_min": 700, "chroma_max": 1400}
PERMILLE_METRICS = ("clip_white", "clip_black")
LIMIT = 10 ** 9                   # a Lab distance, lightness difference or ratio of up to 1e6
MAX_FRAMES = 128                  # stays inside the bridge frame, node and output limits


def _thresholds(value):
    given = exact(value, "thresholds", (), tuple(DEFAULTS))
    thresholds = dict(DEFAULTS)
    for key, number in given.items():
        thresholds[key] = integer(number, f"thresholds.{key}", 0, 1000 if key in PERMILLE_METRICS else LIMIT)
    for low, high in (("detail_min", "detail_max"), ("chroma_min", "chroma_max")):
        if thresholds[low] > thresholds[high]:
            raise ToolInputError(f"thresholds.{low} must not exceed thresholds.{high}")
    return thresholds, {k: "caller" if k in given else "lookgate_default" for k in DEFAULTS}


def _frame(raw, i, thresholds):
    row = exact(raw, f"frames[{i}]", ("id", "metrics"))
    frame_id = identifier(row["id"], f"frames[{i}].id")
    metrics = exact(row["metrics"], f"frames[{i}].metrics", METRICS)
    for name in METRICS:
        if metrics[name] is not None:
            integer(metrics[name], f"frames[{i}].metrics.{name}", 0, 1000 if name in PERMILLE_METRICS else LIMIT)
    checks = [check(name, metrics[name], None if low is None else thresholds[low], thresholds[high])
              for name, low, high in CHECKS]
    return {"id": frame_id, "verdict": verdict(checks), "checks": checks,
            "failing": [c["check"] for c in checks if c["status"] == "fail"],
            "not_measured": [c["check"] for c in checks if c["status"] == "not_measured"]}


def look_gate(arguments):
    exact(arguments, "arguments", ("frames",), ("thresholds",))
    thresholds, sources = _thresholds(arguments.get("thresholds", {}))
    rows = array(arguments["frames"], "frames", 1, MAX_FRAMES)
    frames = [_frame(raw, i, thresholds) for i, raw in enumerate(rows)]
    ids = [f["id"] for f in frames]
    if len(set(ids)) != len(ids):
        raise ToolInputError("frames must not repeat an id")
    result = {"verdict": verdict([c for f in frames for c in f["checks"]]), "gate": "every_frame",
              "role": "rejection_alarm", "frames": frames, "failing_frames": [f["id"] for f in frames
                                                                             if f["verdict"] == "thresholds_not_met"],
              "thresholds": thresholds, "threshold_sources": sources}
    return result["verdict"], result

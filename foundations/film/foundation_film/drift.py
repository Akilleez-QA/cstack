"""drift_verdict: does a generated clip stay on its control passes? (I20: generation adds appearance only.)

Input is the per-frame output of forge/endoforge/tools/film/driftgate.py (or an extension of it), scaled to milli-units:
  edge_f1              F1 of the generated frame's edges against the control line/edge pass (per-mille), required
  mask_iou             IoU of the subject as segmented in the generated frame against the control mask (per-mille)
  depth_error          depth error against the control depth pass after scale/shift fit (milli-units, lower is better)
  identity_similarity  embedding similarity of the subject crop to its reference views (per-mille)
A null entry means that metric was not measured on that frame.

The gate is on the worst frame, never the clip mean: a clip passes only when every frame meets every threshold. An
unconditioned pilot looked right for about a second and then collapsed (edge F1/mask IoU 0.98/0.84 at frame 0, 0.08/0.0
at frame 90), so a mean would have passed it. Defaults are driftgate.py's (edge F1 >= 0.45, mask IoU >= 0.60). Depth
error and identity have no calibrated default: a caller who supplies the series must supply the threshold.
"""
from .measures import ToolInputError, array, check, div_round, exact, integer, measure, verdict

METRICS = {"edge_f1": ("min", 450), "mask_iou": ("min", 600), "depth_error": ("max", None),
           "identity_similarity": ("min", None)}
THRESHOLD_KEYS = {"edge_f1": "edge_f1_min", "mask_iou": "mask_iou_min", "depth_error": "depth_error_max",
                  "identity_similarity": "identity_similarity_min"}
MAX_FRAMES, MAX_LISTED = 2048, 64


def _series(name, value):
    items = array(value, f"frames.{name}", 1, MAX_FRAMES)
    for i, number in enumerate(items):
        if number is not None:
            if name == "depth_error":
                measure(number, f"frames.{name}[{i}]")
                if number < 0:
                    raise ToolInputError("depth_error must be >= 0")
            else:
                integer(number, f"frames.{name}[{i}]", 0, 1000)
    return list(items)


def drift_verdict(arguments):
    exact(arguments, "arguments", ("frames",), ("thresholds",))
    frames = exact(arguments["frames"], "frames", ("edge_f1",), tuple(METRICS))
    series = {name: _series(name, frames[name]) for name in METRICS if name in frames}
    count = len(series["edge_f1"])
    if any(len(v) != count for v in series.values()):
        raise ToolInputError("every per-frame series must have the same length")
    given = exact(arguments.get("thresholds", {}), "thresholds", (), tuple(THRESHOLD_KEYS.values()))
    thresholds, sources = {}, {}
    for name in series:
        key = THRESHOLD_KEYS[name]
        if key in given:
            ceiling = 10 ** 12 if name == "depth_error" else 1000
            thresholds[key], sources[key] = integer(given[key], f"thresholds.{key}", 0, ceiling), "caller"
        elif METRICS[name][1] is not None:
            thresholds[key], sources[key] = METRICS[name][1], "driftgate_default"
        else:
            raise ToolInputError(f"{name} has no calibrated default; supply thresholds.{key}")
    unused = set(given) - set(thresholds)
    if unused:
        raise ToolInputError(f"thresholds {sorted(unused)} name a series that was not supplied")
    per_frame = []
    for i in range(count):
        checks = []
        for name, values in series.items():
            side, bound = METRICS[name][0], thresholds[THRESHOLD_KEYS[name]]
            checks.append(check(name, values[i], bound if side == "min" else None, bound if side == "max" else None))
        per_frame.append(checks)
    failing = [i for i, checks in enumerate(per_frame) if any(c["status"] == "fail" for c in checks)]
    summary = {}
    for name, values in series.items():
        measured = [(v, i) for i, v in enumerate(values) if v is not None]
        side = METRICS[name][0]
        worst = (min(measured) if side == "min" else max(measured, key=lambda p: (p[0], -p[1]))) if measured else None
        summary[name] = {"threshold": thresholds[THRESHOLD_KEYS[name]], "side": side,
                         "worst": None if worst is None else worst[0], "worst_frame": None if worst is None else worst[1],
                         "mean": div_round(sum(v for v, _ in measured), len(measured)) if measured else None,
                         "measured_frames": len(measured),
                         "failing_frames": sum(1 for c in per_frame if any(x["check"] == name and x["status"] == "fail"
                                                                           for x in c))}
    worst_frame = min(range(count), key=lambda i: (-sum(c["status"] == "fail" for c in per_frame[i]),
                                                   series["edge_f1"][i] if series["edge_f1"][i] is not None else 1001, i))
    result = {"verdict": verdict([c for checks in per_frame for c in checks]), "gate": "worst_frame", "frames": count,
              "first_failing_frame": failing[0] if failing else None, "failing_frames": len(failing),
              "failing_frame_indices": failing[:MAX_LISTED], "metrics": summary, "thresholds": thresholds,
              "threshold_sources": sources,
              "worst_frame": {"frame": worst_frame, "values": {n: v[worst_frame] for n, v in series.items()}}}
    return result["verdict"], result

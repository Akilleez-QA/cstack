from .measures import (METRIC, ToolInputError, array, check, div_round, exact, identifier, integer, measure, ms,
                       verdict)

CAMERAS = ("static", "pan", "tilt", "push/pull")
QUANTILES = (250, 500, 750)
MAX_SHOTS, MAX_METRICS, MAX_SEGMENTS, MAX_RULES = 400, 32, 64, 32
DEFAULT_RULE_METRICS = ("sharp", "black", "subject_motion", "luma")
BLACK_FLOOR = 350


def shots(value):
    items, names = [], None
    for i, raw in enumerate(array(value, "shots", 1, MAX_SHOTS)):
        shot = exact(raw, f"shots[{i}]", ("start_ms", "end_ms", "camera", "metrics"))
        start, end = ms(shot["start_ms"], f"shots[{i}].start_ms"), ms(shot["end_ms"], f"shots[{i}].end_ms")
        if end <= start:
            raise ToolInputError(f"shots[{i}] must end after it starts")
        if shot["camera"] not in CAMERAS:
            raise ToolInputError(f"shots[{i}].camera must be one of {list(CAMERAS)}")
        metrics = shot["metrics"]
        if type(metrics) is not dict or not 1 <= len(metrics) <= MAX_METRICS:
            raise ToolInputError(f"shots[{i}].metrics must be an object of 1 to {MAX_METRICS} measures")
        for name, number in metrics.items():
            identifier(name, f"shots[{i}].metrics key", METRIC)
            if name in ("moving_share", "duration_ms"):
                raise ToolInputError(f"{name} is derived from the shots and cannot be supplied")
            measure(number, f"shots[{i}].metrics.{name}")
        if names is None:
            names = sorted(metrics)
        elif sorted(metrics) != names:
            raise ToolInputError(f"shots[{i}] must carry the same metric names as shots[0]")
        if items and start < items[-1]["end_ms"]:
            raise ToolInputError(f"shots[{i}] overlaps the shot before it; shots are in time order and tile the film")
        items.append({"start_ms": start, "end_ms": end, "camera": shot["camera"], "metrics": dict(metrics)})
    return items, names


def weighted_percentile(values, weights, q_permille):
    order = sorted(range(len(values)), key=lambda k: (values[k], k))
    total, running = sum(weights), 0
    for k in order:
        running += weights[k]
        if running * 1000 >= q_permille * total:
            return values[k]
    return values[order[-1]]


def reference_bands(arguments):
    exact(arguments, "arguments", ("shots",))
    items, names = shots(arguments["shots"])
    durations = [s["end_ms"] - s["start_ms"] for s in items]
    total = sum(durations)
    band = lambda values: [weighted_percentile(values, durations, q) for q in QUANTILES]
    moving = sum(d for s, d in zip(items, durations) if s["camera"] != "static")
    result = {"bands": {"moving_share": div_round(1000 * moving, total),
                        "metrics": {n: band([s["metrics"][n] for s in items]) for n in names}},
              "duration_ms": band(durations), "n_shots": len(items), "total_ms": total,
              "quantiles_permille": list(QUANTILES)}
    return "bands_measured", result


def _bands(value, needed):
    bands = exact(value, "bands", ("moving_share", "metrics"))
    integer(bands["moving_share"], "bands.moving_share", 0, 1000)
    metrics = bands["metrics"]
    if type(metrics) is not dict or len(metrics) > MAX_METRICS:
        raise ToolInputError(f"bands.metrics must be an object of at most {MAX_METRICS} bands")
    for name, triple in metrics.items():
        identifier(name, "bands.metrics key", METRIC)
        triple = [measure(v, f"bands.metrics.{name}[{i}]") for i, v in enumerate(array(triple, name, 3, 3))]
        if not triple[0] <= triple[1] <= triple[2]:
            raise ToolInputError(f"bands.metrics.{name} must be ordered p25 <= p50 <= p75")
    absent = [n for n in needed if n not in metrics]
    if absent:
        raise ToolInputError(f"default rules need bands for {absent}; supply them or supply rules")
    return bands


def default_rules(bands):
    m = bands["metrics"]
    return [{"metric": "moving_share", "op": ">=", "target": bands["moving_share"]},
            {"metric": "sharp", "op": "<=", "target": m["sharp"][2]},
            {"metric": "sharp", "op": ">=", "target": -(-m["sharp"][0] // 2)},
            {"metric": "black", "op": "<=", "target": max(m["black"][2], BLACK_FLOOR)},
            {"metric": "subject_motion", "op": ">=", "target": m["subject_motion"][0]},
            {"metric": "luma", "op": ">=", "target": m["luma"][0]}]


def _rules(value, names):
    rules = []
    for i, raw in enumerate(array(value, "rules", 1, MAX_RULES)):
        rule = exact(raw, f"rules[{i}]", ("metric", "op", "target"))
        if rule["metric"] != "moving_share" and rule["metric"] not in names:
            raise ToolInputError(f"rules[{i}].metric must be moving_share or a measured shot metric")
        if rule["op"] not in (">=", "<="):
            raise ToolInputError(f"rules[{i}].op must be >= or <=")
        rules.append({"metric": rule["metric"], "op": rule["op"], "target": measure(rule["target"], "target")})
    return rules


def _segments(value, film_end):
    if value is None:
        return [{"id": "film", "start_ms": 0, "end_ms": film_end}]
    segments, seen = [], set()
    for i, raw in enumerate(array(value, "segments", 1, MAX_SEGMENTS)):
        seg = exact(raw, f"segments[{i}]", ("id", "start_ms", "end_ms"))
        ident = identifier(seg["id"], f"segments[{i}].id")
        start, end = ms(seg["start_ms"], "start_ms"), ms(seg["end_ms"], "end_ms")
        if end <= start or ident in seen:
            raise ToolInputError(f"segments[{i}] must have a unique id and end after it starts")
        seen.add(ident)
        segments.append({"id": ident, "start_ms": start, "end_ms": end})
    return segments


def cinematic_gate(arguments):
    exact(arguments, "arguments", ("shots",), ("bands", "rules", "segments"))
    items, names = shots(arguments["shots"])
    if "rules" in arguments:
        rules, source = _rules(arguments["rules"], names), "caller"
        if "bands" in arguments:
            _bands(arguments["bands"], ())
    elif "bands" in arguments:
        absent = [n for n in DEFAULT_RULE_METRICS if n not in names]
        if absent:
            raise ToolInputError(f"default rules need shot metrics {absent}")
        rules, source = default_rules(_bands(arguments["bands"], DEFAULT_RULE_METRICS)), "reference_bands_default"
    else:
        raise ToolInputError("cinematic_gate needs bands (for the default rules) or rules")
    out, all_checks = [], []
    for seg in _segments(arguments.get("segments"), max(s["end_ms"] for s in items)):
        parts = [(s, min(s["end_ms"], seg["end_ms"]) - max(s["start_ms"], seg["start_ms"])) for s in items]
        parts = [(s, w) for s, w in parts if w > 0]
        covered = sum(w for _, w in parts)
        measured = {}
        if covered:
            measured = {n: div_round(sum(s["metrics"][n] * w for s, w in parts), covered) for n in names}
            measured["moving_share"] = div_round(1000 * sum(w for s, w in parts if s["camera"] != "static"), covered)
        checks = [check(r["metric"], measured.get(r["metric"]), r["target"] if r["op"] == ">=" else None,
                        r["target"] if r["op"] == "<=" else None) for r in rules]
        all_checks += checks
        out.append({**seg, "covered_ms": covered, "verdict": verdict(checks), "measured": measured, "checks": checks,
                    "failing": [c["check"] for c in checks if c["status"] != "pass"]})
    result = {"verdict": verdict(all_checks), "rule_source": source, "rules": rules, "segments": out,
              "failing_segments": [s["id"] for s in out if s["verdict"] != "thresholds_met"]}
    return result["verdict"], result

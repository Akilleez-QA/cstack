"""Differential vectors for the Film port: every tool, enum, boundary and error path of the pinned Python, and a seeded fuzz."""
import json
import random
from lexical_vectors import lexical

CAMERAS = ("static", "pan", "tilt", "push/pull")
SHOTS = [{"start_ms": 0, "end_ms": 7000, "camera": "static", "metrics": {"sharp": 500, "black": 100, "subject_motion": 40, "luma": 400}},
         {"start_ms": 7000, "end_ms": 21000, "camera": "pan", "metrics": {"sharp": 700, "black": 300, "subject_motion": 90, "luma": 300}},
         {"start_ms": 21000, "end_ms": 44000, "camera": "push/pull", "metrics": {"sharp": 300, "black": 500, "subject_motion": 10, "luma": 600}}]
BANDS = {"moving_share": 500, "metrics": {"sharp": [300, 500, 700], "black": [100, 300, 500], "subject_motion": [10, 40, 90], "luma": [300, 400, 600]}}
AUDIO = {"integrated_lufs": -16500, "true_peak_dbtp": -1200, "voice_over_bed_db": 14000, "cuts": 50, "cuts_with_hit": 40, "heard": ["Speech", "music"], "line_wer": [{"line": "l1", "wer_permille": 20}, {"line": "l2", "wer_permille": 60}]}
LOOK_METRICS = {"palette_ab": 5000, "palette_L": 7000, "median_L": 9000, "range_L": 14000, "clip_white": 30, "clip_black": 70, "detail_ratio": 990, "chroma_ratio": 1000}
CUES = {"provided": [{"id": "a", "t_ms": 1000, "end_ms": 2000}, {"id": "b", "t_ms": 1500}, {"id": "c", "t_ms": 5000}], "lanes": [{"lane": "l1", "references": ["a", "x", "gone"]}, {"lane": "l2", "references": ["b", "y"]}],
        "aliases": {"x": "c", "y": "nothing", "z": "a"}, "orders": [{"beat": "b1", "sequence": ["a", "b", "c"]}, {"beat": "b2", "sequence": ["c", "a", "gone"]}, {"beat": "b3", "sequence": ["gone", "lost"]}],
        "min_gaps": [{"rule": "r1", "after": "a", "next": "c", "min_ms": 100}, {"rule": "r2", "after": "b", "next": "a", "min_ms": 0}, {"rule": "r3", "after": "gone", "next": "a", "min_ms": 5}]}
DRIFT = {"frames": {"edge_f1": [980, None, 80, 500], "mask_iou": [840, 700, 0, None], "depth_error": [5, 90, None, 2], "identity_similarity": [900, None, 400, 950]}, "thresholds": {"depth_error_max": 50, "identity_similarity_min": 500}}
SEEDS = {"cinematic_gate": {"shots": SHOTS, "bands": BANDS, "segments": [{"id": "s1", "start_ms": 0, "end_ms": 9000}, {"id": "s2", "start_ms": 9000, "end_ms": 44000}, {"id": "s3", "start_ms": 50000, "end_ms": 60000}]},
         "reference_bands": {"shots": SHOTS}, "audio_gate": AUDIO, "drift_verdict": DRIFT, "cue_vocabulary_check": CUES, "look_gate": {"frames": [{"id": "f1", "metrics": LOOK_METRICS}]}}
BAD = (None, True, False, 0, 1, -1, 1000, 1001, 86400000, 86400001, 10 ** 12, 10 ** 12 + 1, -10 ** 12, -10 ** 12 - 1, "", "x", "static", "a b", "-a", "a" * 64, "a" * 65, [], [1], [None], {}, {"a": 1}, {"constructor": 1})


def _text(value):
    return json.dumps(value, separators=(",", ":"))


def _paths(node, prefix=()):
    yield prefix
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _paths(value, prefix + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _paths(value, prefix + (index,))


def _copy(value):
    return json.loads(json.dumps(value))


def _set(root, path, value):
    if not path:
        return value
    root = _copy(root)
    node = root
    for name in path[:-1]:
        node = node[name]
    node[path[-1]] = value
    return root


def _drop(root, path):
    root = _copy(root)
    node = root
    for name in path[:-1]:
        node = node[name]
    del node[path[-1]]
    return root


def structured():
    out = []
    add = lambda tool, value: out.append((tool, _text(value)))
    for tool, seed in SEEDS.items():
        add(tool, seed)
        for path in _paths(seed):
            for bad in BAD:
                add(tool, _set(seed, path, bad))
            if path:
                add(tool, _drop(seed, path))
                if isinstance(path[-1], str):
                    parent = seed
                    for name in path[:-1]:
                        parent = parent[name]
                    add(tool, _set(seed, path[:-1], {**parent, "extra": 1}))
            add(tool, _set(seed, path + ("extra",), 1) if isinstance(_get(seed, path), dict) else seed)
    for camera in (*CAMERAS, "dolly", "Static"):
        add("reference_bands", {"shots": [{"start_ms": 0, "end_ms": 10, "camera": camera, "metrics": {"m": 1}}]})
    for rule in ({"metric": "moving_share", "op": ">=", "target": 1}, {"metric": "sharp", "op": "<=", "target": 400}, {"metric": "sharp", "op": "<", "target": 1}, {"metric": "nope", "op": ">=", "target": 1}):
        add("cinematic_gate", {"shots": SHOTS, "rules": [rule]})
        add("cinematic_gate", {"shots": SHOTS, "rules": [rule], "bands": BANDS})
        add("cinematic_gate", {"shots": SHOTS, "rules": [rule], "bands": {"moving_share": 1, "metrics": {}}})
    for value in (10 ** 12, -10 ** 12, 999999999999, -999999999999, 1, -1, -3):
        huge = [{"start_ms": 0, "end_ms": 86400000, "camera": "pan", "metrics": {"sharp": value, "black": value, "subject_motion": value, "luma": value}}]
        add("reference_bands", {"shots": huge})
        add("cinematic_gate", {"shots": huge, "bands": {"moving_share": 0, "metrics": {k: [value, value, value] for k in ("sharp", "black", "subject_motion", "luma")}}})
        add("cinematic_gate", {"shots": huge + [{"start_ms": 86399999, "end_ms": 86400000, "camera": "static", "metrics": huge[0]["metrics"]}], "rules": [{"metric": "sharp", "op": ">=", "target": 0}]})
    for sharp in (-3, -2, -1, 0, 1, 2, 3):
        add("cinematic_gate", {"shots": SHOTS, "bands": {"moving_share": 0, "metrics": {**BANDS["metrics"], "sharp": [sharp, 700, 700]}}})
    add("cinematic_gate", {"shots": [{"start_ms": 0, "end_ms": 1, "camera": "pan", "metrics": {"constructor": 5, "tostring": 6, "valueof": 7}}], "rules": [{"metric": "constructor", "op": ">=", "target": 1}, {"metric": "tostring", "op": "<=", "target": 1}]})
    add("reference_bands", {"shots": [{"start_ms": 0, "end_ms": 1, "camera": "pan", "metrics": {"__proto__": 5}}]})
    add("reference_bands", {"shots": [{"start_ms": 0, "end_ms": 1, "camera": "pan", "metrics": {"moving_share": 5}}]})
    add("reference_bands", {"shots": [{"start_ms": 0, "end_ms": 1, "camera": "pan", "metrics": {"duration_ms": 5}}]})
    add("reference_bands", {"shots": [{"start_ms": 0, "end_ms": 1, "camera": "pan", "metrics": {"a": 5}}, {"start_ms": 1, "end_ms": 2, "camera": "pan", "metrics": {"b": 5}}]})
    add("reference_bands", {"shots": [{"start_ms": 5, "end_ms": 9, "camera": "pan", "metrics": {"a": 5}}, {"start_ms": 8, "end_ms": 10, "camera": "pan", "metrics": {"a": 5}}]})
    for key, value in (("integrated_lufs", -17000), ("integrated_lufs", -15000), ("integrated_lufs", -17001), ("true_peak_dbtp", -1000), ("true_peak_dbtp", -999), ("voice_over_bed_db", 12000), ("voice_over_bed_db", 15001),
                       ("cuts", 0), ("cuts", 39), ("cuts", 100000), ("cuts", 100001), ("cuts_with_hit", 0), ("cuts_with_hit", 51), ("heard", []), ("heard", ["sine WAVE", "SPEECH", "Music"]), ("heard", ["\t"]), ("heard", ["x" * 96]), ("heard", ["x" * 97]),
                       ("line_wer", []), ("line_wer", [{"line": "a", "wer_permille": 10000}]), ("line_wer", [{"line": "a", "wer_permille": 10001}]), ("line_wer", [{"line": "a", "wer_permille": 1}, {"line": "a", "wer_permille": 2}])):
        add("audio_gate", {**AUDIO, key: value})
    for key in AUDIO:
        add("audio_gate", {**AUDIO, key: None})
    add("audio_gate", {k: None for k in AUDIO})
    for contract in ({}, None, {"loudness_tolerance": -1}, {"voice_over_bed_min": 20000}, {"wer_max": 1000}, {"wer_max": 1001}, {"cut_hit_share_min": 0}, {"required_heard": []}, {"forbidden_heard": ["Speech"]}, {"required_heard": ["Rain", "it's"]},
                     {"loudness_target": 0, "true_peak_max": 10 ** 12}, {"unknown": 1}, {"z": 1, "a": 2}, 5, []):
        add("audio_gate", {**AUDIO, "contract": contract})
    for frames in ({"edge_f1": [450]}, {"edge_f1": [449]}, {"edge_f1": [None]}, {"edge_f1": [500], "mask_iou": [600]}, {"edge_f1": [500], "mask_iou": [599]}, {"edge_f1": [1, 2], "mask_iou": [1]}, {"edge_f1": [1], "depth_error": [1]}, {"edge_f1": [1], "identity_similarity": [1]},
                   {"edge_f1": [1], "depth_error": [-1], "x": 1}, {"edge_f1": [1], "depth_error": [-1]}, {"mask_iou": [1]}, {"edge_f1": [0, 0, 0, 1000, 1000], "mask_iou": [700, 700, 0, 0, 700]}, {"edge_f1": [None, None, 449, None]}):
        for thresholds in (None, {}, {"edge_f1_min": 1000}, {"edge_f1_min": 1001}, {"depth_error_max": 10 ** 12}, {"identity_similarity_min": 0}, {"mask_iou_min": 0, "edge_f1_min": 0}, {"z": 1}, 5):
            add("drift_verdict", {"frames": frames} if thresholds is None else {"frames": frames, "thresholds": thresholds})
    add("drift_verdict", {"frames": {"edge_f1": [0] * 100}})
    add("drift_verdict", {"frames": {"edge_f1": [1000] * 2048, "depth_error": [10 ** 12] * 2048}, "thresholds": {"depth_error_max": 0}})
    for key, low, high in (("palette_ab", 0, 10 ** 9), ("clip_white", 40, 41), ("clip_black", 0, 1000), ("detail_ratio", 549, 550), ("detail_ratio", 1800, 1801), ("chroma_ratio", 699, 1401)):
        for value in (low, high, None, high + 1, -1):
            add("look_gate", {"frames": [{"id": "f", "metrics": {**LOOK_METRICS, key: value}}]})
    for thresholds in ({"detail_min": 2000}, {"chroma_max": 1}, {"clip_white": 1000}, {"clip_white": 1001}, {"palette_ab": 10 ** 9}, {"palette_ab": 10 ** 9 + 1}, {"nope": 1}, None):
        add("look_gate", {"frames": [{"id": "f", "metrics": LOOK_METRICS}], "thresholds": thresholds})
    add("look_gate", {"frames": [{"id": "f", "metrics": LOOK_METRICS}, {"id": "f", "metrics": LOOK_METRICS}]})
    add("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 5}, {"id": "a", "t_ms": 6}], "lanes": [{"lane": "l", "references": []}]})
    add("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 5, "end_ms": 4}], "lanes": [{"lane": "l", "references": []}]})
    add("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 5}], "aliases": {"a": "a"}, "lanes": [{"lane": "l", "references": []}]})
    add("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 5}], "lanes": [{"lane": "l", "references": ["a", "a"]}]})
    add("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 5}], "lanes": [{"lane": "l", "references": []}, {"lane": "l", "references": []}]})
    add("cue_vocabulary_check", {"provided": [{"id": "1", "t_ms": 5}, {"id": "0", "t_ms": 6}], "aliases": {"9": "1", "2": "0"}, "lanes": [{"lane": "l", "references": ["9", "2", "1"]}]})
    return out


def _get(root, path):
    node = root
    for name in path:
        node = node[name]
    return node


def lexical_vectors():
    out = []
    for tool, seed, path in (("cue_vocabulary_check", {"provided": [{"id": "a", "t_ms": 1000}], "lanes": [{"lane": "l", "references": ["a"]}]}, ("", '"t_ms":1000', '"t_ms":TOKEN')),
                             ("look_gate", {"frames": [{"id": "f", "metrics": LOOK_METRICS}]}, ("", '"clip_white":30', '"clip_white":TOKEN')),
                             ("audio_gate", AUDIO, ("", '"integrated_lufs":-16500', '"integrated_lufs":TOKEN'))):
        _, key, form = path
        head, tail = form.split("TOKEN")
        out += lexical(tool, seed, (head, key, tail))
    return out


def fuzz(count, seed):
    rng = random.Random(seed)
    ids = lambda: rng.choice(("a", "b", "c", "d", "1", "0", "x:y", "s.t", "-bad", "", "a" * 64, "a" * 65, 5, None))
    ms = lambda: rng.choice((0, 1, rng.randint(0, 86400000), rng.randint(0, 100000), 86400000, 86400001, -1, None, "1", True))
    metric_value = lambda: rng.choice((rng.randint(-1000, 1000), rng.randint(-10 ** 12, 10 ** 12), 10 ** 12, -10 ** 12, 10 ** 12 + 1, 0, 1, -1, None, "1", True))
    good = lambda: rng.random() < 0.97

    def shots():
        names = rng.sample(("sharp", "black", "subject_motion", "luma", "tone", "constructor", "m_1"), rng.randint(1, 7))
        if rng.random() < .6:
            names = ["sharp", "black", "subject_motion", "luma"] + names[:1]
        names = list(dict.fromkeys(names))
        out, at = [], 0
        for _ in range(rng.randint(1, 12)):
            start = at + rng.choice((0, 0, rng.randint(0, 5000)))
            end = start + rng.randint(1, 30000)
            value = {"start_ms": start, "end_ms": end, "camera": rng.choice(CAMERAS), "metrics": {n: rng.randint(-1000, 1000) if rng.random() < .9 else rng.randint(-10 ** 12, 10 ** 12) for n in names}}
            if not good():
                value[rng.choice(list(value))] = rng.choice(BAD)
            out.append(value)
            at = end
        return out, names

    def bands(names):
        def triple():
            a = sorted(rng.randint(-1000, 1000) for _ in range(3))
            return a if good() else rng.choice(BAD + ([3, 2, 1],))
        return {"moving_share": rng.randint(0, 1000) if good() else rng.choice(BAD), "metrics": {n: triple() for n in names}}

    def rule(names):
        return {"metric": rng.choice(names + ["moving_share"]) if good() else rng.choice(BAD), "op": rng.choice((">=", "<=")) if good() else rng.choice((">", "=", 5)), "target": rng.randint(-1500, 1500) if good() else rng.choice(BAD)}

    def cinematic():
        items, names = shots()
        end = max(s["end_ms"] if type(s.get("end_ms")) is int and s["end_ms"] > 0 else 0 for s in items) or 1000
        args = {"shots": items}
        kind = rng.random()
        if kind < .5:
            args["bands"] = bands(names)
        else:
            args["rules"] = [rule(names) for _ in range(rng.randint(1, 5))]
            if rng.random() < .2:
                args["bands"] = bands(names)
        if rng.random() < .5:
            segments = []
            for k in range(rng.randint(1, 5)):
                a = rng.randint(0, end)
                segments.append({"id": f"s{k}" if good() else ids(), "start_ms": a, "end_ms": a + rng.randint(1, 20000) if good() else ms()})
            args["segments"] = segments
        return "cinematic_gate", args

    def audio():
        def opt(make):
            return None if rng.random() < .15 else make()
        cuts = rng.randint(0, 200)
        args = {"integrated_lufs": opt(lambda: rng.randint(-18000, -14000)), "true_peak_dbtp": opt(lambda: rng.randint(-2000, 0)), "voice_over_bed_db": opt(lambda: rng.randint(10000, 17000)), "cuts": opt(lambda: cuts),
                "cuts_with_hit": opt(lambda: rng.randint(0, cuts + (0 if good() else 3))), "heard": opt(lambda: rng.sample(("Speech", "speech", "Music", "MUSIC", "Sine wave", "Rain"), rng.randint(0, 4))),
                "line_wer": opt(lambda: [{"line": f"l{k}", "wer_permille": rng.randint(0, 200)} for k in range(rng.randint(1, 5))])}
        if rng.random() < .3:
            args["contract"] = rng.choice(({"wer_max": rng.randint(0, 1000)}, {"loudness_target": rng.randint(-20000, 0), "loudness_tolerance": rng.randint(0, 3000)}, {"required_heard": ["Rain"], "forbidden_heard": ["speech"]}, {"voice_over_bed_min": 16000}, {"cut_hit_share_min": rng.randint(0, 1000), "true_peak_max": rng.randint(-3000, 0)}))
        return "audio_gate", args

    def drift():
        n = rng.randint(1, 40)
        value = lambda top: None if rng.random() < .1 else rng.randint(0, top)
        frames = {"edge_f1": [value(1000) for _ in range(n)]}
        thresholds = {}
        for name, top, key in (("mask_iou", 1000, "mask_iou_min"), ("depth_error", 10 ** 6, "depth_error_max"), ("identity_similarity", 1000, "identity_similarity_min")):
            if rng.random() < .5:
                frames[name] = [value(top) for _ in range(n if good() else n + 1)]
                if name != "mask_iou" and good():
                    thresholds[key] = rng.randint(0, top)
        if rng.random() < .4:
            thresholds["edge_f1_min"] = rng.randint(0, 1000)
        args = {"frames": frames}
        if thresholds or rng.random() < .5:
            args["thresholds"] = thresholds
        return "drift_verdict", args

    def cues():
        names = ["a", "b", "c", "d", "e", "1", "0"]
        provided = [{"id": n, "t_ms": rng.randint(0, 1000)} for n in rng.sample(names, rng.randint(1, 5))]
        for row in provided:
            if rng.random() < .3:
                row["end_ms"] = row["t_ms"] + rng.randint(0 if good() else -5, 100)
        pool = names + ["p", "q", "r"]
        args = {"provided": provided, "lanes": [{"lane": f"l{k}", "references": rng.sample(pool, rng.randint(0, 6))} for k in range(rng.randint(1, 3))]}
        if rng.random() < .6:
            taken = {row["id"] for row in provided}
            args["aliases"] = {k: rng.choice(pool) for k in rng.sample(["p", "q", "r", "s"], rng.randint(0, 4)) if k not in taken}
        if rng.random() < .6:
            args["orders"] = [{"beat": f"b{k}", "sequence": rng.sample(pool, rng.randint(2, 5))} for k in range(rng.randint(0, 3))]
        if rng.random() < .6:
            args["min_gaps"] = [{"rule": f"g{k}", "after": rng.choice(pool), "next": rng.choice(pool), "min_ms": rng.randint(0, 500)} for k in range(rng.randint(0, 3))]
        return "cue_vocabulary_check", args

    def look():
        frames = []
        for k in range(rng.randint(1, 5)):
            metrics = {key: None if rng.random() < .05 else rng.randint(0, 2 * value) for key, value in LOOK_METRICS.items()}
            frames.append({"id": f"f{k}", "metrics": metrics})
        args = {"frames": frames}
        if rng.random() < .4:
            args["thresholds"] = rng.choice(({"detail_min": rng.randint(0, 900)}, {"chroma_max": rng.randint(800, 3000), "clip_white": rng.randint(0, 1000)}, {"palette_ab": rng.randint(0, 20000)}))
        return "look_gate", args

    def bands_tool():
        return "reference_bands", {"shots": shots()[0]}

    out = []
    makers = (cinematic, bands_tool, audio, drift, cues, look)
    for _ in range(count):
        tool, args = rng.choice(makers)()
        if rng.random() < .05:
            paths = [p for p in _paths(args) if p]
            path = rng.choice(paths)
            args = _set(args, path, rng.choice(BAD)) if rng.random() < .7 else _drop(args, path)
        elif rng.random() < .02:
            args["extra" if rng.random() < .5 else "aa"] = 1
        out.append((tool, _text(args)))
    return out

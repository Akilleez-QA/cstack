"""Foundation Film's judgements, including parity with the Endoforge producers' own float logic. Stdlib only."""
import random
import unittest

from foundation_film.tools import run

METRICS = ("sharp", "black", "subject_motion", "luma", "dof", "sat")
BANDS = {"moving_share": 508, "metrics": {"sharp": [130039, 223214, 338637], "black": [30, 47, 184],
                                         "subject_motion": [800, 1833, 10604], "luma": [158, 329, 584]}}


def ok(name, arguments):
    failed, assessment, receipt = run(name, arguments)
    assert not failed, receipt["error"]
    return assessment, receipt["result"]


def refused(test, name, arguments):
    failed, assessment, receipt = run(name, arguments)
    test.assertTrue(failed, arguments)
    test.assertEqual((assessment, receipt["status"], receipt["result"]), ("tool_error", "error", None))
    test.assertTrue(receipt["evidence"])
    return receipt["error"]


def random_film(rng, n):
    shots, t = [], 0
    for _ in range(n):
        d = rng.randint(400, 30000)
        shots.append({"start_ms": t, "end_ms": t + d, "camera": rng.choice(["static", "pan", "tilt", "push/pull"]),
                      "metrics": {"sharp": rng.randint(20000, 900000), "black": rng.randint(0, 900),
                                  "subject_motion": rng.randint(0, 20000), "luma": rng.randint(20, 900),
                                  "dof": rng.randint(500, 3000), "sat": rng.randint(0, 800)}})
        t += d
    return shots


def filmgate_reference(shots, bands, segments):
    """filmgate.py's segment logic in floats (seconds and raw units), as shipped in forge/endoforge/tools/film."""
    sh = [{"start": s["start_ms"] / 1000, "end": s["end_ms"] / 1000, "camera": s["camera"],
           **{k: s["metrics"][k] / 1000 for k in METRICS}} for s in shots]
    B = {"moving_share": bands["moving_share"] / 1000, **{k: [v / 1000 for v in t] for k, t in bands["metrics"].items()}}
    rules = [["moving_share", ">=", B["moving_share"]], ["sharp", "<=", B["sharp"][2]],
             ["sharp", ">=", B["sharp"][0] / 2], ["black", "<=", max(B["black"][2], 0.35)],
             ["subject_motion", ">=", B["subject_motion"][0]], ["luma", ">=", B["luma"][0]]]
    out = []
    for s in segments:
        start, end = s["start_ms"] / 1000, s["end_ms"] / 1000
        parts = [(x, max(0.0, min(x["end"], end) - max(x["start"], start))) for x in sh]
        parts = [(x, w) for x, w in parts if w > 0]
        W = sum(w for _, w in parts) or 1
        m = {k: sum(x[k] * w for x, w in parts) / W for k in METRICS}
        m["moving_share"] = sum(w for x, w in parts if x["camera"] != "static") / W
        out.append([(k, m[k], m[k] >= v if op == ">=" else m[k] <= v, v) for k, op, v in rules])
    return out


def bands_reference(values, weights, q):
    """numpy searchsorted(cumsum(w)/sum(w), q) over values sorted ascending, in floats."""
    order = sorted(range(len(values)), key=lambda k: values[k])
    total, running = float(sum(weights)), 0.0
    for k in order:
        running += weights[k]
        if running / total >= q:
            return values[k]
    return values[order[-1]]


class CinematicGateTests(unittest.TestCase):
    def test_parity_with_filmgate_on_random_films(self):
        rng = random.Random(4377)
        for trial in range(60):
            shots = random_film(rng, rng.randint(1, 30))
            end = shots[-1]["end_ms"]
            cuts = sorted(rng.sample(range(1, end), 3))
            segments = [{"id": f"b{i}", "start_ms": a, "end_ms": b}
                        for i, (a, b) in enumerate(zip([0] + cuts, cuts + [end]))]
            _, result = ok("cinematic_gate", {"shots": shots, "bands": BANDS, "segments": segments})
            for seg, expected in zip(result["segments"], filmgate_reference(shots, BANDS, segments)):
                for c, (metric, value, passed, target) in zip(seg["checks"], expected):
                    self.assertEqual(c["check"], metric)
                    self.assertLessEqual(abs(c["value"] / 1000 - value), 0.001, (trial, seg["id"], metric))
                    if abs(value - target) > 0.002:  # away from the rounding edge the verdicts must agree
                        self.assertEqual(c["status"] == "pass", passed, (trial, seg["id"], metric))

    def test_default_rules_are_exact_and_the_whole_film_is_the_default_segment(self):
        shots = [{"start_ms": 0, "end_ms": 1000, "camera": "pan",
                  "metrics": {"sharp": 65020, "black": 350, "subject_motion": 800, "luma": 158}}]
        assessment, result = ok("cinematic_gate", {"shots": shots, "bands": BANDS})
        self.assertEqual(assessment, "thresholds_met")
        self.assertEqual([(r["metric"], r["op"], r["target"]) for r in result["rules"]],
                         [("moving_share", ">=", 508), ("sharp", "<=", 338637), ("sharp", ">=", 65020),
                          ("black", "<=", 350), ("subject_motion", ">=", 800), ("luma", ">=", 158)])
        self.assertEqual([(s["id"], s["start_ms"], s["end_ms"]) for s in result["segments"]], [("film", 0, 1000)])
        shots[0]["metrics"]["sharp"] = 65019  # just under p25 / 2
        assessment, result = ok("cinematic_gate", {"shots": shots, "bands": BANDS})
        self.assertEqual((assessment, result["segments"][0]["failing"]), ("thresholds_not_met", ["sharp"]))

    def test_a_static_void_fails_and_an_uncovered_segment_is_not_scored(self):
        shots = [{"start_ms": 0, "end_ms": 10000, "camera": "static",
                  "metrics": {"sharp": 700000, "black": 725, "subject_motion": 100, "luma": 90}}]
        _, result = ok("cinematic_gate", {"shots": shots, "bands": BANDS,
                                          "segments": [{"id": "b1", "start_ms": 0, "end_ms": 10000}]})
        self.assertEqual(result["segments"][0]["failing"], ["moving_share", "sharp", "black", "subject_motion", "luma"])
        assessment, result = ok("cinematic_gate", {"shots": shots, "rules": [
            {"metric": "luma", "op": ">=", "target": 1}], "segments": [{"id": "late", "start_ms": 20000, "end_ms": 21000}]})
        self.assertEqual((assessment, result["rule_source"], result["segments"][0]["checks"][0]["status"]),
                         ("not_scored", "caller", "not_measured"))

    def test_malformed_films_are_refused(self):
        shot = {"start_ms": 0, "end_ms": 1000, "camera": "pan", "metrics": {"sharp": 1, "black": 1,
                                                                           "subject_motion": 1, "luma": 1}}
        later = dict(shot, start_ms=500, end_ms=2000)
        for arguments in ({"shots": [shot]}, {"shots": [shot, later], "bands": BANDS},
                          {"shots": [dict(shot, camera="dolly")], "bands": BANDS},
                          {"shots": [dict(shot, metrics={"sharp": 1.5})], "bands": BANDS},
                          {"shots": [dict(shot, metrics={"moving_share": 1})], "bands": BANDS},
                          {"shots": [dict(shot, metrics={"sharp": 1})], "bands": BANDS},
                          {"shots": [shot], "bands": dict(BANDS, metrics={"sharp": [3, 2, 1]})},
                          {"shots": [shot], "rules": [{"metric": "loudness", "op": ">=", "target": 1}]},
                          {"shots": [shot], "bands": BANDS, "segments": [{"id": "a", "start_ms": 5, "end_ms": 5}]},
                          {"shots": [shot], "bands": BANDS, "path": "/tmp/film.mp4"}):
            refused(self, "cinematic_gate", arguments)


class ReferenceBandsTests(unittest.TestCase):
    def test_parity_with_the_weighted_percentile_used_for_the_reference_bands(self):
        rng = random.Random(26)
        for _ in range(60):
            shots = random_film(rng, rng.randint(1, 64))
            _, result = ok("reference_bands", {"shots": shots})
            durations = [s["end_ms"] - s["start_ms"] for s in shots]
            for metric in METRICS:
                values = [s["metrics"][metric] for s in shots]
                self.assertEqual(result["bands"]["metrics"][metric],
                                 [bands_reference(values, durations, q) for q in (0.25, 0.5, 0.75)])
            self.assertEqual(result["duration_ms"], [bands_reference(durations, durations, q) for q in (.25, .5, .75)])
            moving = sum(d for s, d in zip(shots, durations) if s["camera"] != "static") / sum(durations)
            self.assertLessEqual(abs(result["bands"]["moving_share"] / 1000 - moving), 0.0005)

    def test_bands_feed_the_gate_and_the_reference_passes_its_own_gate_on_average(self):
        shots = [{"start_ms": i * 2000, "end_ms": (i + 1) * 2000, "camera": "pan" if i % 2 else "static",
                  "metrics": {"sharp": 200000 + i, "black": 40, "subject_motion": 2000 + i, "luma": 330}}
                 for i in range(8)]
        _, bands = ok("reference_bands", {"shots": shots})
        self.assertEqual((bands["n_shots"], bands["total_ms"], bands["bands"]["moving_share"]), (8, 16000, 500))
        assessment, _ = ok("cinematic_gate", {"shots": shots, "bands": bands["bands"]})
        self.assertEqual(assessment, "thresholds_met")


class AudioGateTests(unittest.TestCase):
    GOOD = {"integrated_lufs": -16200, "true_peak_dbtp": -1500, "voice_over_bed_db": 13500, "cuts": 64,
            "cuts_with_hit": 52, "heard": ["Speech", "music", "Thunder"],
            "line_wer": [{"line": "b1-1", "wer_permille": 0}, {"line": "b2-1", "wer_permille": 50}]}

    def test_a_mix_inside_the_contract_meets_it(self):
        assessment, result = ok("audio_gate", self.GOOD)
        self.assertEqual((assessment, result["failing"], result["contract_overrides"]), ("thresholds_met", [], []))
        self.assertEqual(result["checks"][3]["value"], 813)  # 52 of 64 cuts

    def test_each_breach_names_its_check(self):
        for change, failing in (({"integrated_lufs": -34000}, "integrated_loudness"),
                                ({"integrated_lufs": -14900}, "integrated_loudness"),
                                ({"true_peak_dbtp": -900}, "true_peak"),
                                ({"voice_over_bed_db": 15100}, "voice_over_bed"),
                                ({"cuts_with_hit": 50}, "cut_hit_share"),  # 78 %: the reference's own share
                                ({"heard": ["Speech", "Chirp tone"]}, "heard_required_missing"),
                                ({"heard": ["Speech", "Music", "Sine wave"]}, "heard_forbidden_present"),
                                ({"line_wer": [{"line": "b9-2", "wer_permille": 51}]}, "worst_line_wer")):
            assessment, result = ok("audio_gate", dict(self.GOOD, **change))
            self.assertEqual((assessment, result["failing"]), ("thresholds_not_met", [failing]), change)

    def test_unmeasured_is_not_scored_and_overrides_are_reported(self):
        assessment, result = ok("audio_gate", dict(self.GOOD, line_wer=None))
        self.assertEqual((assessment, result["failing"]), ("not_scored", ["worst_line_wer"]))
        assessment, result = ok("audio_gate", dict(self.GOOD, cuts=0, cuts_with_hit=0))
        self.assertEqual(assessment, "not_scored")
        assessment, result = ok("audio_gate", dict(self.GOOD, contract={"forbidden_heard": ["Thunder"]}))
        self.assertEqual((assessment, result["contract_overrides"]), ("thresholds_not_met", ["forbidden_heard"]))
        for bad in (dict(self.GOOD, cuts_with_hit=65), dict(self.GOOD, contract={"wer_max": 1001}),
                    dict(self.GOOD, contract={"loudness_target": -16.0}), {"integrated_lufs": -16000}):
            refused(self, "audio_gate", bad)


class DriftVerdictTests(unittest.TestCase):
    def test_parity_with_driftgate_every_frame_rule(self):
        rng = random.Random(90)
        for _ in range(60):
            n = rng.randint(1, 121)
            edge = [rng.randint(300, 1000) for _ in range(n)]
            iou = [rng.randint(450, 1000) for _ in range(n)]
            _, result = ok("drift_verdict", {"frames": {"edge_f1": edge, "mask_iou": iou}})
            bad = [i for i in range(n) if not (edge[i] / 1000 >= 0.45 and iou[i] / 1000 >= 0.6)]
            self.assertEqual(result["first_failing_frame"], bad[0] if bad else None)
            self.assertEqual(result["verdict"], "thresholds_not_met" if bad else "thresholds_met")
            self.assertEqual(result["metrics"]["edge_f1"]["worst"], min(edge))

    def test_a_collapse_fails_even_when_the_mean_would_pass(self):
        edge = [980] * 100 + [80] * 21
        _, result = ok("drift_verdict", {"frames": {"edge_f1": edge}})
        self.assertGreater(result["metrics"]["edge_f1"]["mean"], 450)
        self.assertEqual((result["verdict"], result["first_failing_frame"], result["failing_frames"]),
                         ("thresholds_not_met", 100, 21))
        self.assertEqual(result["worst_frame"], {"frame": 100, "values": {"edge_f1": 80}})

    def test_optional_metrics_need_thresholds_and_nulls_are_not_scored(self):
        frames = {"edge_f1": [900, 900], "depth_error": [100, 260], "identity_similarity": [None, 800]}
        error = refused(self, "drift_verdict", {"frames": frames})
        self.assertIn("no calibrated default", error)
        assessment, result = ok("drift_verdict", {"frames": frames, "thresholds": {
            "depth_error_max": 250, "identity_similarity_min": 700}})
        self.assertEqual((assessment, result["first_failing_frame"], result["metrics"]["depth_error"]["worst_frame"]),
                         ("thresholds_not_met", 1, 1))
        assessment, _ = ok("drift_verdict", {"frames": dict(frames, depth_error=[100, 200]), "thresholds": {
            "depth_error_max": 250, "identity_similarity_min": 700}})
        self.assertEqual(assessment, "not_scored")  # frame 0 identity unmeasured
        for bad in ({"frames": {"edge_f1": [1, 2], "mask_iou": [1]}}, {"frames": {"mask_iou": [1]}},
                    {"frames": {"edge_f1": [1]}, "thresholds": {"mask_iou_min": 600}},
                    {"frames": {"edge_f1": [True]}}):
            refused(self, "drift_verdict", bad)


class CueVocabularyTests(unittest.TestCase):
    PROVIDED = [{"id": "b4:w:heat", "t_ms": 41000, "end_ms": 41400}, {"id": "b4:w:vapor", "t_ms": 42500},
                {"id": "b11:w:plant", "t_ms": 101000, "end_ms": 101500}, {"id": "b12:w:and", "t_ms": 104200}]

    def test_a_closed_vocabulary_meets_the_contract(self):
        assessment, result = ok("cue_vocabulary_check", {
            "provided": self.PROVIDED, "aliases": {"b4:heat-in": "b4:w:heat"},
            "lanes": [{"lane": "scene-b04", "references": ["b4:heat-in", "b4:w:vapor"]},
                      {"lane": "sfx-mix", "references": ["b4:w:heat"]}],
            "orders": [{"beat": "b4", "sequence": ["b4:heat-in", "b4:w:vapor"]}],
            "min_gaps": [{"rule": "b11-voice-free", "after": "b11:w:plant", "next": "b12:w:and", "min_ms": 2600}]})
        self.assertEqual((assessment, result["missing_ids"], result["aliases_used"]), ("thresholds_met", [], 1))
        self.assertEqual(result["lanes"][0]["by_alias"], [{"id": "b4:heat-in", "to": "b4:w:heat"}])
        self.assertEqual(result["gaps"][0]["gap_ms"], 2700)

    def test_invented_names_order_and_gap_breaches_are_listed(self):
        assessment, result = ok("cue_vocabulary_check", {
            "provided": self.PROVIDED, "aliases": {"slam-9": "b13:w:loop"},
            "lanes": [{"lane": "scene-b04", "references": ["b4:heat", "b4:w:vapor"]}],
            "orders": [{"beat": "b4", "sequence": ["b4:w:vapor", "b4:w:heat"]}],
            "min_gaps": [{"rule": "tight", "after": "b11:w:plant", "next": "b12:w:and", "min_ms": 3000}]})
        self.assertEqual(assessment, "thresholds_not_met")
        self.assertEqual((result["missing_ids"], result["broken_aliases"]),
                         (["b4:heat"], [{"id": "slam-9", "to": "b13:w:loop"}]))
        self.assertEqual(result["orders"][0]["first_violation"],
                         {"index": 1, "id": "b4:w:heat", "t_ms": 41000, "previous_id": "b4:w:vapor",
                          "previous_t_ms": 42500})
        self.assertEqual([c["check"] for c in result["checks"] if c["status"] == "fail"],
                         ["missing_ids", "broken_aliases", "order:b4", "gap:tight"])

    def test_ambiguous_or_malformed_vocabularies_are_refused(self):
        lanes = [{"lane": "a", "references": ["b4:w:heat"]}]
        for bad in ({"provided": self.PROVIDED, "lanes": lanes, "aliases": {"b4:w:heat": "b4:w:vapor"}},
                    {"provided": self.PROVIDED + [self.PROVIDED[0]], "lanes": lanes},
                    {"provided": self.PROVIDED, "lanes": lanes + lanes},
                    {"provided": self.PROVIDED, "lanes": [{"lane": "a", "references": ["x", "x"]}]},
                    {"provided": self.PROVIDED, "lanes": [{"lane": "a", "references": ["has space"]}]},
                    {"provided": [{"id": "x", "t_ms": 5, "end_ms": 4}], "lanes": lanes}):
            refused(self, "cue_vocabulary_check", bad)


LOOK = ("palette_ab", "palette_L", "median_L", "range_L", "clip_white", "clip_black", "detail_ratio", "chroma_ratio")
# lookgate.py receipts of the 14 rendered beats against their approved concept frames (2026-10-26 reference run).
BEATS = {"b1": (12.9, 48.96, 71.78, 27.09, 0.675, 0.09, 0.723, 0.055),
         "b2": (13.29, 16.71, 36.13, 6.67, 0.0, 0.426, 0.433, 0.181),
         "b3": (8.42, 31.73, 38.21, 45.38, 0.0, 0.591, 0.211, 0.2),
         "b4": (9.9, 21.76, 28.79, 16.78, 0.0, 0.0, 0.23, 1.108),
         "b5": (7.65, 16.85, 14.17, 11.49, 0.034, 0.004, 0.256, 0.662),
         "b6": (6.43, 10.05, 3.49, 40.19, 0.0, 0.0, 0.399, 0.892),
         "b7": (11.11, 28.28, 37.57, 3.48, 0.259, 0.0, 0.082, 1.459),
         "b8": (7.93, 28.81, 32.88, 31.93, 0.0, 0.0, 0.18, 0.555),
         "b9": (17.38, 16.93, 10.27, 50.51, 0.0, 0.091, 0.065, 0.248),
         "b10": (8.76, 3.98, 5.07, 6.4, 0.0, 0.0, 0.561, 0.611),
         "b11": (10.15, 15.92, 31.2, 8.83, 0.001, 0.566, 0.212, 0.091),
         "b12": (5.17, 26.35, 29.99, 20.34, 0.0, 0.0, 0.168, 1.727),
         "b13": (5.43, 21.19, 23.05, 21.25, 0.0, 0.68, 0.407, 0.201),
         "end": (11.23, 28.78, 0.0, 77.45, 0.0, 0.0, 2.366, 5.917)}
LOOKGATE_T = {"palette_ab": 6.0, "palette_L": 8.0, "median_L": 10.0, "range_L": 15.0, "clip_white": 0.04,
              "clip_black": 0.08, "detail_min": 0.55, "detail_max": 1.8, "chroma_min": 0.7, "chroma_max": 1.4}


def look_frame(frame_id, values):
    return {"id": frame_id, "metrics": {k: None if v is None else round(v * 1000) for k, v in zip(LOOK, values)}}


def lookgate_reference(m, T=LOOKGATE_T):
    """lookgate.py's checks in floats, as shipped in forge/endoforge/tools/film."""
    checks = {"palette_ab": m["palette_ab"] <= T["palette_ab"], "palette_L": m["palette_L"] <= T["palette_L"],
              "median_L": m["median_L"] <= T["median_L"], "range_L": m["range_L"] <= T["range_L"],
              "clip_white": m["clip_white"] <= T["clip_white"], "clip_black": m["clip_black"] <= T["clip_black"],
              "detail": T["detail_min"] <= m["detail_ratio"] <= T["detail_max"],
              "chroma": T["chroma_min"] <= m["chroma_ratio"] <= T["chroma_max"]}
    return [k for k, v in checks.items() if not v]


class LookGateTests(unittest.TestCase):
    def test_parity_with_lookgate_on_random_frames(self):
        rng = random.Random(74)
        for _ in range(200):
            values = (round(rng.uniform(0, 12), 2), round(rng.uniform(0, 16), 2), round(rng.uniform(0, 20), 2),
                      round(rng.uniform(0, 30), 2), round(rng.uniform(0, 0.08), 3), round(rng.uniform(0, 0.16), 3),
                      round(rng.uniform(0.2, 2.4), 3), round(rng.uniform(0.4, 1.8), 3))
            assessment, result = ok("look_gate", {"frames": [look_frame("k", values)]})
            failed = lookgate_reference(dict(zip(LOOK, values)))
            self.assertEqual([c.replace("_ratio", "") for c in result["frames"][0]["failing"]], failed, values)
            self.assertEqual(assessment, "thresholds_not_met" if failed else "thresholds_met")

    def test_the_target_passes_against_itself_and_every_rendered_beat_fails(self):
        assessment, result = ok("look_gate", {"frames": [look_frame("self", (0, 0, 0, 0, 0, 0, 1, 1))]})
        self.assertEqual((assessment, result["role"], result["failing_frames"]), ("thresholds_met", "rejection_alarm", []))
        frames = [look_frame(k, v) for k, v in BEATS.items()]
        assessment, result = ok("look_gate", {"frames": frames})
        self.assertEqual((assessment, result["failing_frames"]), ("thresholds_not_met", list(BEATS)))
        for frame, values in zip(result["frames"], BEATS.values()):
            self.assertEqual([c.replace("_ratio", "") for c in frame["failing"]],
                             lookgate_reference(dict(zip(LOOK, values))), frame["id"])
        # Detail is the common failure, not the only one: b1 (0.723) and b10 (0.561) are inside the detail band.
        self.assertEqual([f["id"] for f in result["frames"] if "detail_ratio" not in f["failing"]], ["b1", "b10"])

    def test_one_failing_keyframe_fails_the_set_and_nulls_are_not_scored(self):
        good = look_frame("k00", (2, 3, 1, 4, 0, 0, 0.99, 1.05))
        assessment, result = ok("look_gate", {"frames": [good, look_frame("k01", (2, 3, 1, 4, 0, 0, 0.3, 1))]})
        self.assertEqual((assessment, result["failing_frames"], result["frames"][1]["failing"]),
                         ("thresholds_not_met", ["k01"], ["detail_ratio"]))
        assessment, result = ok("look_gate", {"frames": [good, look_frame("k01", (2, 3, 1, 4, 0, None, 1, 1))]})
        self.assertEqual((assessment, result["frames"][1]["not_measured"]), ("not_scored", ["clip_black"]))

    def test_caller_thresholds_are_reported_and_malformed_requests_refused(self):
        frame = look_frame("k", (7, 3, 1, 4, 0, 0, 1, 1))
        assessment, result = ok("look_gate", {"frames": [frame], "thresholds": {"palette_ab": 7500}})
        self.assertEqual((assessment, result["threshold_sources"]["palette_ab"], result["threshold_sources"]["palette_L"]),
                         ("thresholds_met", "caller", "lookgate_default"))
        self.assertEqual(run("look_gate", {"frames": [frame], "thresholds": {"palette_ab": 7500}})[2]["evidence"][-1]
                         ["evidence"]["basis"]["kind"], "caller")
        metrics = frame["metrics"]
        for bad in ({"frames": []}, {"frames": [frame, frame]}, {"frames": [{"id": "k", "metrics": {}}]},
                    {"frames": [{"id": "k", "metrics": dict(metrics, clip_white=1001)}]},
                    {"frames": [{"id": "k", "metrics": dict(metrics, median_L=-1)}]},
                    {"frames": [{"id": "k", "metrics": dict(metrics, detail_ratio=0.99)}]},
                    {"frames": [frame], "thresholds": {"detail_min": 2000}},
                    {"frames": [frame], "thresholds": {"vibe": 1}}, {"frames": [frame], "target": "concept.png"}):
            refused(self, "look_gate", bad)


if __name__ == "__main__":
    unittest.main()

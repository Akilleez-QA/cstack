from copy import deepcopy

DRAFT = "https://json-schema.org/draft/2020-12/schema"
TEXT = {"type": "string", "maxLength": 1024}
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9:_.\\-]{0,63}$"}
METRIC = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,31}$"}
LABEL = {"type": "string", "pattern": "^[ -~]{1,96}$"}
MEASURE = {"type": "integer", "minimum": -10 ** 12, "maximum": 10 ** 12}
PERMILLE = {"type": "integer", "minimum": 0, "maximum": 1000}
MS = {"type": "integer", "minimum": 0, "maximum": 86_400_000}
NULL = {"type": "null"}
VERDICTS = ["thresholds_met", "thresholds_not_met", "not_scored"]
STATUS = {"enum": ["pass", "fail", "not_measured"]}


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


BOUNDARY = obj({"observation_only": {"const": True}, "acceptance_decision": {"const": False},
                "control_action": {"const": False}})
EVIDENCE_ENTRY = obj({"applies_to": TEXT, "evidence": obj({
    "basis": obj({"kind": {"enum": ["cited", "derived", "caller"]}, "source": TEXT, "note": TEXT}),
    "status": {"enum": ["CHECK", "RECORDED"]}})})
CHECK = obj({"check": {"type": "string", "maxLength": 96}, "value": nullable(MEASURE), "min": nullable(MEASURE),
             "max": nullable(MEASURE), "status": STATUS})


def output(assessments, result):
    receipt = obj({"tool": TEXT, "version": TEXT, "status": {"enum": ["ok", "error"]},
                   "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "boundary": BOUNDARY,
                   "result": {"oneOf": [NULL, result]}, "error": {"type": ["string", "null"]},
                   "evidence": array(EVIDENCE_ENTRY, 1, 16)})
    return {"$schema": DRAFT, **obj({"tool": TEXT, "assessment": {"enum": [*assessments, "tool_error"]},
                                     "formal_proof": {"const": False}, "runtime_goal_acceptance": {"const": False},
                                     "receipt": receipt})}


def inputs(properties, required=None):
    return {"$schema": DRAFT, **obj(properties, required)}


SHOT = obj({"start_ms": MS, "end_ms": MS, "camera": {"enum": ["static", "pan", "tilt", "push/pull"]},
            "metrics": mapping(METRIC, MEASURE, 32, 1)})
SHOTS = array(SHOT, 1, 400)
TRIPLE = array(MEASURE, 3, 3)
BANDS = obj({"moving_share": PERMILLE, "metrics": mapping(METRIC, TRIPLE, 32)})
RULE = obj({"metric": METRIC, "op": {"enum": [">=", "<="]}, "target": MEASURE})
SEGMENT = obj({"id": ID, "start_ms": MS, "end_ms": MS})
SEGMENT_OUT = obj({"id": ID, "start_ms": MS, "end_ms": MS, "covered_ms": MS, "verdict": {"enum": VERDICTS},
                   "measured": mapping(METRIC, MEASURE, 33), "checks": array(CHECK, 1, 32),
                   "failing": array(METRIC, 0, 32)})

CONTRACT_LEVELS = ("loudness_target", "loudness_tolerance", "true_peak_max", "voice_over_bed_min",
                   "voice_over_bed_max")
CONTRACT_PROPS = {**{k: MEASURE for k in CONTRACT_LEVELS}, "cut_hit_share_min": PERMILLE,
                  "required_heard": array(LABEL, 0, 128), "forbidden_heard": array(LABEL, 0, 128), "wer_max": PERMILLE}
LINE_WER = obj({"line": ID, "wer_permille": count(10_000)})

DRIFT_METRICS = ("edge_f1", "mask_iou", "depth_error", "identity_similarity")
DRIFT_KEYS = ("edge_f1_min", "mask_iou_min", "depth_error_max", "identity_similarity_min")
SERIES = array(nullable(PERMILLE), 1, 2048)
DEPTH_SERIES = array(nullable({"type": "integer", "minimum": 0, "maximum": 10 ** 12}), 1, 2048)
DRIFT_THRESHOLDS = obj({"edge_f1_min": PERMILLE, "mask_iou_min": PERMILLE,
                        "depth_error_max": {"type": "integer", "minimum": 0, "maximum": 10 ** 12},
                        "identity_similarity_min": PERMILLE}, [])
FRAME_INDEX = count(2047)
METRIC_SUMMARY = obj({"threshold": {"type": "integer", "minimum": 0, "maximum": 10 ** 12},
                      "side": {"enum": ["min", "max"]}, "worst": nullable(MEASURE), "worst_frame": nullable(FRAME_INDEX),
                      "mean": nullable(MEASURE), "measured_frames": count(2048), "failing_frames": count(2048)})

ALIAS = obj({"id": ID, "to": ID})
MARKER = obj({"id": ID, "t_ms": MS, "end_ms": MS}, ["id", "t_ms"])

LOOK_METRICS = ("palette_ab", "palette_L", "median_L", "range_L", "clip_white", "clip_black", "detail_ratio",
                "chroma_ratio")
LOOK_PERMILLE = ("clip_white", "clip_black")
LOOK_KEYS = ("palette_ab", "palette_L", "median_L", "range_L", "clip_white", "clip_black", "detail_min", "detail_max",
             "chroma_min", "chroma_max")
LOOK_VALUE = {"type": "integer", "minimum": 0, "maximum": 10 ** 9}
LOOK_THRESHOLDS = obj({k: PERMILLE if k in LOOK_PERMILLE else LOOK_VALUE for k in LOOK_KEYS}, [])
LOOK_FRAME = obj({"id": ID, "metrics": obj({k: nullable(PERMILLE if k in LOOK_PERMILLE else LOOK_VALUE)
                                             for k in LOOK_METRICS})})
LOOK_FRAME_OUT = obj({"id": ID, "verdict": {"enum": VERDICTS}, "checks": array(CHECK, 8, 8),
                      "failing": array({"enum": list(LOOK_METRICS)}, 0, 8, uniqueItems=True),
                      "not_measured": array({"enum": list(LOOK_METRICS)}, 0, 8, uniqueItems=True)})

TOOLS = [
    {"name": "cinematic_gate",
     "description": "Per-segment cinematic gate: duration-weighted shot measures (filmstats.py, milli-units) against "
                    "reference bands (default filmgate.py rules) or explicit rules. Gates each beat on the same measures "
                    "the reference was measured on (I16). Observation only.",
     "inputSchema": inputs({"shots": SHOTS, "bands": BANDS, "rules": array(RULE, 1, 32),
                            "segments": array(SEGMENT, 1, 64)}, ["shots"]),
     "outputSchema": output(VERDICTS, obj({
         "verdict": {"enum": VERDICTS}, "rule_source": {"enum": ["caller", "reference_bands_default"]},
         "rules": array(RULE, 1, 32), "segments": array(SEGMENT_OUT, 1, 64), "failing_segments": array(ID, 0, 64)}))},
    {"name": "reference_bands",
     "description": "Duration-weighted p25/p50/p75 bands per shot metric, and moving_share, from a measured reference "
                    "(filmstats.py, milli-units). The output's bands feed cinematic_gate. Observation only.",
     "inputSchema": inputs({"shots": SHOTS}),
     "outputSchema": output(["bands_measured"], obj({
         "bands": obj({"moving_share": PERMILLE, "metrics": mapping(METRIC, TRIPLE, 32, 1)}),
         "duration_ms": array(MS, 3, 3), "n_shots": count(400, 1), "total_ms": MS,
         "quantiles_permille": {"const": [250, 500, 750]}}))},
    {"name": "audio_gate",
     "description": "Soundtrack against the mix contract: integrated loudness and true peak (milli-LU/dBTP), voice over "
                    "bed (milli-dB), share of cuts carrying a hit, AudioSet classes heard, WER per line (per-mille). "
                    "Null means not measured. Observation only.",
     "inputSchema": inputs({"integrated_lufs": nullable(MEASURE), "true_peak_dbtp": nullable(MEASURE),
                            "voice_over_bed_db": nullable(MEASURE), "cuts": nullable(count(100_000)),
                            "cuts_with_hit": nullable(count(100_000)), "heard": nullable(array(LABEL, 0, 128)),
                            "line_wer": nullable(array(LINE_WER, 1, 512)), "contract": obj(CONTRACT_PROPS, [])},
                           ["integrated_lufs", "true_peak_dbtp", "voice_over_bed_db", "cuts", "cuts_with_hit", "heard",
                            "line_wer"]),
     "outputSchema": output(VERDICTS, obj({
         "verdict": {"enum": VERDICTS}, "checks": array(CHECK, 7, 7), "contract": obj(CONTRACT_PROPS),
         "contract_overrides": array({"enum": list(CONTRACT_PROPS)}, 0, 9, uniqueItems=True),
         "heard": obj({"missing": nullable(array(LABEL, 0, 128)), "forbidden_present": nullable(array(LABEL, 0, 128))}),
         "wer": obj({"lines": count(512), "worst_line": nullable(ID), "failing_lines": array(ID, 0, 512)}),
         "failing": array({"type": "string", "maxLength": 96}, 0, 7)}))},
    {"name": "drift_verdict",
     "description": "Clip verdict for control-conditioned generation (I20): per-frame edge F1 and mask IoU, optional "
                    "depth error and identity similarity (driftgate.py, milli-units) against thresholds, gated on the "
                    "worst frame; first failing frame and worst-frame summary. Observation only.",
     "inputSchema": inputs({"frames": obj({"edge_f1": SERIES, "mask_iou": SERIES, "depth_error": DEPTH_SERIES,
                                           "identity_similarity": SERIES}, ["edge_f1"]),
                            "thresholds": DRIFT_THRESHOLDS}, ["frames"]),
     "outputSchema": output(VERDICTS, obj({
         "verdict": {"enum": VERDICTS}, "gate": {"const": "worst_frame"}, "frames": count(2048, 1),
         "first_failing_frame": nullable(FRAME_INDEX), "failing_frames": count(2048),
         "failing_frame_indices": array(FRAME_INDEX, 0, 64),
         "metrics": obj({k: METRIC_SUMMARY for k in DRIFT_METRICS}, ["edge_f1"]),
         "thresholds": obj(DRIFT_THRESHOLDS["properties"], ["edge_f1_min"]),
         "threshold_sources": obj({k: {"enum": ["caller", "driftgate_default"]} for k in DRIFT_KEYS}, ["edge_f1_min"]),
         "worst_frame": obj({"frame": FRAME_INDEX, "values": obj({k: nullable(MEASURE) for k in DRIFT_METRICS},
                                                                 ["edge_f1"])})}))},
    {"name": "cue_vocabulary_check",
     "description": "Static check of the shared cue vocabulary (I18): ids each lane references against the ids the "
                    "voice/markers provide (with aliases), per-beat required order and minimum gaps in time. Lists "
                    "missing ids, broken aliases, alias resolutions and order violations. Observation only.",
     "inputSchema": inputs({"provided": array(MARKER, 1, 1024),
                            "lanes": array(obj({"lane": ID, "references": array(ID, 0, 256, uniqueItems=True)}), 1, 64),
                            "aliases": mapping(ID, ID, 512),
                            "orders": array(obj({"beat": ID, "sequence": array(ID, 2, 64, uniqueItems=True)}), 0, 64),
                            "min_gaps": array(obj({"rule": ID, "after": ID, "next": ID, "min_ms": MS}), 0, 64)},
                           ["provided", "lanes"]),
     "outputSchema": output(VERDICTS, obj({
         "verdict": {"enum": VERDICTS}, "checks": array(CHECK, 2, 130), "missing_ids": array(ID, 0, 32768),
         "broken_aliases": array(ALIAS, 0, 512),
         "lanes": array(obj({"lane": ID, "references": count(256), "direct": count(256),
                             "by_alias": array(ALIAS, 0, 256), "missing": array(ID, 0, 256)}), 1, 64),
         "orders": array(obj({"beat": ID, "status": STATUS, "resolved": count(64), "unresolved": array(ID, 0, 64),
                              "first_violation": nullable(obj({"index": count(63), "id": ID, "t_ms": MS,
                                                               "previous_id": ID, "previous_t_ms": MS}))}), 0, 64),
         "gaps": array(obj({"rule": ID, "gap_ms": nullable({"type": "integer", "minimum": -86_400_000,
                                                            "maximum": 86_400_000}),
                            "min_ms": MS, "status": STATUS}), 0, 64),
         "provided": count(1024, 1), "aliases_used": count(512)}))},
    {"name": "look_gate",
     "description": "Rejection alarm for the look: per frame, lookgate.py's palette distance, exposure, contrast range, "
                    "clipping, detail and chroma ratios against an approved target frame (milli-units), every frame "
                    "against every threshold. A pass means not rejected; the client still accepts. Observation only.",
     "inputSchema": inputs({"frames": array(LOOK_FRAME, 1, 128), "thresholds": LOOK_THRESHOLDS}, ["frames"]),
     "outputSchema": output(VERDICTS, obj({
         "verdict": {"enum": VERDICTS}, "gate": {"const": "every_frame"}, "role": {"const": "rejection_alarm"},
         "frames": array(LOOK_FRAME_OUT, 1, 128), "failing_frames": array(ID, 0, 128),
         "thresholds": obj(LOOK_THRESHOLDS["properties"]),
         "threshold_sources": obj({k: {"enum": ["caller", "lookgate_default"]} for k in LOOK_KEYS})}))},
]


def tool_definitions():
    return deepcopy(TOOLS)

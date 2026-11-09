# Tool catalog

Generated from the code by the documentation generator (an adapted copy of foundation-robotics `tools/gen_docs.py`; it is not in this repository because the documentation change was docs-only). Do not edit by hand.

Protocol `foundation-film-jsonrpc/1`. Canonical tool inventory SHA-256 `4432e0305a84ed9aa1b269f2378f869b5b36850001e503ed1ffc0e018dd17558` (the same value `tools/build_manifest.py` prints as `inventory_sha256`).

## Bridge limits

| Limit | Value |
|---|---|
| `inputFrameBytes` | 65536 |
| `outputFrameBytes` | 1048576 |
| `jsonDepth` | 32 |
| `jsonNodes` | 16384 |
| `stringCharacters` | 1024 |
| `integerDigits` | 15 |
| `idCharacters` | 128 |

## Common result envelope

Every `tools/call` result has `structuredContent` with `tool`, `assessment`, `formal_proof` (always false), `runtime_goal_acceptance` (always false) and `receipt`. The receipt fields are:

| Field | Type and range | Required in its object |
|---|---|---|
| `receipt.tool` | string up to 1024 chars | yes |
| `receipt.version` | string up to 1024 chars | yes |
| `receipt.status` | one of `ok`, `error` | yes |
| `receipt.input_sha256` | string matching `^[0-9a-f]{64}$` | yes |
| `receipt.boundary` | object | yes |
| `receipt.boundary.observation_only` | const true | yes |
| `receipt.boundary.acceptance_decision` | const false | yes |
| `receipt.boundary.control_action` | const false | yes |
| `receipt.error` | string or null | yes |
| `receipt.evidence` | array[1..16] of object | yes |
| `receipt.evidence[].applies_to` | string up to 1024 chars | yes |
| `receipt.evidence[].evidence` | object | yes |
| `receipt.evidence[].evidence.basis` | object | yes |
| `receipt.evidence[].evidence.basis.kind` | one of `cited`, `derived`, `caller` | yes |
| `receipt.evidence[].evidence.basis.source` | string up to 1024 chars | yes |
| `receipt.evidence[].evidence.basis.note` | string up to 1024 chars | yes |
| `receipt.evidence[].evidence.status` | one of `CHECK`, `RECORDED` | yes |

## `cinematic_gate`

Per-segment cinematic gate: duration-weighted shot measures (filmstats.py, milli-units) against reference bands (default filmgate.py rules) or explicit rules. Gates each beat on the same measures the reference was measured on (I16). Observation only.

Assessments: `thresholds_met`, `thresholds_not_met`, `not_scored`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `shots` | array[1..400] of object | yes |
| `shots[].start_ms` | integer 0..86400000 | yes |
| `shots[].end_ms` | integer 0..86400000 | yes |
| `shots[].camera` | one of `static`, `pan`, `tilt`, `push/pull` | yes |
| `shots[].metrics` | map[1..32] of integer -1000000000000..1000000000000 | yes |
| `bands` | object | no |
| `bands.moving_share` | integer 0..1000 | yes |
| `bands.metrics` | map[0..32] of array[3..3] of integer -1000000000000..1000000000000 | yes |
| `rules` | array[1..32] of object | no |
| `rules[].metric` | string matching `^[a-z][a-z0-9_]{0,31}$` | yes |
| `rules[].op` | one of `>=`, `<=` | yes |
| `rules[].target` | integer -1000000000000..1000000000000 | yes |
| `segments` | array[1..64] of object | no |
| `segments[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `segments[].start_ms` | integer 0..86400000 | yes |
| `segments[].end_ms` | integer 0..86400000 | yes |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.rule_source` | one of `caller`, `reference_bands_default` | yes |
| `result.rules` | array[1..32] of object | yes |
| `result.rules[].metric` | string matching `^[a-z][a-z0-9_]{0,31}$` | yes |
| `result.rules[].op` | one of `>=`, `<=` | yes |
| `result.rules[].target` | integer -1000000000000..1000000000000 | yes |
| `result.segments` | array[1..64] of object | yes |
| `result.segments[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.segments[].start_ms` | integer 0..86400000 | yes |
| `result.segments[].end_ms` | integer 0..86400000 | yes |
| `result.segments[].covered_ms` | integer 0..86400000 | yes |
| `result.segments[].verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.segments[].measured` | map[0..33] of integer -1000000000000..1000000000000 | yes |
| `result.segments[].checks` | array[1..32] of object | yes |
| `result.segments[].checks[].check` | string up to 96 chars | yes |
| `result.segments[].checks[].value` | null or integer -1000000000000..1000000000000 | yes |
| `result.segments[].checks[].min` | null or integer -1000000000000..1000000000000 | yes |
| `result.segments[].checks[].max` | null or integer -1000000000000..1000000000000 | yes |
| `result.segments[].checks[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.segments[].failing` | array[0..32] of string matching `^[a-z][a-z0-9_]{0,31}$` | yes |
| `result.failing_segments` | array[0..64] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |

## `reference_bands`

Duration-weighted p25/p50/p75 bands per shot metric, and moving_share, from a measured reference (filmstats.py, milli-units). The output's bands feed cinematic_gate. Observation only.

Assessments: `bands_measured`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `shots` | array[1..400] of object | yes |
| `shots[].start_ms` | integer 0..86400000 | yes |
| `shots[].end_ms` | integer 0..86400000 | yes |
| `shots[].camera` | one of `static`, `pan`, `tilt`, `push/pull` | yes |
| `shots[].metrics` | map[1..32] of integer -1000000000000..1000000000000 | yes |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.bands` | object | yes |
| `result.bands.moving_share` | integer 0..1000 | yes |
| `result.bands.metrics` | map[1..32] of array[3..3] of integer -1000000000000..1000000000000 | yes |
| `result.duration_ms` | array[3..3] of integer 0..86400000 | yes |
| `result.n_shots` | integer 1..400 | yes |
| `result.total_ms` | integer 0..86400000 | yes |
| `result.quantiles_permille` | const [250, 500, 750] | yes |

## `audio_gate`

Soundtrack against the mix contract: integrated loudness and true peak (milli-LU/dBTP), voice over bed (milli-dB), share of cuts carrying a hit, AudioSet classes heard, WER per line (per-mille). Null means not measured. Observation only.

Assessments: `thresholds_met`, `thresholds_not_met`, `not_scored`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `integrated_lufs` | null or integer -1000000000000..1000000000000 | yes |
| `true_peak_dbtp` | null or integer -1000000000000..1000000000000 | yes |
| `voice_over_bed_db` | null or integer -1000000000000..1000000000000 | yes |
| `cuts` | null or integer 0..100000 | yes |
| `cuts_with_hit` | null or integer 0..100000 | yes |
| `heard` | null or array[0..128] of string matching `^[ -~]{1,96}$` | yes |
| `line_wer` | null or array[1..512] of object | yes |
| `contract` | object | no |
| `contract.loudness_target` | integer -1000000000000..1000000000000 | no |
| `contract.loudness_tolerance` | integer -1000000000000..1000000000000 | no |
| `contract.true_peak_max` | integer -1000000000000..1000000000000 | no |
| `contract.voice_over_bed_min` | integer -1000000000000..1000000000000 | no |
| `contract.voice_over_bed_max` | integer -1000000000000..1000000000000 | no |
| `contract.cut_hit_share_min` | integer 0..1000 | no |
| `contract.required_heard` | array[0..128] of string matching `^[ -~]{1,96}$` | no |
| `contract.forbidden_heard` | array[0..128] of string matching `^[ -~]{1,96}$` | no |
| `contract.wer_max` | integer 0..1000 | no |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.checks` | array[7..7] of object | yes |
| `result.checks[].check` | string up to 96 chars | yes |
| `result.checks[].value` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].min` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].max` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.contract` | object | yes |
| `result.contract.loudness_target` | integer -1000000000000..1000000000000 | yes |
| `result.contract.loudness_tolerance` | integer -1000000000000..1000000000000 | yes |
| `result.contract.true_peak_max` | integer -1000000000000..1000000000000 | yes |
| `result.contract.voice_over_bed_min` | integer -1000000000000..1000000000000 | yes |
| `result.contract.voice_over_bed_max` | integer -1000000000000..1000000000000 | yes |
| `result.contract.cut_hit_share_min` | integer 0..1000 | yes |
| `result.contract.required_heard` | array[0..128] of string matching `^[ -~]{1,96}$` | yes |
| `result.contract.forbidden_heard` | array[0..128] of string matching `^[ -~]{1,96}$` | yes |
| `result.contract.wer_max` | integer 0..1000 | yes |
| `result.contract_overrides` | array[0..9] of one of `loudness_target`, `loudness_tolerance`, `true_peak_max`, `voice_over_bed_min`, `voice_over_bed_max`, `cut_hit_share_min`, `required_heard`, `forbidden_heard`, `wer_max` | yes |
| `result.heard` | object | yes |
| `result.heard.missing` | null or array[0..128] of string matching `^[ -~]{1,96}$` | yes |
| `result.heard.forbidden_present` | null or array[0..128] of string matching `^[ -~]{1,96}$` | yes |
| `result.wer` | object | yes |
| `result.wer.lines` | integer 0..512 | yes |
| `result.wer.worst_line` | null or string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.wer.failing_lines` | array[0..512] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.failing` | array[0..7] of string up to 96 chars | yes |

## `drift_verdict`

Clip verdict for control-conditioned generation (I20): per-frame edge F1 and mask IoU, optional depth error and identity similarity (driftgate.py, milli-units) against thresholds, gated on the worst frame; first failing frame and worst-frame summary. Observation only.

Assessments: `thresholds_met`, `thresholds_not_met`, `not_scored`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `frames` | object | yes |
| `frames.edge_f1` | array[1..2048] of null or integer 0..1000 | yes |
| `frames.mask_iou` | array[1..2048] of null or integer 0..1000 | no |
| `frames.depth_error` | array[1..2048] of null or integer 0..1000000000000 | no |
| `frames.identity_similarity` | array[1..2048] of null or integer 0..1000 | no |
| `thresholds` | object | no |
| `thresholds.edge_f1_min` | integer 0..1000 | no |
| `thresholds.mask_iou_min` | integer 0..1000 | no |
| `thresholds.depth_error_max` | integer 0..1000000000000 | no |
| `thresholds.identity_similarity_min` | integer 0..1000 | no |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.gate` | const "worst_frame" | yes |
| `result.frames` | integer 1..2048 | yes |
| `result.first_failing_frame` | null or integer 0..2047 | yes |
| `result.failing_frames` | integer 0..2048 | yes |
| `result.failing_frame_indices` | array[0..64] of integer 0..2047 | yes |
| `result.metrics` | object | yes |
| `result.metrics.edge_f1` | object | yes |
| `result.metrics.edge_f1.threshold` | integer 0..1000000000000 | yes |
| `result.metrics.edge_f1.side` | one of `min`, `max` | yes |
| `result.metrics.edge_f1.worst` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.edge_f1.worst_frame` | null or integer 0..2047 | yes |
| `result.metrics.edge_f1.mean` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.edge_f1.measured_frames` | integer 0..2048 | yes |
| `result.metrics.edge_f1.failing_frames` | integer 0..2048 | yes |
| `result.metrics.mask_iou` | object | no |
| `result.metrics.mask_iou.threshold` | integer 0..1000000000000 | yes |
| `result.metrics.mask_iou.side` | one of `min`, `max` | yes |
| `result.metrics.mask_iou.worst` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.mask_iou.worst_frame` | null or integer 0..2047 | yes |
| `result.metrics.mask_iou.mean` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.mask_iou.measured_frames` | integer 0..2048 | yes |
| `result.metrics.mask_iou.failing_frames` | integer 0..2048 | yes |
| `result.metrics.depth_error` | object | no |
| `result.metrics.depth_error.threshold` | integer 0..1000000000000 | yes |
| `result.metrics.depth_error.side` | one of `min`, `max` | yes |
| `result.metrics.depth_error.worst` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.depth_error.worst_frame` | null or integer 0..2047 | yes |
| `result.metrics.depth_error.mean` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.depth_error.measured_frames` | integer 0..2048 | yes |
| `result.metrics.depth_error.failing_frames` | integer 0..2048 | yes |
| `result.metrics.identity_similarity` | object | no |
| `result.metrics.identity_similarity.threshold` | integer 0..1000000000000 | yes |
| `result.metrics.identity_similarity.side` | one of `min`, `max` | yes |
| `result.metrics.identity_similarity.worst` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.identity_similarity.worst_frame` | null or integer 0..2047 | yes |
| `result.metrics.identity_similarity.mean` | null or integer -1000000000000..1000000000000 | yes |
| `result.metrics.identity_similarity.measured_frames` | integer 0..2048 | yes |
| `result.metrics.identity_similarity.failing_frames` | integer 0..2048 | yes |
| `result.thresholds` | object | yes |
| `result.thresholds.edge_f1_min` | integer 0..1000 | yes |
| `result.thresholds.mask_iou_min` | integer 0..1000 | no |
| `result.thresholds.depth_error_max` | integer 0..1000000000000 | no |
| `result.thresholds.identity_similarity_min` | integer 0..1000 | no |
| `result.threshold_sources` | object | yes |
| `result.threshold_sources.edge_f1_min` | one of `caller`, `driftgate_default` | yes |
| `result.threshold_sources.mask_iou_min` | one of `caller`, `driftgate_default` | no |
| `result.threshold_sources.depth_error_max` | one of `caller`, `driftgate_default` | no |
| `result.threshold_sources.identity_similarity_min` | one of `caller`, `driftgate_default` | no |
| `result.worst_frame` | object | yes |
| `result.worst_frame.frame` | integer 0..2047 | yes |
| `result.worst_frame.values` | object | yes |
| `result.worst_frame.values.edge_f1` | null or integer -1000000000000..1000000000000 | yes |
| `result.worst_frame.values.mask_iou` | null or integer -1000000000000..1000000000000 | no |
| `result.worst_frame.values.depth_error` | null or integer -1000000000000..1000000000000 | no |
| `result.worst_frame.values.identity_similarity` | null or integer -1000000000000..1000000000000 | no |

## `cue_vocabulary_check`

Static check of the shared cue vocabulary (I18): ids each lane references against the ids the voice/markers provide (with aliases), per-beat required order and minimum gaps in time. Lists missing ids, broken aliases, alias resolutions and order violations. Observation only.

Assessments: `thresholds_met`, `thresholds_not_met`, `not_scored`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `provided` | array[1..1024] of object | yes |
| `provided[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `provided[].t_ms` | integer 0..86400000 | yes |
| `provided[].end_ms` | integer 0..86400000 | no |
| `lanes` | array[1..64] of object | yes |
| `lanes[].lane` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `lanes[].references` | array[0..256] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `aliases` | map[0..512] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | no |
| `orders` | array[0..64] of object | no |
| `orders[].beat` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `orders[].sequence` | array[2..64] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `min_gaps` | array[0..64] of object | no |
| `min_gaps[].rule` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `min_gaps[].after` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `min_gaps[].next` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `min_gaps[].min_ms` | integer 0..86400000 | yes |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.checks` | array[2..130] of object | yes |
| `result.checks[].check` | string up to 96 chars | yes |
| `result.checks[].value` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].min` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].max` | null or integer -1000000000000..1000000000000 | yes |
| `result.checks[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.missing_ids` | array[0..32768] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.broken_aliases` | array[0..512] of object | yes |
| `result.broken_aliases[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.broken_aliases[].to` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.lanes` | array[1..64] of object | yes |
| `result.lanes[].lane` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.lanes[].references` | integer 0..256 | yes |
| `result.lanes[].direct` | integer 0..256 | yes |
| `result.lanes[].by_alias` | array[0..256] of object | yes |
| `result.lanes[].by_alias[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.lanes[].by_alias[].to` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.lanes[].missing` | array[0..256] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.orders` | array[0..64] of object | yes |
| `result.orders[].beat` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.orders[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.orders[].resolved` | integer 0..64 | yes |
| `result.orders[].unresolved` | array[0..64] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.orders[].first_violation` | null or object | yes |
| `result.gaps` | array[0..64] of object | yes |
| `result.gaps[].rule` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.gaps[].gap_ms` | null or integer -86400000..86400000 | yes |
| `result.gaps[].min_ms` | integer 0..86400000 | yes |
| `result.gaps[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.provided` | integer 1..1024 | yes |
| `result.aliases_used` | integer 0..512 | yes |

## `look_gate`

Rejection alarm for the look: per frame, lookgate.py's palette distance, exposure, contrast range, clipping, detail and chroma ratios against an approved target frame (milli-units), every frame against every threshold. A pass means not rejected; the client still accepts. Observation only.

Assessments: `thresholds_met`, `thresholds_not_met`, `not_scored`, `tool_error`.

### Input

| Field | Type and range | Required in its object |
|---|---|---|
| `frames` | array[1..128] of object | yes |
| `frames[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `frames[].metrics` | object | yes |
| `frames[].metrics.palette_ab` | null or integer 0..1000000000 | yes |
| `frames[].metrics.palette_L` | null or integer 0..1000000000 | yes |
| `frames[].metrics.median_L` | null or integer 0..1000000000 | yes |
| `frames[].metrics.range_L` | null or integer 0..1000000000 | yes |
| `frames[].metrics.clip_white` | null or integer 0..1000 | yes |
| `frames[].metrics.clip_black` | null or integer 0..1000 | yes |
| `frames[].metrics.detail_ratio` | null or integer 0..1000000000 | yes |
| `frames[].metrics.chroma_ratio` | null or integer 0..1000000000 | yes |
| `thresholds` | object | no |
| `thresholds.palette_ab` | integer 0..1000000000 | no |
| `thresholds.palette_L` | integer 0..1000000000 | no |
| `thresholds.median_L` | integer 0..1000000000 | no |
| `thresholds.range_L` | integer 0..1000000000 | no |
| `thresholds.clip_white` | integer 0..1000 | no |
| `thresholds.clip_black` | integer 0..1000 | no |
| `thresholds.detail_min` | integer 0..1000000000 | no |
| `thresholds.detail_max` | integer 0..1000000000 | no |
| `thresholds.chroma_min` | integer 0..1000000000 | no |
| `thresholds.chroma_max` | integer 0..1000000000 | no |

### Result

| Field | Type and range | Required in its object |
|---|---|---|
| `result.verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.gate` | const "every_frame" | yes |
| `result.role` | const "rejection_alarm" | yes |
| `result.frames` | array[1..128] of object | yes |
| `result.frames[].id` | string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.frames[].verdict` | one of `thresholds_met`, `thresholds_not_met`, `not_scored` | yes |
| `result.frames[].checks` | array[8..8] of object | yes |
| `result.frames[].checks[].check` | string up to 96 chars | yes |
| `result.frames[].checks[].value` | null or integer -1000000000000..1000000000000 | yes |
| `result.frames[].checks[].min` | null or integer -1000000000000..1000000000000 | yes |
| `result.frames[].checks[].max` | null or integer -1000000000000..1000000000000 | yes |
| `result.frames[].checks[].status` | one of `pass`, `fail`, `not_measured` | yes |
| `result.frames[].failing` | array[0..8] of one of `palette_ab`, `palette_L`, `median_L`, `range_L`, `clip_white`, `clip_black`, `detail_ratio`, `chroma_ratio` | yes |
| `result.frames[].not_measured` | array[0..8] of one of `palette_ab`, `palette_L`, `median_L`, `range_L`, `clip_white`, `clip_black`, `detail_ratio`, `chroma_ratio` | yes |
| `result.failing_frames` | array[0..128] of string matching `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | yes |
| `result.thresholds` | object | yes |
| `result.thresholds.palette_ab` | integer 0..1000000000 | yes |
| `result.thresholds.palette_L` | integer 0..1000000000 | yes |
| `result.thresholds.median_L` | integer 0..1000000000 | yes |
| `result.thresholds.range_L` | integer 0..1000000000 | yes |
| `result.thresholds.clip_white` | integer 0..1000 | yes |
| `result.thresholds.clip_black` | integer 0..1000 | yes |
| `result.thresholds.detail_min` | integer 0..1000000000 | yes |
| `result.thresholds.detail_max` | integer 0..1000000000 | yes |
| `result.thresholds.chroma_min` | integer 0..1000000000 | yes |
| `result.thresholds.chroma_max` | integer 0..1000000000 | yes |
| `result.threshold_sources` | object | yes |
| `result.threshold_sources.palette_ab` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.palette_L` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.median_L` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.range_L` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.clip_white` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.clip_black` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.detail_min` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.detail_max` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.chroma_min` | one of `caller`, `lookgate_default` | yes |
| `result.threshold_sources.chroma_max` | one of `caller`, `lookgate_default` | yes |

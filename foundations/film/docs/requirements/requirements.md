# Requirements

Shall statements for foundation-film. Verification methods: T test, A analysis, I inspection, D demonstration. Every row appears in [the verification matrix](../verification/verification-matrix.md).

| ID | Requirement (shall) | Rationale | Verification |
|---|---|---|---|
| REQ-FILM-001 | The Foundation shall provide the `cinematic_gate` tool: Per-segment cinematic gate: duration-weighted shot measures (filmstats.py, milli-units) against reference bands (default filmgate.py rules) or explicit rules. | Domain capability exposed to the host. | T |
| REQ-FILM-002 | The Foundation shall provide the `reference_bands` tool: Duration-weighted p25/p50/p75 bands per shot metric, and moving_share, from a measured reference (filmstats.py, milli-units). | Domain capability exposed to the host. | T |
| REQ-FILM-003 | The Foundation shall provide the `audio_gate` tool: Soundtrack against the mix contract: integrated loudness and true peak (milli-LU/dBTP), voice over bed (milli-dB), share of cuts carrying a hit, AudioSet classes heard, WER per line (per-mille). | Domain capability exposed to the host. | T |
| REQ-FILM-004 | The Foundation shall provide the `drift_verdict` tool: Clip verdict for control-conditioned generation (I20): per-frame edge F1 and mask IoU, optional depth error and identity similarity (driftgate.py, milli-units) against thresholds, gated on the worst frame; first failing frame and worst-frame summary. | Domain capability exposed to the host. | T |
| REQ-FILM-005 | The Foundation shall provide the `cue_vocabulary_check` tool: Static check of the shared cue vocabulary (I18): ids each lane references against the ids the voice/markers provide (with aliases), per-beat required order and minimum gaps in time. | Domain capability exposed to the host. | T |
| REQ-FILM-006 | The Foundation shall provide the `look_gate` tool: Rejection alarm for the look: per frame, lookgate.py's palette distance, exposure, contrast range, clipping, detail and chroma ratios against an approved target frame (milli-units), every frame against every threshold. | Domain capability exposed to the host. | T |
| REQ-FILM-007 | The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships. | The host pins the manifest before dispatch. | T |
| REQ-FILM-008 | Every tool shall be read-only and mark its result `boundary.observation_only`. | Foundations judge; they never act. | I |
| REQ-FILM-009 | Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`. | Every verdict must be traceable. | T |
| REQ-FILM-010 | Every result shall carry `receipt.input_sha256` computed from the request. | The host recomputes it to bind result to request. | T |
| REQ-FILM-011 | The bridge shall run with the Python standard library only, with no network and no caller-controlled paths. | Bounded, reproducible execution. | I |
| REQ-FILM-012 | The bridge shall reject inputs that exceed its frame, depth, node, string or integer limits. | Bounded execution on both sides. | T |

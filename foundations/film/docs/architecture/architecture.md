# Architecture

## Context

foundation-film is one Foundation. A Foundation owns the meaning, data and acceptance of one domain. POODO governs how it is used. The host (Cstack, through its stdio adapter) starts the bridge, pins its source and validates every result.

## Components

| Component | Path | Role |
|---|---|---|
| Domain package | `foundation_film/` | Pure functions over caller-supplied values |
| Bridge | `foundation_film_bridge/` | Line-delimited JSON-RPC over stdio: `python -B -m foundation_film_bridge` |
| Schemas | `foundation_film_bridge/schemas.py` | Tool inventory and input/output schemas |
| Manifest tool | `tools/build_manifest.py` | Writes `SOURCE-MANIFEST.json`, prints the three pins |
| Tests | `tests/` | Unit and bridge tests |

## Tools

| Tool | Purpose |
|---|---|
| `cinematic_gate` | Per-segment cinematic gate: duration-weighted shot measures (filmstats.py, milli-units) against reference bands (default filmgate.py rules) or explicit rules |
| `reference_bands` | Duration-weighted p25/p50/p75 bands per shot metric, and moving_share, from a measured reference (filmstats.py, milli-units) |
| `audio_gate` | Soundtrack against the mix contract: integrated loudness and true peak (milli-LU/dBTP), voice over bed (milli-dB), share of cuts carrying a hit, AudioSet classes heard, WER per line (per-mille) |
| `drift_verdict` | Clip verdict for control-conditioned generation (I20): per-frame edge F1 and mask IoU, optional depth error and identity similarity (driftgate.py, milli-units) against thresholds, gated on the worst frame; first failing frame and worst-frame summary |
| `cue_vocabulary_check` | Static check of the shared cue vocabulary (I18): ids each lane references against the ids the voice/markers provide (with aliases), per-beat required order and minimum gaps in time |
| `look_gate` | Rejection alarm for the look: per frame, lookgate.py's palette distance, exposure, contrast range, clipping, detail and chroma ratios against an approved target frame (milli-units), every frame against every threshold |

## Data flow

Host request → bridge input limits → schema validation → domain function → result with `receipt.input_sha256` and `receipt.evidence` → host re-validates against the pinned output schema.

## Decisions

- Read-only observations only. A verdict is not an acceptance decision.
- Standard library only, so the source can be hashed and pinned as a whole.

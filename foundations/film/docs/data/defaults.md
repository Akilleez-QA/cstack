# Default values

Generated from the code by the documentation generator (an adapted copy of foundation-robotics `tools/gen_docs.py`; it is not in this repository because the documentation change was docs-only). Do not edit by hand.

Defaults are module constants. None has been approved by a qualified person; the Evidence attached to each result says how far each set was calibrated.

| Tool | Key | Value | Unit | Defined in |
|---|---|---|---|---|
| `audio_gate` | `loudness_target` | -16000 | milli-LUFS | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `loudness_tolerance` | 1000 | milli-LU | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `true_peak_max` | -1000 | milli-dBTP | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `voice_over_bed_min` | 12000 | milli-dB | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `voice_over_bed_max` | 15000 | milli-dB | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `cut_hit_share_min` | 800 | per-mille | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `required_heard` | ["Speech", "Music"] | AudioSet labels | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `forbidden_heard` | ["Sine wave"] | AudioSet labels | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `audio_gate` | `wer_max` | 50 | per-mille | `foundation_film/audio.py` `DEFAULT_CONTRACT` |
| `drift_verdict` | `edge_f1_min` | 450 | milli-units (min) | `foundation_film/drift.py` `METRICS` |
| `drift_verdict` | `mask_iou_min` | 600 | milli-units (min) | `foundation_film/drift.py` `METRICS` |
| `drift_verdict` | `depth_error_max` | none (caller must supply) | milli-units (max) | `foundation_film/drift.py` `METRICS` |
| `drift_verdict` | `identity_similarity_min` | none (caller must supply) | milli-units (min) | `foundation_film/drift.py` `METRICS` |
| `look_gate` | `palette_ab` | 6000 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `palette_L` | 8000 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `median_L` | 10000 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `range_L` | 15000 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `clip_white` | 40 | per-mille | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `clip_black` | 80 | per-mille | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `detail_min` | 550 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `detail_max` | 1800 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `chroma_min` | 700 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `look_gate` | `chroma_max` | 1400 | milli-units | `foundation_film/look.py` `DEFAULTS` |
| `cinematic_gate` | black ceiling floor | 350 | milli-units | `foundation_film/cinema.py` `BLACK_FLOOR` |
| `cinematic_gate`, `reference_bands` | quantiles | 250, 500, 750 | per-mille | `foundation_film/cinema.py` `QUANTILES` |

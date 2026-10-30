# Foundation Film v0.1

The film-production domain: what "cinematic", "the mix is right", "the generation stayed on its passes", "the lanes
agree on their cue names" and "this frame could not be the approved look" mean, as checks that can fail. It owns the domain's meaning and acceptance; POODO governs how
it is used. It is a sibling of the other Foundations, never a subclass.

Every tool is a read-only observation and a pure function of the numbers the caller supplies. There are no file
paths, no video decoding, no models and no network here. The **measuring producers live in Endoforge**
(`forge/endoforge/tools/film/`: `filmstats.py`, `audiostats.py`, `audiotags.py`, `driftgate.py`, `lookgate.py`); their JSON outputs,
scaled to integers, are what this Foundation judges. The playbook that explains why each gate exists is
`forge/endoforge/docs/PLAYBOOK-film.md`.

A verdict compares supplied measures with stated thresholds. It is **not acceptance of a film**: that stays a person's
quality call, so every receipt's boundary says `acceptance_decision: false` (I11, I12).

## Numeric profile

Bounded integers only. Every measure is an integer in **milli-units** of its natural unit, `round(value * 1000)`:

| Measure | Unit on the wire | Example |
|---|---|---|
| shares, ratios, F1, IoU, similarity, WER | per-mille | moving share 0.508 → `508`; WER 5 % → `50`; detail ratio 0.99 → `990` |
| times | milliseconds | 14.67 s → `14670` |
| loudness, true peak, level margins | milli-LU, milli-dB | −16.9 LUFS → `-16900`; −1 dBTP → `-1000` |
| any other measure (sharpness, depth error, pan px/s, Lab distance) | thousandths | Laplacian variance 223.214 → `223214`; palette EMD 6.0 → `6000` |

The host reuses the shared integer decoder (`adapters/wire.py`), so no float ever crosses the bridge.

## Tools

| Tool | Takes | Returns | Thresholds and their source |
|---|---|---|---|
| `reference_bands` | per-shot measures with start/end and camera kind (filmstats `shots.json`) | duration-weighted p25/p50/p75 per metric and of shot length, plus `moving_share` | none; the method reproduces the reference run's duration band exactly |
| `cinematic_gate` | the same shots, plus reference bands or explicit rules, plus segments (beats) | per-segment verdict, measured means, every check, failing checks | filmgate.py defaults (CHECK): camera moves at least as often as the reference, sharpness inside p25/2 … p75, black ≤ max(p75, 35 %), subject motion and luma ≥ p25 |
| `audio_gate` | integrated LUFS, true peak, voice over bed, cuts and cuts with a hit, classes heard, WER per line (null = not measured) | verdict, each check, missing and forbidden classes, worst line | the mix contract (CHECK): −16 ± 1 LUFS, ≤ −1 dBTP, voice 12–15 dB over bed, hits on ≥ 80 % of cuts, Speech and Music heard and no Sine wave, WER ≤ 5 % per line; any value can be overridden and the override is reported |
| `drift_verdict` | per-frame edge F1 and optional mask IoU, depth error, identity similarity | clip verdict gated on the **worst frame**, first failing frame, per-metric worst and mean, the worst frame's values | driftgate.py defaults (CHECK): edge F1 ≥ 0.45, mask IoU ≥ 0.60; depth and identity have no calibrated default, so the caller must supply them |
| `cue_vocabulary_check` | ids each lane references, ids the voice/markers provide (with times), aliases, per-beat required order, minimum gaps | missing ids, broken aliases, alias resolutions, first order violation per beat, gap results | I18: the vocabulary is frozen before lanes start and checked before any render |
| `look_gate` | per frame (keyframes, beats, clip samples), lookgate.py's metrics against the approved target: palette EMD (a/b and L), median-L and contrast-range differences, extra white/black clipping, detail and chroma ratios | per-frame verdict, every check, failing and unmeasured checks; the set fails if any frame fails | lookgate.py defaults (CHECK): palette a/b ≤ 6, L ≤ 8, median L ≤ 10, range L ≤ 15, clip white ≤ 4 %, black ≤ 8 %, detail 0.55–1.8, chroma 0.7–1.4. A **rejection alarm**: calibrated so the concept frame and restyled keyframes pass and flat renders fail. The client, on moving proofs, stays the acceptance authority |

Every check reads `{"check", "value", "min", "max", "status"}` with status `pass`, `fail` or `not_measured`. A verdict
is `thresholds_met`, `thresholds_not_met` or `not_scored`; it is never met while any check is unmeasured.

Evidence on every receipt says where each threshold comes from: `cited` (a named source), `derived` (computed here
from the input) or `caller` (supplied by the caller). `CHECK` marks thresholds still awaiting calibration on
known-good and known-bad films (I3); `RECORDED` marks facts.

The protocol is `foundation-film-jsonrpc/1`. It is not MCP. The plumbing (pinned manifest, bounded bridge, exact
receipts, read-only grants) is the template's; see `foundations/template/README.md`.

## Check it

```sh
cd foundations/film
python -B -m unittest discover -s tests       # the tools (with parity against the producers' own logic), the bridge, the manifest
python -B tools/build_manifest.py             # rewrites SOURCE-MANIFEST.json; prints the three pins
python -B tools/build_manifest.py --inventory > ../../schemas/film-v01-tools.json
```

After any change, re-pin `adapters/film_stdio.py` and `contracts/SOURCE-PINS.json`. From the repository root,
`python -B -m unittest tests.test_film_conformance` runs the host side.

## Not in v0.1

- Calibrated thresholds. Every default is CHECK until a known-good film passes and known-bad ones fail on the matching
  check.
- A look *acceptance* score. `look_gate` only rejects; a frame that passes may still be wrong, and the client judges
  moving proofs.
- Region-separated drift (character vs equipment), flow and temporal-consistency metrics: the producer does not emit
  them yet.
- Arc-over-time measures (music sections, pacing curve) and likeness: still judged by the producers and a person.

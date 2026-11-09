# How the checks work

Each judged tool turns measurements the caller already made into checks. A check has a value, an optional minimum and maximum, and a status of `pass`, `fail` or `not_measured`. The verdict is `thresholds_not_met` if any check fails, `not_scored` if any check could not be measured, and `thresholds_met` otherwise. `reference_bands` has no checks; it returns measured bands (`bands_measured`).

All quantities cross the bridge as integers: times in milliseconds, measures in milli-units. Averages and shares use integer arithmetic that rounds half away from zero.

## Shots, bands and the cinematic gate

A film is a list of shots in time order, each with a camera class and the same set of metrics (from the offline producer or another measuring tool).

- `reference_bands` gives, for each metric and for shot duration, the 25th, 50th and 75th percentile weighted by screen time: the first value, in ascending order, at which the running screen time reaches that share of the total. It also gives the moving-camera share of screen time.
- `cinematic_gate` cuts the film into segments (the whole film by default), computes each segment's screen-time-weighted metrics and moving share, and checks them against rules. With `bands`, it uses six default rules: moving share at least the reference's; sharpness at most p75 and at least half of p25; black at most p75 (never below 350, that is 0.35); subject motion and luma at least p25. With `rules`, the caller's rules apply instead. A segment that no shot covers is `not_scored`.

Being inside the reference bands is a measured proxy for the look of the reference, not proof of quality.

## Audio

`audio_gate` checks seven things against a mix contract: integrated loudness within -16 ± 1 LUFS, true peak at most -1 dBTP, voice 12 to 15 dB over the bed, a hit on at least 80 % of cuts, Speech and Music heard, no Sine wave heard, and every line's word error rate at most 5 %. Any input may be `null`, which makes its check `not_measured`. The caller may override any contract value; the result lists which.

## Drift

`drift_verdict` checks every frame of edge F1 (default minimum 0.45) and mask IoU (default minimum 0.60), and optionally depth error and identity similarity, which have no default and need caller thresholds. The gate is the worst frame. A clip whose mean passes but whose last frames collapse fails, and the result names the first failing frame.

## Cue vocabulary

`cue_vocabulary_check` treats the ids that lanes share as a contract. Every id a lane references must be provided directly or through an alias; aliases must point at provided ids and may not shadow them. Per beat, a sequence of ids must appear in strictly increasing time. A minimum gap rule measures from the end of one marker (or its start, if it has no end) to the start of the next.

## Look

`look_gate` checks every frame against an approved target on eight measures: palette distance in a/b and in L, median L, L range, white and black clipping, and detail and chroma ratios, which must sit inside a band. It is a rejection alarm: `thresholds_met` means "not rejected", never "approved".

## Where the defaults come from

The default rules, contract and thresholds were taken from the reference scripts and one reference production run. Each result's Evidence says how far that set was calibrated and marks uncalibrated ones `CHECK`. The parity tests show the integer tools reproduce the reference scripts' outcomes. All values: [defaults](../../data/defaults.md).

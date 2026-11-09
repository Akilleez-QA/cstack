# Limitations

This page replaces a hazard report (SWEHB 5.24 is not applicable because nothing in this repository is safety-critical). The family standard recommends it for every Foundation.

## What the outputs are

Each result is a bounded observation about measurements the caller supplied, with Evidence and an input hash. Every receipt says `observation_only: true`, `acceptance_decision: false` and `control_action: false`, and every tool result says `formal_proof: false` and `runtime_goal_acceptance: false`. A pass means the supplied numbers met the stated thresholds. It is not an acceptance of a film, a cut or a mix; the client remains the acceptance authority.

## What the software does not do

- The bridge never opens media. It cannot tell whether the numbers describe the film they claim to.
- It does not measure loudness, speech recognition, AudioSet classes, edge F1, mask IoU or look metrics itself. Those come from other tools.
- It does not judge story, performance, taste or anything a measure does not capture.
- The offline producer does not extract audio, palettes or contact strips.

## Data and calibration limits

- The mix contract, the look thresholds and the default cinematic rules come from one reference production run. Most are marked `CHECK` in Evidence and have not been calibrated on other films or looks.
- The drift thresholds are starting values; their calibration is pending, as the Evidence says.
- The producer records zero motion when optical flow finds too few features, so a `static` camera class is not proof that tracking worked.
- No test validates results against the output schemas (GAP-FILM-07 in the [requirements](../../requirements/requirements.md#8-untested-behaviour-gaps)).

## Use in decisions

The self-assessed Class E classification holds because no engineering or safety decision depends on this software. Do not use a verdict as the sole basis for accepting delivered work, a broadcast or a contract deliverable. Check delivery against the authoritative specification for the outlet, for example the loudness recommendation it names (such as EBU R 128 or ITU-R BS.1770 measurement), and against a person's review.

## Misuse and security considerations

The bridge treats every request as untrusted: fixed parse limits, integers only, unknown fields refused, no caller paths, no network. The offline producer opens whatever local file it is given and decodes it with OpenCV and PySceneDetect, so run it only on files you trust. Report security problems privately as described in [SECURITY.md](../../../SECURITY.md).

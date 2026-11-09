# foundation-robotics data dictionary

| Field | Value |
|---|---|
| Document ID | FROBO-DD |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Generated parts: `python -B tools/gen_docs.py` writes the [tool catalog](../guides/reference/tool-catalog.md), the [defaults table](defaults.md) and the [calibration cases](calibration-cases.md). `tests/test_docs.py::DocTests.test_generated_docs_are_current` fails when any of them is stale. The rest of this page is written by hand and checked against the code at the baseline commit.

Not applicable: channelization, rate-group, raw or calibrated sensor, telemetry, data-recorder and partitioning data. The software has no hardware or telemetry interface.

## 1. Tools

| Name | Purpose | Required parameters | Result | Restrictions | Source |
|---|---|---|---|---|---|
| `scale_timing` | Timing for a body of this size under gravity | exactly one of `leg_length_mm`, `height_mm` | factors, walk table, limits, pendulum periods, fall times | up to 8 Froude values, 16 appendages, 16 drop heights | `foundation_robotics/scale.py` |
| `gait_check` | Judge a walk, run or stand | `speed_mm_s`; one of `leg_length_mm`, `height_mm`; `fps_milli` when any foot has a track | verdict, checks, measured values, per-foot rows, expected walk | up to 4 feet, 2 to 1200 frames per track; a stand needs feet with tracks or `slide_mean_mm_s` | `foundation_robotics/gait.py` |
| `balance_check` | Judge balance per frame | `fps_milli`, `frames` | verdict, checks, worst margins, per-frame margins | 1 to 400 frames, up to 16 contacts per frame; COM must be above its support | `foundation_robotics/balance.py` |
| `ik_check` | Judge a joint chain per pose | `joints`, `tip_mm`, `poses` | verdict, reach, per-pose tip, limits, singular values, target error | 1 to 16 joints, 1 to 200 poses; `q` has one value per joint; axis not zero; `min` not above `max` | `foundation_robotics/kinematics.py` |
| `mechanism_check` | Judge a machine's motion | `kind` and the kind's fields | verdict, checks, kind-specific detail | 1 to 16 gear stages, up to 1000 frames; a judged call needs measured speeds or frames | `foundation_robotics/mechanisms.py` |
| `squash_check` | Judge squash and stretch volume | `frames` | verdict, worst frame, per-frame volume and conserving lateral scale | 1 to 1000 frames; scales 1 to 1000000 permille | `foundation_robotics/squash.py` |

Field-level types and ranges: [tool catalog](../guides/reference/tool-catalog.md).

## 2. Data elements and conventions

| Name | Type | Units | Range / limits | Default | Meaning | Defined in |
|---|---|---|---|---|---|---|
| Measure | integer | milli-SI or per-mille, named by suffix | -10^12 to 10^12 | — | Any input or output quantity | `foundation_robotics/measures.py` `MEASURE_LIMIT` |
| Coordinate | integer | mm (positions), mrad or mm (joint values) | -10^9 to 10^9 | — | Positions, joint values and limits | `measures.py` `COORD_LIMIT` |
| Identifier | string | — | `^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$` | — | Foot, joint, gear and appendage ids; unique within a list | `measures.py` `ID` |
| `gravity_mm_s2` | integer | mm/s² | 1 to 10^6 | 9806.65 (standard gravity, used as a float) | Gravity for scaling, Froude and free fall | `measures.py` `gravity` |
| `up_axis` | string | — | `y` or `z` | `y` | Vertical axis; ground plane is the other two | `measures.py` `up_axis` |
| `fps_milli` | integer | milli-frames per second | 1 to 10^6 | — (required where used) | Frame rate; 30000 = 30 fps | each tool module |
| `thresholds` | object | per key | up to 8 keys from the tool's own list, each a Measure | from `defaults.json` | Caller overrides of default thresholds | `measures.py` `thresholds` |
| Revolute joint value `q` | integer | mrad | Coordinate | — | Joint angle | `kinematics.py` |
| Prismatic joint value `q` | integer | mm | Coordinate | — | Joint extension along its axis | `kinematics.py` |
| Rounding | — | — | — | — | Floats are rounded half away from zero and clipped to 10^12; a non-finite value refuses the call | `measures.py` `rnd` |
| Check | object | — | `status` `pass`, `fail` or `not_measured` | — | One threshold test with value, min and max | `measures.py` `check` |
| Verdict | string | — | `thresholds_met`, `thresholds_not_met`, `not_scored` | — | Combined check outcome (REQ-ROB-021) | `measures.py` `verdict` |

## 3. Records and files

| Record / file | Format | Schema | Producer | Consumer | Retention |
|---|---|---|---|---|---|
| `foundation_robotics/data/defaults.json` | JSON | `foundation-robotics-defaults/1`: section → key → `value`, `unit`, `status`, `source`, optional `note` | maintainer | `sources.py` at import | in git |
| `foundation_robotics/data/calibration.json` | JSON | `foundation-robotics-calibration/1`: `cases[]` with `id`, `tool`, `label`, `source`, optional `assumed`, `arguments`, `verdict`, optional `fails` | maintainer | tests | in git |
| `SOURCE-MANIFEST.json` | JSON | `foundation-robotics-source-manifest/1`: `version`, `files` (path → SHA-256) | `tools/build_manifest.py` | host adapter, tests, CI | in git |
| Tool receipt | JSON on stdout | per-tool `outputSchema` | `tools.run` | host | not stored by this repository |

## 4. Reference data provenance

| Table | Source | Units | Transformation | Validation test |
|---|---|---|---|---|
| Hip height 0.530 x standing height; 1750 mm reference height | Winter (2009), Biomechanics and Motor Control of Human Movement, 4th ed., ch. 4 | per-mille, mm | none | `tests/test_tools.py::ScaleTimingTests` (928 mm leg from 1750 mm) |
| Stride = 2.3 L Froude^0.3 | Alexander (1976), Nature 261 | per-mille coefficient and exponent | none | `tests/test_tools.py::GaitTests`, `ScaleTimingTests` |
| Walk-run transition near Froude 0.5; duty factor at least 0.5 for a walk | Alexander (1989), Physiological Reviews 69(4); Kram et al. (1997), J. Exp. Biol. 200 | per-mille | none | `tests/test_tools.py::GaitTests` |
| Gait, balance, IK, mechanism and squash thresholds | `calibration` source: the known-good and known-bad cases in `calibration.json`; or the cited method (ZMP, Newton, Yoshikawa, Norton, Shannon, Thomas and Johnston) | see [defaults](defaults.md) | none | `tests/test_tools.py::CalibrationTests` |
| Calibration cases | Internal motion trials and an internal animation project, described in each case's `source` field; leg lengths marked `assumed` where the clip recorded none | tool units | measured values converted to milli-SI integers by hand (each case states the original numbers) | `tests/test_tools.py::CalibrationTests.test_every_recorded_case_reaches_its_verdict` |

Full citations: `SOURCES` in `foundation_robotics/sources.py`. Every default value with its status: [defaults](defaults.md).

## 5. Configuration keys

None. The bridge reads no environment variables, options or configuration files. All tunable values are per-call `thresholds` and `gravity_mm_s2`.

## 6. Operational limits

| Limit | Value | Enforced in | Test |
|---|---|---|---|
| Input frame | 65536 bytes | `server.decode_frame` | none (GAP-ROB-01) |
| Output frame | 1048576 bytes | `server.encode_response` | none (GAP-ROB-06) |
| JSON depth | 32 | `server.decode_frame` | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` |
| JSON nodes | 16384 | `server.decode_frame` | none (GAP-ROB-02) |
| String length | 1024 characters | `server.decode_frame` | none (GAP-ROB-03) |
| Integer digits | 15 | `server._integer` | none (GAP-ROB-04) |
| Request id | 128 characters, string or integer | `server.Bridge.dispatch` | none (GAP-ROB-10) |
| Evidence entries per receipt | 1 to 16 | `outputSchema` | REQ-ROB-022 tests, when `jsonschema` is present |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | b4de079 | Initial baseline | docs/nasa-standard PR |

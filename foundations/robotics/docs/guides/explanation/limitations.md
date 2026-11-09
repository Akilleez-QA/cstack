# Limitations and safety-relevant use

This page replaces a hazard report (SWEHB 5.24 is not applicable because nothing in this repository is safety-critical). Read it before using any result outside animation review or research.

## What the outputs are

Each result is a bounded observation about numbers the caller supplied, with Evidence and an input hash. Every receipt says `observation_only: true`, `acceptance_decision: false` and `control_action: false`, and every tool result says `formal_proof: false`. A verdict of `thresholds_met` means the supplied numbers passed thresholds that are, for the most part, still marked `CHECK`. It is not an engineering approval, a safety determination, a clinical assessment or a regulatory compliance check.

## What the software does not do

- It does not command, monitor or stop any robot, actuator or machine.
- It does not read motion data itself. It cannot tell whether the numbers it is given describe the real motion.
- It does not perform dynamics with masses, inertias, torques or contact forces, apart from the cart-table ZMP and free fall.
- It does not check structural strength, gear tooth strength, wear, fatigue or lubrication.
- It does not replace a qualified engineer's analysis, a risk assessment or a clinical gait assessment.

## Data sources and their limits

| Data | Basis | Limit |
|---|---|---|
| Stride relation 2.3 L Froude^0.3 | Alexander (1976), fitted across animals | Scatter around the fit; the approved human walk in the calibration set measured 1.23 times the prediction |
| Hip height 0.530 x standing height | Winter (2009) | Adult human proportions only; give `leg_length_mm` for other builds |
| Walk-run transition near Froude 0.5 | Kram et al. (1997), Alexander (1989) | Human and animal walking; not a limit for machines |
| ZMP inside the support polygon | Cart-table model (Kajita et al. 2003; Vukobratović and Borovac 2004) | Ignores angular momentum about the COM: necessary, not sufficient |
| Gait, balance, IK, mechanism and squash thresholds | `foundation_robotics/data/defaults.json` | Most are `CHECK`: tried on a few human-scale walks, one giant, one squash, and constructed cases, and not approved by a qualified person ([defaults](../../data/defaults.md), [calibration](../../data/calibration-cases.md)) |

Full citations are in `foundation_robotics/sources.py`. Provenance per table is in the [data dictionary](../../data/data-dictionary.md#4-reference-data-provenance).

## Use in safety, engineering or regulated decisions

Do not use these outputs as the sole basis for any decision about a physical robot, machine, mechanism or person. The self-assessed Class E classification holds only because no real engineering decision depends on this software. Anyone who uses it for such a decision takes on Class D-analog obligations (independent verification, configuration control and validation against authoritative data) that this project does not provide.

Verify against the authoritative source for the domain instead, for example:

- Machinery risk assessment: ISO 12100.
- Industrial robot safety: ISO 10218-1 and ISO 10218-2; collaborative operation: ISO/TS 15066.
- Personal care and service robots: ISO 13482.
- Safety-related control systems: ISO 13849-1, IEC 62061, IEC 61508.
- Gear rating and mechanism design: AGMA standards, the component manufacturer's data and a qualified mechanical engineer.
- Human gait and balance for clinical purposes: a clinical gait laboratory and a qualified clinician.

## Misuse and security considerations

The bridge treats every request as untrusted. It parses with fixed limits, accepts only integers, refuses unknown fields, reads no caller paths and opens no network connections. The worst a hostile request can do is waste up to one bounded computation and get an error. Report security problems privately as described in [SECURITY.md](../../../SECURITY.md).

## Known limitations

| Limitation | Effect | Issue |
|---|---|---|
| Most thresholds are `CHECK`, calibrated on few cases | A pass or fail can be wrong for quadrupeds, runs, giants or robots | none filed |
| Input schemas do not encode every rule | A schema-valid request can be refused as `tool_error` | none filed |
| Mixed revolute and prismatic chains | The singular-value ratio mixes units; the receipt says so | none filed |
| Many bridge error paths are untested | See requirements §8, GAP-ROB-01 to 14 | none filed |
| CI does not validate results against the output schemas | A schema drift would pass CI | none filed |

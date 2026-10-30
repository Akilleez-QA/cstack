# Architecture

## Context

foundation-robotics is one Foundation. A Foundation owns the meaning, data and acceptance of one domain. POODO governs how it is used. The host (Cstack, through its stdio adapter) starts the bridge, pins its source and validates every result.

## Components

| Component | Path | Role |
|---|---|---|
| Domain package | `foundation_robotics/` | Pure functions over caller-supplied values |
| Bridge | `foundation_robotics_bridge/` | Line-delimited JSON-RPC over stdio: `python -B -m foundation_robotics_bridge` |
| Schemas | `foundation_robotics_bridge/schemas.py` | Tool inventory and input/output schemas |
| Manifest tool | `tools/build_manifest.py` | Writes `SOURCE-MANIFEST.json`, prints the three pins |
| Tests | `tests/` | Unit and bridge tests |

## Tools

| Tool | Purpose |
|---|---|
| `scale_timing` | Expected timing for a body of this size under gravity (dynamic similarity): time, speed and strength factors against a reference adult, walking speed, stride and cadence at chosen Froude numbers, leg and appendage swing periods, fall times |
| `gait_check` | Judge a walk, run or stand: Froude band, stride against Alexander's relation, speed = stride / cycle, duty factor, foot slide scaled to leg length, and left/right step symmetry |
| `balance_check` | Judge balance per frame: COM over the support polygon (static), ZMP inside it (dynamic), capture point inside it at the end (stop), and free fall at g in flight |
| `ik_check` | Judge a joint chain per pose by forward kinematics: joint limits, reach, tip error against a target, and distance from singularity (Jacobian singular-value ratio) |
| `mechanism_check` | Judge a machine's motion against its geometry: gear-train speed ratios and senses, mesh phase lock, slider-crank position, four-bar Grashof class and output angle, rotor strobing at the frame rate |
| `squash_check` | Judge squash and stretch for constant volume per frame, with the side scale that would keep it |

## Data flow

Host request → bridge input limits → schema validation → domain function → result with `receipt.input_sha256` and `receipt.evidence` → host re-validates against the pinned output schema.

## Decisions

- Read-only observations only. A verdict is not an acceptance decision.
- Standard library only, so the source can be hashed and pinned as a whole.

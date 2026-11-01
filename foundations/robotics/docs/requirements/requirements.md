# Requirements

Shall statements for foundation-robotics. Verification methods: T test, A analysis, I inspection, D demonstration. Every row appears in [the verification matrix](../verification/verification-matrix.md).

| ID | Requirement (shall) | Rationale | Verification |
|---|---|---|---|
| REQ-ROB-001 | The Foundation shall provide the `scale_timing` tool: Expected timing for a body of this size under gravity (dynamic similarity): time, speed and strength factors against a reference adult, walking speed, stride and cadence at chosen Froude numbers, leg and appendage swing periods, fall times. | Domain capability exposed to the host. | T |
| REQ-ROB-002 | The Foundation shall provide the `gait_check` tool: Judge a walk, run or stand: Froude band, stride against Alexander's relation, speed = stride / cycle, duty factor, foot slide scaled to leg length, and left/right step symmetry. | Domain capability exposed to the host. | T |
| REQ-ROB-003 | The Foundation shall provide the `balance_check` tool: Judge balance per frame: COM over the support polygon (static), ZMP inside it (dynamic), capture point inside it at the end (stop), and free fall at g in flight. | Domain capability exposed to the host. | T |
| REQ-ROB-004 | The Foundation shall provide the `ik_check` tool: Judge a joint chain per pose by forward kinematics: joint limits, reach, tip error against a target, and distance from singularity (Jacobian singular-value ratio). | Domain capability exposed to the host. | T |
| REQ-ROB-005 | The Foundation shall provide the `mechanism_check` tool: Judge a machine's motion against its geometry: gear-train speed ratios and senses, mesh phase lock, slider-crank position, four-bar Grashof class and output angle, rotor strobing at the frame rate. | Domain capability exposed to the host. | T |
| REQ-ROB-006 | The Foundation shall provide the `squash_check` tool: Judge squash and stretch for constant volume per frame, with the side scale that would keep it. | Domain capability exposed to the host. | T |
| REQ-ROB-007 | The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships. | The host pins the manifest before dispatch. | T |
| REQ-ROB-008 | Every tool shall be read-only and mark its result `boundary.observation_only`. | Foundations judge; they never act. | I |
| REQ-ROB-009 | Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`. | Every verdict must be traceable. | T |
| REQ-ROB-010 | Every result shall carry `receipt.input_sha256` computed from the request. | The host recomputes it to bind result to request. | T |
| REQ-ROB-011 | The bridge shall run with the Python standard library only, with no network and no caller-controlled paths. | Bounded, reproducible execution. | I |
| REQ-ROB-012 | The bridge shall reject inputs that exceed its frame, depth, node, string or integer limits. | Bounded execution on both sides. | T |

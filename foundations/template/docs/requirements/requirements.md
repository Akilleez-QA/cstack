# Requirements

Shall statements for foundation-template. Verification methods: T test, A analysis, I inspection, D demonstration. Every row appears in [the verification matrix](../verification/verification-matrix.md).

| ID | Requirement (shall) | Rationale | Verification |
|---|---|---|---|
| REQ-TPL-001 | The Foundation shall provide the `echo_observation` tool: PLACEHOLDER: returns its validated input as an observation with Evidence. | Domain capability exposed to the host. | T |
| REQ-TPL-002 | The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships. | The host pins the manifest before dispatch. | T |
| REQ-TPL-003 | Every tool shall be read-only and mark its result `boundary.observation_only`. | Foundations judge; they never act. | T |
| REQ-TPL-004 | Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`. | Every verdict must be traceable. | T |
| REQ-TPL-005 | Every result shall carry `receipt.input_sha256` computed from the request. | The host recomputes it to bind result to request. | T |
| REQ-TPL-006 | The bridge shall run with the Python standard library only, with no network and no caller-controlled paths. | Bounded, reproducible execution. | I |
| REQ-TPL-007 | The bridge shall reject inputs that exceed its frame, depth, node, string or integer limits. | Bounded execution on both sides. | T |

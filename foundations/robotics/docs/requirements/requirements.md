# foundation-robotics software requirements specification

| Field | Value |
|---|---|
| Document ID | FROBO-SRS |
| Version | 2.1 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Introduction

### 1.1 Purpose and audience

This document states what foundation-robotics shall do and how each statement is verified. It is for contributors changing the code and for host maintainers who pin it.

### 1.2 Scope

In scope: the six read-only motion tools, the stdio JSON-RPC bridge that exposes them, the default and calibration data, and the source manifest.

Out of scope: commanding hardware, reading files or clips, network access, and any acceptance decision. Trust assumptions: the host process that starts the bridge is trusted; each request it forwards is treated as untrusted input and bounded.

### 1.3 System overview

foundation-robotics is one Foundation in the Cstack family. The host starts `python -B -m foundation_robotics_bridge` as a child process and exchanges one JSON-RPC message per line. See the [design description](../architecture/architecture.md) and the [Cstack interface](../icd/icd-cstack.md).

## 2. Requirement record format

Each requirement has an ID, one "shall" statement, rationale, derivation (source paths), allocated-to (SDD component IDs in [architecture §4](../architecture/architecture.md#4-components)), verification method (T test, A analysis, I inspection, D demonstration) and status (Proposed, Baselined, Deleted). IDs are never reused. `tools/check_trace.py` parses this section format.

## 3. Functional requirements

### REQ-ROB-001 — scale_timing tool

The Foundation shall provide the `scale_timing` tool, which returns dynamic-similarity factors against a 1750 mm reference adult, walking speed, stride and cadence at each requested Froude number, the walk-run limits, leg and appendage pendulum periods and free-fall times.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/scale.py`, `foundation_robotics/tools.py`
- Allocated to: C-SCALE
- Verification: T
- Status: Baselined

### REQ-ROB-002 — gait_check tool

The Foundation shall provide the `gait_check` tool, which judges a walk, run or stand by Froude band, stride against Alexander's relation, speed = stride / cycle, duty factor, foot slide scaled by the square root of leg length, and left/right step-time symmetry.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/gait.py`, `foundation_robotics/tools.py`
- Allocated to: C-GAIT
- Verification: T
- Status: Baselined

### REQ-ROB-003 — balance_check tool

The Foundation shall provide the `balance_check` tool, which judges per frame the COM margin over the support polygon (static), the ZMP margin (dynamic), the capture-point margin at the end (stop) and the free-fall error in unsupported frames.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/balance.py`, `foundation_robotics/tools.py`
- Allocated to: C-BALANCE
- Verification: T
- Status: Baselined

### REQ-ROB-004 — ik_check tool

The Foundation shall provide the `ik_check` tool, which computes forward kinematics of a revolute/prismatic chain per pose and judges joint limits, reach, tip error against a target and the Jacobian singular-value ratio.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/kinematics.py`, `foundation_robotics/tools.py`
- Allocated to: C-IK
- Verification: T
- Status: Baselined

### REQ-ROB-005 — mechanism_check tool

The Foundation shall provide the `mechanism_check` tool, which judges gear-train speeds and senses, gear-mesh phase lock, slider-crank position, four-bar Grashof class and output angle, and rotor strobing at the frame rate.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/mechanisms.py`, `foundation_robotics/tools.py`
- Allocated to: C-MECH
- Verification: T
- Status: Baselined

### REQ-ROB-006 — squash_check tool

The Foundation shall provide the `squash_check` tool, which judges volume preservation per frame and reports the lateral scale that would keep volume constant.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_robotics/squash.py`, `foundation_robotics/tools.py`
- Allocated to: C-SQUASH
- Verification: T
- Status: Baselined

### REQ-ROB-007 — source manifest

The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships outside the root `.github/` tree, excluding `.git`, `__pycache__`, `.pyc` files and the manifest itself.

- Rationale: the host pins the manifest before dispatch.
- Derivation: `tools/build_manifest.py`, `SOURCE-MANIFEST.json`
- Allocated to: C-MANIFEST
- Verification: T
- Status: Baselined

### REQ-ROB-008 — read-only boundary

Every tool shall be read-only, and every receipt shall carry `boundary` = `{observation_only: true, acceptance_decision: false, control_action: false}`.

- Rationale: Foundations judge; they never act.
- Derivation: `foundation_robotics/tools.py`
- Allocated to: C-TOOLS
- Verification: T, I
- Status: Baselined

### REQ-ROB-009 — Evidence on every result

Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`.

- Rationale: every verdict must be traceable to a source or to the caller's numbers.
- Derivation: `foundation_robotics/tools.py`
- Allocated to: C-TOOLS
- Verification: T
- Status: Baselined

### REQ-ROB-010 — input hash

Every result shall carry `receipt.input_sha256`, the SHA-256 of the arguments serialized as sorted-key, compact, ASCII JSON.

- Rationale: the host recomputes it to bind the result to the request.
- Derivation: `foundation_robotics/tools.py`
- Allocated to: C-TOOLS
- Verification: T
- Status: Baselined

### REQ-ROB-015 — argument refusal

A tool call whose arguments break the tool's input rules (missing, extra or out-of-range fields, wrong types, repeated ids, contradictory fields, nothing to judge) shall return `isError: true`, assessment `tool_error`, receipt status `error`, `result: null`, an error message of at most 1024 characters and an Evidence entry.

- Rationale: a refused request must still be a well-formed, traceable receipt.
- Derivation: `foundation_robotics/measures.py`, `foundation_robotics/tools.py`
- Allocated to: C-MEASURES, C-TOOLS
- Verification: T
- Status: Baselined

### REQ-ROB-017 — calibration replay

With default thresholds, every case in `foundation_robotics/data/calibration.json` shall reach its recorded verdict and, where the case lists failing checks, exactly that set of failing checks.

- Rationale: a threshold change that flips a known-good or known-bad case must fail the build.
- Derivation: `foundation_robotics/data/calibration.json`, `foundation_robotics/data/defaults.json`
- Allocated to: C-SOURCES
- Verification: T
- Status: Baselined

### REQ-ROB-018 — default provenance

Every default value in `foundation_robotics/data/defaults.json` shall carry a status of `CHECK` or `RECORDED` and a source key that resolves in `foundation_robotics/sources.py`.

- Rationale: no number enters a verdict without a named basis.
- Derivation: `foundation_robotics/data/defaults.json`, `foundation_robotics/sources.py`
- Allocated to: C-SOURCES
- Verification: T
- Status: Baselined

### REQ-ROB-019 — up-axis invariance in balance_check

`balance_check` shall give identical `worst` margins for the same motion expressed with `up_axis` `y` and with `up_axis` `z` (axes swapped).

- Rationale: callers come from y-up (three.js) and z-up (Blender) tools.
- Derivation: `foundation_robotics/measures.py`, `foundation_robotics/balance.py`
- Allocated to: C-BALANCE
- Verification: T
- Status: Baselined

### REQ-ROB-020 — caller gravity in balance_check

When `gravity_mm_s2` is supplied, `balance_check` shall judge free fall against that value instead of standard gravity (9806.65 mm/s²).

- Rationale: reduced-gravity scenes must not fail a correct fall.
- Derivation: `foundation_robotics/measures.py`, `foundation_robotics/balance.py`
- Allocated to: C-BALANCE
- Verification: T
- Status: Baselined

### REQ-ROB-021 — verdict rule

A judged tool shall return `thresholds_not_met` if any check fails, otherwise `not_scored` if any check is `not_measured`, otherwise `thresholds_met`.

- Rationale: an unmeasured check must never read as a pass.
- Derivation: `foundation_robotics/measures.py`
- Allocated to: C-MEASURES
- Verification: T
- Status: Baselined

### REQ-ROB-023 — field-level tool catalog

The generated tool catalog shall list every field path of every tool's input and result schema, including the fields inside each `anyOf`/`oneOf` branch (labelled "variant N of M" when more than one branch has fields), inside map values (`<key>`) and inside nullable objects and arrays.

- Rationale: the ICD points callers to the catalog for every field, type and range; a field missing there is undocumented.
- Derivation: `tools/gen_docs.py`, `docs/guides/reference/tool-catalog.md`
- Allocated to: C-DOCTOOLS
- Verification: T
- Status: Baselined

### REQ-ROB-024 — test report verdict

`tools/gen_reports.py` shall conclude "NOT PASSED" and exit 1 when either unittest run exits non-zero, reports a test count that differs from the outcomes it parsed, or records any outcome other than ok (a skip, an expected failure, an unexpected success, a failure, an error, or a failed subtest); when the trace check reports a problem; or when `SOURCE-MANIFEST.json` does not match the working tree.

- Rationale: the test plan accepts no skips and no failed gates, so the report must not call such a run passed.
- Derivation: `tools/gen_reports.py`
- Allocated to: C-DOCTOOLS
- Verification: T
- Status: Baselined

## 4. Interface requirements

### REQ-ROB-011 — bounded execution environment

The bridge shall run with the Python standard library only, open no network connection, accept no command-line arguments (exit status 2 if any are given) and read no caller-named path.

- Rationale: bounded, reproducible execution that can be pinned as a whole. See [ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds).
- Derivation: `foundation_robotics_bridge/server.py`, `foundation_robotics_bridge/__main__.py`
- Allocated to: C-SERVER
- Verification: I, T
- Status: Baselined

### REQ-ROB-012 — wire profile

The bridge shall reject a frame nested deeper than 32 levels with error `-32002`, and shall reject duplicate object keys, non-integer numbers and `NaN` with error `-32700`.

- Rationale: bounded parsing on both sides; numbers cross the wire only as integers in milli-SI units. See [ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics).
- Derivation: `foundation_robotics_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-ROB-013 — initialize handshake

`initialize` with `protocolVersion` `foundation-robotics-jsonrpc/1` shall return that protocol version and `mcpCompatible: false`.

- Rationale: the host must not mistake the bridge for an MCP server. See [ICD §3](../icd/icd-cstack.md#3-messages-and-data-elements).
- Derivation: `foundation_robotics_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-ROB-014 — tool catalog

`tools/list` shall return the tool definitions from `foundation_robotics_bridge/schemas.py` unchanged, in the order `scale_timing`, `gait_check`, `balance_check`, `ik_check`, `mechanism_check`, `squash_check`.

- Rationale: the host pins the canonical inventory digest. See [ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility).
- Derivation: `foundation_robotics_bridge/schemas.py`, `foundation_robotics/tools.py`
- Allocated to: C-SCHEMAS
- Verification: T
- Status: Baselined

### REQ-ROB-016 — session order and tool names

The bridge shall answer `tools/call` before a successful `initialize` with error `-32000`, and a call naming a tool outside the catalog with error `-32602`.

- Rationale: no tool runs outside an initialized session or outside the pinned inventory. See [ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics).
- Derivation: `foundation_robotics_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-ROB-022 — output schema conformance

Every tool receipt shall validate against the tool's published `outputSchema`, and every accepted argument object used by the tests shall validate against its `inputSchema`.

- Rationale: the host re-validates results against the pinned output schema.
- Derivation: `foundation_robotics_bridge/schemas.py`
- Allocated to: C-SCHEMAS
- Verification: T (runs only when `jsonschema` is importable; CI does not install it, see SAR finding F-3)
- Status: Baselined

## 5. Non-functional requirements

Reusability (SWE-147), portability and design constraints are covered by REQ-ROB-007 (pinnable source), REQ-ROB-011 (standard library only) and the CONTRIBUTING rules (no code comments, GPL-3.0-only). No performance or timing requirement is stated: no timing is measured or bounded by a test. Resource bounds are the bridge limits in [ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds); only the depth limit is tested (REQ-ROB-012), the rest are gaps in §8.

## 6. Not applicable categories

- Safety requirements: N/A. Not safety-critical (SMP §1); no hazard analysis assigns this software a hazard cause, control or mitigation.
- Control-system, operating-system, board-support-package, partitioning and hardware-interface requirements: N/A. The software commands nothing and has no hardware interface.
- User-interface requirements: N/A. The only user interface is the JSON-RPC bridge, covered in §4.

## 7. Qualification provisions

Tests are run with the CI commands in the [test plan](../verification/test-plan.md). Each requirement maps to tests or inspection targets in the [verification matrix](../verification/verification-matrix.md). Inspection (I) rows name the file inspected and what is looked for. `tools/check_trace.py` fails if a requirement has no matrix row, a row names a missing test, or a test traces to nothing.

## 8. Untested behaviour (gaps)

The code does the following, but no test checks it, so it is not stated as a requirement. Each is a candidate requirement once a test exists. TBD count: 0.

| ID | Behaviour in code | Where |
|---|---|---|
| GAP-ROB-01 | Input frames over 65536 bytes are rejected with `-32002` | `foundation_robotics_bridge/server.py` `decode_frame` |
| GAP-ROB-02 | More than 16384 JSON nodes are rejected with `-32002` | `decode_frame` |
| GAP-ROB-03 | Strings over 1024 characters are rejected with `-32002` | `decode_frame` |
| GAP-ROB-04 | Integers over 15 digits are rejected with `-32002` | `_integer` |
| GAP-ROB-05 | An oversized or unterminated line gets one `-32002` reply, then the session ends with exit status 2 | `serve` |
| GAP-ROB-06 | A response over 1048576 bytes is replaced by a `-32002` "Result withheld" error | `encode_response` |
| GAP-ROB-07 | `ping` returns `{}` and works before `initialize` | `Bridge.dispatch` |
| GAP-ROB-08 | A second `initialize` returns `-32000`; a wrong `protocolVersion` returns `-32001` | `Bridge.dispatch` |
| GAP-ROB-09 | A message without `id` (notification) gets no reply and is not executed | `Bridge.dispatch` |
| GAP-ROB-10 | Batches, extra envelope fields, wrong `jsonrpc`, empty method and `null` or over-long ids return `-32600`; unknown methods `-32601`; non-object `arguments` `-32602` | `Bridge.dispatch` |
| GAP-ROB-11 | An unexpected exception inside a tool returns `-32603` with no result | `Bridge.dispatch` |
| GAP-ROB-12 | Error receipts carry `input_sha256` (only success receipts are asserted) | `foundation_robotics/tools.py` `run` |
| GAP-ROB-13 | Caller-supplied thresholds replace defaults, are labelled `caller` in `threshold_sources` and add a `CHECK` Evidence entry | `measures.thresholds`, `tools.threshold_evidence` |
| GAP-ROB-14 | `gait_check` honours `up_axis`; `scale_timing` and `gait_check` honour `gravity_mm_s2` | `gait.py`, `scale.py` |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | d779a9f | Initial table of REQ-ROB-001 to 012 | Initial commit |
| 1.1 | 2026-10-30 | 86f2280 | Inspection-only verification methods aligned | PR #4 |
| 1.2 | 2026-11-04 | 8bc1227 | REQ-ROB-007 excludes the root `.github/` tree | PR #10 |
| 2.0 | 2026-11-08 | b4de079 | Family standard: metadata, record format, derivation and allocation per requirement. Added REQ-ROB-013 to 022 for tested behaviour. Narrowed REQ-ROB-012 to the tested depth limit and wire profile; the untested frame, node, string and integer limits moved to §8. REQ-ROB-008 and 011 gained test evidence (T, I). Untested behaviour listed as GAP-ROB-01 to 14 | docs/nasa-standard PR |
| 2.1 | 2026-11-09 | d5bbe35 | Added REQ-ROB-023 (field-level tool catalog) and REQ-ROB-024 (test report verdict) | PR fixing the 2026-11-09 backfill-review findings |

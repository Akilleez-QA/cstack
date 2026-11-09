# foundation-film software requirements specification

| Field | Value |
|---|---|
| Document ID | FFILM-SRS |
| Version | 2.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Introduction

### 1.1 Purpose and audience

This document states what foundation-film shall do and how each statement is verified. It is for contributors changing the code and for host maintainers who pin it.

### 1.2 Scope

In scope: the six read-only film acceptance tools, the stdio JSON-RPC bridge that exposes them, the optional offline video producer `foundation_film/filmstats.py`, and the source manifest.

Out of scope: rendering, editing, reading media through the bridge, network access and any acceptance decision. Trust assumptions: the host process that starts the bridge is trusted; each request it forwards is untrusted and bounded. The offline producer is run by a local operator on local files.

### 1.3 System overview

foundation-film is one Foundation in the Cstack family. The host starts `python -B -m foundation_film_bridge` as a child process and exchanges one JSON-RPC message per line. The offline producer turns a local video into the `shots` argument of the cinematic tools. See the [design description](../architecture/architecture.md) and the [Cstack interface](../icd/icd-cstack.md).

## 2. Requirement record format

Each requirement has an ID, one "shall" statement, rationale, derivation (source paths), allocated-to (SDD component IDs in [architecture §4](../architecture/architecture.md#4-components)), verification method (T test, A analysis, I inspection, D demonstration) and status (Proposed, Baselined, Deleted). IDs are never reused.

## 3. Functional requirements

### REQ-FILM-001 — cinematic_gate tool

The Foundation shall provide the `cinematic_gate` tool, which computes duration-weighted shot measures per segment and judges them against caller rules or against the default rules derived from reference bands.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/cinema.py`, `foundation_film/tools.py`
- Allocated to: C-CINEMA
- Verification: T
- Status: Baselined

### REQ-FILM-002 — reference_bands tool

The Foundation shall provide the `reference_bands` tool, which returns duration-weighted 25th, 50th and 75th percentile bands per shot metric, the shot-duration band and the moving-camera share.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/cinema.py`, `foundation_film/tools.py`
- Allocated to: C-CINEMA
- Verification: T
- Status: Baselined

### REQ-FILM-003 — audio_gate tool

The Foundation shall provide the `audio_gate` tool, which judges integrated loudness, true peak, voice over bed, the share of cuts with a hit, required and forbidden AudioSet classes, and the worst per-line WER against the mix contract.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/audio.py`, `foundation_film/tools.py`
- Allocated to: C-AUDIO
- Verification: T
- Status: Baselined

### REQ-FILM-004 — drift_verdict tool

The Foundation shall provide the `drift_verdict` tool, which judges every frame of edge F1, mask IoU and optional depth error and identity similarity against thresholds, gates on the worst frame (never the mean), and reports the first failing frame.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/drift.py`, `foundation_film/tools.py`
- Allocated to: C-DRIFT
- Verification: T
- Status: Baselined

### REQ-FILM-005 — cue_vocabulary_check tool

The Foundation shall provide the `cue_vocabulary_check` tool, which checks lane references against provided ids and aliases, and checks per-beat order and minimum gaps in time.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/cues.py`, `foundation_film/tools.py`
- Allocated to: C-CUES
- Verification: T
- Status: Baselined

### REQ-FILM-006 — look_gate tool

The Foundation shall provide the `look_gate` tool, which judges every frame's palette distance, exposure, contrast range, clipping, detail and chroma ratios against thresholds, as a rejection alarm.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_film/look.py`, `foundation_film/tools.py`
- Allocated to: C-LOOK
- Verification: T
- Status: Baselined

### REQ-FILM-007 — source manifest

The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships outside the root `.github/` tree, excluding `.git`, `__pycache__`, `.pyc` files, `PR_BODY.md` and the manifest itself.

- Rationale: the host pins the manifest before dispatch.
- Derivation: `tools/build_manifest.py`, `SOURCE-MANIFEST.json`
- Allocated to: C-MANIFEST
- Verification: T
- Status: Baselined

### REQ-FILM-008 — read-only boundary

Every tool shall be read-only, and every receipt shall carry `boundary` = `{observation_only: true, acceptance_decision: false, control_action: false}`.

- Rationale: Foundations judge; they never act.
- Derivation: `foundation_film/tools.py`
- Allocated to: C-TOOLS
- Verification: T, I
- Status: Baselined

### REQ-FILM-009 — Evidence on every result

Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`.

- Rationale: every verdict must be traceable to a source or to the caller's numbers.
- Derivation: `foundation_film/tools.py`
- Allocated to: C-TOOLS
- Verification: T
- Status: Baselined

### REQ-FILM-010 — input hash

Every result shall carry `receipt.input_sha256`, the SHA-256 of the arguments serialized as sorted-key, compact, ASCII JSON.

- Rationale: the host recomputes it to bind the result to the request.
- Derivation: `foundation_film/tools.py`
- Allocated to: C-TOOLS
- Verification: T
- Status: Baselined

### REQ-FILM-013 — offline video producer

An optional local video producer shall detect shots and measure camera motion and visual properties, emitting integer milliseconds and milli-unit metrics accepted by the cinematic tools, without adding dependencies to the bridge.

- Rationale: receive the visual measurement core from Endoforge.
- Derivation: `foundation_film/filmstats.py`
- Allocated to: C-PRODUCER
- Verification: T (the four video tests run only when NumPy, OpenCV and PySceneDetect are installed; CI skips them)
- Status: Baselined

### REQ-FILM-016 — argument refusal

A tool call whose arguments break the tool's input rules shall return `isError: true`, assessment `tool_error`, receipt status `error`, `result: null`, an error message of at most 1024 characters and an Evidence entry.

- Rationale: a refused request must still be a well-formed, traceable receipt.
- Derivation: `foundation_film/measures.py`, `foundation_film/tools.py`
- Allocated to: C-MEASURES, C-TOOLS
- Verification: T
- Status: Baselined

### REQ-FILM-019 — verdict rule

A judged tool shall return `thresholds_not_met` if any check fails, otherwise `not_scored` if any check is `not_measured`, otherwise `thresholds_met`.

- Rationale: an unmeasured check must never read as a pass.
- Derivation: `foundation_film/measures.py`
- Allocated to: C-MEASURES
- Verification: T
- Status: Baselined

### REQ-FILM-020 — caller overrides reported

When the caller supplies rules (`cinematic_gate`), contract values (`audio_gate`) or thresholds (`look_gate`), the result shall name them (`rule_source: caller`, `contract_overrides`, `threshold_sources`), and `look_gate` shall add a `caller` Evidence entry.

- Rationale: a caller's calibration must never pass as the Foundation's.
- Derivation: `foundation_film/cinema.py`, `foundation_film/audio.py`, `foundation_film/look.py`, `foundation_film/tools.py`
- Allocated to: C-CINEMA, C-AUDIO, C-LOOK, C-TOOLS
- Verification: T
- Status: Baselined

### REQ-FILM-021 — parity with the reference scripts

`cinematic_gate`, `reference_bands`, `drift_verdict` and `look_gate` shall reach the same per-check outcomes as the floating-point reference rules they replace (filmgate, the duration-weighted percentile, driftgate and lookgate) on seeded random inputs. For `cinematic_gate`, measured values agree within 0.001 and outcomes are compared where the value is more than 0.002 from the threshold.

- Rationale: the integer tools must not change the verdicts that the reference scripts gave.
- Derivation: `foundation_film/cinema.py`, `foundation_film/drift.py`, `foundation_film/look.py`
- Allocated to: C-CINEMA, C-DRIFT, C-LOOK
- Verification: T
- Status: Baselined

## 4. Interface requirements

### REQ-FILM-011 — bounded execution environment

The bridge and the acceptance tools shall run with the Python standard library only, open no network connection, accept no command-line arguments (exit status 2 if any are given) and read no caller-named path.

- Rationale: bounded, reproducible execution that can be pinned as a whole. See [ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds).
- Derivation: `foundation_film_bridge/server.py`, `foundation_film_bridge/__main__.py`, `foundation_film/tools.py`
- Allocated to: C-SERVER
- Verification: I, T
- Status: Baselined

### REQ-FILM-012 — input limits

The bridge shall accept each input at its limit and reject one unit beyond it with `-32002`: frame 65536 bytes, depth 32, 16384 nodes, 1024-character strings and 15-digit integers. A stream line over the frame limit shall get one `-32002` reply and end the session with exit status 2.

- Rationale: bounded execution on both sides. See [ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics).
- Derivation: `foundation_film_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-FILM-014 — initialize handshake

`initialize` with `protocolVersion` `foundation-film-jsonrpc/1` shall return that protocol version and `mcpCompatible: false`.

- Rationale: the host must not mistake the bridge for an MCP server. See [ICD §3](../icd/icd-cstack.md#3-messages-and-data-elements).
- Derivation: `foundation_film_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-FILM-015 — tool catalog

`tools/list` shall return the tool definitions from `foundation_film_bridge/schemas.py` unchanged, in the order `cinematic_gate`, `reference_bands`, `audio_gate`, `drift_verdict`, `cue_vocabulary_check`, `look_gate`.

- Rationale: the host pins the canonical inventory digest. See [ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility).
- Derivation: `foundation_film_bridge/schemas.py`, `foundation_film/tools.py`
- Allocated to: C-SCHEMAS
- Verification: T
- Status: Baselined

### REQ-FILM-017 — session order and tool names

The bridge shall answer `tools/call` before a successful `initialize` with error `-32000`, and a call naming a tool outside the catalog with error `-32602`.

- Rationale: no tool runs outside an initialized session or outside the pinned inventory.
- Derivation: `foundation_film_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-FILM-018 — numeric and key profile

The bridge shall reject duplicate object keys, non-integer numbers and `NaN` with error `-32700`.

- Rationale: numbers cross the wire only as integers; parsing is unambiguous.
- Derivation: `foundation_film_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

### REQ-FILM-022 — ping

`ping` shall return an empty result without requiring `initialize`.

- Rationale: the host can probe liveness before the handshake.
- Derivation: `foundation_film_bridge/server.py`
- Allocated to: C-SERVER
- Verification: T
- Status: Baselined

## 5. Non-functional requirements

Reusability (SWE-147), portability and design constraints are covered by REQ-FILM-007 (pinnable source), REQ-FILM-011 (standard library only for the bridge) and the CONTRIBUTING rules (no code comments, GPL-3.0-only). No performance or timing requirement is stated: none is measured or bounded by a test. Resource bounds are the bridge limits (REQ-FILM-012) and the per-tool array limits in the [tool catalog](../guides/reference/tool-catalog.md).

## 6. Not applicable categories

- Safety requirements: N/A. Not safety-critical (SMP §1).
- Control-system, operating-system, board-support-package, partitioning and hardware-interface requirements: N/A. The software commands nothing and has no hardware interface.
- User-interface requirements: N/A beyond the JSON-RPC bridge (§4) and the producer command line (REQ-FILM-013).

## 7. Qualification provisions

Tests are run with the CI commands in the [test plan](../verification/test-plan.md). Each requirement maps to tests or inspection targets in the [verification matrix](../verification/verification-matrix.md). The trace check is recorded in the [assurance record](../assurance/assurance-record.md); this repository has no trace-check tool yet.

## 8. Untested behaviour (gaps)

The code does the following, but no test checks it, so it is not stated as a requirement. TBD count: 0.

| ID | Behaviour in code | Where |
|---|---|---|
| GAP-FILM-01 | A response over 1048576 bytes is replaced by a `-32002` "Result withheld" error | `foundation_film_bridge/server.py` `encode_response` |
| GAP-FILM-02 | A second `initialize` returns `-32000`; a wrong `protocolVersion` returns `-32001` | `Bridge.dispatch` |
| GAP-FILM-03 | A message without `id` (notification) gets no reply and is not executed | `Bridge.dispatch` |
| GAP-FILM-04 | Batches, extra envelope fields, wrong `jsonrpc`, empty method and `null` or over-long ids return `-32600`; unknown methods `-32601`; non-object `arguments` `-32602` | `Bridge.dispatch` |
| GAP-FILM-05 | An unexpected exception inside a tool returns `-32603` with no result | `Bridge.dispatch` |
| GAP-FILM-06 | Error receipts carry `input_sha256` (only success receipts are asserted) | `foundation_film/tools.py` `run` |
| GAP-FILM-07 | Results conform to each tool's `outputSchema` (no test validates against the schemas) | `foundation_film_bridge/schemas.py` |
| GAP-FILM-08 | `drift_verdict` labels caller thresholds `caller` in `threshold_sources` and adds a `caller` Evidence entry | `foundation_film/drift.py`, `tools._drift` |
| GAP-FILM-09 | `FOUNDATION_FILM_PLAYBOOK` and `FOUNDATION_FILM_PRODUCERS` change the citation text in Evidence | `foundation_film/tools.py` |
| GAP-FILM-10 | `cue_vocabulary_check` measures a gap from the earlier marker's `t_ms` when it has no `end_ms` (only the `end_ms` case is asserted) | `foundation_film/cues.py` |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 5c37f74 | Initial table of REQ-FILM-001 to 012 | Initial commit |
| 1.1 | 2026-10-30 | 9725403 | Inspection-only verification methods aligned | PR #4 |
| 1.2 | 2026-11-01 | e6e6405 | REQ-FILM-013 offline producer | PR #5 |
| 1.3 | 2026-11-04 | 42a5e27 | REQ-FILM-007 excludes the root `.github/` tree | PR #11 |
| 2.0 | 2026-11-08 | 852f976 | Family standard: metadata, record format, derivation and allocation. Added REQ-FILM-014 to 022 for tested behaviour. REQ-FILM-012 states the tested limits and stream behaviour. REQ-FILM-008 and 011 gained test evidence. Untested behaviour listed as GAP-FILM-01 to 10 | docs/nasa-standard PR |

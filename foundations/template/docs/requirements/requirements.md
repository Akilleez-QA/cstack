# foundation-template software requirements specification

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-SRS |
| Version | 2.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Introduction

### 1.1 Purpose and audience

This document states what foundation-template does, as inspected in the code and checked by its tests. It serves two readers: someone changing the template itself, and someone copying it to start a new Foundation. A copy keeps the record format and the general requirements (REQ-TPL-002 to REQ-TPL-011), renames the prefix, and replaces REQ-TPL-001 and REQ-TPL-012 with its own domain tools. See [Start a new Foundation](../guides/how-to/start-a-new-foundation.md).

Every requirement below is behaviour the code has and a test or inspection checks. Behaviour the code has but no test checks is listed in §9 as a gap.

### 1.2 Scope

In scope: the domain package `foundation_template/`, the stdio JSON-RPC bridge `foundation_template_bridge/`, the tests and the tools in `tools/`. Out of scope: the host adapter in Cstack. Trust assumptions: the operator running the bridge is trusted; request content is untrusted and is bounded and validated before use.

### 1.3 System overview

foundation-template is the copy source for new Foundations in the Cstack family. It has one placeholder tool, `echo_observation`, behind the same kind of bridge every Foundation uses. The design is in the [software design description](../architecture/architecture.md) and the host interface in the [interface control document](../icd/icd-cstack.md).

## 2. Requirement record format

Each requirement has an ID, one "shall" statement, a rationale, a derivation (source paths), an allocation (SDD section), a verification method (T test, A analysis, I inspection, D demonstration) and a status (Proposed, Baselined, Deleted). IDs use `REQ-TPL-NNN` and are never reused. A copy changes the prefix in this file, in the verification matrix and in `PREFIX` in `tools/check_trace.py`. The [verification matrix](../verification/verification-matrix.md) maps each ID to tests; `tools/check_trace.py` fails when a requirement lacks a field, a matrix row or an SDD allocation.

## 3. Functional requirements: tools

### REQ-TPL-001 — Placeholder tool

The Foundation shall provide the `echo_observation` tool, which returns its validated `observation` argument unchanged as an observation with Evidence.

- Rationale: Shows the full tool path (schema, validation, receipt, Evidence) with no domain meaning. A copy replaces it.
- Derivation: `foundation_template/tools.py`, `foundation_template_bridge/schemas.py`
- Allocated to: SDD §4 (domain tools, schemas)
- Verification: T
- Status: Baselined

### REQ-TPL-012 — Placeholder argument validation

`echo_observation` shall accept exactly one argument, `observation`, a string of 1 to 256 characters, and return a tool error for any other argument set, type or length.

- Rationale: Shows exact-field and bounds checks at the tool level.
- Derivation: `foundation_template/tools.py`
- Allocated to: SDD §4 (domain tools)
- Verification: T
- Status: Baselined

## 4. Functional requirements: receipts and boundary

### REQ-TPL-003 — Read-only observation boundary

Every tool shall be read-only and return a receipt whose `boundary` has `observation_only: true` and `domain_determination` and `control_action` both `false`.

- Rationale: Foundations judge; they never act.
- Derivation: `foundation_template/tools.py`, `foundation_template_bridge/schemas.py`
- Allocated to: SDD §4 (domain tools, schemas)
- Verification: T
- Status: Baselined

### REQ-TPL-004 — Evidence on every result

Every tool result, errors included, shall carry at least one Evidence entry in `receipt.evidence`.

- Rationale: Every verdict must be traceable; a tool error records that the request was refused at the argument check.
- Derivation: `foundation_template/tools.py`, `foundation_template_bridge/schemas.py`
- Allocated to: SDD §4 (domain tools)
- Verification: T
- Status: Baselined

### REQ-TPL-005 — Input binding

Every receipt shall carry `receipt.input_sha256`, the SHA-256 of the tool arguments serialized as JSON with sorted keys and compact separators.

- Rationale: The host recomputes it to bind a result to its request.
- Derivation: `foundation_template/tools.py`
- Allocated to: SDD §4 (domain tools)
- Verification: T
- Status: Baselined

## 5. Interface requirements

### REQ-TPL-002 — Source manifest

The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships outside the root `.github/` tree, excluding Git internals, Python caches and bytecode and the manifest itself.

- Rationale: The host pins the manifest before dispatch ([ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility)).
- Derivation: `tools/build_manifest.py`, `SOURCE-MANIFEST.json`
- Allocated to: SDD §4 (manifest tool)
- Verification: T
- Status: Baselined

### REQ-TPL-006 — Bounded execution environment

The bridge shall run with the Python standard library only, open no network connection and accept no command-line options or paths.

- Rationale: Bounded, reproducible execution ([ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds)).
- Derivation: `foundation_template_bridge/server.py`, `foundation_template_bridge/__main__.py`
- Allocated to: SDD §4 (bridge server, bridge entry point)
- Verification: I and T
- Status: Baselined

### REQ-TPL-007 — Input limits

The bridge shall reject input frames over 65 536 bytes, JSON nesting over 32, more than 4096 JSON nodes, strings (values or keys) over 1024 characters and integers over 15 digits with code `-32002`, and accept inputs exactly at each limit.

- Rationale: Bounded execution on both sides ([ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds)).
- Derivation: `foundation_template_bridge/server.py`
- Allocated to: SDD §4 (bridge server)
- Verification: T
- Status: Baselined

### REQ-TPL-008 — Handshake and method dispatch

The bridge shall answer `ping` with an empty result, answer `tools/call` before `initialize` with `-32000`, return `protocolVersion` `foundation-template-jsonrpc/1` and `mcpCompatible: false` from `initialize`, and answer an unknown tool name with `-32602`.

- Rationale: A fixed, ordered protocol the host can verify ([ICD §2](../icd/icd-cstack.md#2-interface-type-and-transport)).
- Derivation: `foundation_template_bridge/server.py`
- Allocated to: SDD §4 (bridge server)
- Verification: T
- Status: Baselined

### REQ-TPL-009 — Tool inventory

`tools/list` shall return exactly `tool_definitions()`, in the order of `TOOL_NAMES`.

- Rationale: The host pins the inventory digest ([ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility)).
- Derivation: `foundation_template_bridge/schemas.py`, `foundation_template/tools.py`
- Allocated to: SDD §4 (schemas)
- Verification: T
- Status: Baselined

### REQ-TPL-010 — Numeric profile and duplicate keys

The bridge shall refuse any non-integer number, NaN, Infinity and duplicate object keys with code `-32700`.

- Rationale: The template's numeric profile is bounded integers only; a copy that needs decimals widens it deliberately (see foundation-refrigeration).
- Derivation: `foundation_template_bridge/server.py`
- Allocated to: SDD §4 (bridge server)
- Verification: T
- Status: Baselined

### REQ-TPL-011 — Process exit status

The bridge process shall exit 0 when stdin closes after complete frames, and exit 2 after reporting a frame over the byte limit or when started with any command-line argument.

- Rationale: The host can tell a clean stop from a refused session.
- Derivation: `foundation_template_bridge/server.py`, `foundation_template_bridge/__main__.py`
- Allocated to: SDD §4 (bridge server, bridge entry point)
- Verification: T
- Status: Baselined

### REQ-TPL-013 — Test report verdict

`tools/gen_reports.py` shall conclude "FAILED" and exit 1 when a unittest run exits non-zero, runs no tests, or records any outcome other than ok (skipped, expected failure, unexpected success, failed or unparsed); when the trace check reports a problem; or when the manifest, generated-catalog or Gitleaks gate fails or did not run.

- Rationale: the test plan accepts no skips and no failed gates (TP-1), so the report must not call such a run passed.
- Derivation: `tools/gen_reports.py`
- Allocated to: SDD §4 (documentation tools)
- Verification: T
- Status: Baselined

## 9. Untested behaviour (gaps)

The code does the following, but no test checks it. These are not baselined requirements; each is a candidate for a test. Found by reading the code at the baseline commit and searching `tests/` for the code path.

| Gap | Behaviour in code | Where | Missing test |
|---|---|---|---|
| GAP-TPL-001 | A wrong `protocolVersion` gives `-32001`; a second `initialize` gives `-32000`; `tools/list` before `initialize` gives `-32000` | `foundation_template_bridge/server.py` `Bridge.dispatch` | No test sends these |
| GAP-TPL-002 | A response over 1 048 576 bytes, or one that cannot be encoded, is replaced by an error "Result withheld" | `foundation_template_bridge/server.py` `encode_response` | No test produces one |
| GAP-TPL-003 | An unexpected exception becomes `-32603` | `foundation_template_bridge/server.py` | No test reaches it |
| GAP-TPL-004 | Batches, extra envelope fields, a wrong `jsonrpc` value and bad `id` types are refused with `-32600`; a request without `id` gets no response | `foundation_template_bridge/server.py` `Bridge.dispatch` | No test sends these |
| GAP-TPL-005 | A final frame without a newline closes the session with exit 2; a broken output pipe exits 2 | `foundation_template_bridge/server.py` `serve` | No test sends an unterminated frame or closes stdout |
| GAP-TPL-006 | `python -B tools/build_manifest.py --inventory` prints the canonical inventory; the normal run prints `files`, `sha256` and `inventory_sha256` | `tools/build_manifest.py` | No test runs the tool |

## 10. Non-functional requirements

Performance and timing: no requirement; the bridge is sequential and the only timing bound in the tests is a 30 s subprocess timeout. Design constraints: standard library only (REQ-TPL-006); no code comments; GPL-3.0-only. Reusability (SWE-147 analog): the template exists to be copied; [Start a new Foundation](../guides/how-to/start-a-new-foundation.md) lists every file a copy changes.

## 11. Not applicable categories

- Safety requirements: N/A. Not safety-critical (SMP §1).
- Control-system, operating-system, board-support-package, partitioning and hardware-interface requirements: N/A. The software has none of these elements.
- Data requirements: N/A for the template, which embeds no reference data. A copy that embeds data adds data requirements and provenance (see the [data dictionary](../data/data-dictionary.md#4-reference-data-provenance)).

## 12. Qualification provisions

Test (T): automated `unittest` tests, run by `python -B -m unittest discover -s tests -t .` and the same with `-O` ([test plan](../verification/test-plan.md)). Inspection (I): reading the named source files, target recorded in the verification matrix.

## 13. Open items

| ID | TBD / question | Owner | Issue |
|---|---|---|---|
| — | None. Untested behaviour is listed in §9. | — | — |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | fbfaadb | Seven requirements in one table | Initial commit |
| 1.2 | 2026-11-03 | ab81203 | REQ-TPL-002 excludes the root `.github/` tree | PR #10 |
| 2.0 | 2026-11-08 | fb9993c | NASA-standard record format; REQ-TPL-008 to REQ-TPL-012 added for tested behaviour; untested behaviour listed as gaps | PR adding the NASA-standard documentation set |
| 2.1 | 2026-11-09 | 3814683 | REQ-TPL-013 (test report verdict) | PR fixing the 2026-11-09 backfill-review findings |

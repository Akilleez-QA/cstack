# foundation-refrigeration software requirements specification

| Field | Value |
|---|---|
| Document ID | FREFRIG-SRS |
| Version | 2.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Introduction

### 1.1 Purpose and audience

This document states what foundation-refrigeration does, as inspected in the code and checked by its tests. It is for contributors changing the code, for host maintainers (Cstack) who pin it, and for reviewers checking the trace. Every requirement below is behaviour the code has and a test or inspection checks. Behaviour the code has but no test checks is listed separately in §9 as a gap. It is not hidden in a requirement.

### 1.2 Scope

In scope: the domain package `foundation_refrigeration/`, the stdio JSON-RPC bridge `foundation_refrigeration_bridge/`, the embedded data in `foundation_refrigeration/data/`, the reference points in `golden/` and the tools in `tools/`.

Out of scope: the host adapter in Cstack, the table generators that produced the data (not shipped here), and any plant, sensor or control system. Trust assumptions: the operator running the bridge is trusted; request content is untrusted and is bounded and validated before use.

### 1.3 System overview

foundation-refrigeration is a Foundation in the Cstack family. It answers read-only questions about refrigeration data: saturation pressure and temperature for nine refrigerants, pressure and temperature unit conversion, a reading compared with saturation, cited ammonia exposure limits, and equipment-kind names. A host starts the bridge as a child process and talks to it over stdio. The design is in the [software design description](../architecture/architecture.md). The host interface is in the [interface control document](../icd/icd-cstack.md). Limits on use are in [Limitations and safety-relevant use](../guides/explanation/limitations.md).

## 2. Requirement record format

Each requirement has an ID, one "shall" statement, a rationale, a derivation (source paths), an allocation (SDD section), a verification method (T test, A analysis, I inspection, D demonstration) and a status (Proposed, Baselined, Deleted). IDs use `REQ-REF-NNN` and are never reused. The verification matrix maps each ID to its tests: [verification matrix](../verification/verification-matrix.md). `tools/check_trace.py` fails when a requirement lacks a field, a matrix row or an SDD allocation.

## 3. Functional requirements: tools

### REQ-REF-001 — Saturation pressure tool

The Foundation shall provide the `saturation_pressure` tool, which returns the saturation pressure in kPa(a), six pressure views and the atmosphere used, for a fluid and a temperature inside the generated table range.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/thermo.py`
- Allocated to: SDD §4 (tool dispatcher, saturation tables)
- Verification: T
- Status: Baselined

### REQ-REF-002 — Saturation temperature tool

The Foundation shall provide the `saturation_temperature` tool, which returns the saturation temperature in degC and four temperature views for a fluid and an absolute or gauge pressure inside the generated table range.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/thermo.py`
- Allocated to: SDD §4 (tool dispatcher, saturation tables)
- Verification: T
- Status: Baselined

### REQ-REF-003 — Pressure conversion tool

The Foundation shall provide the `convert_pressure` tool, which converts a pressure between kPa(a), kPa(g), psia, psig, bar(a) and bar(g), using the stated atmosphere for gauge units.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/units.py`
- Allocated to: SDD §4 (tool dispatcher, units)
- Verification: T
- Status: Baselined

### REQ-REF-004 — Temperature conversion tool

The Foundation shall provide the `convert_temperature` tool, which converts an absolute temperature between degC, degF, K and degR.

- Rationale: domain capability exposed to the host.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/units.py`
- Allocated to: SDD §4 (tool dispatcher, units)
- Verification: T
- Status: Baselined

### REQ-REF-005 — Reading compared with saturation

The Foundation shall provide the `check_reading_against_saturation` tool, which reports superheat-style and subcooling-style deltas for one pressure and temperature reading as an observation, with no diagnosis and no normal or abnormal call.

- Rationale: domain capability exposed to the host, without crossing into diagnosis.
- Derivation: `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (tool dispatcher)
- Verification: T
- Status: Baselined

### REQ-REF-006 — Exposure limits tool

The Foundation shall provide the `exposure_limits` tool, which lists the cited ammonia exposure limits (OSHA, NIOSH, ACGIH), optionally filtered by issuer, and returns caller-supplied policy set points as a separate kind that is never a legal limit.

- Rationale: reference data for a person, with policy values kept apart from published limits.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/safety_limits.py`
- Allocated to: SDD §4 (tool dispatcher, exposure limits)
- Verification: T
- Status: Baselined

### REQ-REF-007 — Equipment-kind resolution tool

The Foundation shall provide the `resolve_equipment_kind` tool, which resolves a legacy equipment-kind term, or a line-service code when `vocabulary` is `line_service`, to the canonical `plant-taxonomy/1` entry.

- Rationale: one vocabulary across legacy sources.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration/plant_model.py`
- Allocated to: SDD §4 (tool dispatcher, plant taxonomy)
- Verification: T
- Status: Baselined

### REQ-REF-031 — Reading delta definitions

The `check_reading_against_saturation` tool shall compute the superheat-style delta as reading temperature minus dew-point temperature and the subcooling-style delta as bubble-point temperature minus reading temperature, both at the reading pressure, classify each as `above`, `below` or `within_lookup_resolution` (table error plus 0.0001 K), and list what it does not determine.

- Rationale: the deltas must be reproducible arithmetic with stated definitions, not a judgement.
- Derivation: `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (tool dispatcher)
- Verification: T
- Status: Baselined

## 4. Functional requirements: receipts and boundary

### REQ-REF-009 — Read-only observation boundary

Every tool shall be read-only and return a receipt whose `boundary` has `observation_only: true` and `engineering_determination`, `safety_determination`, `compliance_determination`, `diagnosis` and `control_action` all `false`.

- Rationale: Foundations judge; they never act.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration_bridge/schemas.py`
- Allocated to: SDD §4 (tool dispatcher, schemas)
- Verification: T
- Status: Baselined

### REQ-REF-010 — Evidence on success, explicit error on failure

Every successful tool result shall carry at least one Evidence entry in `receipt.evidence`, and every tool error shall return `isError: true`, assessment `tool_error`, `receipt.status: "error"`, a null result, an error code, empty `evidence` and `data_sources`, and the common limitations.

- Rationale: every verdict must be traceable, and a failure must never look like a result. Version 1.0 of this document said errors also carry Evidence; the code and `tests/test_bridge.py` have always returned an empty list, so the statement was corrected in version 2.0.
- Derivation: `foundation_refrigeration/tools.py`, `foundation_refrigeration_bridge/schemas.py`
- Allocated to: SDD §4 (tool dispatcher), SDD §7
- Verification: T
- Status: Baselined

### REQ-REF-011 — Input binding

Every receipt shall carry `receipt.input_sha256`, the SHA-256 of the tool arguments serialized as JSON with sorted keys and compact separators.

- Rationale: the host recomputes it to bind a result to its request.
- Derivation: `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (tool dispatcher)
- Verification: T
- Status: Baselined

### REQ-REF-034 — Deterministic receipts

The same tool name and arguments shall produce an identical receipt.

- Rationale: the host and reviewers can reproduce a result exactly.
- Derivation: `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (tool dispatcher)
- Verification: T
- Status: Baselined

## 5. Functional requirements: saturation data

### REQ-REF-019 — Lookup method and refusals

Saturation lookups shall interpolate linearly in ln(P) against 1/T between adjacent table rows, refuse any temperature or pressure outside the table with `outside_table_range`, require `side` (`bubble` or `dew`) for zeotropic blends with `side_required`, and invert consistently (temperature to pressure and back to within 1e-6 degC).

- Rationale: no extrapolation and no guessed blend side.
- Derivation: `foundation_refrigeration/thermo.py`
- Allocated to: SDD §4 (saturation tables)
- Verification: T
- Status: Baselined

### REQ-REF-020 — Agreement with reference points

Saturation lookups shall agree with the direct CoolProp 8.0.0 points in `golden/coolprop-8.0.0-points.json` within the table's lookup error plus 0.001 K in temperature and 2e-4 relative in pressure, with the generator's off-grid points in `golden/generator-golden-points.json` within the lookup error times 1.8 plus 0.002 degF, and with the ammonia anchor points 15.69, 33.49 and 181.10 psig at 0, 20 and 95 degF.

- Rationale: the tables must match the oracle they came from. Agreement with an oracle is consistency, not experimental validation.
- Derivation: `foundation_refrigeration/thermo.py`, `golden/coolprop-8.0.0-points.json`, `golden/generator-golden-points.json`
- Allocated to: SDD §4 (saturation tables, golden reference)
- Verification: T
- Status: Baselined

### REQ-REF-021 — Table provenance and integrity

The Foundation shall load exactly nine saturation tables (NH3, CO2, R134a, R290, R22, R404A, R410A, R507A, R448A), each with schema `refrigerant-saturation/1`, source `CoolProp 8.0.0`, generated CHECK evidence and no approver, rows equal to the unit conversion of the generated rows, strictly increasing temperature and pressure, bubble pressure at or above dew pressure for blends, and vapour enthalpy above liquid enthalpy.

- Rationale: the data's origin and shape are checked, not assumed.
- Derivation: `foundation_refrigeration/thermo.py`, `foundation_refrigeration/projection.py`, `foundation_refrigeration/data/refrigerant-saturation.nh3.json`
- Allocated to: SDD §4 (saturation tables, projection loader, data)
- Verification: T
- Status: Baselined

### REQ-REF-036 — Fluid names

The Foundation shall resolve a fluid name to its table after lower-casing and removing spaces, hyphens, underscores and parentheses, accept the aliases in `thermo.FLUID_ALIASES` (for example R717 and ammonia for NH3, R744 and carbon dioxide for CO2, propane for R290), and refuse any other name, an empty name, a non-string or a name over 64 characters with `unknown_fluid`.

- Rationale: common names work; an unsupported refrigerant is refused, never mapped to a near match.
- Derivation: `foundation_refrigeration/thermo.py`
- Allocated to: SDD §4 (saturation tables)
- Verification: T
- Status: Baselined

### REQ-REF-022 — No hand-typed numeric tables in source

The package Python source shall contain no list or tuple literal with five or more numeric constants; numeric reference data lives only in the JSON projections.

- Rationale: data is reviewed and hashed as data, with provenance, not hidden in code.
- Derivation: `foundation_refrigeration/thermo.py`, `foundation_refrigeration/units.py`
- Allocated to: SDD §4 (data)
- Verification: T
- Status: Baselined

## 6. Functional requirements: units and atmosphere

### REQ-REF-023 — Quantities and unit constants

Every physical input shall be a `{value, unit}` object with a listed unit and a finite, non-boolean number of magnitude at most 1e9; the Foundation shall use 1 psi = 0.45359237 × 9.80665 / 0.0254² Pa, a standard atmosphere of 101.325 kPa, refuse temperatures at or below absolute zero and refuse non-positive absolute pressures.

- Rationale: no bare numbers, no implicit units, exact constants.
- Derivation: `foundation_refrigeration/units.py`
- Allocated to: SDD §4 (units)
- Verification: T
- Status: Baselined

### REQ-REF-024 — Site atmosphere

Gauge conversions shall use the stated atmosphere basis: `standard` (101.325 kPa), `elevation` (−500 to 6000 m, `101.325 × (1 − 2.25577e-5 × h)^5.25588` kPa) or `measured` (40 to 110 kPa absolute); when the atmosphere is omitted the tool shall use the standard atmosphere and record `assumed: true`.

- Rationale: a gauge value depends on the site, and an assumption must be visible.
- Derivation: `foundation_refrigeration/units.py`, `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (units)
- Verification: T
- Status: Baselined

## 7. Functional requirements: evidence, limits, taxonomy, decisions, screens

### REQ-REF-025 — Evidence model

Evidence records shall have status `CHECK`, `APPROVED` or `DISPUTED` and a basis of kind `cited`, `generated`, `policy` or `practice` with that kind's required fields; `APPROVED` shall require `approvedBy` and `approvedOn`, approval fields shall appear only on `APPROVED`, a dispute only on `DISPUTED`, and every legacy status spelling other than `APPROVED` shall map to `CHECK`.

- Rationale: silence is not approval.
- Derivation: `foundation_refrigeration/evidence.py`
- Allocated to: SDD §4 (evidence)
- Verification: T
- Status: Baselined

### REQ-REF-026 — Published exposure-limit content

The Foundation shall hold exactly six published ammonia limits, each with a cited basis, an https URL, a quotation containing the value, retrieval date 2026-10-06 and status CHECK, with the OSHA PEL-TWA of 50 ppm as the only enforceable limit, shall record ERPG-1/2/3 as an explicit gap with no value, and shall name in its provenance only test files present in the repository.

- Rationale: the most common error in this domain is calling 25 ppm the OSHA limit; the data must make the issuer and legal status explicit.
- Derivation: `foundation_refrigeration/safety_limits.py`, `foundation_refrigeration/data/exposure-limits.json`
- Allocated to: SDD §4 (exposure limits, data)
- Verification: T
- Status: Baselined

### REQ-REF-027 — Policy set points kept separate

A caller-supplied policy set point shall need exactly `label`, `concentration` (ppm, non-negative), `set_by`, `scope` (`plant`, `client` or `expression`) and `reason`, shall be refused when its label names an issuer, a limit type or legal status, shall be returned with `legal_status: "not_a_legal_limit"`, and at most 16 shall be accepted per call.

- Rationale: an alarm level chosen by a plant must never be shown as a legal limit.
- Derivation: `foundation_refrigeration/safety_limits.py`, `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (exposure limits, tool dispatcher)
- Verification: T
- Status: Baselined

### REQ-REF-028 — Mislabel detector

`find_mislabelled_ammonia_limits` shall return each line of text that attributes a 25 ppm value to the OSHA PEL.

- Rationale: lets a caller check its own text for the common error.
- Derivation: `foundation_refrigeration/safety_limits.py`
- Allocated to: SDD §4 (exposure limits)
- Verification: T
- Status: Baselined

### REQ-REF-029 — Taxonomy closure and no guessing

Every value of every legacy list in `plant-taxonomy.json` shall resolve to a canonical kind, every kind's parent chain shall end at a root without cycles, an unknown term shall be reported unresolved with a null kind, and a resolved line-service code shall report its open decisions as `DISPUTED` with no chosen position.

- Rationale: one closed vocabulary; nothing is guessed.
- Derivation: `foundation_refrigeration/plant_model.py`, `foundation_refrigeration/data/plant-taxonomy.json`
- Allocated to: SDD §4 (plant taxonomy)
- Verification: T
- Status: Baselined

### REQ-REF-030 — Open decisions stay open

The open-decision loader shall refuse any decision that is not `DISPUTED`, has a chosen position or has fewer than two positions.

- Rationale: an unresolved expert question must not be presented as settled.
- Derivation: `foundation_refrigeration/decisions.py`, `foundation_refrigeration/data/open-decisions.json`
- Allocated to: SDD §4 (open decisions)
- Verification: T
- Status: Baselined

### REQ-REF-032 — Federal ammonia quantity screen

`process_safety.screen_ammonia_quantity` shall compare a process-maximum anhydrous-ammonia quantity range with the cited thresholds (OSHA PSM: at or above 10 000 lb; EPA RMP: above 10 000 lb), return `quantity-trigger-met`, `quantity-trigger-not-met` or `unknown`, return `unknown` with named gaps when the range straddles the threshold or any review, freshness or source field is missing, label the output as a screen with `compliance_determination: false`, and not be exposed as a bridge tool.

- Rationale: a screen that cannot overstate its result.
- Derivation: `foundation_refrigeration/process_safety.py`, `foundation_refrigeration/data/psm-thresholds.json`
- Allocated to: SDD §4 (process safety)
- Verification: T
- Status: Baselined

### REQ-REF-033 — Standard selection guard

`process_safety.assess_standard_requirement_selection` shall return `reference-supported` only when every scope, source, edition, review and access field is present and consistent, and `review-required` with the list of gaps otherwise.

- Rationale: a cited standard edition must be traceable to a retained, reviewed source.
- Derivation: `foundation_refrigeration/process_safety.py`
- Allocated to: SDD §4 (process safety)
- Verification: T
- Status: Baselined

## 8. Interface requirements

### REQ-REF-008 — Source manifest

The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships outside the root `.github/` tree, excluding Git internals, Python caches and bytecode, the manifest itself and `PR_BODY.md`.

- Rationale: the host pins the manifest before dispatch ([ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility)).
- Derivation: `tools/build_manifest.py`, `SOURCE-MANIFEST.json`
- Allocated to: SDD §4 (manifest tool)
- Verification: T
- Status: Baselined

### REQ-REF-012 — Bounded execution environment

The bridge shall run with the Python standard library only, open no network connection, accept no command-line options or paths, and read only its own package data files.

- Rationale: bounded, reproducible execution ([ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds)).
- Derivation: `foundation_refrigeration_bridge/server.py`, `foundation_refrigeration_bridge/__main__.py`, `foundation_refrigeration/projection.py`
- Allocated to: SDD §4 (bridge server, bridge entry point, projection loader)
- Verification: I and T
- Status: Baselined

### REQ-REF-013 — Input limits

The bridge shall reject input frames over 65 536 bytes, JSON nesting over 32, more than 4096 JSON nodes, strings over 1024 characters, integers over 15 digits, number literals over 24 characters, exponents, NaN, Infinity, duplicate object keys and invalid UTF-8.

- Rationale: bounded execution on both sides ([ICD §6](../icd/icd-cstack.md#6-security-and-input-bounds)).
- Derivation: `foundation_refrigeration_bridge/server.py`
- Allocated to: SDD §4 (bridge server)
- Verification: T
- Status: Baselined

### REQ-REF-017 — Handshake and method dispatch

The bridge shall answer `tools/list` and `tools/call` only after a successful `initialize` with protocol `foundation-refrigeration-jsonrpc/1` (else `-32000`), refuse any other protocol version with `-32001`, refuse a second `initialize` with `-32000`, answer unknown methods with `-32601` and unknown tool names with `-32602`, and send no response to a request without an `id`.

- Rationale: a fixed, ordered protocol the host can verify ([ICD §2](../icd/icd-cstack.md#2-interface-type-and-transport)).
- Derivation: `foundation_refrigeration_bridge/server.py`
- Allocated to: SDD §4 (bridge server)
- Verification: T
- Status: Baselined

### REQ-REF-018 — Fixed tool inventory

`tools/list` shall return exactly the seven tools in the fixed order of `TOOL_NAMES`, each with closed input and output schemas (`additionalProperties: false`) and a description stating it is not MCP and not an engineering, safety or compliance determination; repeated calls shall return identical definitions.

- Rationale: the host pins the inventory digest ([ICD §5](../icd/icd-cstack.md#5-identity-versioning-and-compatibility)).
- Derivation: `foundation_refrigeration_bridge/schemas.py`, `foundation_refrigeration/tools.py`
- Allocated to: SDD §4 (schemas)
- Verification: T
- Status: Baselined

### REQ-REF-035 — Process exit status

The bridge process shall exit 0 when stdin closes after complete frames, and exit 2 after reporting an oversized frame or a final frame without a newline, or when started with any command-line argument.

- Rationale: the host can tell a clean stop from a refused session ([ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics)).
- Derivation: `foundation_refrigeration_bridge/server.py`, `foundation_refrigeration_bridge/__main__.py`
- Allocated to: SDD §4 (bridge server, bridge entry point)
- Verification: T
- Status: Baselined

### REQ-REF-014 — Invariant relations

The local Python invariant evaluator shall compare explicit pressure and temperature quantities using `eq`, `lt` or `gt` with a 1e-6 tolerance in canonical units (kPa(a), degC), requiring an explicit atmosphere for gauge pressure.

- Rationale: domain checks received from Endoforge without engine dependencies ([ICD §9](../icd/icd-cstack.md#9-python-invariant-interface)).
- Derivation: `foundation_refrigeration/invariants.py`
- Allocated to: SDD §4 (invariant evaluator)
- Verification: T
- Status: Baselined

### REQ-REF-015 — Invariant saturation check

The evaluator shall check a claimed saturation temperature against the Foundation tables within the table's lookup error plus 0.001 K, refusing unsupported fluids, missing or invalid blend sides and pressures outside the table.

- Rationale: reference-backed claim checking.
- Derivation: `foundation_refrigeration/invariants.py`, `foundation_refrigeration/thermo.py`
- Allocated to: SDD §4 (invariant evaluator)
- Verification: T
- Status: Baselined

### REQ-REF-016 — Invariant failures and source binding

The evaluator shall return `passed: false` with a reason for unknown checks and invalid claims, never raise, leave the caller's claim unchanged, and bind every result to `library_version`, `refrigeration-invariants/0:` plus the SHA-256 of the package Python and data JSON hashes captured at import.

- Rationale: traceable, read-only local observations.
- Derivation: `foundation_refrigeration/invariants.py`
- Allocated to: SDD §4 (invariant evaluator)
- Verification: T
- Status: Baselined

### REQ-REF-037 — Test report verdict

`tools/gen_reports.py` shall conclude "FAILED" and exit 1 when a unittest run exits non-zero, runs no tests, records a skipped, failed or unparsed outcome, or records different tests in the normal and optimized runs; when the trace check reports a problem; or when the manifest, generated-docs or Gitleaks gate fails. A gate that did not run shall be listed as "not run, so not passed" in the report.

- Rationale: the test plan accepts no skips and no failed gates (TP-1), so the report must not call such a run passed.
- Derivation: `tools/gen_reports.py`
- Allocated to: SDD §4 (documentation tools)
- Verification: T
- Status: Baselined

## 9. Untested behaviour (gaps)

The code does the following, but no test checks it. These are not baselined requirements. Each is a candidate for a test, after which it becomes a requirement. Found by reading the code at the baseline commit and searching `tests/` for the code path.

| Gap | Behaviour in code | Where | Missing test |
|---|---|---|---|
| GAP-REF-001 | A response larger than 1 048 576 bytes is withheld and replaced by a `-32002` error | `foundation_refrigeration_bridge/server.py` `encode_response` | No test produces an oversized response |
| GAP-REF-002 | An unexpected exception becomes `-32603` "Internal bridge error"; an unencodable result becomes `-32603` "Result cannot be represented" | `foundation_refrigeration_bridge/server.py` | No test reaches either path |
| GAP-REF-003 | Batches, extra envelope fields, a wrong `jsonrpc` value and bad `id` types (null, float, over-long string, unsafe integer) are refused with `-32600` | `foundation_refrigeration_bridge/server.py` `Bridge.dispatch` | No test sends these envelopes |
| GAP-REF-004 | `ping` with empty params returns `{}` | `foundation_refrigeration_bridge/server.py` | No test calls `ping` |
| GAP-REF-005 | The projection loader refuses path-like names, duplicate keys, NaN or Infinity, and envelope or schema mismatches | `foundation_refrigeration/projection.py` `load` | No test feeds a bad projection |
| GAP-REF-006 | Load-time validation of saturation rows (`projection_invalid`), exposure-limit rows, taxonomy aliases and parents, and PSM threshold quotes | `foundation_refrigeration/thermo.py`, `safety_limits.py`, `plant_model.py`, `process_safety.py` | Only the shipped, valid data is loaded in tests |
| GAP-REF-007 | Tool error codes `invalid_issuer`, `invalid_vocabulary` and `invalid_term` | `foundation_refrigeration/tools.py` | No test triggers these codes |
| GAP-REF-008 | A broken stdout pipe or other `OSError` ends the session with exit 2 | `foundation_refrigeration_bridge/server.py` `serve` | No test closes the output pipe |

## 10. Non-functional requirements

Performance and timing: no requirement. The bridge is sequential and the tests set no timing bound except a 30 s subprocess timeout in `tests/test_bridge.py`. Memory and output size are bounded by REQ-REF-013 and GAP-REF-001.

Design constraints: standard library only (REQ-REF-012); no code comments (CONTRIBUTING); no numeric tables in source (REQ-REF-022); GPL-3.0-only.

Reusability (SWE-147 analog): the package and bridge run from a source checkout with no installation, and `foundation-template` documents how a new Foundation copies this shape.

## 11. Not applicable categories

- Safety requirements: N/A. The software is not safety-critical (SMP §1).
- Control-system, operating-system, board-support-package, partitioning and hardware-interface requirements: N/A. The software has none of these elements and commands no hardware.
- Requirements on the table generators: N/A here. The generators are not shipped in this repository; their identity is recorded in the data dictionary.

## 12. Qualification provisions

Test (T): automated `unittest` tests, run by `python -B -m unittest discover -s tests -t .` and the same with `-O` ([test plan](../verification/test-plan.md)). Inspection (I): reading the named source files, with the target recorded in the verification matrix. Analysis and demonstration: not used at this baseline.

## 13. Open items

| ID | TBD / question | Owner | Issue |
|---|---|---|---|
| — | None. Untested behaviour is listed in §9. | — | — |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 9b459ef | Initial thirteen requirements in one table | Initial commit |
| 1.1 | 2026-11-01 | 4bd3311 | REQ-REF-014 to REQ-REF-016 for the invariant evaluator | PR #3 |
| 1.2 | 2026-11-04 | f51290c | REQ-REF-008 excludes the root `.github/` tree | PR #9 |
| 2.0 | 2026-11-08 | 62764c7 | NASA-standard record format; REQ-REF-010 corrected to match code; REQ-REF-017 to REQ-REF-036 added for tested behaviour; untested behaviour listed as gaps | PR adding the NASA-standard documentation set |
| 2.1 | 2026-11-09 | e58a71c | REQ-REF-037 (test report verdict) | PR fixing the 2026-11-09 backfill-review findings |

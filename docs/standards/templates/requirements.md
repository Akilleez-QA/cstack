# <Repo> software requirements specification

| Field | Value |
|---|---|
| Document ID | <CODE>-SRS |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWEHB 5.09. NPR SWE-050, 051, 052, 053, 054, 055, 210. Keep existing IDs; new IDs follow the repo scheme; never reuse a retired ID (mark it Deleted). Describe inspected behavior or accepted obligations, not aspirations. -->

## 1. Introduction

### 1.1 Purpose and audience
### 1.2 Scope
<!-- What is in and out. Trust assumptions (e.g. trusted single operator, untrusted requests). -->
### 1.3 System overview
<!-- Where this software sits in the family; link SDD and ICDs. -->

## 2. Requirement record format

Each requirement has: ID, one "shall" statement, rationale, derivation (source paths), allocated-to (SDD section), verification method (T test, A analysis, I inspection, D demonstration) and status (Proposed, Baselined, Deleted).

## 3. Functional requirements

### <PREFIX>-REQ-001 — <short name>

<The software shall ...>

- Rationale:
- Derivation: `<path>`
- Allocated to: SDD §<n>
- Verification: T — see verification matrix
- Status: Baselined

<!-- Group by: states and modes; data; input validation and error handling; algorithms; security and privacy; fault management (fail-closed behavior, timeouts, quarantine). -->

## 4. Interface requirements

<!-- External software, user (CLI/UI), communication (stdio JSON-RPC, HTTP), service/API. Each cites its ICD. -->

## 5. Non-functional requirements

<!-- Performance and timing (only measured or bounded values), quality attributes (reliability, maintainability, portability, reusability SWE-147), design constraints (stdlib-only, licenses, no-comments rule), resource limits (output bounds, memory). -->

## 6. Not applicable categories

<!-- One line each, e.g.: Safety requirements: N/A, not safety-critical (SMP §1). Control-system, operating-system, board-support-package, partitioning, hardware-interface requirements: N/A, no such elements. -->

## 7. Qualification provisions

<!-- How each method is applied; link test-plan.md and verification-matrix.md. -->

## 8. Open items

| ID | TBD / question | Owner | Issue |
|---|---|---|---|

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

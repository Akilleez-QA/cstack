# <Repo> <interface name> interface control document

| Field | Value |
|---|---|
| Document ID | <CODE>-ICD-NAME |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWEHB 5.02 (schema-level, not bit-level). NPR SWE-050, 052, 057, 058. One file per external interface: docs/icd/icd-<name>.md. -->

## 1. Interfacing entities and ownership

| Side | Entity | Owns |
|---|---|---|

## 2. Interface type and transport

<!-- e.g. stdio JSON-RPC 2.0, newline-delimited; CLI; library API; files. Framing, encoding, ordering, concurrency, timeouts. -->

## 3. Messages and data elements

<!-- Generate from the schema/catalog. Record the generator command. -->

| Message / call | Field | Type | Units | Range / limits | Required | Meaning |
|---|---|---|---|---|---|---|

## 4. Errors and result semantics

| Condition | Response | Caller action | Test |
|---|---|---|---|

## 5. Identity, versioning and compatibility

<!-- Catalog / manifest digests, version fields, what counts as a breaking change, how compatibility is checked (test name). -->

## 6. Security and input bounds

<!-- Admission checks, size limits, authority/grants, quarantine. -->

## 7. Requirements addressed

| Requirement | Section |
|---|---|

## 8. Change acceptance

<!-- Who must review, which tests must pass, how pins are bumped on both sides. -->

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

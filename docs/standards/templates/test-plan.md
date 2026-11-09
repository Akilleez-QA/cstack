# <Repo> software test plan and procedures

| Field | Value |
|---|---|
| Document ID | <CODE>-STP |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWEHB 5.10 merged with 5.14. NPR SWE-065, 066, 068, 071, 073, 187, 189, 190, 191, 211, 062, 186. Commands must be identical to CI. -->

## 1. Scope and approach

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | | | |
| Integration | | | |
| System / end-to-end | | | |
| Regression | Full suite on every PR | CI | |

<!-- Add performance / security / acceptance rows only if they exist. -->

## 3. Test environment

| Item | Values | Source |
|---|---|---|
| OS | | CI matrix |
| Runtime | | |
| External services | <none / live, how isolated> | |

## 4. Pass criteria and acceptance

<!-- E.g. all tests pass, zero new static-analysis findings, trace check passes. Known accepted failures listed with issue. -->

## 5. Coverage

<!-- Tool, command, last measured value with commit. MC/DC: N/A (not safety-critical, SWE-219). -->

## 6. Test data and fixtures

## 7. Procedures

<!-- Automated tests: the code is the procedure; give the command per suite. Manual or live procedures get numbered entries below. -->

### TP-1 — <name>

- Purpose / requirements:
- Preconditions:
- Steps:
- Inputs:
- Expected result and pass/fail criteria:
- Last run: <date>, commit <sha>, result

## 8. Test risks and limitations

## 9. Traceability

See [verification matrix](verification-matrix.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

# <Repo> configuration management plan

| Field | Value |
|---|---|
| Document ID | <CODE>-SCMP |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWEHB 5.06. NPR SWE-079–085, 045, 146, 206. Extend the existing cstack document rather than replacing it. -->

## 1. Organization and responsibilities

## 2. Configuration identification

| Item | Identity | Control point |
|---|---|---|

<!-- Baselines are commits/tags; branch names are mutable. Include vendored sources, manifests, catalogs, lockfiles, CI workflows, docs. -->

### 2.1 Byte identities

<!-- Generated: `sha256sum <files>` at baseline. -->

| File | SHA-256 |
|---|---|

## 3. Change control

<!-- Branch protection, required checks, merge train, who approves, how pins are bumped. -->

## 4. Status accounting

<!-- Tags, CHANGELOG, VDDs, manifests; where to see what is in a release. -->

## 5. Configuration audits

<!-- Release-time audit (docs baseline = tag, manifests = files, VDD = artifacts); recorded in SAR. -->

## 6. Generated outputs

<!-- Generators, their inputs and pinned versions; whether outputs are committed; edits to generated files forbidden or how controlled. "None" if none. -->

## 7. Release management and delivery

<!-- Tagging, release notes, artifacts, distribution channel, VDD generation. -->

## 8. Plan maintenance

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

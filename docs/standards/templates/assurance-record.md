# <Repo> assurance record

| Field | Value |
|---|---|
| Document ID | <CODE>-SAR |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- Rolling record. SWEHB 5.21 (requirements analysis), 5.22 (design analysis), 5.23 (testing analysis), 5.25 (audit), 5.26 (code quality), 5.03 summary. NPR SWE-051, 054, 055, 135, 185, 207, 068, 084, 087, 201. Newest entry first. Short entries are fine; techniques used must still be listed. -->

## Entry <YYYY-MM-DD> — baseline <sha> (<tag or PR>)

- Analyzed by: <maintainer / agent session name> (agent analysis is not independent)
- Inputs: <documents and versions>

### Requirements analysis

<!-- Techniques: trace check, ambiguity/testability review, orphan check. Findings: missing, untestable, untraced, unnecessary. -->

### Design analysis

<!-- SDD vs code: components that exist but are undocumented, documented but absent, requirement allocations that don't hold. -->

### Testing analysis

<!-- Matrix rows vs tests; tests with wrong or weak assertions; coverage gaps; flaky tests. -->

### Source code quality

| Tool | Command | Findings (new / total) |
|---|---|---|

### Configuration audit

<!-- Docs baseline vs code; manifest digests vs files; VDD vs artifacts. -->

### Peer review summary

<!-- PRs merged in range; how many had findings; notable defects. Generated with gh. -->

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|

### Overall assessment

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

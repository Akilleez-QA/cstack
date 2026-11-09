# <Repo> verification matrix

| Field | Value |
|---|---|
| Document ID | <CODE>-VM |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- NPR SWE-052 bidirectional traceability. Pass criteria in family-doc-standard.md §5. Never embed historical pass counts; "Last result" points to an STR. -->

Trace check: `<tools/check_trace.py or manual steps>` at commit `<sha>`: <pass/fail summary>.

| Requirement | Method | Test (file::Class.method) or inspection target | Acceptance observation / limit | Last result |
|---|---|---|---|---|
| <PREFIX>-REQ-001 | T | `tests/test_x.py::XTests.test_y` | | STR-<tag> |

## Tests without a requirement

| Test | Classification (supporting / infrastructure / candidate requirement) |
|---|---|

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

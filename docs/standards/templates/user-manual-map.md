# <Repo> user manual map

| Field | Value |
|---|---|
| Document ID | <CODE>-SUM-MAP |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- SWEHB 5.12 tailored: the user manual is README + Diátaxis guides. This map proves coverage. Install as docs/guides/SUM-MAP.md. Every "Where" cell must link an existing section; write N/A with reason otherwise. -->

| SUM element | Where | Verified how |
|---|---|---|
| Application summary and intended users | README §intro, Status | |
| Inventory (what is installed / shipped) | README §What is inside; VDD | |
| Environment and prerequisites | README §Quickstart; guides/reference | |
| Modes and states of operation | guides/explanation/ | |
| Security and privacy | SECURITY.md; guides/explanation/ | |
| Assistance and problem reporting | SUPPORT.md; issue templates | |
| First-time use | guides/tutorials/<first>.md | Tutorial run at <commit> |
| Starting, stopping, suspending | guides/how-to/ | |
| Capabilities and commands reference | guides/reference/ | Generated from <--help / catalog> |
| Conventions (IDs, units, file layout) | guides/reference/; data dictionary | |
| Processing procedures | guides/how-to/ | |
| Data backup and recovery from errors | guides/how-to/troubleshooting.md | |
| Messages, errors and exit codes | guides/reference/errors.md | Generated from <enum> |
| Assumptions and limitations | README §Not included; guides/explanation/limitations.md | |
| Safety-related constraints | guides/explanation/limitations.md | |
| Version-specific changes | CHANGELOG; docs/releases/ | |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

# foundation-template user manual map

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-SUM-MAP |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

The user manual is the README plus the guides. This map shows where each user-manual element (SWEHB 5.12) lives. A copy keeps the map and updates the targets.

| SUM element | Where | Verified how |
|---|---|---|
| Application summary and intended users | [README](../../README.md#foundation-template), [Status](../../README.md#status) | Read against the code at the baseline commit |
| Inventory (what is shipped) | [README: What is inside](../../README.md#what-is-inside), [Layout](../../README.md#layout); [version descriptions](../releases/README.md) | Version description generated from `SOURCE-MANIFEST.json` |
| Environment and prerequisites | [README: Quickstart](../../README.md#quickstart); [SMP §4](../plan/software-management-plan.md#4-engineering-and-test-environment) | Quickstart run at the baseline commit |
| Modes and states of operation | [Explanation: Modes and states](explanation/README.md#modes-and-states) | Checked against `foundation_template_bridge/server.py` |
| Security and privacy | [SECURITY.md](../../SECURITY.md); [SMP §7](../plan/software-management-plan.md#7-security-privacy-and-secure-coding) | Read against the code |
| Assistance and problem reporting | [SUPPORT.md](../../SUPPORT.md); [issue templates](../../.github/ISSUE_TEMPLATE/problem-report.md) | Files exist |
| First-time use | [Tutorial: first bridge session](tutorials/first-bridge-session.md) | Run at the baseline commit; output pasted |
| Starting, stopping, suspending | [Tutorial](tutorials/first-bridge-session.md); [ICD §2](../icd/icd-cstack.md#2-interface-type-and-transport). Suspending: not supported | Tutorial run |
| Capabilities and commands reference | [Tool catalog](reference/tool-catalog.md); [Reference: Commands](reference/README.md#commands) | Catalog generated from the schemas |
| Conventions (IDs, units, file layout) | [Data dictionary](../data/data-dictionary.md#2-data-elements); [README: Layout](../../README.md#layout) | Read against the code |
| Processing procedures | [How-to guides](how-to/README.md); [Start a new Foundation](how-to/start-a-new-foundation.md) | Commands run at the baseline commit |
| Data backup and recovery from errors | [How-to: Recover after an error](how-to/README.md#recover-after-an-error). Backup: not applicable | Read against `server.serve` |
| Messages, errors and exit codes | [Tool catalog](reference/tool-catalog.md#json-rpc-error-codes); [exit status](reference/README.md#bridge-exit-status); [troubleshooting](how-to/README.md#troubleshooting) | Error tables generated from the source |
| Assumptions and limitations | [README: Limitations](../../README.md#limitations); [Limitations](explanation/limitations.md) | Read against the code |
| Safety-related constraints | [Limitations](explanation/limitations.md): none for the placeholder | Read against the code |
| Version-specific changes | [CHANGELOG](../../CHANGELOG.md); [version descriptions](../releases/README.md) | Reviewed in the pull request |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | fb9993c | Initial baseline | PR adding the NASA-standard documentation set |

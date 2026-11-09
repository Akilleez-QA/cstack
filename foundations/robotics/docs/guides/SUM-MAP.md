# foundation-robotics user manual map

| Field | Value |
|---|---|
| Document ID | FROBO-SUM-MAP |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

The user manual (SWEHB 5.12, tailored) is the README plus the guides. This map shows where each element lives.

| SUM element | Where | Verified how |
|---|---|---|
| Application summary and intended users | [README](../../README.md) intro and Status | Checked against code at baseline |
| Inventory (what is shipped) | [README, What is inside](../../README.md#what-is-inside); [version descriptions](../releases/README.md) | VDD generated from the tree |
| Environment and prerequisites | [README, Quickstart](../../README.md#quickstart); [test plan §3](../verification/test-plan.md#3-test-environment-and-exact-ci-commands) | Quickstart run at baseline |
| Modes and states of operation | [ICD §2 and §3](../icd/icd-cstack.md#2-interface-type-and-transport) (uninitialized, initialized; end of input) | `tests/test_bridge.py` |
| Security and privacy | [SECURITY.md](../../SECURITY.md); [limitations](explanation/limitations.md#misuse-and-security-considerations) | Inspection |
| Assistance and problem reporting | [SUPPORT.md](../../SUPPORT.md); [issue templates](../../.github/ISSUE_TEMPLATE/) | Files exist |
| First-time use | [Tutorial: your first motion check](tutorials/first-check.md) | Tutorial run end to end at baseline plus this change, 2026-11-08 (test plan TP-1) |
| Starting, stopping, suspending | [Tutorial](tutorials/first-check.md); [ICD §2](../icd/icd-cstack.md#2-interface-type-and-transport) (start command, end of input, exit statuses) | `tests/test_bridge.py` |
| Capabilities and commands reference | [Tool catalog](reference/tool-catalog.md) | Generated from `schemas.py` |
| Conventions (IDs, units, file layout) | [Data dictionary §2](../data/data-dictionary.md#2-data-elements-and-conventions); [README, Layout](../../README.md#layout) | Checked against `measures.py` |
| Processing procedures | [How-to guides](how-to/README.md) | Commands run at baseline |
| Data backup and recovery from errors | [How-to, Troubleshoot an error](how-to/README.md#troubleshoot-an-error). Backup: not applicable, the tools store no data | — |
| Messages, errors and exit codes | [ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics) | Checked against `server.py`; tested codes marked |
| Assumptions and limitations | [README, Limitations](../../README.md#limitations); [limitations](explanation/limitations.md) | Inspection |
| Safety-related constraints | [Limitations and safety-relevant use](explanation/limitations.md#use-in-safety-engineering-or-regulated-decisions) | Inspection |
| Version-specific changes | [CHANGELOG](../../CHANGELOG.md); [releases](../releases/README.md) | — |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | b4de079 | Initial baseline | docs/nasa-standard PR |

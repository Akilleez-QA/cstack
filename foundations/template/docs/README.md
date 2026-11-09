# Documentation

Control documents carry their own baseline commits. Reading or indexing them does not create a new verification result. Classification: self-assessed Class E analog, not safety-critical; this is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

**This documentation set is the template for a new Foundation's documentation.** Each control document below is a filled-in instance for the template itself: copy the repository, then follow [Start a new Foundation](guides/how-to/start-a-new-foundation.md) to adapt every document. The set follows the Cstack family documentation standard (organized after NASA software documentation guidance, tailored for a small open-source project).

## Start here

| Need | Index |
|---|---|
| Run it for the first time | [Tutorials](guides/tutorials/README.md) |
| Do a specific task | [How-to guides](guides/how-to/README.md) |
| Look up tools, fields, errors, commands | [Reference](guides/reference/README.md) |
| Understand the design and limits | [Explanation](guides/explanation/README.md) |
| Where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

## Control documents

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | FTEMPLATE-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | FTEMPLATE-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | FTEMPLATE-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | FTEMPLATE-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Interfaces | FTEMPLATE-ICD-CSTACK | 5.02 | [icd/icd-cstack.md](icd/icd-cstack.md) |
| Data dictionary | FTEMPLATE-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) (generated: [tool catalog](guides/reference/tool-catalog.md)) |
| Test plan and procedures | FTEMPLATE-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | FTEMPLATE-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports | FTEMPLATE-STR-* | 5.11, 5.05 | [verification/reports/](verification/reports/README.md) |
| Configuration management | FTEMPLATE-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions | FTEMPLATE-VDD-* | 5.16 | [releases/](releases/README.md) |
| Assurance record | FTEMPLATE-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |
| User manual map | FTEMPLATE-SUM-MAP | 5.12 | [guides/SUM-MAP.md](guides/SUM-MAP.md) |

Problem reports and change requests (5.01) use the [issue templates](../.github/ISSUE_TEMPLATE/problem-report.md); peer review (5.03) uses the [pull request template](../.github/pull_request_template.md).

Not applicable for this repository (rationale in the SMP and the [compliance matrix](plan/compliance-matrix.md)): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24; replaced by the [limitations page](guides/explanation/limitations.md), which a copy with engineering or safety-relevant data must fill in). This repository has no `docs/rules/` folder; contribution rules are in [CONTRIBUTING.md](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).

See [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [Support](../SUPPORT.md).

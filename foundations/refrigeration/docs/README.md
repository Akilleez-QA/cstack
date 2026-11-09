# Documentation

foundation-refrigeration is a read-only checker for refrigeration numbers: saturation tables, unit conversion, cited ammonia exposure limits and equipment names, each returned with its source. The [README](../README.md) shows what it does in one example.

**Exposure limits and other data here are not for life-safety decisions.** Read [Limitations and safety-relevant use](guides/explanation/limitations.md) first.

## Find what you need

| I want to | Go to |
|---|---|
| Learn: run it for the first time | [Tutorial: your first bridge session](guides/tutorials/first-bridge-session.md) ([all tutorials](guides/tutorials/README.md)) |
| Do a task: run tests, rebuild the manifest, check links | [How-to guides](guides/how-to/README.md) |
| Look up a tool, argument, unit, error or command | [Reference](guides/reference/README.md), including the [tool catalog](guides/reference/tool-catalog.md) |
| Understand the design and its limits | [Explanation](guides/explanation/README.md) and [Limitations and safety-relevant use](guides/explanation/limitations.md) |
| See where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

Also: [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [Support](../SUPPORT.md).

## Engineering records

These documents record how the software is planned, specified, built and verified. They are organized after NASA software documentation guidance. Each carries its own baseline commit; reading or indexing them does not create a new verification result.

Classification: self-assessed Class E analog, not safety-critical, and Class E only because no real engineering decision depends on this software; this is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | FREFRIG-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | FREFRIG-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | FREFRIG-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | FREFRIG-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Interfaces | FREFRIG-ICD-CSTACK | 5.02 | [icd/icd-cstack.md](icd/icd-cstack.md) |
| Data dictionary | FREFRIG-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) (generated: [reference data provenance](data/reference-data.md)) |
| Test plan and procedures | FREFRIG-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | FREFRIG-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports | FREFRIG-STR-* | 5.11, 5.05 | [verification/reports/](verification/reports/README.md) |
| Configuration management | FREFRIG-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions | FREFRIG-VDD-* | 5.16 | [releases/](releases/README.md) |
| Assurance record | FREFRIG-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |
| User manual map | FREFRIG-SUM-MAP | 5.12 | [guides/SUM-MAP.md](guides/SUM-MAP.md) |

Problem reports and change requests (5.01) use the [issue templates](../.github/ISSUE_TEMPLATE/problem-report.md); peer review (5.03) uses the [pull request template](../.github/pull_request_template.md).

Not applicable for this repository (rationale in the SMP and the [compliance matrix](plan/compliance-matrix.md)): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24; replaced by the limitations page). This repository has no `docs/rules/` folder; contribution rules are in [CONTRIBUTING.md](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).

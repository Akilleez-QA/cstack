# Documentation

foundation-film is a read-only checker for film production measurements: shots, soundtrack mix, drift in generated clips, cue timing and look. The [README](../README.md) shows what it does in one example.

**Results are observations, not acceptance decisions.** Read [Limitations](guides/explanation/limitations.md) to see what a pass does and does not mean.

## Find what you need

| I want to | Go to |
|---|---|
| Learn: send my first check | [Tutorial: your first film check](guides/tutorials/first-check.md) ([all tutorials](guides/tutorials/README.md)) |
| Do a task: measure a video, override a default, fix an error | [How-to guides](guides/how-to/README.md) |
| Look up a tool, field, range or error | [Reference](guides/reference/README.md), including the [tool catalog](guides/reference/tool-catalog.md) |
| Understand the checks and their limits | [How the checks work](guides/explanation/how-the-checks-work.md) and [Limitations](guides/explanation/limitations.md) ([all explanation](guides/explanation/README.md)) |
| See where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

Also: [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [Support](../SUPPORT.md).

## Engineering records

These documents record how the software is planned, specified, built and verified. They are organized after NASA software documentation guidance. Each carries its own baseline commit; reading or indexing them does not create a new verification result.

Classification: self-assessed Class E analog, not safety-critical. This is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | FFILM-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | FFILM-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | FFILM-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | FFILM-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Interface: Cstack stdio bridge | FFILM-ICD-CSTACK | 5.02 | [icd/icd-cstack.md](icd/icd-cstack.md) |
| Data dictionary | FFILM-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) (generated part: [defaults](data/defaults.md)) |
| Test plan and procedures | FFILM-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | FFILM-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports | FFILM-STR-* | 5.11, 5.05 | [verification/reports/](verification/reports/README.md) |
| Configuration management | FFILM-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions | FFILM-VDD-* | 5.16 | [releases/](releases/README.md) |
| Assurance record | FFILM-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |

This repository has no `rules/` folder; contributor rules are in [CONTRIBUTING](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).

Not applicable for this family (rationale in the SMP and the compliance matrix): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24, replaced by the limitations page).


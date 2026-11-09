# Documentation

foundation-robotics is a read-only checker that tells you whether motion numbers obey physics. The [README](../README.md) shows what it does in one example.

**Results are observations, not engineering approvals.** Read [Limitations and safety-relevant use](guides/explanation/limitations.md) before any safety or engineering use.

## Find what you need

| I want to | Go to |
|---|---|
| Learn: send my first check | [Tutorial: your first motion check](guides/tutorials/first-check.md) ([all tutorials](guides/tutorials/README.md)) |
| Do a task: override a threshold, send z-up coordinates, fix an error | [How-to guides](guides/how-to/README.md) |
| Look up a tool, field, range or error | [Reference](guides/reference/README.md), including the [tool catalog](guides/reference/tool-catalog.md) |
| Understand the physics and the limits | [How the checks work](guides/explanation/how-the-checks-work.md) and [Limitations and safety-relevant use](guides/explanation/limitations.md) ([all explanation](guides/explanation/README.md)) |
| See where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

Also: [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [Support](../SUPPORT.md).

## Engineering records

These documents record how the software is planned, specified, built and verified. They are organized after NASA software documentation guidance. Each carries its own baseline commit; reading or indexing them does not create a new verification result.

Classification: self-assessed Class E analog, not safety-critical; Class E holds only because no real engineering decision depends on this software. This is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | FROBO-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | FROBO-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | FROBO-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | FROBO-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Interface: Cstack stdio bridge | FROBO-ICD-CSTACK | 5.02 | [icd/icd-cstack.md](icd/icd-cstack.md) |
| Data dictionary | FROBO-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) (generated parts: [defaults](data/defaults.md), [calibration cases](data/calibration-cases.md)) |
| Test plan and procedures | FROBO-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | FROBO-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports | FROBO-STR-* | 5.11, 5.05 | [verification/reports/](verification/reports/README.md) |
| Configuration management | FROBO-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions | FROBO-VDD-* | 5.16 | [releases/](releases/README.md) |
| Assurance record | FROBO-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |

This repository has no `rules/` folder; contributor rules are in [CONTRIBUTING](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).

Not applicable for this family (rationale in the SMP and the compliance matrix): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24, replaced by the limitations page).

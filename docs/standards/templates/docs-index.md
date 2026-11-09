# Documentation

<!-- Install as docs/README.md. Keep the cstack shape: Diátaxis entry points first, then control documents. Every row must link an existing file. -->

Control documents carry their own baseline commits. Reading or indexing them does not create a new verification result. Classification: self-assessed Class E analog, not safety-critical; this is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

## Start here

| Need | Index |
|---|---|
| Run it for the first time | [Tutorials](guides/tutorials/README.md) |
| Do a specific task | [How-to guides](guides/how-to/README.md) |
| Look up commands, tools, fields, errors | [Reference](guides/reference/README.md) |
| Understand the design and limits | [Explanation](guides/explanation/README.md) |
| Where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

## Control documents

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | <CODE>-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | <CODE>-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | <CODE>-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | <CODE>-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Interfaces | <CODE>-ICD-* | 5.02 | [icd/](icd/) |
| Data dictionary | <CODE>-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) |
| Test plan and procedures | <CODE>-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | <CODE>-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports | <CODE>-STR-* | 5.11, 5.05 | [verification/reports/](verification/reports/) |
| Configuration management | <CODE>-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions | <CODE>-VDD-* | 5.16 | [releases/](releases/README.md) |
| Assurance record | <CODE>-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |
| Repository rules | — | — | [rules/](rules/) |

Not applicable for this family (rationale in the SMP): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24).

See [Contributing](../CONTRIBUTING.md) and [Security](../SECURITY.md).

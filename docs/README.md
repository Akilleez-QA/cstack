# Documentation

Cstack's documents, by what you need. The guides follow [Diátaxis](https://diataxis.fr/): tutorials teach, how-to guides solve a task, reference states facts, explanation gives background. The control documents follow the [Cstack family documentation standard](standards/family-doc-standard.md), whose canonical copy lives here.

Control documents carry their own baseline commits. Reading or indexing them does not create a new verification result. Classification: self-assessed Class E analog, not safety-critical; this is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

## Start here

| Need | Start with |
|---|---|
| Install Cstack and run your first goals | [Tutorial: first run](guides/tutorials/first-run.md) |
| Run the CI checks before a pull request | [How to run CI checks locally](guides/how-to/run-ci-locally.md) |
| Move to a newer EndoForge | [How to repin EndoForge](guides/how-to/repin-endoforge.md) |
| Other tasks: bots, merge train, domains | [How-to guides](guides/how-to/README.md) |
| Look up a command, config key or environment variable | [Reference](guides/reference/README.md) |
| Understand how EndoForge, the server and the adapters fit | [Explanation](guides/explanation/README.md) |
| Know what results mean and what Cstack does not do | [Limitations and safety-relevant use](guides/explanation/limitations.md) |
| Find where each user-manual topic lives | [User manual map](guides/SUM-MAP.md) |

## Control documents

| Document | ID | SWEHB | Path |
|---|---|---|---|
| Software management plan | CSTACK-SMP | 5.08, 5.04, 5.17, 5.27 | [plan/software-management-plan.md](plan/software-management-plan.md) |
| Requirements mapping matrix | CSTACK-RMM | 7.16 | [plan/compliance-matrix.md](plan/compliance-matrix.md) |
| Requirements | CSTACK-SRS | 5.09 | [requirements/requirements.md](requirements/requirements.md) |
| Design | CSTACK-SDD | 5.13 | [architecture/architecture.md](architecture/architecture.md) |
| Foundation interfaces | CSTACK-ICD-FOUNDATIONS | 5.02 | [icd/icd-foundations.md](icd/icd-foundations.md) |
| EndoForge interface | CSTACK-ICD-ENDOFORGE | 5.02 | [icd/icd-endoforge.md](icd/icd-endoforge.md) |
| EndoForge source pin | CSTACK-ICD-ENDOFORGE-PIN | 5.02 | [icd/icd-endoforge-pin.md](icd/icd-endoforge-pin.md) |
| POODO source interface | CSTACK-ICD-POODO | 5.02 | [icd/icd-poodo.md](icd/icd-poodo.md) |
| Data dictionary (generated) | CSTACK-DD | 5.07 | [data/data-dictionary.md](data/data-dictionary.md) |
| Test plan and procedures | CSTACK-STP | 5.10, 5.14 | [verification/test-plan.md](verification/test-plan.md) |
| Verification matrix | CSTACK-VM | SWE-052 | [verification/verification-matrix.md](verification/verification-matrix.md) |
| Test reports (generated) | CSTACK-STR-* | 5.11, 5.05 | [verification/reports/STR-baseline.md](verification/reports/STR-baseline.md) |
| Configuration management plan | CSTACK-SCMP | 5.06 | [configuration/configuration-management.md](configuration/configuration-management.md) |
| Version descriptions (generated) | CSTACK-VDD-* | 5.16 | [releases/README.md](releases/README.md) |
| Assurance record | CSTACK-SAR | 5.21–5.23, 5.25, 5.26 | [assurance/assurance-record.md](assurance/assurance-record.md) |
| User manual map | CSTACK-SUM-MAP | 5.12 | [guides/SUM-MAP.md](guides/SUM-MAP.md) |
| Repository rules | — | — | [rules/no-comments.md](rules/no-comments.md) |

Not applicable (rationale in the SMP and the standard): training plan (5.15), safety plan (5.18), assurance status report (5.19), IV&V plan (5.20), hazard report (5.24; the limitations page stands in).

## Verification records

These are measurement and acceptance records kept as written.

| Document | Scope |
|---|---|
| [Foundation routes](verification/foundation-routes.md) | Measured routes from a workcell into each Foundation (2026-11-06) |
| [Wiring acceptance](verification/wiring-acceptance.md) | The acceptance frozen before end-to-end wiring (historical) |

## Family standard

| Document | Use |
|---|---|
| [Family documentation standard](standards/family-doc-standard.md) | What each family repository documents, where and how |
| [Documentation checklist](standards/doc-checklist.md) | Paste into a docs pull request and tick |
| [Templates](standards/templates/README.md) | Skeletons for each control document, issue and PR template |

Other family repositories link to https://github.com/Akilleez-QA/cstack/tree/main/docs/standards instead of copying it.

Decision records and contracts live in [`contracts/`](../contracts/): [ADR 001](../contracts/DECISION.md) and DECISION-003 to DECISION-006, the [interfaces](../contracts/INTERFACES.md) and the [acceptance contract](../contracts/ACCEPTANCE.md).

## Repository layout exception

Python entry points and composition files (`cli.py`, `bootstrap.py`, `__init__.py` and `__main__.py`) remain at the repository root. See the [repository layout](../README.md#layout). The documentation directories do not change those import paths.

See [Contributing](../CONTRIBUTING.md) for the review workflow and local checks, [Security](../SECURITY.md) for reporting guidance and [Support](../SUPPORT.md) for help.

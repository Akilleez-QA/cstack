# Documentation

Find what you need by what you want to do. New here? Start with the [README](../README.md), then the tutorial.

## Learn

| You will | Start with |
|---|---|
| Install Cstack and run a Foundation call, an approval and a forge goal, in about ten minutes | [Tutorial: first run](guides/tutorials/first-run.md) |

## Do a task

| Task | Guide |
|---|---|
| Approve calls marked `ask`, on a terminal or from a file | [Approve ask calls](guides/how-to/approve-asks.md) |
| Name your bots and what needs your approval | [Define your bots](guides/how-to/define-bots.md) |
| Let a real model write forge code | [Use a real model](guides/how-to/use-a-real-model.md) |
| Add your own domain tools | [Add a domain](guides/how-to/add-a-domain.md) |
| Merge bot pull requests in dependency order | [Run the merge train](guides/how-to/merge-train.md) |
| Run the checks CI runs, before a pull request | [Run CI checks locally](guides/how-to/run-ci-locally.md) |
| Move to a newer EndoForge | [Repin EndoForge](guides/how-to/repin-endoforge.md) |
| Everything else | [All how-to guides](guides/how-to/README.md) |

## Look something up

| Need | Reference |
|---|---|
| A `cli.py` option, a tool in `tools/`, an error code | [Commands](guides/reference/commands.md) |
| A key in `cstack.config.json` | [Configuration](guides/reference/configuration.md) |
| An environment variable | [Environment variables](guides/reference/environment.md) |
| The core's records, lanes, ask and deny, budgets | [Interfaces](../contracts/INTERFACES.md) |
| Every reference page | [Reference index](guides/reference/README.md) |

## Understand the design

| Question | Read |
|---|---|
| How do the CLI, the MCP server and the adapters fit together? | [The server, the driver and the adapters](guides/explanation/server-and-adapters.md) |
| Why is EndoForge a pinned copy, and how does a forge goal run? | [How Cstack vendors and runs EndoForge](guides/explanation/endoforge-vendoring.md) |
| Which Foundations ship here, and what does a pin prove? | [Foundations and pins](guides/explanation/foundations-and-pins.md) |
| What do results mean, and what does Cstack not do? | [Limitations and safety-relevant use](guides/explanation/limitations.md) |
| What are the core's rules? | [Control decisions](../contracts/DECISION.md) and the [design](architecture/architecture.md) |

The guides follow [Diátaxis](https://diataxis.fr/): tutorials teach, how-to guides solve a task, reference states facts, explanation gives background. The [user manual map](guides/SUM-MAP.md) shows where each user-manual topic lives.

## Engineering records

Cstack keeps a control document set organised after NASA's software documentation standards. The documents follow the [Cstack family documentation standard](standards/family-doc-standard.md), whose canonical copy lives here. Each carries its own baseline commit; reading or indexing them does not create a new verification result.

Classification: self-assessed Class E analog under NPR 7150.2D, not safety-critical. Cstack is not NASA software, and this is not a NASA compliance determination or certification (see the [software management plan](plan/software-management-plan.md#1-software-classification-self-assessed)).

### Control documents

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

### Verification records

These are measurement and acceptance records kept as written.

| Document | Scope |
|---|---|
| [Foundation routes](verification/foundation-routes.md) | Measured routes from a workcell into each Foundation (2026-11-06) |
| [Wiring acceptance](verification/wiring-acceptance.md) | The acceptance frozen before end-to-end wiring (historical) |
| [Measurements, November 2026](verification/measured-2026-11.md) | The README's former "Measured" table (historical) |

### Family standard

| Document | Use |
|---|---|
| [Family documentation standard](standards/family-doc-standard.md) | What each family repository documents, where and how |
| [Documentation checklist](standards/doc-checklist.md) | Paste into a docs pull request and tick |
| [Templates](standards/templates/README.md) | Skeletons for each control document, issue and PR template |

Other family repositories link to https://github.com/Akilleez-QA/cstack/tree/main/docs/standards instead of copying it.

Decision records and contracts live in [`contracts/`](../contracts/): [ADR 001](../contracts/DECISION.md) and DECISION-003 to DECISION-006, the [interfaces](../contracts/INTERFACES.md) and the [acceptance contract](../contracts/ACCEPTANCE.md).

## Repository layout exception

Python entry points and composition files (`cli.py`, `bootstrap.py`, `__init__.py` and `__main__.py`) remain at the repository root. See [what's inside](../README.md#whats-inside). The documentation directories do not change those import paths.

See [Contributing](../CONTRIBUTING.md) for the review workflow and local checks, [Security](../SECURITY.md) for reporting guidance and [Support](../SUPPORT.md) for help.

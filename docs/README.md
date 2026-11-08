# Documentation

Cstack's documents, by what you need. The guides follow [Diátaxis](https://diataxis.fr/): tutorials teach, how-to guides solve a task, reference states facts, explanation gives background.

## Guides

| Need | Start with |
|---|---|
| Install Cstack and run your first goals | [Tutorial: first run](guides/tutorials/first-run.md) |
| Run the CI checks before a pull request | [How to run CI checks locally](guides/how-to/run-ci-locally.md) |
| Move to a newer EndoForge | [How to repin EndoForge](guides/how-to/repin-endoforge.md) |
| Other tasks: bots, merge train, domains | [How-to guides](guides/how-to/README.md) |
| Look up a command, config key or environment variable | [Reference](guides/reference/README.md) |
| Understand how EndoForge, the server and the adapters fit | [Explanation](guides/explanation/README.md) |

## Engineering records

These describe inspected implementation at their stated baselines. Indexing them doesn't establish a new verification result.

| Document | Scope |
|---|---|
| [Requirements](requirements/requirements.md) | Control-core, Foundation boundary, EndoForge evidence and workcell runtime requirements |
| [Architecture](architecture/architecture.md) | Composition, components and control flow |
| [Foundation interfaces](icd/icd-foundations.md) | Foundation adapters, source pins and boundaries |
| [EndoForge interface](icd/icd-endoforge.md) | Witnessed evidence storage and the workcell runtime |
| [EndoForge source pin](icd/icd-endoforge-pin.md) | The vendored EndoForge commit and slice |
| [POODO source interface](icd/icd-poodo.md) | The mirrored POODO skill snapshot |
| [Verification matrix](verification/verification-matrix.md) | Requirement-to-test traceability and evidence limits |
| [Foundation routes](verification/foundation-routes.md) | Measured routes from a workcell into each Foundation |
| [Wiring acceptance](verification/wiring-acceptance.md) | The acceptance frozen before end-to-end wiring |
| [Configuration management](configuration/configuration-management.md) | Baseline identities and change control |
| [No code comments](rules/no-comments.md) | Repository rule and where reasoning belongs |

Decision records and contracts live in [`contracts/`](../contracts/): [ADR 001](../contracts/DECISION.md) and DECISION-003 to DECISION-006, the [interfaces](../contracts/INTERFACES.md) and the [acceptance contract](../contracts/ACCEPTANCE.md).

## Repository layout exception

Python entry points and composition files (`cli.py`, `bootstrap.py`, `__init__.py` and `__main__.py`) remain at the repository root. See the [repository layout](../README.md#layout). The documentation directories do not change those import paths.

See [Contributing](../CONTRIBUTING.md) for the review workflow and local checks, and [Security](../SECURITY.md) for reporting guidance.

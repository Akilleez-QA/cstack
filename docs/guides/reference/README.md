# Reference

Facts to look up. Each page gives defaults as the code defines them.

## Using Cstack

| Reference | Contents |
|---|---|
| [Commands](commands.md) | `cli.py` options, input and output schemas and error codes; every tool in `tools/`; the memory CLI; the CI scripts |
| [Configuration](configuration.md) | Every key in `cstack.config.json`, which ones the code reads, and their defaults |
| [Environment variables](environment.md) | Every variable the code reads, with defaults |
| [Interfaces](../../../contracts/INTERFACES.md) | Core records, lanes, ask and deny, budgets, capacity admission and the MCP client |
| [Control contract](../../../contracts/CONTRACT.json) | Machine-readable control contract |

## Engineering records

| Reference | Contents |
|---|---|
| [Requirements](../../requirements/requirements.md) | Requirement identifiers, rationale and verification methods |
| [EndoForge interface](../../icd/icd-endoforge.md) | Witnessed evidence storage and the workcell runtime |
| [EndoForge source pin](../../icd/icd-endoforge-pin.md) | The vendored EndoForge commit and slice |
| [Foundation interfaces](../../icd/icd-foundations.md) | Foundation adapters and their pinned identities |
| [POODO source interface](../../icd/icd-poodo.md) | The mirrored POODO skill snapshot |
| [Verification matrix](../../verification/verification-matrix.md) | Requirements mapped to tests and inspection evidence |
| [Foundation routes](../../verification/foundation-routes.md) | Measured routes from a workcell into each Foundation |
| [Configuration management](../../configuration/configuration-management.md) | Baseline identities and change control |
| [No code comments](../../rules/no-comments.md) | Repository comment rule |

Return to the [documentation index](../../README.md).

# Documentation

This index covers the documents under `docs/`. The control documents retain their stated baseline commits and proposed status; moving or indexing them does not establish a new verification result.

## Start here

| Need | Index |
|---|---|
| Run the existing example | [Tutorials](guides/tutorials/README.md) |
| Configure bots, wire the merge train or add a domain | [How-to guides](guides/how-to/README.md) |
| Look up requirements, interfaces and verification records | [Reference](guides/reference/README.md) |
| Understand the control core and Foundation boundaries | [Explanation](guides/explanation/README.md) |

## Control documents

| Document | Scope |
|---|---|
| [Requirements](requirements/requirements.md) | Selected control-core and Foundation boundary requirements |
| [Architecture](architecture/architecture.md) | Composition, components and control flow |
| [Foundation interfaces](icd/icd-foundations.md) | Ownership, source pins and adapter boundaries |
| [Verification matrix](verification/verification-matrix.md) | Requirement-to-test traceability and evidence limits |
| [Configuration management](configuration/configuration-management.md) | Baseline identities and change control |
| [No code comments](rules/no-comments.md) | Repository rule and where reasoning belongs |

## Repository layout exception

Python entry points and composition files (`cli.py`, `bootstrap.py`, `__init__.py` and `__main__.py`) remain at the repository root. See the [repository layout](../README.md#layout). The documentation directories do not change those import paths.

See [Contributing](../CONTRIBUTING.md) for the review workflow and local checks, and [Security](../SECURITY.md) for reporting guidance.

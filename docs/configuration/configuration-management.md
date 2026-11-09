# Cstack configuration management plan

| Field | Value |
|---|---|
| Document ID | CSTACK-SCMP |
| Version | 2.2 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 84cd19d238a057b1c07af63e64b50edfb515d615 |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## Organization and change control

The maintainer (`Akilleez-QA`, sole CODEOWNER) approves and merges every change to `main`. Agent sessions and external contributors work on their own branches and open pull requests. `main` has no branch protection rule at the baseline (checked with `gh api repos/Akilleez-QA/cstack/branches/main/protection`, which answers "Branch not protected"); change control is the PR review plus the local checks listed in each PR body, and `tools/merge_train.py` for stacked PRs. A baseline is a commit on `main`; no tag exists yet.

## Configuration identification

Identify each reviewed baseline by an immutable export or commit. Branch names and upstream main are mutable references; source and catalog digests are separate byte-identity controls. No single Cstack package version is substituted for the commit identifier.

| Item | Verified baseline identity | Control point |
|---|---|---|
| Foundation Math distribution | v0.14 / directory `vendor/foundation-math-v014/` | `NOTICE.md`, `bootstrap.DEFAULT_MATH_ROOT` |
| Math capability | `foundation-math-v014` | `extensions/foundation_math.py` |
| Math domain descriptor | `0.1.0` | `extensions/foundation_math.py`; this is not the vendor release number |
| Math catalog | `7df9574ee6788e55bb51aec8ebf858e958c252808ec3f4c217e43f598c961ba9` | canonical encoding in `adapters/math_stdio.py` |
| Export listing schema | `your-org/cstack-export-listing/1` | `EXPORT-MANIFEST.json` |

### Manifest byte identities

SHA-256 values below identify raw manifest files at the baseline, not repository commits, signatures or mathematical correctness.

| Manifest | SHA-256 |
|---|---|
| `EXPORT-MANIFEST.json` | Regenerate with the export builder after changes |
| `vendor/foundation-math-v014/SOURCE-MANIFEST.json` | `23219ba772c84796c007eee75458afc499b6ac257b154e78cf3068e41bfdb9a2` |
| `foundations/template/SOURCE-MANIFEST.json` | `38ff83296a5aaf468eaab28dc9d4d7aeb99aa305226fcfa997ce5cc462ca1a31` |
| `foundations/refrigeration/SOURCE-MANIFEST.json` | `b7de586a4a67683e44beda5352c359df7cde43b4a8f4e9864ff2c6301c7aa74e` |
| `foundations/robotics/SOURCE-MANIFEST.json` | `624cb8315a9d2483271eacc3b201e8456c061e5283ef00aad99a3df6f6e92d97` |
| `vendor/endoforge/SOURCE-MANIFEST.json` | `c59a2e91d89afc3b6a9cce0bc84edd53da793659e8d658837a21f42c2a8c7612` |
| `vendor/foundation-engine-v020/SOURCE-MANIFEST.json` | `0617efcbbb594919137ca6b748de189516ee9ec35e49f56765109cfe9fb01349` |
| `foundations/film/SOURCE-MANIFEST.json` | `be2c5614046704b773f8e28583910ddc3138adb01ca8b03635d97fa807685b31` |

The source-manifest values above were recomputed with `sha256sum` at the baseline commit and match. The generated [version description](../releases/README.md) records every manifest digest, including `EXPORT-MANIFEST.json`, at its own commit.

## Upstream sources

Foundation Engine is partially vendored under `vendor/foundation-engine-v020/` (bridge, tool schema and upstream manifest, commit `8445d319fd35115093f44a2081beb29ff108be49`). The Math distribution is pinned independently under `vendor/`. Evaluate candidate updates against the current source and catalog contracts.

### Vendored Foundation commits

These public main heads were copied on 2026-11-08. Each source manifest and every listed file are copied byte-for-byte; upstream manifests no longer list `.github/`, so the upstream CI workflows are not copied. Tool inventories and bridge interface semantics are unchanged. New in the copies and not reached through the bridges: `foundations/film/foundation_film/filmstats.py` and `foundations/refrigeration/foundation_refrigeration/invariants.py`. The [Foundations ICD](../icd/icd-foundations.md#upstream-source-commits) lists file counts and manifest digests.

| Foundation | Upstream commit |
|---|---|
| `foundation_refrigeration` | `069ea9e8b90308257565db7d00c1884119ed84d6` |
| `foundation_robotics` | `e6abce6d4b5b7c06ed87d8270ad4785af5be1886` |
| `foundation_film` | `7601fc51d1e01771db5be3a3f0c576b93ed7b078` |
| `foundation_template` | `a57f14cb744093aec40a52d35420d2cee1b1797d` |

### Endoforge source

`vendor/endoforge/` holds a 27-file slice of Endoforge commit
`ea7b8d651ce23acd100f5a5d81d6e8fda0d604a3` on `main`: the lifecycle model, run ledger,
gates and evaluator, `IsolatePool` and its workcell, the capacity planner and two
support tools. Control the slice list in `tools/pin_endoforge.py`, the upstream and
exported hashes, and the `endoforge` record in `contracts/SOURCE-PINS.json` together,
as described in [the source-pin ICD](../icd/icd-endoforge-pin.md) and
[the repin guide](../guides/how-to/repin-endoforge.md). Python comment tokens are
removed mechanically during export. Cstack's side of the runtime, `adapters/workcell/`,
is pinned separately as `workcell_runtime` (`tools/pin_workcell.py`), and every forge
run checks both pins before it starts. Rollback restores the previous vendor slice
and pin records from Git together.

### Vendored documentation and upstream

Each vendored Foundation under `foundations/` carries its own `docs/` tree (requirements, architecture, ICDs, verification) as part of its byte-pinned copy, and `vendor/` and `reasoning/` hold upstream files the same way. These copies are mirrors: they are listed in each `SOURCE-MANIFEST.json` or pin, checked by the adapter and pin tests, and never edited in Cstack. A documentation fix for a Foundation, EndoForge or POODO is made in that upstream repository, merged there, and then reaches Cstack only through a repin that copies the new bytes and updates the pin records together (procedure below). Between repins, a vendored doc may describe an older upstream state than the upstream repository's `main`; the pin commit says which. The family documentation standard itself is canonical here, in [`docs/standards/`](../standards/family-doc-standard.md), and upstream repositories link to it rather than copying it.

## POODO skill snapshot

`contracts/SOURCE-PINS.json` pins `poodo_skill` to upstream main commit `4a111aab0a51ec5fc4c611390e7ea8eee7d3a3a9` from https://github.com/Akilleez-QA/poodo. Its `files` list identifies the byte-exact subset; `status: partial-sync` and both deferred lists prevent treating this as a complete mirror.

Ten paths absent upstream were preserved with `git mv` under `TODELETE/reasoning/poodo/`. The under-400-line update defers README, licensing, repository metadata and engineering records; the unchanged export manifest is historical and must be regenerated separately before publishing an export.

## Controlled items and responsibilities

Approved-atoms CLI validation is unavailable because no Registry provider is included. Any future enablement must control the provider source and dependency identity, update the claim-gate interface and CS-REQ-016 verification, and demonstrate atom validation before removing the explicit rejection. A sibling checkout or installed package does not enable this path.

The change author identifies affected sources, schemas, inventory, pins, documentation and tests. The reviewer checks consistency and evidence; repository review establishes acceptance. This document assigns workflow roles, not a named organizational approval board. Keep requirements identifiers stable and record reasons for changed obligations.

Control the Foundation source directories, their source manifests, per-domain adapters, extension descriptors, `bootstrap.py`, `contracts/ADAPTERS.json`, bridge tool schemas, fixtures and tests together. Runtime source identity checks cover manifest-listed files, not arbitrary extra files elsewhere in a checkout.

Control `EndoforgePort`, its core models/routing, `icd-endoforge.md` contract 0.3, record schemas 0.1/0.2, CS-REQ-020–023 (port), CS-REQ-024–026 (file adapter), CS-REQ-027–030 (routing), the file adapter, bootstrap/CLI and all three Endoforge test files together. Approval-bearing precommits use 0.2; existing records retain their bytes/hashes and upgraded readers accept mixed chains. Old readers reject 0.2, so upgrade readers before writes; no automatic migration or rollback rewriting is provided. `poodo_core_endoforge_routing_0_2` identifies the new core bytes in `contracts/SOURCE-PINS.json`; historical and vendor pins remain unchanged. A contract change does not authorize a vendor update; the pinned lifecycle slice supplies no storage primitive. Never silently repair or truncate a corrupt ledger.

The host provisions `cstack.config.json` from `cstack.config.example.json`: `endoforge.path` is relative to the config directory unless absolute. Provision its parent directory with suitable ownership before use. Bootstrap creates a fresh session id, owns the exclusive file lock and closes it on run exit. Missing config/section leaves legacy composition; configured failures never disable witnessing. Keep operational ledgers outside tracked source. Local durability qualification, independent witnessing and recovery remain deployment work.

## Change procedure

1. Start a focused branch from an identified main commit. Record the intended behavior and affected interfaces before altering a dependency.
2. Obtain the proposed source snapshot and retain the old baseline. Record the upstream commit or artifact origin separately from its manifest digest.
3. Compare tool names/order, input/output schemas, numeric rules, protocol identifiers, receipts and evidence ceilings. A narrower upstream extraction requires a migration, not a directory replacement.
4. For a change to a vendored Foundation under `foundations/`, copy its upstream manifest and every listed file exactly, then run `foundations/<name>/tools/build_manifest.py` from that Foundation's root and verify that the manifest remains byte-identical to upstream. Update the matching adapter source hash/file count and any intentionally changed catalog pin. Do not run a domain builder against the entire repository.
5. For Math, retain the historical vendor packaging/provenance controls and review `PinnedMathSource` and inventory checks together. There is no root-level automatic Math upgrade command in this baseline.
6. Update requirements, design, ICD and traceability records when the controlled behavior changes. Record any verification gap explicitly.
7. Run the root unittest suite, each affected Foundation suite and link checks. Record candidate SHA, commands, interpreter, failures and skips. Review before integration; preserve the previous commit for rollback.

## Export manifest handling

`EXPORT-MANIFEST.json` contains per-file SHA-256 and byte counts. Regenerate it with `python -B tools/build_export_manifest.py` after changing the tree. It is distinct from the source manifests enforced by bridge adapters.

If an export is regenerated in a later change, first define its inclusion/exclusion policy and review tooling, then record the new digest and coverage. Do not describe an unchanged listing as a complete inventory of newly added documents.

## Verification environment

The GitHub workflow runs root unittest discovery and `bash ci/run-local.sh python links trace`, plus a TruffleHog scan. The wrapper runs the root and Foundation suites in normal and optimized modes, then the link check and the trace check. See [run CI checks locally](../guides/how-to/run-ci-locally.md) and the [test plan](../verification/test-plan.md).

## Status accounting

Status is recovered from Git, not kept by hand: `git log` and merged PRs for changes, `contracts/SOURCE-PINS.json` and the source manifests for vendored identities, the CHANGELOG for user-visible changes, and generated version descriptions in [`docs/releases/`](../releases/README.md).

## Configuration audits

At each release, and at each documentation baseline, the assurance record gets a configuration-audit entry: control-document baseline commits against the release commit, manifest digests against files (this document's table and the generated version description), and pin tests passing. See the [assurance record](../assurance/assurance-record.md).

## Control of generated outputs

Cstack generates no source code. These generated records are committed and regenerated by their tool, never edited by hand:

| Output | Generator | When |
|---|---|---|
| `EXPORT-MANIFEST.json` | `python -B tools/build_export_manifest.py` | After any change to the tracked file set or contents, as the last step before commit |
| `vendor/endoforge/` and the `endoforge` pin | `tools/pin_endoforge.py` | On repin |
| `workcell_runtime` pin | `tools/pin_workcell.py` | When `adapters/workcell/` changes |
| `docs/verification/reports/STR-<label>.md`, `docs/releases/VDD-<label>.md` | `python3 -B tools/gen_release_docs.py --label <label>` | At each tag and documentation baseline |

The generators' inputs are the tracked tree, Git history, the CHANGELOG and `ci/run-local.sh`; the tools themselves are tracked and reviewed like code.

## Release management

No release has been tagged. To cut one: update the CHANGELOG section, tag the commit on `main`, run `tools/gen_release_docs.py --label <tag>` at that commit, record the configuration audit in the assurance record, and commit the generated files. GitHub Release bodies may link the generated files.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

## CLI approval configuration

Control `cli.py`, `bootstrap.py`, `adapters/terminal_approver.py`, the ask example,
approval tests and approval interface documentation together. Host-owned answer
files are local inputs, never repository fixtures containing standing authority.
Consumed approval markers persist under `$XDG_STATE_HOME/cstack/cli-approvals`
(default `~/.local/state/cstack/cli-approvals`); each is private and uniquely named.
Marker storage failure prevents approval dispatch. This path is separate from AOR
approvals.db and does not add durability to the CLI ledger. Rolling back the code
retains existing consumption records; do not reuse or remove them as a reset.

## Refrigeration acceptance baseline

Control `examples/refrigeration-e2e.json`, `tests/test_refrigeration_e2e.py`, and `tools/e2e_refrigeration.sh` together under CS-REQ-031. The harness creates disposable host configuration, approval SQLite store and Endoforge ledger in a temporary directory; it never modifies repository-local runtime configuration or source pins. Each run records a fresh synthetic approval_id with a five-minute expiry. `PYTHON` selects the runner interpreter. `ci/run-local.sh refrigeration` is the named suite and is included in the default suite list; `python links` also exercises both acceptance cases through unittest discovery.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Identification, pins, change procedure, CLI approval and refrigeration acceptance baselines | See `git log -- docs/configuration/configuration-management.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard header; organization, status accounting, audits, generated outputs, release management; vendored docs and upstream; trace suite in CI | docs/nasa-standard PR |
| 2.1 | 2026-11-08 | b7c64b19e3966baaf1aa6793491b454e28f51446 | Foundation, Engine and POODO repin: manifest digests, upstream commits, POODO commit | PR #78 |
| 2.2 | 2026-11-08 | 84cd19d238a057b1c07af63e64b50edfb515d615 | EndoForge repin to ea7b8d6: 27-file slice, manifest digest | PR #79 |

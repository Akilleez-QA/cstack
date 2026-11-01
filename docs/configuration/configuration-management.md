# Cstack configuration management

Status: reusable documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

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
| `foundations/template/SOURCE-MANIFEST.json` | `7ce77706f1bee842dab391dfd8c0256be231be2d6b6f5483c39574718eea6158` |
| `foundations/refrigeration/SOURCE-MANIFEST.json` | `a4e096d2b1169ee23c3f111b121d9dbc593ab63a52ec20167d451ff97c21399e` |
| `foundations/robotics/SOURCE-MANIFEST.json` | `4667a558554e6a766e855be078031563b72337b8a6407eabf466d42b9df3bdb6` |
| `foundations/film/SOURCE-MANIFEST.json` | `4734c76b9d0d5b830e150bd2bb435539e202ffd81d967692cff8dacfc3b5a417` |

## Upstream sources

Foundation Engine is linked as a sibling. The Math distribution is pinned independently under `vendor/`. Evaluate candidate updates against the current source and catalog contracts.

### Vendored Foundation commits

These public main heads were copied on 2026-11-01. Each source manifest and every listed file, including the upstream CI workflow, are copied byte-for-byte. Runtime code, tool inventories and interface semantics are unchanged.

| Foundation | Upstream commit |
|---|---|
| `foundation_refrigeration` | `3fe90a939f85aeb4e4aa6913b0993374e115f176` |
| `foundation_robotics` | `ebd6d4d14e050a5ebda2e4961b9fd1464d1e5653` |
| `foundation_film` | `c4110bc0241a35cf0bd16eaa6cfe116b6e45986a` |
| `foundation_template` | `9ce46fa2af5dd1cb9c363a6913bae0aa4175ff47` |

## POODO skill snapshot

`contracts/SOURCE-PINS.json` pins `poodo_skill` to upstream main commit `d1cce9e58fe80d8e35419c2d7ad335edd2c69044` from https://github.com/Akilleez-QA/poodo. Its `files` list identifies the byte-exact subset; `status: partial-sync` and both deferred lists prevent treating this as a complete mirror.

Ten paths absent upstream were preserved with `git mv` under `TODELETE/reasoning/poodo/`. The under-400-line update defers README, licensing, repository metadata and engineering records; the unchanged export manifest is historical and must be regenerated separately before publishing an export.

## Controlled items and responsibilities

Approved-atoms CLI validation is unavailable because no Registry provider is included. Any future enablement must control the provider source and dependency identity, update the claim-gate interface and CS-REQ-016 verification, and demonstrate atom validation before removing the explicit rejection. A sibling checkout or installed package does not enable this path.

The change author identifies affected sources, schemas, inventory, pins, documentation and tests. The reviewer checks consistency and evidence; repository review establishes acceptance. This document assigns workflow roles, not a named organizational approval board. Keep requirements identifiers stable and record reasons for changed obligations.

Control the Foundation source directories, their source manifests, per-domain adapters, extension descriptors, `bootstrap.py`, `contracts/ADAPTERS.json`, bridge tool schemas, fixtures and tests together. Runtime source identity checks cover manifest-listed files, not arbitrary extra files elsewhere in a checkout.

Control `EndoforgePort`, its core models/routing, `icd-endoforge.md` contract 0.2, record schemas 0.1/0.2, CS-REQ-020–023 (port), CS-REQ-024–026 (file adapter), CS-REQ-027–030 (routing), the file adapter, bootstrap/CLI and all three Endoforge test files together. Approval-bearing precommits use 0.2; existing records retain their bytes/hashes and upgraded readers accept mixed chains. Old readers reject 0.2, so upgrade readers before writes; no automatic migration or rollback rewriting is provided. `poodo_core_endoforge_routing_0_2` identifies the new core bytes in `contracts/SOURCE-PINS.json`; historical and vendor pins remain unchanged. A contract change does not authorize a vendor update; the pinned lifecycle slice supplies no storage primitive. Never silently repair or truncate a corrupt ledger.

The host provisions `cstack.config.json` from `cstack.config.example.json`: `endoforge.path` is relative to the config directory unless absolute. Provision its parent directory with suitable ownership before use. Bootstrap creates a fresh session id, owns the exclusive file lock and closes it on run exit. Missing config/section leaves legacy composition; configured failures never disable witnessing. Keep operational ledgers outside tracked source. Local durability qualification, independent witnessing and recovery remain deployment work.

## Change procedure

1. Start a focused branch from an identified main commit. Record the intended behavior and affected interfaces before altering a dependency.
2. Obtain the proposed source snapshot and retain the old baseline. Record the upstream commit or artifact origin separately from its manifest digest.
3. Compare tool names/order, input/output schemas, numeric rules, protocol identifiers, receipts and evidence ceilings. A narrower upstream extraction requires a migration, not a directory replacement.
4. For a change to a vendored Foundation under `foundations/`, copy its upstream manifest and every listed file exactly, then run its `tools/build_manifest.py` from the corresponding Foundation root and verify that the manifest remains byte-identical to upstream. Update the matching adapter source hash/file count and any intentionally changed catalog pin. Do not run a domain builder against the entire repository.
5. For Math, retain the historical vendor packaging/provenance controls and review `PinnedMathSource` and inventory checks together. There is no root-level automatic Math upgrade command in this baseline.
6. Update requirements, design, ICD and traceability records when the controlled behavior changes. Record any verification gap explicitly.
7. Run the root unittest suite, each affected Foundation suite and link checks. Record candidate SHA, commands, interpreter, failures and skips. Review before integration; preserve the previous commit for rollback.

## Export manifest handling

`EXPORT-MANIFEST.json` contains per-file SHA-256 and byte counts. Regenerate it with `python -B tools/build_export_manifest.py` after changing the tree. It is distinct from the source manifests enforced by bridge adapters.

If an export is regenerated in a later change, first define its inclusion/exclusion policy and review tooling, then record the new digest and coverage. Do not describe an unchanged listing as a complete inventory of newly added documents.

## Verification environment and known discrepancy

The GitHub workflow runs root unittest discovery and `bash ci/run-local.sh python links`. The latter validates `ci/host-only.txt` before suites. That file names paths under `forge/endoforge/`, which this export does not contain; the wrapper can therefore fail before testing. Record this separately and run the direct suite commands to obtain test evidence. Documentation changes do not resolve that infrastructure discrepancy.

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

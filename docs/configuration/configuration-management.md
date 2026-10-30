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
| `foundations/template/SOURCE-MANIFEST.json` | `259316e6768ce551e8427e860620b588e010ce847933a2cd1106bd1ab4d1625c` |
| `foundations/refrigeration/SOURCE-MANIFEST.json` | `be9799b6753b60f03851348525cd774db6e480d0483bd8141238236aa7e8eef9` |
| `foundations/robotics/SOURCE-MANIFEST.json` | `0eef13a6ff1dd52c1b301491f065d72cba2a10db3304fdb647cf29b3e2763575` |
| `foundations/film/SOURCE-MANIFEST.json` | `83130de85d2b7a52a32591c205a76735b0048e364ec1f92394c33f51b77eea6a` |

## Upstream sources

Foundation Engine is linked as a sibling. The Math distribution is pinned independently under `vendor/`. Evaluate candidate updates against the current source and catalog contracts.

## Controlled items and responsibilities

The change author identifies affected sources, schemas, inventory, pins, documentation and tests. The reviewer checks consistency and evidence; repository review establishes acceptance. This document assigns workflow roles, not a named organizational approval board. Keep requirements identifiers stable and record reasons for changed obligations.

Control the Foundation source directories, their source manifests, per-domain adapters, extension descriptors, `bootstrap.py`, `contracts/ADAPTERS.json`, bridge tool schemas, fixtures and tests together. Runtime source identity checks cover manifest-listed files, not arbitrary extra files elsewhere in a checkout.

## Change procedure

1. Start a focused branch from an identified main commit. Record the intended behavior and affected interfaces before altering a dependency.
2. Obtain the proposed source snapshot and retain the old baseline. Record the upstream commit or artifact origin separately from its manifest digest.
3. Compare tool names/order, input/output schemas, numeric rules, protocol identifiers, receipts and evidence ceilings. A narrower upstream extraction requires a migration, not a directory replacement.
4. For a change to a vendored Foundation under `foundations/`, inspect and run its `tools/build_manifest.py` from the corresponding Foundation root. Update the matching adapter source hash/file count and any intentionally changed catalog pin. Do not run a domain builder against the entire repository.
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

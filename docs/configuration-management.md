# Cstack configuration management

Baseline: Cstack `7a29c95aec2c39c139ec42fe2aa5fc3db16dd034`. Status: proposed documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

## Configuration identification

The reviewed baseline is identified by the Cstack commit above. Branch names and upstream main are mutable references; source and catalog digests are separate byte-identity controls. No single Cstack package version is substituted for the commit identifier.

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
| `EXPORT-MANIFEST.json` | `66d7a19ac924975ed43e7c96375bfb96d7bc7d84e97ad76d1d3bf377a93ff8ba` |
| `vendor/foundation-math-v014/SOURCE-MANIFEST.json` | `23219ba772c84796c007eee75458afc499b6ac257b154e78cf3068e41bfdb9a2` |
| `foundations/template/SOURCE-MANIFEST.json` | `c1bd44192f1b3fcbdcde0187f697c7855bafdfdf3ab03928efef40501de5d609` |
| `foundations/refrigeration/SOURCE-MANIFEST.json` | `d07eb4c0255416ecce5beff9654c73597ca41fbd35754ce111af7a6e19a70b75` |
| `foundations/robotics/SOURCE-MANIFEST.json` | `9b2b28a25958156160c054477df21b017e77bbd0cb90a360c17c0aa2c685603c` |
| `foundations/film/SOURCE-MANIFEST.json` | `0c76023c51630ba74d2326ba02931f404888d4839aaf98728d0fa61f88487f85` |

## Upstream observation record

Both repositories were inspected through fresh `gh repo clone` checkouts. These identifiers record the inspected upstream snapshots; they are not Cstack dependency pins.

- [Foundation Engine](https://github.com/Akilleez-QA/foundation-engine), commit `d44e1e18281efbb8622ce5bcaa7837e5a99de5f1`: `package.json` declares `0.2.0`. Cstack links this sibling but includes no engine runtime or commit pin.
- [Foundation Math](https://github.com/Akilleez-QA/foundation-math), commit `d70ef495fb2221575bb2ccc31978f78963b46427`: `SOURCE-MANIFEST.json` names candidate `scalar-control-v1-20261027`. Its README states that only selected character and split-bundle runtime components of v0.14 are included. This is not the full Cstack vendor distribution.

## Controlled items and responsibilities

The change author identifies affected sources, schemas, inventory, pins, documentation and tests. The reviewer checks consistency and evidence; repository review establishes acceptance. This document assigns workflow roles, not a named organizational approval board. Keep requirements identifiers stable and record reasons for changed obligations.

Control the Foundation source directories, their source manifests, per-domain adapters, extension descriptors, `bootstrap.py`, `contracts/ADAPTERS.json`, bridge tool schemas, fixtures and tests together. Runtime source identity checks cover manifest-listed files, not arbitrary extra files elsewhere in a checkout.

## Change procedure

1. Start a focused branch from an identified main commit. Record the intended behavior and affected interfaces before altering a dependency.
2. Obtain the proposed source snapshot and retain the old baseline. Record the upstream commit or artifact origin separately from its manifest digest.
3. Compare tool names/order, input/output schemas, numeric rules, protocol identifiers, receipts and evidence ceilings. A narrower upstream extraction requires a migration, not a directory replacement.
4. For a local sibling source change, inspect and run its `tools/build_manifest.py` from the corresponding Foundation root. Update the matching adapter source hash/file count and any intentionally changed catalog pin. Do not run a domain builder against the entire repository.
5. For Math, retain the historical vendor packaging/provenance controls and review `PinnedMathSource` and inventory checks together. There is no root-level automatic Math upgrade command in this baseline.
6. Update requirements, design, ICD and traceability records when the controlled behavior changes. Record any verification gap explicitly.
7. Run the root unittest suite, each affected Foundation suite and link checks. Record candidate SHA, commands, interpreter, failures and skips. Review before integration; preserve the previous commit for rollback.

## Export manifest handling

`EXPORT-MANIFEST.json` contains per-file SHA-256 and byte counts. It is a baseline export listing, distinct from the source manifests enforced by bridge adapters. No root export-manifest generator or root test requiring regeneration for newly added documentation was found in the inspected baseline. Therefore documentation-only PRs retain this listing unchanged rather than silently redefining its coverage.

If an export is regenerated in a later change, first define its inclusion/exclusion policy and review tooling, then record the new digest and coverage. Do not describe an unchanged listing as a complete inventory of newly added documents.

## Verification environment and known discrepancy

The GitHub workflow runs root unittest discovery and `bash ci/run-local.sh python links`. The latter validates `ci/host-only.txt` before suites. That file names paths under `forge/endoforge/`, which this export does not contain; the wrapper can therefore fail before testing. Record this separately and run the direct suite commands to obtain test evidence. Documentation changes do not resolve that infrastructure discrepancy.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

# Cstack software management plan

| Field | Value |
|---|---|
| Document ID | CSTACK-SMP |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

This plan follows the family standard in [`docs/standards/`](../standards/family-doc-standard.md), of which this repository holds the canonical copy.

## 1. Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. Cstack is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** Cstack meets none of the five criteria in NASA-STD-8739.8B §4.2, and no hazard analysis assigns it a hazard cause, control or mitigation.
- Cstack vendors Foundations with engineering data (refrigeration saturation tables and exposure limits, robotics kinematics). Their outputs, and the example refrigeration acceptance, are bounded observations for research and acceptance checks. They are not engineering approvals. Anyone who relies on them for engineering, safety or regulatory decisions takes on the Class D-analog obligations for that use and must verify against authoritative sources. See [limitations](../guides/explanation/limitations.md).
- Cstack runs agents and commands on the operator's machine. That makes it a host for other software's effects, but its own role is to record, gate and refuse; it commands no physical hardware.
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the [compliance matrix](compliance-matrix.md).
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path; handling personal or secret data beyond local configuration; external deployment as a shared service.
- Assessed by / date / baseline commit: Akilleez-QA / 2026-11-08 / 6ae5481fd302439dabb23044d1b715ac8c4a9bec.

## 2. Purpose, scope and organization

Cstack (code name Mjölnir) is the host of the Cstack family: a template for running a fleet of AI bots under one human approver. It vendors the Foundations and an EndoForge slice byte-pinned and owns the composition, adapter and approval interfaces. Family members and their roles are in the [README](../../README.md#related-projects).

Authority: the maintainer (GitHub `Akilleez-QA`, the only entry in `.github/CODEOWNERS`) is the sole approver and merges every change. Agent sessions contribute through branches and pull requests. External contributors use pull requests under [CONTRIBUTING](../../CONTRIBUTING.md).

## 3. Life-cycle model and work tracking

Trunk-based development on `main`. Every change is a pull request from its own branch, one concern per PR, about 400 changed lines. Agents each use their own branch. Work items are GitHub issues; there are no milestones. `tools/merge_train.py` merges stacked PRs in dependency order. No tag has been cut yet; when one is, `tools/gen_release_docs.py --label <tag>` writes its test report and version description.

Cost estimation, staffing plans, budgets, subcontractor management and CMMI are not applicable: the project is unfunded open source with one maintainer.

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Python | 3.12 in CI (`uv venv --python 3.12`); 3.12 or newer locally | `.github/workflows/ci.yml`, README Quickstart |
| Python packages | jsonschema 4.26.0; cryptography 50.0.2, pillow 13.0.0, numpy 2.5.4 for tests | `requirements.txt`, `ci/requirements.txt` |
| Node | 24 in CI; 22 or newer locally | `.github/workflows/ci.yml`, README |
| Node packages | Workcell toolchain lockfile | `adapters/workcell-toolchain/package-lock.json` |
| Test runner | Python `unittest` discovery | `ci/run-local.sh` |
| Static analysis | None configured beyond the trace, link and secret checks | §6 |
| Secret scanning | gitleaks 8.30.1 (pre-commit and local suite); TruffleHog 3.99.7 (CI) | `.pre-commit-config.yaml`, `.github/workflows/ci.yml` |
| CI | GitHub Actions, `ubuntu-latest` | `.github/workflows/ci.yml` |
| Dependency updates | Dependabot, weekly, pip and GitHub Actions | `.github/dependabot.yml` |

## 5. Verification and validation approach

Verification: peer review on every PR (§6), the root unittest suite in normal and optimized modes, the five vendored Foundation suites, the link and trace checks, the refrigeration end-to-end acceptance and secret scans. Records: the [verification matrix](../verification/verification-matrix.md), the [test plan](../verification/test-plan.md), [test reports](../verification/reports/) and the [assurance record](../assurance/assurance-record.md).

Validation (does it do the intended job): the [first-run tutorial](../guides/tutorials/first-run.md) run on a fresh clone; `tools/check_readme.py`, which runs every README command on a fresh clone; the refrigeration acceptance (CS-REQ-031) through the real CLI with a host approval; and differential tests of in-process kernels against the pinned Foundations (CS-REQ-033).

Acceptance criteria for merging to `main`: the commands in `.github/workflows/ci.yml` pass locally or in CI; `tools/check_trace.py` passes; the PR lists its checks with one-line results. For a release: the same plus a generated test report and version description at the tag commit.

## 6. Software assurance

Cstack has one maintainer, so there is no organizational independence between author and assurer. Agent reviewers and CI gates provide separation of method only, not of organization, and agent review is recorded as not independent.

| Gate | Command | Fails on | Record |
|---|---|---|---|
| Root tests | `python -B -m unittest discover -s tests` (CI step) | Any failing or erroring test | CI log; STR |
| All Python suites | `bash ci/run-local.sh python` | Root or Foundation suite failure, normal or `-O` | STR |
| Link check | `bash ci/run-local.sh links` | A repository path named in a doc that does not exist; stale allow-list entries | STR |
| Trace check | `bash ci/run-local.sh trace` | Untraced or untested requirement, missing test, unclassified test file, allocation mismatch, dead link or anchor in a control document | STR; SAR |
| Refrigeration acceptance | `bash ci/run-local.sh refrigeration` | CS-REQ-031 failure | STR |
| gitleaks | `bash ci/run-local.sh gitleaks`; pre-commit hook | Any leak | STR |
| TruffleHog | `bash ci/scan-secrets.sh` (CI job `secrets`) | Any finding | CI log; STR |
| README commands | `python -B tools/check_readme.py` | A README command fails or is uncovered | README "Measured" table |
| Claim gate | `python -B tools/claim_gate.py` | A written claim without matching recorded evidence | Run output |

CI runs `bash ci/run-local.sh python links trace` and the TruffleHog job. The refrigeration and gitleaks suites run locally in the default `ci/run-local.sh` list. When a gate is added or removed, this table changes in the same PR.

## 7. Security, privacy and secure coding

Attack surface: untrusted JSON on CLI stdin; MCP JSON-RPC frames on stdio; replies from Foundation bridge processes and external MCP servers; files under host-configured state roots (ledgers, approval stores, memory database); `gh` invocations for fleet mail. No network listener is opened by Cstack itself.

Practices, each backed by a requirement: strict JSON (duplicate keys, non-finite numbers and floats refused where exact data is needed); size bounds on every frame and output; fixed argument vectors and no shell; process-group kill on timeout; private (0600, no symlink) state files; authority only from host configuration; fail-closed storage; secret redaction in memory ingest. Secret scanning runs on every PR. Dependencies are pinned and updated through Dependabot. See [SECURITY.md](../../SECURITY.md) for reporting.

## 8. Open-source, reused and vendored components

| Component | License | Pin | Update method |
|---|---|---|---|
| Foundation Math v0.14 | Provenance files in `vendor/foundation-math-v014/` | `SOURCE-MANIFEST.json` digest; catalog digest in the adapter | Manual migration (SCMP) |
| Foundation Engine bridge (partial) | GPL-3.0-only | Upstream commit and manifest in `contracts/SOURCE-PINS.json` | Manual copy and repin |
| EndoForge slice | GPL-3.0 (`vendor/endoforge/LICENSE`) | Commit, manifest digest and per-file hashes in `contracts/SOURCE-PINS.json` | `tools/pin_endoforge.py` ([how-to](../guides/how-to/repin-endoforge.md)) |
| Film, Refrigeration, Robotics, Template Foundations | GPL-3.0, license in each directory | Upstream commits and `SOURCE-MANIFEST.json` | Byte copy and manifest rebuild |
| POODO skill subset | MIT (`reasoning/poodo/LICENSE`) | `poodo_skill` in `contracts/SOURCE-PINS.json` | Partial byte sync |
| Python packages; AssemblyScript, binaryen and long (npm, Apache-2.0) | Their own | `requirements.txt`, `ci/requirements.txt`, `package-lock.json` | Dependabot |

Full notices: [NOTICE.md](../../NOTICE.md). Cstack is reusable by others under GPL-3.0-only (SWE-148); commercial terms are available from the licensor named in the README.

## 9. Problem reporting and severity

| Severity | Meaning | Response |
|---|---|---|
| S1 | Wrong result presented as valid, data loss, or security exposure | Fix or withdraw before the next merge |
| S2 | Feature unusable, no workaround | Next release |
| S3 | Feature degraded, workaround exists | Scheduled |
| S4 | Cosmetic or documentation | As convenient |

Problems and changes are reported through the [problem report](../../.github/ISSUE_TEMPLATE/problem-report.md) and [change request](../../.github/ISSUE_TEMPLATE/change-request.md) issue templates. Closing an issue needs a linked PR that names its verification. Security issues go privately per SECURITY.md.

## 10. Configuration management

Baselines are commits on `main` (no tags yet). Pins, manifests and digests are controlled as described in the [configuration management plan](../configuration/configuration-management.md).

## 11. Operations, maintenance and retirement

Changes are analyzed in the issue or PR, implemented on a branch, reviewed and merged by the maintainer. Supported version: the latest commit on `main` (SECURITY.md). Migration notes go in the CHANGELOG. Distribution is the public Git repository; there are no packages. Users find version data in the CHANGELOG and in [version descriptions](../releases/README.md). Backup operational software is not applicable; the previous commit or tag is the fallback. Retirement: a final tag, an archive notice in the README Status section, and GitHub repository archiving.

## 12. Risk register

Reviewed at each release and when this plan changes. Likelihood (L) and consequence (C) are 1–5.

| ID | Risk | L | C | Mitigation | Status | Issue |
|---|---|---|---|---|---|---|
| R-1 | Vendored mirrors drift from upstream, so fixes made upstream never reach Cstack | 4 | 3 | Byte pins and pin tests (CS-REQ-064, CS-REQ-070); repin procedure in the SCMP | Open | - |
| R-2 | A user treats Foundation outputs or the refrigeration example as engineering approval | 2 | 4 | Evidence ceilings (CS-REQ-008); [limitations page](../guides/explanation/limitations.md); README status | Open | - |
| R-3 | Single maintainer: no independent review, and knowledge concentrated in one person | 5 | 3 | Agent review labelled not independent; documented procedures and traceability checks | Accepted | - |
| R-4 | Local ledgers lose or corrupt evidence on power loss; durability is not qualified | 3 | 3 | fsync before acknowledgement, fail-closed chain checks (CS-REQ-024, CS-REQ-025, CS-REQ-047) | Open | - |
| R-5 | Docs go stale against code, as the 2026-11-08 audit found | 4 | 2 | `tools/check_trace.py` and `tools/check_links.py` in CI; staleness rule in the standard | Open | - |
| R-6 | Model-written kernels attempt to escape the workcell | 2 | 4 | Authority with the core (CS-REQ-034); declared imports only (CS-REQ-033). A workcell is not an OS sandbox | Open | - |

## 13. Measurement

Each test report carries a metrics block generated by `tools/gen_release_docs.py`: tests run, skipped and failed per suite; requirements total, with tests and listed gaps; traced test files; issues open and closed; merged PRs; secret-scan results; tracked line counts. Coverage is not measured.

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

Every control document and guide is listed, with its ID, in the [documentation index](../README.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Initial baseline | docs/nasa-standard PR |

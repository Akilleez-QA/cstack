# foundation-refrigeration software management plan

| Field | Value |
|---|---|
| Document ID | FREFRIG-SMP |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. foundation-refrigeration is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system.
- **Class E holds only because no real engineering decision depends on this software.** Its content (refrigerant saturation tables, unit conversion, ammonia exposure limits, process-safety thresholds) resembles the thermal and engineering analysis tools that NPR 7150.2D gives as Class D examples. If anyone relies on its outputs for a real engineering, safety or regulatory decision, the Class D analog applies to that use, and that user takes on the Class D obligations, including verification against authoritative sources. This project does not provide that assurance.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** foundation-refrigeration meets none of the five criteria in NASA-STD-8739.8B §4.2: it does not cause or contribute to a hazard, provide a hazard control or mitigation, control a safety-critical function, mitigate damage, or detect and respond to a hazardous state. It reads and reports reference data and commands nothing. No hazard analysis assigns it a hazard cause, control or mitigation.
- Exposure limits are safety-relevant data even though the software is not safety-critical. Outputs are bounded observations for research and acceptance checks. They are not engineering approvals, exposure assessments or compliance determinations, and must not be used for life-safety decisions. See [Limitations and safety-relevant use](../guides/explanation/limitations.md).
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the [compliance matrix](compliance-matrix.md).
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path (for example alarm set points, PSM or RMP applicability, respirator selection); handling personal or secret data beyond local configuration; external deployment as a shared service.
- Assessed by / date / baseline commit: Akilleez-QA maintainer (assessment drafted by an agent documentation lane, not independent) / 2026-11-08 / 62764c7526ce2bbf064ccf633d5295f4390fc984.

## 2. Purpose, scope and organization

foundation-refrigeration is a **foundation**-type repository in the Cstack family: a stdio JSON-RPC bridge with read-only tools whose results carry Evidence. It provides refrigeration reference data and checks to the Cstack host and to local Python callers. The [README](../../README.md) lists the family.

Authority: the maintainer (Refrigeration.AI, GitHub `Akilleez-QA`) is the sole approver and the only code owner. Agent lanes and external contributors propose changes by pull request.

## 3. Life-cycle model and work tracking

Trunk-based development on `main`. Every change is a pull request with one concern; the maintainer reviews and merges. Work is tracked as GitHub issues (problem reports and change requests, see §9) and pull requests. Releases are cut by tag with owner approval (none yet). Cost, staffing, budgets and CMMI: not applicable (unfunded open-source project with one maintainer).

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Language runtime | CPython 3.11+ (README badge); CI uses 3.12 | README, `.github/workflows/ci.yml` |
| Runtime dependencies | None (standard library only) | REQ-REF-012 |
| Test runner | `unittest` (standard library), normal and `-O` modes | `.github/workflows/ci.yml` |
| Environment manager in CI | `astral-sh/setup-uv@v7`, `uv run --no-project --python 3.12` | `.github/workflows/ci.yml` |
| Secret scan | gitleaks 8.28.0 | `.github/workflows/ci.yml`, `.gitleaks.toml` |
| Static analysis / type check | None configured | — (risk R-4) |
| Offline data tools | CoolProp 8.0.0 via `uvx`, only for `tools/compute_golden.py` | [test plan TP-2](../verification/test-plan.md#tp-2--regenerate-the-golden-coolprop-points-manual-offline) |
| CI | GitHub Actions, `ubuntu-latest` | `.github/workflows/ci.yml` |

## 5. Verification and validation approach

Verification: pull-request review, the unit, integration and system tests in the [test plan](../verification/test-plan.md), the manifest check and the secret scan. The [verification matrix](../verification/verification-matrix.md) traces every requirement to its tests; `tools/check_trace.py` enforces the trace in CI through `tests/test_docs_trace.py`. Results are recorded in generated test reports.

Validation: the saturation tables are cross-checked against an independent direct CoolProp 8.0.0 run and against the generator's own off-grid points (REQ-REF-020); exposure limits and PSM thresholds carry their source quotations, and the loader checks that each quotation contains the stored value (REQ-REF-026, REQ-REF-032). This shows consistency with the cited sources and the oracle. It is not experimental validation, and no qualified person has approved the data (all Evidence is CHECK).

Release acceptance criteria (SWE-034 analog): the pass criteria in test plan §4 at the tag commit, a generated test report and version description for the tag, and a configuration audit entry in the assurance record.

## 6. Software assurance

There is one maintainer, so there is no organizational independence. Agent reviewers and CI gates give separation of method, not of organization; an agent's review is labelled as not independent. Assurance records live in the [assurance record](../assurance/assurance-record.md).

| Gate | Command | Fails on | Record |
|---|---|---|---|
| Tests | `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .` | Any failing test, including trace, link and generated-document checks | CI log; STR |
| Tests, optimized | `uv run --no-project --python 3.12 python -B -O -m unittest discover -s tests -t .` | Any failing test with `-O` | CI log; STR |
| Secret scan | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | Any default-rule finding in history | CI log; STR test log |
| Manifest | `uv run --no-project --python 3.12 python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json` | Committed manifest differs from the tree | CI log |
| Trace and links | `python -B tools/check_trace.py` (also run by the test suite) | Untraced requirement, missing test, unallocated requirement, dead link | STR; SAR |

## 7. Security, privacy and secure coding

Attack surface: JSON-RPC on stdin from the host. The bridge takes no command-line options or paths, opens no network connection, spawns no process and writes only to stdout and stderr. Inputs are bounded before parsing completes (frame size, depth, nodes, string and number length; duplicate keys, exponents, NaN and Infinity refused) and every object is checked against an exact field set. Outputs are bounded to 1 MiB. Secure-coding practices: closed schemas, explicit units, no `eval` or dynamic import of caller input, fixed data file names. Secrets: none are used; gitleaks scans history in CI. Personal data: none is processed; the policy set-point schema asks for a role, never a person's name. Dependency policy: no runtime dependencies; GitHub Actions versions are updated by Dependabot. Reporting: [SECURITY.md](../../SECURITY.md).

## 8. Open-source, reused and vendored components

| Component | Use | License | Pin |
|---|---|---|---|
| Python standard library | Runtime | PSF License | Runtime version (3.11+) |
| CoolProp 8.0.0 | Offline only: generated the saturation tables and golden points; not shipped or imported at runtime | MIT | `uvx --from CoolProp==8.0.0`; version check in `tools/compute_golden.py` |
| `invariants.py` | Received from Akilleez-QA/endoforge (same family, same owner) | GPL-3.0-only in this repository | Source commit recorded in the [SCMP](../configuration/configuration-management.md#71-invariant-provenance) |
| GitHub Actions `actions/checkout@v7`, `astral-sh/setup-uv@v7`; gitleaks 8.28.0 | CI only | Their own licenses | Major-version tags; gitleaks by exact release |

Reuse by others: GPL-3.0-only, with commercial licenses available (see [NOTICE.md](../../NOTICE.md)). The module layout follows foundation-template so other Foundations can copy it.

## 9. Problem reporting and severity

| Severity | Meaning | Response |
|---|---|---|
| S1 | Wrong result presented as valid, data loss, or security exposure | Fix or withdraw release before next merge |
| S2 | Feature unusable, no workaround | Next release |
| S3 | Feature degraded, workaround exists | Scheduled |
| S4 | Cosmetic / docs | As convenient |

A wrong saturation value, unit conversion or exposure-limit value returned as a success is S1. Issues are opened with the templates in `.github/ISSUE_TEMPLATE/` (problem report, change request). An issue closes only with a linked pull request that verifies the fix. Security reports go privately per SECURITY.md.

## 10. Configuration management

Baselines are commits on `main`; the source manifest pins every covered file; generated documents are reproduced by tools and checked in CI. Details: [configuration management plan](../configuration/configuration-management.md).

## 11. Operations, maintenance and retirement

- Changes: issue, pull request with one concern, review, CI, merge; the host repins after any covered change.
- Supported versions: the latest commit on `main` ([SECURITY.md](../../SECURITY.md)). There are no tags yet.
- Migration notes: in `CHANGELOG.md` under the release that needs them.
- Delivery: the public Git repository; Cstack vendors a byte-pinned copy. No package registry.
- Version data for users: `foundation_refrigeration.__version__`, the `initialize` response `serverInfo.version`, and the [version descriptions](../releases/README.md).
- Data maintenance: exposure limits and PSM thresholds were retrieved in October 2026 and can change at the source; re-check at each release (risk R-1).
- Backup operational software: not applicable; the prior commit or tag is the fallback.
- Retirement: a final tag, a README status line saying the repository is retired, and GitHub archive.

## 12. Risk register

Reviewed at every release. Likelihood (L) and consequence (C) are 1–5.

| ID | Risk | L | C | Mitigation | Status | Issue |
|---|---|---|---|---|---|---|
| R-1 | Cited exposure limits or PSM thresholds change at the source after retrieval (2026-10-06, 2026-10-25), so stored values go stale | 3 | 4 | Retrieval dates and quotations stored with each value; status CHECK; limitations page tells users to re-check the official source; re-check at each release | Open | — |
| R-2 | Someone uses outputs for a real engineering or life-safety decision | 2 | 5 | Boundary object and limitations in every receipt; limitations page; classification statement; no normal/abnormal or compliance verdicts | Open | — |
| R-3 | `main` has no branch protection, so a change could merge with failing CI | 2 | 3 | Maintainer merges only after checks pass; CI runs on every PR and push | Open | — |
| R-4 | No static analysis or type checking is configured | 3 | 2 | Small standard-library code base; closed schemas; full test suite in two modes | Open | — |
| R-5 | Behaviour without tests (GAP-REF-001 to GAP-REF-008) regresses unnoticed | 2 | 3 | Gaps listed in the SRS; candidates for tests | Open | — |
| R-6 | CoolProp mixture models differ from REFPROP or measured data for blends | 3 | 3 | Stated in every table's limitations; tables marked CHECK; no design use claimed | Open | — |

## 13. Measurement

Each test report generated by `tools/gen_reports.py` carries a metrics block: tests run, passed and failed in both modes; requirements total and traced; untested gaps; TBD count; issues by state and severity; merged pull requests; source lines by file type. Coverage is not measured (see test plan §5).

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

The [documentation index](../README.md) lists every control document and guide.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 62764c7 | Initial baseline | PR adding the NASA-standard documentation set |

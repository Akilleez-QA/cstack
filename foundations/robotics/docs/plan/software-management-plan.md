# foundation-robotics software management plan

| Field | Value |
|---|---|
| Document ID | FROBO-SMP |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. foundation-robotics is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system.
- Why not Class D: Class D covers software that supports engineering work, and kinematics, balance and mechanism checks resemble the engineering analysis tools it lists. **Class E holds only because no real engineering decision depends on foundation-robotics.** Its outputs judge animation and research motion. If anyone uses them for a real engineering decision about a robot, machine or person, the Class D analog applies to that use, and this project does not provide what Class D requires.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** foundation-robotics meets none of the five criteria in NASA-STD-8739.8B §4.2: it causes or contributes to no hazard, provides no hazard control or mitigation, controls no safety-critical function, mitigates no damage, and detects or responds to no hazardous state. No hazard analysis assigns it a hazard cause, control or mitigation.
- Outputs are bounded observations for research and acceptance checks. They are not engineering approvals. Anyone who relies on them for engineering, safety or regulatory decisions takes on the Class D-analog obligations for that use and must verify against authoritative sources (see [limitations](../guides/explanation/limitations.md)).
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the [compliance matrix](compliance-matrix.md).
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path (including any robot or machine design sign-off); handling personal or secret data beyond local configuration; external deployment as a shared service.
- Assessed by / date / baseline commit: Akilleez-QA (documentation lane, agent-assisted) / 2026-11-08 / b4de079f2d99114e5efe6b204704df57d392e454.

## 2. Purpose, scope and organization

foundation-robotics is a Foundation (repository type F) in the Cstack family: six read-only motion checks behind a stdio JSON-RPC bridge, used by the Cstack host. The maintainer (Akilleez-QA, Refrigeration.AI) is the sole approver and merges every change. Agent lanes and external contributors propose changes through pull requests. CODEOWNERS assigns every path to the maintainer.

## 3. Life-cycle model and work tracking

Trunk-based development on `main`. Each change is a pull request with one concern; issues are opened first for anything beyond a small fix ([CONTRIBUTING](../../CONTRIBUTING.md)). GitHub issues are the work breakdown; no milestones exist yet. Dependabot opens weekly GitHub Actions updates (`.github/dependabot.yml`). Releases are tags cut only with owner approval; none exists yet. Cost, staffing and CMMI: not applicable (unfunded, single-maintainer open source).

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Language runtime | CPython 3.11 or newer; CI uses 3.12 | README; `.github/workflows/ci.yml` |
| Runtime dependencies | None (standard library only) | REQ-ROB-011 |
| Test runner | `unittest` (standard library) | ci.yml |
| Optional test dependency | `jsonschema`, not installed in CI | `tests/test_tools.py` |
| Static analysis / type check | None in CI | — |
| Secret scan | gitleaks 8.28.0 with default rules | ci.yml, `.gitleaks.toml` |
| CI | GitHub Actions, `ubuntu-latest`, jobs `tests`, `gitleaks`, `manifest` | `.github/workflows/ci.yml` |

## 5. Verification and validation approach

Verification: pull-request review, the unit and bridge tests in both normal and `-O` modes, the trace and link check, and the manifest check. Records: [verification matrix](../verification/verification-matrix.md), generated [test reports](../verification/reports/README.md) and the [assurance record](../assurance/assurance-record.md). Procedures: [test plan](../verification/test-plan.md).

Validation: the calibration set replays known-good and known-bad motion that a person judged (REQ-ROB-017); closed-form physics results are compared exactly in the tests (pendulum period, cart-table ZMP, four-bar loop closure, slider-crank position). No validation against captured robot or clinical data exists.

Release acceptance (SWE-034): all CI jobs green at the tag commit; a generated STR and VDD for the tag; trace check with zero problems; CHANGELOG section for the tag.

## 6. Software assurance

The project has one maintainer, so there is no organizational independence. Agent reviewers and CI gates give separation of method only, and agent review is not independent.

| Gate | Command | Fails on | Record |
|---|---|---|---|
| Unit and bridge tests | `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .` | any failing test, including trace, links and generated-docs freshness (`tests/test_docs.py`) | CI log, STR |
| Optimized-mode tests | same with `-O` | behaviour that depends on `assert` | CI log, STR |
| Source manifest | `uv run --no-project --python 3.12 python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json` | manifest not regenerated | CI log |
| Secret scan | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | any finding in history | CI log, SAR |
| Peer review | pull request | unresolved review findings | PR, SAR summary |

## 7. Security, privacy and secure coding

Attack surface: stdin of one child process. No network, no file writes, no subprocesses, no options, no caller paths, no environment variables read. Practices: fail-closed parsing with byte, depth, node, string and integer limits; integer-only numbers; exact field sets; bounded arrays; deterministic output. Secrets: gitleaks in CI; none are needed to run. Personal data: none processed. Dependency policy: no runtime dependencies; GitHub Actions are updated weekly by Dependabot. Reporting: [SECURITY.md](../../SECURITY.md).

## 8. Open-source, reused and vendored components

No third-party code is shipped or vendored. CI uses `actions/checkout@v7`, `astral-sh/setup-uv@v7` and the gitleaks release binary 8.28.0. The repository is GPL-3.0-only with commercial licences available ([NOTICE.md](../../NOTICE.md)) and is reusable by any host that pins `SOURCE-MANIFEST.json`. Cstack vendors it byte-pinned; fixes go upstream here and the host repins.

## 9. Problem reporting and severity

| Severity | Meaning | Response |
|---|---|---|
| S1 | Wrong result presented as valid, data loss, or security exposure | Fix or withdraw release before next merge |
| S2 | Feature unusable, no workaround | Next release |
| S3 | Feature degraded, workaround exists | Scheduled |
| S4 | Cosmetic / docs | As convenient |

Problems and change requests use the [issue templates](../../.github/ISSUE_TEMPLATE/). An issue closes only with a linked pull request that records how the fix was verified. Security problems go privately per SECURITY.md.

## 10. Configuration management

Baselines are commits on `main`; the source identity is `SOURCE-MANIFEST.json` plus the tool inventory digest. See the [configuration management plan](../configuration/configuration-management.md).

## 11. Operations, maintenance and retirement

Changes are analyzed in an issue, implemented in a pull request, verified by CI and the trace check, and merged by the maintainer. Supported version: the latest commit on `main` ([SECURITY.md](../../SECURITY.md)). Behaviour changes are recorded in the CHANGELOG; interface changes also change the manifest and inventory pins, and the host repins in the same change. Distribution is the public GitHub repository; there is no package. Users find version data in `SOURCE-MANIFEST.json`, `serverInfo.version` and the [version descriptions](../releases/README.md). Retirement: final tag, README status notice, GitHub archive. Operational backup software: not applicable; a prior commit or tag is the fallback.

## 12. Risk register

Reviewed at every release; likelihood (L) and consequence (C) 1 to 5.

| ID | Risk | L | C | Mitigation | Status | Issue |
|---|---|---|---|---|---|---|
| R-1 | A user treats a `thresholds_met` verdict as approval of a real robot or machine motion | 2 | 4 | Boundary block in every receipt; limitations page; classification statement | Open | — |
| R-2 | Thresholds marked `CHECK` misjudge motion outside the calibration set (quadrupeds, runs, robots) | 4 | 2 | Status reported per default; caller overrides labelled; calibration replay in CI | Open | — |
| R-3 | Output schema drifts from results unnoticed because CI lacks `jsonschema` | 3 | 2 | Local check documented; SAR finding F-3 | Open | — |
| R-4 | Untested bridge error paths regress (GAP-ROB-01 to 11) | 3 | 2 | Listed in SRS §8; candidate tests | Open | — |
| R-5 | A host runs stale code because the manifest was not regenerated | 2 | 3 | CI `manifest` job; manifest test; host repins | Mitigated | — |

## 13. Measurement

Each generated STR carries a metrics block: tests run and failed per mode, requirement count, traced tests, trace problems, open and closed issues, merged pull requests with reviews, and line counts. Produced by `tools/gen_reports.py`.

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

See the [documentation index](../README.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | b4de079 | Initial baseline | docs/nasa-standard PR |

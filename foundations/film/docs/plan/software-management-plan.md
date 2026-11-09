# foundation-film software management plan

| Field | Value |
|---|---|
| Document ID | FFILM-SMP |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. foundation-film is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** foundation-film meets none of the five criteria in NASA-STD-8739.8B §4.2: it causes or contributes to no hazard, provides no hazard control or mitigation, controls no safety-critical function, mitigates no damage, and detects or responds to no hazardous state. No hazard analysis assigns it a hazard cause, control or mitigation.
- Outputs are bounded observations for film acceptance review. They are not acceptance decisions; the client remains the acceptance authority (see [limitations](../guides/explanation/limitations.md)).
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the [compliance matrix](compliance-matrix.md).
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path; handling personal or secret data beyond local configuration (the offline producer opens local media); external deployment as a shared service.
- Assessed by / date / baseline commit: Akilleez-QA (documentation lane, agent-assisted) / 2026-11-08 / 852f976aacaf8f08618bd0f37777f37822ce2614.

## 2. Purpose, scope and organization

foundation-film is a Foundation (repository type F) in the Cstack family: six read-only film acceptance checks behind a stdio JSON-RPC bridge, used by the Cstack host, plus an optional offline video producer. The maintainer (Akilleez-QA, Refrigeration.AI) is the sole approver and merges every change. Agent lanes and external contributors propose changes through pull requests. CODEOWNERS assigns every path to the maintainer.

## 3. Life-cycle model and work tracking

Trunk-based development on `main`. Each change is a pull request with one concern; issues are opened first for anything beyond a small fix ([CONTRIBUTING](../../CONTRIBUTING.md)). GitHub issues are the work breakdown; no milestones exist yet. Dependabot opens weekly GitHub Actions updates (`.github/dependabot.yml`). Releases are tags cut only with owner approval; none exists yet. Cost, staffing and CMMI: not applicable (unfunded, single-maintainer open source).

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Language runtime | CPython 3.12 in CI; the code uses no syntax newer than 3.11 | `.github/workflows/ci.yml` |
| Runtime dependencies | None for the bridge and tools (REQ-FILM-011). The offline producer needs NumPy, opencv-python-headless and scenedetect | README |
| Test runner | `unittest` (standard library) | ci.yml |
| Optional test dependencies | The producer libraries; without them four tests are skipped (always in CI) | `tests/test_filmstats.py` |
| Static analysis / type check | None in CI | — |
| Secret scan | gitleaks 8.28.0 with default rules | ci.yml, `.gitleaks.toml` |
| CI | GitHub Actions, `ubuntu-latest`, jobs `tests`, `gitleaks`, `manifest` | `.github/workflows/ci.yml` |

## 5. Verification and validation approach

Verification: pull-request review, the unit, bridge and limit tests in both normal and `-O` modes, the manual producer tests (test plan TP-2), the trace check and the manifest check. Records: [verification matrix](../verification/verification-matrix.md), generated [test reports](../verification/reports/README.md) and the [assurance record](../assurance/assurance-record.md). Procedures: [test plan](../verification/test-plan.md).

Validation: parity tests show the integer tools reproduce the reference scripts' outcomes on seeded random inputs (REQ-FILM-021); fixed cases replay numbers from one reference production run. No validation across other films exists.

Release acceptance (SWE-034): all CI jobs green at the tag commit; TP-2 passing with no skips; a generated STR and VDD for the tag; trace check with zero problems; CHANGELOG section for the tag.

## 6. Software assurance

The project has one maintainer, so there is no organizational independence. Agent reviewers and CI gates give separation of method only, and agent review is not independent.

| Gate | Command | Fails on | Record |
|---|---|---|---|
| Unit, bridge and limit tests | `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .` | any failing test | CI log, STR |
| Optimized-mode tests | same with `-O` | behaviour that depends on `assert` | CI log, STR |
| Source manifest | `uv run --no-project --python 3.12 python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json` | manifest not regenerated | CI log |
| Secret scan | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | any finding in history | CI log, SAR |
| Peer review | pull request | unresolved review findings | PR, SAR summary |

## 7. Security, privacy and secure coding

Attack surface: stdin of one child process; two optional environment variables that change Evidence text only. No network, no file writes, no subprocesses, no options, no caller paths. The offline producer is a separate local program that opens a video path given by its operator and decodes it with third-party libraries. Practices: fail-closed parsing with byte, depth, node, string and integer limits; integer-only numbers; exact field sets; bounded arrays; deterministic output. Secrets: gitleaks in CI; none are needed to run. Personal data: none processed. Dependency policy: no runtime dependencies for the bridge; the producer's libraries are unpinned and fetched by `uv` at run time; GitHub Actions are updated weekly by Dependabot. Reporting: [SECURITY.md](../../SECURITY.md).

## 8. Open-source, reused and vendored components

No third-party code is shipped or vendored. `foundation_film/filmstats.py` is adapted from Endoforge main at `819fa8a6b3eea9cae5f1388eb67a78556ad65727` (`tools/film/filmstats.py`, same GPL-3.0-only licence). The producer imports NumPy, opencv-python-headless and scenedetect at run time; they are not shipped. CI uses `actions/checkout@v7`, `astral-sh/setup-uv@v7` and the gitleaks release binary 8.28.0. The repository is GPL-3.0-only with commercial licences available ([NOTICE.md](../../NOTICE.md)) and is reusable by any host that pins `SOURCE-MANIFEST.json`. Cstack vendors it byte-pinned; fixes go upstream here and the host repins.

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
| R-1 | A user treats `thresholds_met` as acceptance of delivered work | 2 | 3 | Boundary block in every receipt; limitations page; Evidence wording | Open | — |
| R-2 | Defaults from one reference run misjudge other films | 4 | 2 | Evidence marks them `CHECK`; caller overrides are named | Open | — |
| R-3 | Producer regressions go unnoticed because CI skips its video tests | 3 | 2 | TP-2 manual run required for producer changes | Open | — |
| R-4 | A producer library update breaks it (scenedetect already warns that `get_seconds()` is deprecated) | 3 | 2 | SAR finding; pin or update the call | Open | — |
| R-5 | A host runs stale code because the manifest was not regenerated | 2 | 3 | CI `manifest` job; manifest test; host repins | Mitigated | — |

## 13. Measurement

Each generated STR carries a metrics block: tests run and failed per mode, requirement count, traced tests, trace problems, open and closed issues, merged pull requests with reviews, and line counts. It is produced by the documentation lane's report generator (an adapted copy of foundation-robotics `tools/gen_reports.py`, not yet in this repository).

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

See the [documentation index](../README.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 852f976 | Initial baseline | docs/nasa-standard PR |

# <Repo> software management plan

| Field | Value |
|---|---|
| Document ID | <CODE>-SMP |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWEHB 5.08 (with 5.04 maintenance, 5.17 assurance, 5.27 risk, 5.05 metrics plan, 5.15 training decision). NPR SWE-013, 020, 022, 033, 042, 121, 125, 139, 176, 205, 024, 034, 027, 147, 148, 156, 154, 207, 185, 075, 195, 196, 086, 090. Keep it short: S and T repos can fit on two screens. -->

## 1. Software classification (self-assessed)

<!-- Paste the classification statement template from family-doc-standard.md §2.2 and fill every <...>. Foundations with engineering data (refrigeration, robotics, math) keep the Class D-analog sentence. -->

## 2. Purpose, scope and organization

<!-- What the repo is, where it sits in the family (host / engine / foundation / skill-tool / template), who has authority: maintainer as sole approver; agent sessions as contributors; external contributors via PR. -->

## 3. Life-cycle model and work tracking

<!-- E.g. trunk-based with PR review and merge train; issues and milestones as work breakdown; how releases are cut. Link CONTRIBUTING. Cost, staffing and CMMI: N/A (unfunded single-maintainer open source). -->

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Language runtime | <e.g. Python 3.11+, Node 20> | <pyproject / package.json / CI matrix> |
| Test runner | | |
| Static analysis / type check | | |
| CI | <workflow path> | |

## 5. Verification and validation approach

<!-- Verification: peer review (PR), unit/integration/system tests, static analysis; records live in verification matrix, STR, SAR. Validation: how we show it does the intended job for users (tutorial runs, acceptance/e2e, domain cross-checks against authoritative data). Link test-plan.md. Acceptance criteria for a release (SWE-034). -->

## 6. Software assurance

<!-- SWEHB 5.17 tailored. State plainly: single maintainer, no organizational independence; agent reviewers and CI gates provide separation of method only. List each assurance gate copied from CI: name, command, what it fails on. Where records live (SAR). -->

| Gate | Command | Fails on | Record |
|---|---|---|---|
| | | | |

## 7. Security, privacy and secure coding

<!-- SWE-156/154/207/185: cybersecurity assessment summary (attack surface: CLI, stdio, network, subprocess, file writes), secure coding practices adopted, secret scanning, dependency policy. Link SECURITY.md. -->

## 8. Open-source, reused and vendored components

<!-- SWE-027/147/148: list dependencies and vendored code with license, pin method (lockfile, SOURCE-MANIFEST digest), how updates are evaluated, how this repo is reusable by others. -->

## 9. Problem reporting and severity

| Severity | Meaning | Response |
|---|---|---|
| S1 | Wrong result presented as valid, data loss, or security exposure | Fix or withdraw release before next merge |
| S2 | Feature unusable, no workaround | Next release |
| S3 | Feature degraded, workaround exists | Scheduled |
| S4 | Cosmetic / docs | As convenient |

<!-- Adjust only with rationale. Issues via .github/ISSUE_TEMPLATE; closure requires a linked verifying PR. -->

## 10. Configuration management

<!-- One paragraph + link to docs/configuration/configuration-management.md. -->

## 11. Operations, maintenance and retirement

<!-- SWEHB 5.04 tailored: how changes are analyzed, implemented, reviewed and released; supported versions (link SECURITY.md); migration notes policy (CHANGELOG); delivery/distribution channel; how users find version data (VDD); retirement = final tag + archive notice + README status. Backup operational software: N/A, prior tag is the fallback. -->

## 12. Risk register

<!-- SWEHB 5.27 tailored. Review at every release. Likelihood/consequence 1–5. -->

| ID | Risk | L | C | Mitigation | Status | Issue |
|---|---|---|---|---|---|---|
| R-1 | | | | | Open | |

## 13. Measurement

<!-- Which metrics are produced in each STR (5.05 tailored) and by what script. -->

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

<!-- Table of every control document and guide with path and status. Can link docs/README.md instead. -->

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

# foundation-template software management plan

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-SMP |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. foundation-template is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system. Its one tool echoes the caller's own text and carries no domain data.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** foundation-template meets none of the five criteria in NASA-STD-8739.8B §4.2, and no hazard analysis assigns it a hazard cause, control or mitigation.
- For copies: a Foundation started from this template must redo this assessment for its own domain. A Foundation with engineering data (for example foundation-refrigeration or foundation-robotics) adds the sentence: "Outputs are bounded observations for research and acceptance checks. They are not engineering approvals. Anyone who relies on them for engineering, safety or regulatory decisions takes on the Class D-analog obligations for that use and must verify against authoritative sources," and must have a limitations page.
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the [compliance matrix](compliance-matrix.md).
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path; handling personal or secret data beyond local configuration; external deployment as a shared service; adding domain data.
- Assessed by / date / baseline commit: Akilleez-QA maintainer (assessment drafted by an agent documentation lane, not independent) / 2026-11-08 / fb9993c55e9c708a3cfdd295b237466d4bef7ff1.

## 2. Purpose, scope and organization

foundation-template is the **template**-type repository in the Cstack family: the copy source for new Foundations (stdio JSON-RPC bridge, read-only tools, Evidence-carrying results). Its documentation is itself the template for a new Foundation's documentation: every control document here is a filled-in instance a copy edits. The maintainer (Refrigeration.AI, GitHub `Akilleez-QA`) is the sole approver and code owner; agents and external contributors propose changes by pull request.

## 3. Life-cycle model and work tracking

Trunk-based development on `main`; every change is a pull request with one concern, reviewed and merged by the maintainer. Work is tracked as GitHub issues (problem reports and change requests) and pull requests. Releases by tag with owner approval (none yet). Cost, staffing and CMMI: not applicable.

## 4. Engineering and test environment

| Item | Version / source | Where defined |
|---|---|---|
| Language runtime | CPython 3.11+; CI uses 3.12 | `.github/workflows/ci.yml` |
| Runtime dependencies | None (standard library only) | REQ-TPL-006 |
| Test runner | `unittest`, normal and `-O` modes | `.github/workflows/ci.yml` |
| CI environment | `actions/checkout@v4`, `astral-sh/setup-uv@v7`, `ubuntu-latest` | `.github/workflows/ci.yml` |
| Secret scan | gitleaks 8.28.0 | `.github/workflows/ci.yml` |
| Static analysis / type check | None configured | — (risk R-3) |

## 5. Verification and validation approach

Verification: pull-request review, the tests in the [test plan](../verification/test-plan.md), the manifest check and the secret scan; the [verification matrix](../verification/verification-matrix.md) traces every requirement and `tools/check_trace.py` enforces it inside the test suite. Validation: the template's purpose is to be copied, so validation is a copy that keeps a passing, traced suite (TP-3 in the test plan; not yet run). Release acceptance: test-plan §4 criteria at the tag commit, a generated test report and version description, and a configuration-audit entry in the assurance record.

## 6. Software assurance

One maintainer, so no organizational independence; agent reviewers and CI gates give separation of method only, and agent review is labelled as not independent. Records: [assurance record](../assurance/assurance-record.md).

| Gate | Command | Fails on | Record |
|---|---|---|---|
| Tests | `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .` | Any failing test, including trace, link and generated-catalog checks | CI log; STR |
| Tests, optimized | same with `-O` | Any failing test with `-O` | CI log; STR |
| Secret scan | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | Any finding in history | CI log; STR |
| Manifest | `uv run --no-project --python 3.12 python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json` | Manifest differs from the tree | CI log |
| Trace and links | `python -B tools/check_trace.py` (also run by the tests) | Untraced requirement, missing test, unallocated requirement, dead link | STR; SAR |

## 7. Security, privacy and secure coding

Attack surface: JSON-RPC on stdin. No options, paths, network, child processes or file access; stdout and stderr only. Inputs are bounded (frame, depth, nodes, strings, integer digits; non-integers, NaN and duplicate keys refused) and checked against exact field sets; outputs are bounded to 1 MiB. No secrets or personal data are processed; gitleaks scans history in CI. No runtime dependencies; Dependabot updates CI actions. Reporting: [SECURITY.md](../../SECURITY.md).

## 8. Open-source, reused and vendored components

| Component | Use | License | Pin |
|---|---|---|---|
| Python standard library | Runtime | PSF License | Runtime version |
| `actions/checkout@v4`, `astral-sh/setup-uv@v7`, gitleaks 8.28.0 | CI only | Their own licenses | Major-version tags; gitleaks by exact release |

No third-party code is shipped or vendored. Reuse: GPL-3.0-only, with commercial licenses available ([NOTICE.md](../../NOTICE.md)).

## 9. Problem reporting and severity

| Severity | Meaning | Response |
|---|---|---|
| S1 | Wrong result presented as valid, data loss, or security exposure | Fix or withdraw release before next merge |
| S2 | Feature unusable, no workaround | Next release |
| S3 | Feature degraded, workaround exists | Scheduled |
| S4 | Cosmetic / docs | As convenient |

For the template, a defect that copies would inherit (for example a bridge limit not enforced) is at least S2. Issues use the templates in `.github/ISSUE_TEMPLATE/`; an issue closes only with a verifying pull request. Security reports go privately per SECURITY.md.

## 10. Configuration management

Baselines are commits on `main`; the source manifest pins every covered file; generated documents are reproduced by tools and checked in CI. Details: [configuration management plan](../configuration/configuration-management.md).

## 11. Operations, maintenance and retirement

- Changes: issue, pull request, review, CI, merge; Cstack repins its vendored copy.
- Supported versions: the latest commit on `main` ([SECURITY.md](../../SECURITY.md)); no tags yet.
- Copies do not track the template automatically. A fix to the bridge here is ported to each Foundation by its own pull request; the CHANGELOG entry says when a fix should be ported.
- Delivery: the public Git repository. Version data: `foundation_template.__version__`, `initialize` `serverInfo.version`, [version descriptions](../releases/README.md).
- Backup operational software: not applicable; the prior commit or tag is the fallback.
- Retirement: final tag, README status line, GitHub archive.

## 12. Risk register

Reviewed at every release. Likelihood (L) and consequence (C) are 1–5.

| ID | Risk | L | C | Mitigation | Status | Issue |
|---|---|---|---|---|---|---|
| R-1 | A bridge defect here is copied into every new Foundation | 2 | 4 | Input-limit tests at each boundary; gaps listed in the SRS; CHANGELOG says when to port a fix | Open | — |
| R-2 | `main` has no branch protection, so a change could merge with failing CI | 2 | 3 | Maintainer merges only after checks pass | Open | — |
| R-3 | No static analysis or type checking | 3 | 2 | Small code base; tests in two modes | Open | — |
| R-4 | A copy keeps template wording (placeholder tool, REQ-TPL IDs, "foundation-template") that no longer fits | 3 | 2 | [Start a new Foundation](../guides/how-to/start-a-new-foundation.md) lists every rename; `tools/check_trace.py` fails on stale IDs or dead links | Open | — |

## 13. Measurement

Each generated test report (`tools/gen_reports.py`) carries counts: tests run, passed and failed in both modes; requirements and gaps; TBDs; issues; merged pull requests; source lines by type. Coverage is not measured.

## 14. Training

Not applicable. SWEHB 5.15 anticipates one training plan per NASA Center, NPR SWE-017 applies only to Classes A–C, and the repo has no staff. Contributor onboarding is CONTRIBUTING plus the tutorials.

## 15. Documentation list

The [documentation index](../README.md) lists every control document and guide.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | fb9993c | Initial baseline | PR adding the NASA-standard documentation set |

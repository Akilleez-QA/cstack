# Cstack requirements mapping matrix

| Field | Value |
|---|---|
| Document ID | CSTACK-RMM |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Self-assessed class: Class E analog, not safety-critical. Baseline: Class E with voluntary adoption of the Class D documentation set.

| SWE | Topic | NPR classes | Decision | How met / rationale |
|---|---|---|---|---|
| 013 | Software plans | A–E | Applies | [SMP](software-management-plan.md) |
| 020 | Classification | A–E | Applies | [SMP §1](software-management-plan.md#1-software-classification-self-assessed) |
| 176 | Classification records | A–E | Applies | [SMP §1](software-management-plan.md#1-software-classification-self-assessed) and its change history |
| 205 | Safety-critical determination | A–E | Applies | [SMP §1](software-management-plan.md#1-software-classification-self-assessed): not safety-critical |
| 022 | SA / safety / IV&V planning | A–E | Tailored | [SMP §6](software-management-plan.md#6-software-assurance); no independent assurance organization; no IV&V |
| 033 | Acquire vs develop | A–E | Applies | [SMP §8](software-management-plan.md#8-open-source-reused-and-vendored-components): vendored Foundations and EndoForge are acquired; host code is developed |
| 042 | Source code access | A–E | Applies | Public repository https://github.com/Akilleez-QA/cstack |
| 121 / 139 / 125 | Tailoring, compliance, this matrix | A–E | Applies | This document |
| 148 | Contribute to reuse | A–E | Applies | GPL-3.0-only; [README family table](../../README.md#related-projects); [family standard](../standards/family-doc-standard.md) |
| 156 | Cybersecurity assessment | A–E | Applies | [SMP §7](software-management-plan.md#7-security-privacy-and-secure-coding), [SECURITY.md](../../SECURITY.md) |
| 024 / 034 / 036 / 037 | Tracking, acceptance criteria, doc plan, milestones | A–D | Tailored | GitHub issues; [SMP §5](software-management-plan.md#5-verification-and-validation-approach) acceptance; [docs index](../README.md) |
| 039 / 040 | Developer status reporting and deliverables to acquirer | A–D | N/A | No acquirer/supplier split; public repository and releases serve the purpose |
| 027 | COTS/OSS components | A–D | Applies | [SMP §8](software-management-plan.md#8-open-source-reused-and-vendored-components): vendored Foundations and EndoForge are acquired; host code is developed |
| 015 / 151 / 174 / 016 / 046 / 018 | Cost and schedule | A–D (018: A–C) | N/A | Unfunded single-maintainer project |
| 017 | Training | A–C | N/A | [SMP §14](software-management-plan.md#14-training) |
| 141 / 131 / 178 / 179 | IV&V | A–B | N/A | Not an IV&V-category project |
| 023 / 134 / 219 / 220 | Safety-critical software | A–D if safety-critical | N/A | Not safety-critical (SWE-205) |
| 032 | CMMI rating | A–B | N/A | Not applicable to open-source single maintainer |
| 146 / 206 | Auto-generated code | A–C / A–D | Applies | No generated source code. Generated records (export manifest, pins, test reports, version descriptions) are controlled in the [SCMP](../configuration/configuration-management.md#control-of-generated-outputs) |
| 147 | Reusability requirements | A–D | Applies | [SRS §5](../requirements/requirements.md#5-non-functional-requirements) |
| 154 / 157 / 159 / 207 / 185 / 210 | Cybersecurity risks, protections, secure coding, verification | A–D (210: A–C) | Tailored | [SMP §7](software-management-plan.md#7-security-privacy-and-secure-coding), [SAR](../assurance/assurance-record.md) |
| 050 / 051 / 053 / 054 / 055 | Requirements | A–D (051: A–C) | Applies | [SRS](../requirements/requirements.md), [SAR](../assurance/assurance-record.md) |
| 184 | Safety constraints in requirements | A–C | N/A | No hazards |
| 052 | Bidirectional traceability | A–D | Applies | [Verification matrix](../verification/verification-matrix.md), `tools/check_trace.py` |
| 057 / 058 | Architecture and design | A–C | Applies (voluntary) | [SDD](../architecture/architecture.md), [ICDs](../icd/) |
| 143 | Architecture review | A–C | Tailored | PR review of SDD changes |
| 060 / 061 | Code, coding standards | A–C / A–D | Applies | [CONTRIBUTING](../../CONTRIBUTING.md), [no-comments rule](../rules/no-comments.md); no linter configured |
| 135 | Static analysis | A–D | Applies | [SMP §6](software-management-plan.md#6-software-assurance), [SAR](../assurance/assurance-record.md); no static analyzer configured, recorded as a finding |
| 062 / 186 | Unit test, repeatable | A–D | Applies | [Test plan](../verification/test-plan.md) |
| 063 | Version description | A–D | Applies | [Releases](../releases/README.md) |
| 136 / 070 | Tool / model accreditation | A–C | Tailored | Tools pinned in [SMP §4](software-management-plan.md#4-engineering-and-test-environment); no accreditation |
| 065 / 066 / 068 / 071 | Test plan, testing, evaluate results, update | A–D | Applies | [Test plan](../verification/test-plan.md), [reports](../verification/reports/) |
| 187 | CM before test | A–C | Applies | CI runs on committed code (`.github/workflows/ci.yml`) |
| 073 | Target platform validation | A–C | Tailored | One CI environment (ubuntu-latest, Python 3.12, Node 24); local Linux runs recorded in test reports |
| 189 / 190 | Code coverage | A–D / A–C | Tailored | Not measured; no coverage tool configured. Recorded in the STR metrics |
| 191 | Regression testing | A–C | Applies | Full suite on every PR ([test plan](../verification/test-plan.md)) |
| 192 / 193 | Hazard tests, uplinked data | A–D / A–B | N/A | No hazards; no uplink |
| 211 | Test reused components | A–C | Tailored | Vendored Foundation suites run in `ci/run-local.sh python`; pins checked by conformance tests |
| 075 / 077 / 194 / 195 / 196 | Operations, delivery, maintenance, retirement | A–D | Tailored | [SMP §11](software-management-plan.md#11-operations-maintenance-and-retirement), [releases](../releases/README.md) |
| 079–085 | Configuration management | A–D | Applies | [SCMP](../configuration/configuration-management.md) |
| 045 | Joint audits | A–C | N/A | No acquirer |
| 086 | Risk management | A–C | Tailored | [SMP §12](software-management-plan.md#12-risk-register) |
| 087 / 088 / 089 | Peer review | A–C | Tailored | [PR template](../../.github/pull_request_template.md); [SAR](../assurance/assurance-record.md) summary; no effort metrics |
| 090 / 093 / 094 / 199 / 200 | Measurement | A–C (200: A–B) | Tailored | [STR](../verification/reports/STR-baseline.md) metrics block |
| 201 / 202 | Non-conformances, severity | A–D / A–C | Applies | GitHub issues; [SMP §9](software-management-plan.md#9-problem-reporting-and-severity) |
| 203 / 204 | OSS defect assessment, process assessment | A–C / A–B | Tailored | Dependabot advisories reviewed; S1 root-cause note in the issue |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Initial baseline | docs/nasa-standard PR |

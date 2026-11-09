# <Repo> requirements mapping matrix

| Field | Value |
|---|---|
| Document ID | <CODE>-RMM |
| Version | 1.0 |
| Status | Draft |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD> |
| Baseline commit | <40-hex sha> |
| Applies to | <repo> <tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

<!-- Template from family-doc-standard.md. Delete every HTML comment when instantiating. Delete a heading only with a one-line tailoring note in its place. -->

<!-- SWE-125 (invoked for Class E). Rows: NPR 7150.2D requirements. Class column from Appendix C parse (verify edge cases against the PDF). Family defaults pre-filled; edit "How met" links and any repo-specific decision. Decision values: Applies, Tailored, N/A. -->

Self-assessed class: Class E analog, not safety-critical. Baseline: Class E with voluntary adoption of the Class D documentation set.

| SWE | Topic | NPR classes | Decision | How met / rationale |
|---|---|---|---|---|
| 013 | Software plans | A–E | Applies | docs/plan/software-management-plan.md |
| 020 | Classification | A–E | Applies | SMP §1 |
| 176 | Classification records | A–E | Applies | SMP §1 + change history |
| 205 | Safety-critical determination | A–E | Applies | SMP §1: not safety-critical |
| 022 | SA / safety / IV&V planning | A–E | Tailored | SMP §6; no independent SA organization; no IV&V |
| 033 | Acquire vs develop | A–E | Applies | SMP §8 |
| 042 | Source code access | A–E | Applies | Public repository |
| 121 / 139 / 125 | Tailoring, compliance, this matrix | A–E | Applies | This document |
| 148 | Contribute to reuse | A–E | Applies | Public license; README family table |
| 156 | Cybersecurity assessment | A–E | Applies | SMP §7, SECURITY.md |
| 024 / 034 / 036 / 037 | Tracking, acceptance criteria, doc plan, milestones | A–D | Tailored | Issues/milestones; SMP §5 acceptance; docs/README.md |
| 039 / 040 | Developer status reporting and deliverables to acquirer | A–D | N/A | No acquirer/supplier split; public repository and releases serve the purpose |
| 027 | COTS/OSS components | A–D | Applies | SMP §8 |
| 015 / 151 / 174 / 016 / 046 / 018 | Cost and schedule | A–D (018: A–C) | N/A | Unfunded single-maintainer project; milestones only |
| 017 | Training | A–C | N/A | SMP §14 |
| 141 / 131 / 178 / 179 | IV&V | A–B | N/A | Not an IV&V-category project |
| 023 / 134 / 219 / 220 | Safety-critical software | A–D if safety-critical | N/A | Not safety-critical (SWE-205) |
| 032 | CMMI rating | A–B | N/A | Not applicable to open-source single maintainer |
| 146 / 206 | Auto-generated code | A–C / A–D | <Applies/N/A> | <SCMP generated-output section, or "no generated source"> |
| 147 | Reusability requirements | A–D | Applies | SRS non-functional section |
| 154 / 157 / 159 / 207 / 185 / 210 | Cybersecurity risks, protections, secure coding, verification | A–D (210: A–C) | Tailored | SMP §7, SAR static-analysis entry |
| 050 / 051 / 053 / 054 / 055 | Requirements | A–D (051: A–C) | Applies | docs/requirements/requirements.md, SAR |
| 184 | Safety constraints in requirements | A–C | N/A | No hazards |
| 052 | Bidirectional traceability | A–D | Applies | docs/verification/verification-matrix.md, trace check |
| 057 / 058 | Architecture and design | A–C | Applies (voluntary) | docs/architecture/architecture.md, docs/icd/ |
| 143 | Architecture review | A–C | Tailored | PR review of SDD changes |
| 060 / 061 | Code, coding standards | A–C / A–D | Applies | CONTRIBUTING, linters, docs/rules/ |
| 135 | Static analysis | A–D | Applies | SMP §6, SAR |
| 062 / 186 | Unit test, repeatable | A–D | Applies | test-plan.md |
| 063 | Version description | A–D | Applies | docs/releases/ |
| 136 / 070 | Tool / model accreditation | A–C | Tailored | Tools pinned in SMP §4; no accreditation |
| 065 / 066 / 068 / 071 | Test plan, testing, evaluate results, update | A–D | Applies | docs/verification/ |
| 187 | CM before test | A–C | Applies | CI runs on committed code |
| 073 | Target platform validation | A–C | Tailored | CI OS/runtime matrix |
| 189 / 190 | Code coverage | A–D / A–C | Tailored | Measured where tooling exists; value recorded in STR |
| 191 | Regression testing | A–C | Applies | Full suite on every PR |
| 192 / 193 | Hazard tests, uplinked data | A–D / A–B | N/A | No hazards; no uplink |
| 211 | Test reused components | A–C | Tailored | Vendored pins re-tested via host suite |
| 075 / 077 / 194 / 195 / 196 | Operations, delivery, maintenance, retirement | A–D | Tailored | SMP §11, VDD |
| 079–085 | Configuration management | A–D | Applies | docs/configuration/configuration-management.md |
| 045 | Joint audits | A–C | N/A | No acquirer |
| 086 | Risk management | A–C | Tailored | SMP §12 |
| 087 / 088 / 089 | Peer review | A–C | Tailored | PR template; SAR summary; no effort metrics |
| 090 / 093 / 094 / 199 / 200 | Measurement | A–C (200: A–B) | Tailored | STR metrics block |
| 201 / 202 | Non-conformances, severity | A–D / A–C | Applies | Issues; SMP §9 |
| 203 / 204 | OSS defect assessment, process assessment | A–C / A–B | Tailored | Dependency advisories reviewed; S1 root-cause note in issue |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | <YYYY-MM-DD> | <sha> | Initial baseline | PR #<n> |

# Cstack family documentation standard

| Field | Value |
|---|---|
| Document ID | MJOLNIR-DOCSTD |
| Version | 1.0 |
| Status | Baselined (canonical copy) |
| Owner | Akilleez-QA maintainer |
| Date | 2026-11-08 |
| Canonical location | https://github.com/Akilleez-QA/cstack/tree/main/docs/standards |
| Sources | NPR 7150.2D (eff. 2022-03-08); NASA-STD-8739.8B; NASA-HDBK-2203 (SWEHB Ver D) topic 7.18 and pages 5.01–5.27. Links and digests: [Sources](#sources) |

This standard tells a documentation contributor what to write for one Cstack-family repository, where to put it, and how to keep it true. It adapts the NASA documentation guidance to a small open-source family. It does not make any repository a NASA project. Follow the standard's intent: each document should help a reader run, change, verify or release the software. A heading that holds no real content should be deleted with a one-line tailoring note. Leaving it in with filler is worse.

Contents: 1 Scope and repo types · 2 Classification and disclaimer · 3 Metadata header · 4 Docs layout · 5 Traceability rule · 6 Per-document requirements (SWEHB 5.01–5.27) · 7 Tailoring summary · 8 Keeping documents accurate · 9 Writing rules.

## 1. Scope and repository types

| Repo | Type | Notes |
|---|---|---|
| cstack | host | Vendors the Foundations and EndoForge byte-pinned. Owns the composition, adapter and approval interfaces |
| endoforge | engine | Workshop and evaluator engine. Has ledger, capacity and constraint interfaces |
| poodo | skill/tool | Reasoning skill. The product is mostly prose and a validator |
| foundation-engine | foundation (library variant) | TypeScript/three.js games framework. Its interface is a library API rather than a stdio bridge |
| foundation-math, foundation-film, foundation-refrigeration, foundation-robotics | foundation | stdio JSON-RPC bridge, read-only tools, Evidence-carrying results |
| foundation-template | template | Copy source for new Foundations. Its docs are themselves templates that must stay instantiable |

Vendored copies inside cstack (`foundations/*`, `vendor/*`) are byte-pinned mirrors. Fix their docs upstream and re-pin. Never edit the mirror.

## 2. Software classification statement and disclaimer

### 2.1 Family self-assessment (rationale)

NPR 7150.2D Appendix D defines Classes A–E for engineering software and Class F for business and IT infrastructure. Each family repository is assessed against it as follows:

- **Class E (Design Concept, Research, Technology, and General Purpose Software)** is the best analog. The family runs in a general-purpose computing environment. It supports no ground tests, flight tests or operations. A defect affects the productivity of a single user or a small group. It cannot be safety-critical.
- **Class F does not fit.** It covers Agency business and IT infrastructure, such as enterprise applications, networks and the public Web, where a defect affects many users across locations. The family is not deployed infrastructure.
- **Class D does not apply by definition.** Class D covers software that supports NASA engineering, research facilities or airborne vehicles. Its examples include thermal and structural analysis tools. foundation-refrigeration (saturation tables, exposure limits) and foundation-robotics (kinematics, balance) resemble those examples, so their statements must say Class E holds only because no NASA or operational engineering decision depends on them. If a user relies on them for real engineering decisions, the Class D analog applies to that use.
- **Not safety-critical.** NASA-STD-8739.8B §4.2 calls software safety-critical when it meets any of five criteria. It causes or contributes to a hazard, provides a hazard control or mitigation, controls safety-critical functions, mitigates damage, or detects and responds to hazardous states. The determination traces to a hazard analysis. The family meets none of these criteria and has no system hazard analysis to trace to. This is the SWE-205 determination record.

**Documentation baseline: Class E classification, Class D-informed documentation.** Under NPR 7150.2D Appendix C, Class E invokes only a few requirements: SWE-013, 020, 022, 033, 042, 121, 125, 139, 148, 156, 176 and 205. The family voluntarily adopts the Class D documentation set (requirements, design, traceability, CM, testing, version description, defect tracking, static analysis and secure coding), because the maintainer asked for fleshed-out documentation. Requirements that apply only to Classes A–C stay out, with the rationale given in §7. Examples are IV&V (SWE-141), CMMI rating (SWE-032), MC/DC (SWE-219) and training (SWE-017).

The class applicability was parsed from the Appendix C Table 2 text extraction. The X marks extract left-packed, so check any edge case against the PDF before citing it.

### 2.2 Classification statement template (put in the Software Management Plan §1 and summarize in README Status)

```markdown
## Software classification (self-assessed)

- Assessed against: NPR 7150.2D Appendix D and NASA-STD-8739.8B §4.2, as an analog. <REPO> is not NASA software and no NASA authority has reviewed this assessment.
- Analog class: **Class E** (general-purpose research/technology software). Rationale: runs on general-purpose computers; supports no ground test, flight test or operation; a defect affects the productivity of an individual user or a small group; it is not used for decisions about an operational system.
- Not Class F: not Agency business or IT infrastructure.
- Safety-critical determination (SWE-205 analog): **not safety-critical.** <REPO> meets none of the five criteria in NASA-STD-8739.8B §4.2, and no hazard analysis assigns it a hazard cause, control or mitigation.
- <Foundations with engineering data only> Outputs are bounded observations for research and acceptance checks. They are not engineering approvals. Anyone who relies on them for engineering, safety or regulatory decisions takes on the Class D-analog obligations for that use and must verify against authoritative sources.
- Documentation baseline: Class E with voluntary adoption of the Class D documentation set; see the compliance matrix.
- Re-evaluation triggers: commanding physical hardware; use in a regulated, safety or production decision path; handling personal or secret data beyond local configuration; external deployment as a shared service.
- Assessed by / date / baseline commit: <maintainer> / <YYYY-MM-DD> / <sha>.
```

### 2.3 Standard disclaimer (put verbatim after the metadata header of every control document)

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

This replaces the older cstack sentence "No NASA software classification … is asserted". The family now records a self-assessed analog classification and labels it as self-assessed. Link to the NASA URLs. Do not commit the standards PDFs or text into repositories.

## 3. Document metadata header

Every control document (`docs/plan`, `requirements`, `architecture`, `icd`, `data`, `verification`, `configuration`, `assurance`, `releases`) starts with the following. Guides and root files are exempt; they use the Diátaxis and community-file conventions.

```markdown
# <Repo> <document title>

| Field | Value |
|---|---|
| Document ID | <CODE>-<DOC> (e.g. CSTACK-SRS) |
| Version | <major.minor> (major = re-baselined content; minor = corrections) |
| Status | Draft · Baselined · Superseded by <ID> |
| Owner | <maintainer handle, no @> |
| Date | <YYYY-MM-DD of this version> |
| Baseline commit | <full 40-hex commit the content was checked against> |
| Applies to | <repo> <release tag or "main at baseline commit"> |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> <standard disclaimer §2.3>

...body...

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | YYYY-MM-DD | <sha> | Initial baseline | PR #<n> |
```

Repo codes: CSTACK, ENDOFORGE, POODO, FENGINE, FMATH, FFILM, FREFRIG, FROBO, FTEMPLATE. Document codes: SMP, RMM (compliance matrix), SRS, SDD (design), ICD-<name>, DD (data dictionary), STP, VM (verification matrix), STR-<tag>, SCMP, VDD-<tag>, SAR (assurance record), SUM-MAP.

"Baselined" means the content was checked against the named commit in a merged PR. A doc whose baseline commit is older than the code it describes is stale (see §8).

## 4. Standard repository docs layout

This extends the layout cstack and the vendored Foundations already use (`architecture/ configuration/ guides/ icd/ requirements/ rules/ verification/`). Nothing existing moves. New folders are added only where a document is required.

```
README.md                 SUM front door: purpose, status+classification summary, quickstart, family table, docs link
CONTRIBUTING.md           Dev environment, local checks, PR/peer-review process, branch & commit rules
SECURITY.md               Vulnerability reporting, supported versions, security posture summary
SUPPORT.md                Where to ask, problem-report route
CHANGELOG.md              Keep-a-Changelog; one section per tag; source for VDD
LICENSE, NOTICE.md        Licensing (SMP/maintenance licensing item)
.github/ISSUE_TEMPLATE/   problem-report.md, change-request.md        (5.01)
.github/pull_request_template.md  peer-review record + doc checklist (5.03)
docs/
  README.md               Index: Diátaxis entry points + control-document table
  plan/
    software-management-plan.md   SMP (5.08 + 5.04 maint + 5.17 SA + 5.27 risk + metrics plan)
    compliance-matrix.md          Requirements mapping matrix (SWE-125)
  requirements/requirements.md    SRS (5.09)
  architecture/architecture.md    Software design description (5.13); extra design notes alongside
  icd/icd-<interface>.md          One ICD per external interface (5.02)
  data/data-dictionary.md         Data dictionary (5.07); generated tables where possible
  verification/
    test-plan.md                  STP + test procedures (5.10, 5.14)
    verification-matrix.md        Requirement ↔ test trace (SWE-052)
    reports/STR-<tag>.md          Test report per release (5.11 + metrics 5.05)
  configuration/configuration-management.md   SCMP (5.06)
  releases/VDD-<tag>.md           Version description per release (5.16)
  assurance/assurance-record.md   Rolling analysis/audit record (5.21, 5.22, 5.23, 5.25, 5.26, 5.03 summary)
  rules/                          Repository rules (existing)
  guides/
    tutorials/  how-to/  reference/  explanation/   Diátaxis (SUM body, 5.12)
```

Rules:
- endoforge has both `docs/icd/` and `docs/interfaces/`. New ICDs go in `docs/icd/`. Existing `docs/interfaces/*` may stay. The docs index and the SDD must link both, until a later PR moves them and fixes the links.
- For a skill/tool or template repo, one file may hold several merged documents, using the section headings from the templates. Say so in the docs index.
- Released artefacts (STR, VDD) may instead be GitHub Release bodies, provided `docs/releases/README.md` links each one by tag.

### 4.1 Diátaxis and root-file mapping

| NASA content | Where it lives |
|---|---|
| SUM: software summary, environment, modes, security/privacy, assistance, problem reporting | README (Status, What is inside, Security, Support links) + `guides/explanation/` |
| SUM: first-time use, starting/stopping a session | `guides/tutorials/` (one end-to-end runnable tutorial minimum) |
| SUM: processing procedures, backup, recovery from errors, messages | `guides/how-to/` (task recipes, troubleshooting, error/exit-code table) |
| SUM: capabilities, conventions, commands, configuration keys | `guides/reference/` (CLI/tool/API reference; links to ICDs and data dictionary) |
| SUM: assumptions, limitations, safety-related constraints | README "Not included / Limitations" + `guides/explanation/limitations.md` |
| SUM: version-unique information | CHANGELOG + VDD |
| Maintenance: problem/modification process, peer review | CONTRIBUTING + PR template |
| Maintenance: security posture, supported versions | SECURITY.md |
| CR/PR intake | SUPPORT.md → issue templates |
| Licensing of components | LICENSE, NOTICE.md, SMP §OSS |

## 5. Bidirectional traceability rule (SWE-052)

Every requirement must trace forward to design, code, test and verification result. Every test and design element must trace back to a requirement, or be labelled as supporting or infrastructure.

| Link | Forward record | Backward record |
|---|---|---|
| Requirement → design | SRS "Allocated to" field names SDD section/component | SDD component lists the requirement IDs it satisfies |
| Requirement → code | SRS "Derivation" field names source path(s) | not tagged in code (no-comments rule); recovered via SRS/SDD paths |
| Requirement → test | Verification matrix row: requirement → `file::Class.method` (or test ID) + method (T/A/I/D) | Test name or test-plan entry cites requirement ID; a trace check lists tests with no requirement |
| Test → result | STR-<tag> lists each test ID with pass/fail at the release commit | Verification matrix "Last result" column points to STR-<tag> |
| Interface → requirement | ICD "Requirements addressed" section | SRS interface requirement cites the ICD |

Pass criteria for a baseline:
1. Zero requirements with no verification-matrix row. A requirement verified only by inspection (I) or analysis (A) must name what is inspected or analyzed.
2. Zero matrix rows that point at a test which does not exist at the baseline commit.
3. Zero design components that implement no requirement, unless they are marked "infrastructure".
4. Each matrix row's result comes from a recorded run at a named commit. A historical pass count is not current evidence.
5. A changed requirement or test in a PR updates the matrix in the same PR.

Automate where possible. A `tools/check_trace.py` per repo (standard library only) should parse requirement IDs from the SRS, rows from the matrix, and test names from the test tree. It fails on items 1–3. Until such a tool exists, the contributor performs these checks by hand and records them in the assurance record.

## 6. Per-document requirements (SWEHB 5.01–5.27)

Abbreviations for repo types: H host, E engine, F foundation, S skill/tool, T template. "Req" means Required, "Tail" means Tailored, "N/A" means not applicable. NPR SWE IDs are listed for traceability only. Class E invokes only the IDs marked with *, and the rest are adopted voluntarily.

### 5.01 Software change request / problem report (CR-PR)
- **Purpose:** record each anomaly or requested change from report to verified closure.
- **Minimum content (paraphrased):** affected item and version or configuration; description, with steps or the reason for the change; who reported it and how severe they rate it; analysis and corrective action; the life-cycle phase where it was found; decision (accepted or rejected); the assignee; status and dates; any workaround; safety or security impact; how the fix was verified and in which release.
- **Supports:** SWE-080, 201, 202, 203, 204; SWE-053.
- **Tailoring: Tail.** Use GitHub Issues with two issue templates: problem report and change request. Severity is a label from S1 to S4, defined in the SMP. The PR that closes the issue records the verification. No separate document.
- **Repos:** H E F S T.
- **Location:** `.github/ISSUE_TEMPLATE/`. The severity definitions go in the SMP.
- **Accuracy:** the STR and VDD list the issues closed and still open at the tag, by query (`gh issue list --state ...`).

### 5.02 Interface design description (IDD / ICD)
- **Purpose:** pin down every external interface, so that both sides can change independently without breaking each other.
- **Minimum content:** the interfacing entities and which side owns what; the interface type (stdio JSON-RPC, CLI, library API, files); data elements (name, type, units, range, encoding); assemblies (messages, records, files, schemas); the communication method and protocol (framing, ordering, timeouts, errors); identity and version or compatibility controls; traceability to requirements; how compatibility is checked; safety- and security-related features (input bounds, quarantine, authority).
- **Supports:** SWE-050 (interface requirements), 052, 057, 058.
- **Tailoring: Req**, with these changes. Bit-level layout becomes schema-level (JSON Schema or TypeScript types). "Interface priority" is dropped. Physical compatibility is N/A.
- **Repos:** H (adapters, Foundations, EndoForge pin, POODO, CLI approval); E (cstack, ledger, capacity); F (stdio bridge or library API); S (skill invocation contract); T (bridge contract that copies inherit).
- **Location:** `docs/icd/icd-<interface>.md`.
- **Accuracy:** generate the message and field tables from the schema files (`schemas/`, `contracts/`, tool catalogs). Record catalog digests. Point a test at each documented error path.

### 5.03 Software peer reviews / inspections
- **Purpose:** catch defects before merge, and keep a record that the review happened.
- **Minimum content:** what was reviewed and what kind of review it was; date; participants and their roles; defects found by severity and type; the outcome (pass or re-review); the defect list.
- **Supports:** SWE-087, 088, 089.
- **Tailoring: Tail.** The pull request is the review record. Reviewers are the human approver plus any agent reviewers, named in the PR. Effort and hour measures are dropped, because the project has a single maintainer and nothing is gained by tracking them. Defects are the review comments that were resolved. The outcome is the merge or the requested changes. Agent review is labelled as not independent.
- **Repos:** all.
- **Location:** `.github/pull_request_template.md`. The SAR keeps a per-baseline summary (how many PRs, how many had review findings).
- **Accuracy:** generate summaries from `gh pr list --json` for the baseline range.

### 5.04 Software maintenance plan
- **Purpose:** say how the software is changed, released, migrated and retired after first release.
- **Minimum content:** maintenance process; problem and modification analysis; implementing and accepting changes; migration and retirement; assurance and risk assessment for changes; upgrade cadence; the verification environment; doc updates; licensing; backup copies; delivery and installation; how users find version data.
- **Supports:** SWE-075, 077, 194, 195, 196.
- **Tailoring: Tail**, merged into SMP §"Operations, maintenance and retirement". Operational backup software is N/A; the substitute is a pinned prior tag. Facility delivery becomes package and registry distribution.
- **Repos:** all.
- **Location:** SMP section, plus SECURITY.md (supported versions) and CONTRIBUTING.
- **Accuracy:** the supported-versions table is derived from tags. The retirement section names the archive procedure: GitHub archive plus the final tag.

### 5.05 Software metrics report
- **Purpose:** give measured status. Claims are not enough.
- **Minimum content:** progress (tests written, run, passed); functionality (requirements in the release); quality (open and closed issues by severity, reviews, static-analysis results, requirements verified); volatility (requirement count, changes, TBDs); characteristics (language, lines of code, resource use).
- **Supports:** SWE-090, 093, 094, 199, 200.
- **Tailoring: Tail.** There is no standalone report. A generated metrics block goes into each STR. Cost, schedule and function points are N/A, because the project is unfunded and has a single maintainer. Resource use is included where the repo measures it, for example EndoForge capacity or cstack route timings.
- **Repos:** H E F (full block); S T (counts only).
- **Location:** `docs/verification/reports/STR-<tag>.md` §Metrics.
- **Accuracy:** produce the metrics with a script (test runner output, `gh` queries, `git diff --stat`, `cloc` if available). Never type in numbers by hand.

### 5.06 Software configuration management plan (SCMP)
- **Purpose:** say what is under control, how it is identified, how changes are approved, and how releases are built and audited.
- **Minimum content:** organization and responsibilities; applicable policies; configuration identification (items, naming, baselines); change control; status accounting; configuration audits; control of auto-generated outputs and their tools and inputs; schedule and resources; how the plan is maintained; release management and delivery.
- **Supports:** SWE-079, 080, 081, 082, 083, 084, 085, 045, 146, 206.
- **Tailoring: Req.** The organization is the maintainer plus agent contributors. A baseline is a commit or tag. Branch protection and the merge train are the change control. Status accounting comes from tags, CHANGELOG and manifests.
- **Repos:** all. H and E must cover pins, vendored manifests and SHA-256 identities. F and T must cover SOURCE-MANIFEST and the tool catalog digest.
- **Location:** `docs/configuration/configuration-management.md` (existing).
- **Accuracy:** generate the manifest digest tables (`sha256sum`, `tools/build_export_manifest.py`). A CI check compares each table to the files.

### 5.07 Software data dictionary
- **Purpose:** define every data item the software reads, writes or exchanges, with type, units, range and meaning.
- **Minimum content (applicable subset):** I/O variables (format, units, definition); command and tool definitions (purpose, parameters, restrictions); operational limits (min, max, wire limits); data-file formats and provenance; scheduling and concurrency mechanisms where relevant. Channelization, rate groups, raw or calibrated sensor data, telemetry, recorder formats and partitioning are N/A, because no hardware or telemetry exists.
- **Supports:** SWE-050 (data requirements), 058.
- **Tailoring: Tail.**
- **Repos:** F (Req: tool parameters, units, ranges, data-table provenance; refrigeration and robotics must give the source and units of each table); H (config keys, contract and schema fields, ledger records); E (ledger and receipt records, capacity fields, config); S (minimal: input and output record fields); T (template fields).
- **Location:** `docs/data/data-dictionary.md`. It may link out to `guides/reference/` instead of duplicating it.
- **Accuracy:** generate the tables from JSON Schemas, tool catalogs and config examples. A test asserts that every schema field appears in the dictionary.

### 5.08 Software development / management plan (SDP/SMP)
- **Purpose:** one place that says how this repo is built, verified, assured, released and maintained, and under what classification.
- **Minimum content:** organization and authority; classification and safety-critical determination; the tailoring/compliance matrix; engineering and test environment; life-cycle model; work breakdown (as the issue and milestone structure); quality, safety, security and privacy management; verification methods, work products, environments and records; validation methods and records; user involvement; risk management; security policy; licensing and approvals; tracking and reporting; training (N/A, see 5.15); CM pointer; peer-review process; software metrics; documentation list; handling of OSS and reused components.
- **Supports:** SWE-013*, 020*, 022*, 033*, 042* (public source), 121*, 125*, 139*, 176*, 205*, 024, 034, 036, 037, 027, 147, 148*, 156*, 154, 207, 185.
- **Tailoring: Tail.** One short SMP. Cost estimation, staffing, budgets, subcontractor management and CMMI are N/A. Schedule becomes milestones or the merge train.
- **Repos:** all (S and T may be short).
- **Location:** `docs/plan/software-management-plan.md` and `docs/plan/compliance-matrix.md`.
- **Accuracy:** the review checks the SMP each time the release process, CI or tooling changes. The compliance matrix rows link to real files, and a link checker fails on dead links.

### 5.09 Software requirements specification (SRS)
- **Purpose:** state what the software shall do and how each item is qualified.
- **Minimum content:** introduction (purpose, scope, system overview); functional requirements (states and modes, data, I/O with validation and error handling, algorithms, security and privacy, fault management); non-functional requirements (performance and timing, quality attributes, design constraints, resource use); interface requirements (external and internal software, user, communication, service or API); user requirements; a qualification method per requirement (test, analysis, inspection, demonstration); rationale; other information. Safety, control-system, OS, BSP, partitioning and hardware-interface requirements are N/A unless the repo actually has them, and each must be stated as N/A.
- **Supports:** SWE-050, 051, 052, 053, 054, 055, 184 (N/A: no hazards), 210.
- **Tailoring: Req.** Each requirement records: a stable ID (keep the repo's existing scheme, such as `CS-REQ-###` or `REQ-<AREA>-###`, and never reuse an ID); one "shall" statement; rationale; derivation (source paths); allocated-to (SDD section); verification method; status (proposed, baselined or deleted). Requirements describe inspected behavior or an accepted obligation. They are not aspirations.
- **Repos:** all.
- **Location:** `docs/requirements/requirements.md` (existing).
- **Accuracy:** the trace check (§5); TBD count reported in the STR; a PR that changes behavior updates the SRS in the same PR.

### 5.10 Software test plan (STP)
- **Purpose:** define the test levels, environments, coverage approach, acceptance criteria and regression strategy.
- **Minimum content:** test levels (unit, integration, system or end-to-end, acceptance, regression; performance and security where relevant); test types; test progression and schedule (CI stages); acceptance and pass criteria; coverage approach and target; witnessing (N/A, or human approver sign-off); test data; test risks; qualification approach; the trace to requirements.
- **Supports:** SWE-065, 066, 068, 071, 073, 187, 189, 190, 191, 211, 062, 186.
- **Tailoring: Tail**, merged with 5.14. Formal witnessing is N/A. Testing on the target platform means named OS and runtime versions. Coverage is measured where tooling exists (Python `coverage`, `c8` for TypeScript), and the target is recorded as an actual measured value with no invented threshold. MC/DC is N/A because the software is not safety-critical (SWE-219).
- **Repos:** all.
- **Location:** `docs/verification/test-plan.md`.
- **Accuracy:** commands are copied from the CI workflow and `ci/run-local.sh`, and a check compares them. The environment table is regenerated from the CI matrix.

### 5.11 Software test report (STR)
- **Purpose:** record what was run, on what, with what result, at a release.
- **Minimum content:** overview (conclusion, remaining deficiencies, test-environment impact); detailed results (test ID, requirements verified, problems, deviations); test log (date, software version or commit, environment, who or what ran it); rationale for decisions such as accepting a known failure.
- **Supports:** SWE-068, 201, 194.
- **Tailoring: Tail.** Generate it from the CI run or a local `ci/run-local.sh` run at the tag commit. The person is the CI job or the operator. Add the metrics block from 5.05.
- **Repos:** H E F (each release); S T (each release; may be the release body).
- **Location:** `docs/verification/reports/STR-<tag>.md` or the GitHub Release body linked from `docs/releases/README.md`.
- **Accuracy:** never hand-edit results. Attach the run URL or log digest.

### 5.12 Software user manual (SUM)
- **Purpose:** let a new user install, run, recover and get help without reading source.
- **Minimum content:** summary (application, environment, modes, security and privacy, assistance, problem reporting); access (first use, starting and stopping); processing reference (capabilities, conventions, procedures, backup and recovery, error messages); assumptions, limitations and safety-related constraints; version-specific information.
- **Supports:** SWE-077 (delivery records); content per SWEHB 5.12.
- **Tailoring: Tail.** There is no single SUM file. The content is spread over README and the Diátaxis guides per §4.1, and `docs/guides/SUM-MAP.md` (template `user-manual-map.md`) records where each element lives. foundation-refrigeration and foundation-robotics must have an explicit "Limitations and safety-relevant use" explanation page. Engineering or exposure data must not be the sole basis for safety decisions, and the page names the authoritative sources.
- **Repos:** all.
- **Location:** README, `docs/guides/**`, `docs/guides/SUM-MAP.md`.
- **Accuracy:** tutorials run in CI (a doc-test or smoke script) where feasible. The CLI reference is generated from `--help` and the tool reference from the catalog. Error-message tables are generated from the error enums.

### 5.13 Software design description (SDD)
- **Purpose:** explain how the requirements are met, to a reader about to change the code.
- **Minimum content:** design decisions and trade-offs; architecture (components, responsibilities, multiple views); decomposition and relationships; per component, how it satisfies requirements (algorithms, data structures); I/O; static relationships; execution concept (data flow, control flow, timing, concurrency); requirements ↔ design ↔ code trace; resource use; rationale, assumptions and limitations; interface design (pointer to the ICDs); key quality attributes (performance, availability, maintainability, security, testability, usability).
- **Supports:** SWE-057, 058, 052, 143 (architecture review: N/A as formal, done by PR review).
- **Tailoring: Req.**
- **Repos:** all (S: short; T: describes the skeleton every Foundation inherits).
- **Location:** `docs/architecture/architecture.md`, plus topic files next to it.
- **Accuracy:** module and component tables are generated from the package tree. Diagrams are Mermaid in markdown, not images, so they diff. Each component row lists its requirement IDs.

### 5.14 Software test procedures
- **Purpose:** give enough detail to rerun any test and get the same verdict.
- **Minimum content:** environment (OS, runtimes, tools, test beds); schedule; per test: ID, grouping, purpose, version under test, preconditions, steps, inputs and outputs, expected results, pass/fail criteria, rerun notes; the trace matrix.
- **Supports:** SWE-065, 071, 186.
- **Tailoring: Tail.** The executable tests are the procedures. The test plan gives the commands, environment and fixtures. Manual or live-service procedures (EndoForge live runs, cstack e2e, foundation-engine browser checks) each get a numbered procedure section in the test plan. Hazard-control verification grouping is N/A.
- **Repos:** all.
- **Location:** `docs/verification/test-plan.md` §Procedures.
- **Accuracy:** procedure commands are smoke-run by CI or listed as "manual, last run <date/commit>".

### 5.15 Software training plan
- **Tailoring: N/A.** SWEHB anticipates one plan per NASA Center. SWE-017 applies to Classes A–C. The family has no staff to train. Contributor onboarding is covered by CONTRIBUTING and the tutorials, which are themselves verified.
- **Repos:** none. The SMP states this decision in one line.

### 5.16 Version description document (VDD)
- **Purpose:** identify exactly what a release is and how to rebuild and verify it.
- **Minimum content:** full identification (name, version, tag, commit); executable or installable contents; life-cycle data defining the product (docs baseline); archive and release data; build instructions; integrity checks (digests); product files; open CRs and PRs with workarounds; CRs and PRs implemented since the last VDD; confirmation that security and coding-standard scans ran.
- **Supports:** SWE-063, 085, 077, 194.
- **Tailoring: Req** (SWE-063 is Class D; adopted voluntarily).
- **Repos:** all, one per tag.
- **Location:** `docs/releases/VDD-<tag>.md` or the release body, indexed by `docs/releases/README.md`.
- **Accuracy:** generate entirely from `git describe`, `git log <prev>..<tag>`, the CHANGELOG section, `gh issue list`, `sha256sum` of artefacts and manifests, and CI scan job results. A release script should emit it.

### 5.17 Software assurance plan
- **Purpose:** say how quality and conformance are checked independently of the author.
- **Minimum content:** assurance activities (audits, status, analyses); methods (review, test witnessing, analysis techniques, static analysis); stakeholders; resources and tools; roles; data management and storage; acceptance criteria; classification concurrence; safety-criticality assessment; risk; training.
- **Supports:** SWE-022*, SWE-205*; NASA-STD-8739.8B Table 1 (SASS tasks) as an analog.
- **Tailoring: Tail**, merged into SMP §"Software assurance". With one maintainer there is no organizational independence, and the SMP says so plainly. Agent reviewers and CI gates provide separation of method, not of organization. The SMP lists the tools: test runner, static analysis or linters, type checks, secret scanning, link and README checks, claim gate.
- **Repos:** all.
- **Location:** SMP §Assurance.
- **Accuracy:** the tool list is copied from the CI workflow. When a gate is removed, this section is updated in the same PR.

### 5.18 Software safety plan
- **Tailoring: N/A.** It is needed only when software is safety-critical (SWE-023, 8739.8B §4.2). The SWE-205 determination is "not safety-critical", and it is recorded in the classification statement along with the re-evaluation triggers.

### 5.19 Software assurance status report
- **Tailoring: N/A as a periodic report.** The status function is covered by the STR metrics block, the SAR and the issue tracker, so a periodic report would only duplicate them with no added value.

### 5.20 IV&V project execution plan
- **Tailoring: N/A.** SWE-141, 131, 178 and 179 apply only to Classes A and B and to specific project categories. There is no IV&V provider.

### 5.21 / 5.22 / 5.23 / 5.26 Requirements, design, testing and source-code-quality analysis reports
- **Purpose:** record what was analyzed, how, and what was found, so findings are tracked to closure.
- **Minimum content (common):** what was analyzed, and at which commit; who or what analyzed it; when; the inputs used; techniques (and why others were not used); a findings summary by technique; an overall assessment; major and minor findings with risk; status open or closed, linked to issues. Typical finding types: requirements that are missing, untestable or ambiguous, or untraced (orphan parent or child); design not meeting a requirement or not reflected in code; tests not covering a requirement or with wrong expected results; code-quality and security findings from static analysis.
- **Supports:** SWE-051, 054, 055, 135, 185, 207, 068, 201.
- **Tailoring: Tail.** All four are folded into one rolling `docs/assurance/assurance-record.md`, with one dated entry per baseline. Entries are short when nothing was found, but the techniques used must still be listed.
- **Repos:** H E (Req); F (Req, short); S T (Tail: trace and static-analysis entries only).
- **Location:** `docs/assurance/assurance-record.md`.
- **Accuracy:** paste tool output summaries (counts) with the command and commit. Every major finding links an issue.

### 5.24 Hazard report
- **Tailoring: N/A.** No software is safety-critical and there is no system hazard analysis to contribute to. The substitute is the SUM "Limitations and safety-relevant use" content (required for refrigeration and robotics, and recommended for the host because it executes agents and commands) and SECURITY.md for misuse.

### 5.25 Audit report
- **Purpose:** check that the product and records match: functional and physical configuration audit.
- **Minimum content:** identification; auditor; date; governing documents; scope; techniques; summary; major and minor findings; observations; actions with due dates.
- **Supports:** SWE-084, 045.
- **Tailoring: Tail.** A release-time configuration audit (docs baseline vs tag, manifest digests vs files, VDD vs artefacts) is recorded as a SAR entry. Formal external audit reports are N/A.
- **Repos:** all, at release.
- **Location:** SAR entry, referenced from the VDD.

### 5.27 Risk management plan
- **Purpose:** identify, track and retire risks.
- **Minimum content:** strategy; process; documentation method; reviews; communication; stakeholders and roles; risk types and sources; configuration control.
- **Supports:** SWE-086, 154 (cybersecurity risks).
- **Tailoring: Tail.** A risk register table goes in SMP §Risk: ID, risk, likelihood and consequence (1–5), mitigation, owner, status, linked issue. Process: review at each release. Communication: via the PR or issue. NPR 8000.4 organizational content is N/A.
- **Repos:** all (S and T may have very few rows).
- **Location:** SMP §Risk.

### Additional required item: requirements mapping (compliance) matrix
- **Purpose:** show for each NPR requirement whether it applies, how it is met, or why it is tailored out. SWEHB 7.16 and SWE-125 apply to Class E.
- **Tailoring: Req**, as a tailored matrix. The rows are the Class D-and-above SWE IDs listed in §6. The template is pre-filled with the family defaults, and contributors only edit repo-specific cells.
- **Location:** `docs/plan/compliance-matrix.md`.

## 7. Tailoring summary

| SWEHB | Document | Decision | H | E | F | S | T | Where |
|---|---|---|---|---|---|---|---|---|
| 5.01 | CR-PR | Tail: issue templates + severity labels | ✓ | ✓ | ✓ | ✓ | ✓ | `.github/ISSUE_TEMPLATE/` |
| 5.02 | IDD/ICD | Req (schema-level) | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/icd/` |
| 5.03 | Peer review | Tail: PR is the record | ✓ | ✓ | ✓ | ✓ | ✓ | PR template; SAR summary |
| 5.04 | Maintenance plan | Tail: SMP section | ✓ | ✓ | ✓ | ✓ | ✓ | SMP |
| 5.05 | Metrics report | Tail: generated block in STR | ✓ | ✓ | ✓ | counts | counts | STR |
| 5.06 | SCMP | Req | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/configuration/` |
| 5.07 | Data dictionary | Tail: no HW/telemetry | ✓ | ✓ | ✓ (Req) | min | ✓ | `docs/data/` |
| 5.08 | SDP/SMP | Tail: one short SMP + compliance matrix | ✓ | ✓ | ✓ | short | short | `docs/plan/` |
| 5.09 | SRS | Req | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/requirements/` |
| 5.10 | Test plan | Tail: merged with 5.14; no witnessing/MC/DC | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/verification/test-plan.md` |
| 5.11 | Test report | Tail: generated per release | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/verification/reports/` |
| 5.12 | User manual | Tail: README + Diátaxis + SUM-MAP | ✓ | ✓ | ✓ | ✓ | ✓ | README, `docs/guides/` |
| 5.13 | Design description | Req | ✓ | ✓ | ✓ | short | ✓ | `docs/architecture/` |
| 5.14 | Test procedures | Tail: executable tests + procedure section | ✓ | ✓ | ✓ | ✓ | ✓ | test plan |
| 5.15 | Training plan | N/A: Center-level; SWE-017 A–C; no staff | – | – | – | – | – | SMP one-liner |
| 5.16 | VDD | Req (voluntary D), generated | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/releases/` |
| 5.17 | SA plan | Tail: SMP section, independence limit stated | ✓ | ✓ | ✓ | ✓ | ✓ | SMP |
| 5.18 | Safety plan | N/A: not safety-critical (SWE-205) | – | – | – | – | – | classification statement |
| 5.19 | SA status report | N/A: covered by STR metrics + SAR + issues | – | – | – | – | – | – |
| 5.20 | IV&V PEP | N/A: SWE-141 Class A/B only | – | – | – | – | – | – |
| 5.21 | Req. analysis report | Tail: SAR entry | ✓ | ✓ | ✓ | trace | trace | `docs/assurance/` |
| 5.22 | Design analysis report | Tail: SAR entry | ✓ | ✓ | ✓ | – | – | `docs/assurance/` |
| 5.23 | Testing analysis report | Tail: SAR entry | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/assurance/` |
| 5.24 | Hazard report | N/A: no hazards; substitute limitations page | lim. | – | lim.* | – | – | `guides/explanation/` |
| 5.25 | Audit report | Tail: release config audit in SAR | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/assurance/` |
| 5.26 | Code quality analysis | Tail: SAR entry from static analysis | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/assurance/` |
| 5.27 | Risk mgmt plan | Tail: SMP risk register | ✓ | ✓ | ✓ | ✓ | ✓ | SMP |
| 7.16 | Compliance matrix | Req (SWE-125, Class E) | ✓ | ✓ | ✓ | ✓ | ✓ | `docs/plan/` |

`lim.*` = required for foundation-refrigeration and foundation-robotics; recommended for other foundations.

## 8. Keeping documents accurate

| Fact | Single source | Mechanism |
|---|---|---|
| Requirement ↔ test trace | SRS IDs + test tree | `tools/check_trace.py` in CI (§5) |
| Tool, message and field tables | JSON Schemas, catalogs, `contracts/` | generator script; CI diff check |
| CLI reference | `--help` output | generated; CI diff check |
| Version, contents, changes | git tags, CHANGELOG, `git log` | VDD generator |
| Digests and pins | SOURCE-MANIFEST, EXPORT-MANIFEST, `sha256sum` | SCMP table generated; CI compares |
| Test results and metrics | CI run at tag | STR generator; never hand-typed |
| Open and closed issues | GitHub Issues | `gh` query in STR/VDD generator |
| Test commands | CI workflow, `ci/run-local.sh` | test plan copies them; check compares |
| Links | docs tree | `tools/check_links.py` / `ci/run-local.sh links` |
| README claims | code and measurements | `tools/check_readme.py`, `tools/claim_gate.py` where present |

Staleness rule: if any file named in a document's derivation or allocation fields changed after the document's baseline commit, the document is stale. The contributor updates it, or bumps the baseline after re-checking. `git log <baseline>..HEAD -- <paths>` is the check.

Until a generator exists, the contributor runs the command by hand, pastes the output, and records the command and commit beside the table. Writing the generator is a follow-up issue, not a blocker.

## 9. Writing rules

- Write in plain English, in short sections. Describe inspected behavior. Every claim must have a source path, test, measurement or link. Use "shall" only in the SRS.
- No marketing claims or unmeasured performance numbers. A measured number carries its command, its commit and the machine class it ran on.
- Do not paste NASA text at length. Paraphrase it and cite the SWEHB topic or SWE ID.
- The no-comments rule applies to code. The HTML guidance comments in `templates/` must be removed when a document is instantiated.
- Diagrams are Mermaid or ASCII. No binary images in control documents.
- One document per concern. Link rather than duplicate. Where content would be duplicated, the generated or reference copy wins and the other place links to it.
- Do not document secrets, tokens, local machine paths or private hosts.

## Sources

The NASA documents are US Government works. Link to them; do not commit copies to family repositories.

| Document | URL | SHA-256 of the PDF read for this version |
|---|---|---|
| NPR 7150.2D, NASA Software Engineering Requirements (eff. 2022-03-08) | https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all | `1a5b7f9b0b0141e88374adf7a21a4d6ced0b29c221ca89a0a514f495d6532802` |
| NASA-STD-8739.8B, Software Assurance and Software Safety Standard | https://standards.nasa.gov/standard/nasa/nasa-std-87398 | `e360f16cd3730ce32975f5207945840c1073dab7b54d3b71a443978afbe03539` |
| NASA-HDBK-2203 (SWEHB Ver D) topic 7.18, Documentation Guidance | https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance | HTML page, read 2026-11-08 |
| SWEHB Ver D pages 5.01–5.27, minimum recommended content per document | https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance (linked from topic 7.18) | HTML pages, read 2026-11-08 |

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-08 | First published canonical copy in cstack `docs/standards/` |

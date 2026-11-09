# Family documentation checklist (copy into the PR body)

Standard: `family-doc-standard.md` v1.0. Repo: `<repo>` · Type: H / E / F / S / T · Baseline commit: `<sha>`

Tick each line or replace `[ ]` with `N/A: <reason>`. A tick means the pass criterion was checked at the baseline commit. Do not tick a line because the file merely exists.

## Root and community files
- [ ] README: purpose, Status line with version and classification summary, runnable quickstart, family table, docs link, Limitations section. Quickstart commands were run at the baseline.
- [ ] CONTRIBUTING: dev setup, the exact local check command(s) matching CI, PR and peer-review process, link to this checklist.
- [ ] SECURITY: reporting route, supported-versions table derived from tags, security posture summary.
- [ ] SUPPORT: help route; points to the issue templates.
- [ ] CHANGELOG: one section per tag; an Unreleased section exists; the latest tag has a section.
- [ ] LICENSE and NOTICE: license matches the README badge. Vendored and third-party components are listed with their licenses.
- [ ] `.github/ISSUE_TEMPLATE/problem-report.md` and `change-request.md` exist and cover the 5.01 fields (item and version, description, severity, workaround, verification).
- [ ] `.github/pull_request_template.md` records the peer review: reviewers (agent or human, independence noted), findings, outcome, checklist link.

## Control documents (every one: metadata header §3, disclaimer §2.3, change history)
- [ ] `docs/README.md` index lists every control document and Diátaxis entry point. No dead links (`links` check passes).
- [ ] SMP `docs/plan/software-management-plan.md`: classification statement with rationale, safety-critical determination and re-evaluation triggers; environment; life cycle; V&V approach; assurance tools copied from CI; maintenance and retirement; severity scale S1–S4; risk register with at least 3 real rows (S/T: at least 1); training N/A line.
- [ ] Compliance matrix `docs/plan/compliance-matrix.md`: every row says Applies, Tailored or N/A. Each "how met" cell links an existing file or workflow.
- [ ] SRS `docs/requirements/requirements.md`: every requirement has an ID, one "shall", rationale, derivation path(s), allocated SDD section, method (T/A/I/D) and status. N/A requirement categories are stated. The TBD count is known.
- [ ] SDD `docs/architecture/architecture.md`: components table with responsibilities and requirement IDs; data and control flow; concurrency and timing; design decisions with rationale; quality attributes; limitations. Diagrams are text-based.
- [ ] ICDs `docs/icd/icd-*.md`: one per external interface. Owner per side; protocol and framing; message and field tables generated from schemas; error semantics; version and identity controls (digests); requirements addressed.
- [ ] Data dictionary `docs/data/data-dictionary.md`: every schema, tool-parameter and config field, with type, units, range and meaning. Data tables carry their provenance (F: required). Generation command recorded.
- [ ] Test plan `docs/verification/test-plan.md`: levels, environment (OS and runtime versions from the CI matrix), exact commands identical to CI, pass criteria, coverage as a measured value, regression approach, numbered manual or live procedures with last-run commit.
- [ ] Verification matrix `docs/verification/verification-matrix.md`: zero requirements without a row; every referenced test exists at the baseline; I/A rows name what is inspected; "Last result" points to an STR.
- [ ] SCMP `docs/configuration/configuration-management.md`: configuration items, baseline identity (commit or tag), change control (branch protection or merge train), digest tables regenerated at the baseline, release procedure, control of generated outputs.
- [ ] SUM map `docs/guides/SUM-MAP.md`: every SWEHB 5.12 element mapped to a README or guide section that exists. At least one tutorial was run end-to-end at the baseline.
- [ ] Limitations and safety-relevant use page (required for refrigeration and robotics; recommended for host): states that outputs are not engineering or safety approvals and names authoritative sources.
- [ ] Assurance record `docs/assurance/assurance-record.md`: an entry for this baseline with trace check, static analysis and secret scan (command, commit, counts), test analysis, docs-vs-code audit, PR review summary. Each major finding links an issue.

## Per release (when this PR cuts or documents a tag)
- [ ] VDD `docs/releases/VDD-<tag>.md` (or the release body indexed in `docs/releases/README.md`): tag and commit, contents, build instructions, artifact and manifest SHA-256, changes since the previous tag, open issues with workarounds, scan confirmation. Generated, not hand-typed.
- [ ] STR `docs/verification/reports/STR-<tag>.md`: run at the tag commit, environment, per-test results or suite totals with failures listed, deviations, metrics block, run URL or log digest.
- [ ] Release configuration audit entry in the SAR: docs baseline equals the tag, manifests match files, VDD matches artifacts.

## Traceability and accuracy
- [ ] Trace check passes (`tools/check_trace.py`, or the manual steps of §5 recorded in the SAR).
- [ ] Staleness check: `git log <doc baseline>..HEAD -- <derivation paths>` is empty for every control doc, or the doc was updated.
- [ ] Every number in the docs carries its command, commit and machine class, or was removed.
- [ ] No NASA text pasted at length. NASA documents are linked by URL. No standards PDFs committed.
- [ ] Template guidance comments removed. No secrets, local paths or private hosts.
- [ ] Vendored mirrors untouched (host only: docs fixed upstream and re-pinned).

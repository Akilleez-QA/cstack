# Changelog

Format: Keep a Changelog 1.1, SemVer.

## [Unreleased]

### Documentation

- NASA-standard documentation set that new Foundations copy (self-assessed Class E analog, not safety-critical): software management plan, compliance matrix, requirements in record format (REQ-TPL-001 to REQ-TPL-012, untested behaviour as GAP-TPL-001 to GAP-TPL-006), design, interface, data dictionary, test plan, verification matrix, configuration management plan, assurance record, user manual map, tutorial, limitations page and "Start a new Foundation".
- Corrected the interface document: the numeric profile is integers only (no decimal strings).
- Corrected the secret-scanning claim to what CI enforces (gitleaks).
- Problem-report and change-request issue templates replace the bug template; the pull request template records peer review.

### Added

- `tools/check_trace.py`, `tools/gen_docs.py`, `tools/gen_reports.py` and `tests/test_docs_trace.py`, which runs the trace and generated-catalog checks in the suite. Port these to existing Foundations with their documentation.

### Fixed

- Exclude `.github/` automation and repository metadata from the source manifest so CI-only changes do not invalidate source pins.

### Added

- Initial release: Foundation package, stdio bridge, tests, and NASA-style docs under `docs/`.

# Changelog

Format: Keep a Changelog 1.1, SemVer.

## [Unreleased]

### Added

- Initial release: Foundation package, stdio bridge, tests, and NASA-style docs under `docs/`.
- Documentation to the Cstack family standard (organized after NASA NPR 7150.2D and the NASA Software Engineering Handbook; self-assessed Class E analog, not safety-critical): software management plan, compliance matrix, data dictionary, test plan, test report, version description, assurance record, user manual map, tutorial, how-to guides, generated tool catalog and defaults, and explanation pages including limitations.
- Problem-report and change-request issue templates (replacing the bug template) and a peer-review pull request template.

### Changed

- Requirements: added REQ-FILM-014 to 022 for tested behaviour; listed untested behaviour as GAP-FILM-01 to 10.

### Fixed

- Documentation claims that did not match the code: the verification matrix cited the bridge test for four tools' behaviour; the interface document omitted `ping` and mentioned decimal strings that the bridge never accepts; the configuration document and AGENTS.md claimed trufflehog runs before every push.
- Exclude `.github/` automation and repository metadata from the source manifest so CI-only changes do not invalidate source pins.

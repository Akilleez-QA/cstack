# foundation-film verification matrix

| Field | Value |
|---|---|
| Document ID | FFILM-VM |
| Version | 2.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Trace check: performed with an out-of-tree adaptation of foundation-robotics `tools/check_trace.py` (this repository has no trace tool yet; the documentation change was docs-only). Result and command are in the [assurance record](../assurance/assurance-record.md). The check fails on a requirement with no row, a row naming a missing test or path, a `T` row with no test, a test that traces to nothing, an unallocated requirement, or a dead link. A reference `file::Class` covers every test method in that class. Results come from the latest report in [reports/](reports/README.md).

| Requirement | Method | Test (file::Class.method) or inspection target | Acceptance observation / limit | Last result |
|---|---|---|---|---|
| REQ-FILM-001 | T | `tests/test_tools.py::CinematicGateTests` | Parity with filmgate on 60 seeded films; exact default rules; whole film is the default segment; static void fails five rules; uncovered segment not scored | STR (latest) |
| REQ-FILM-002 | T | `tests/test_tools.py::ReferenceBandsTests` | Bands equal the reference weighted percentile on 60 seeded films; moving share within 0.0005; bands feed the gate | STR (latest) |
| REQ-FILM-003 | T | `tests/test_tools.py::AudioGateTests` | A mix inside the contract passes (hit share 813); each of eight breaches names its check | STR (latest) |
| REQ-FILM-004 | T | `tests/test_tools.py::DriftVerdictTests`, `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | First failing frame 2 over the bridge; a late collapse fails although the mean passes | STR (latest) |
| REQ-FILM-005 | T | `tests/test_tools.py::CueVocabularyTests` | Closed vocabulary passes with one alias; invented names, broken aliases, order and gap breaches listed | STR (latest) |
| REQ-FILM-006 | T | `tests/test_tools.py::LookGateTests` | Target passes against itself; a rendered set fails frame by frame; one failing keyframe fails the set | STR (latest) |
| REQ-FILM-007 | T | `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file` | Manifest file map equals a fresh hash of the tree under the same exclusions | STR (latest) |
| REQ-FILM-008 | T, I | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence`, `foundation_film/tools.py` | Test: receipt boundary equals the constant. Inspection: `run` sets `boundary` on every receipt; no tool module writes files, opens sockets or starts processes | STR (latest); inspection in SAR 2026-11-08 |
| REQ-FILM-009 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence`, `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence` | Evidence present on a verdict and on refusals for all six tools | STR (latest) |
| REQ-FILM-010 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | `input_sha256` equals `input_sha256(arguments)` on a success receipt (error path: GAP-FILM-06) | STR (latest) |
| REQ-FILM-011 | I, T | `foundation_film_bridge/server.py`, `foundation_film/tools.py`, `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed`, `tests/test_filmstats.py::FilmstatsBoundaryTests.test_imports_without_optional_dependencies` | Test: `--root /` gives exit 2; tools and producer import with `-S` (no site packages). Inspection: tool modules import only the standard library; the producer imports NumPy, OpenCV and PySceneDetect inside functions | STR (latest); inspection in SAR 2026-11-08 |
| REQ-FILM-012 | T | `tests/test_requirement_limits.py::RequirementLimitsTests` | Each limit accepted at the limit and rejected one past it with `-32002`; an oversized stream line ends the session with status 2 | STR (latest) |
| REQ-FILM-013 | T | `tests/test_filmstats.py::FilmstatsBoundaryTests.test_milli_rounding`, `tests/test_filmstats.py::FilmstatsVisionTests` | Half-up milli rounding; NaN and infinity refused; uniform frame metrics; pan versus still; a two-shot video through the CLI gives shots 0–3000 and 3000–6000 ms; bad sampling refused. The vision class is skipped without the optional dependencies (CI skips it) | STR (latest) states whether it ran |
| REQ-FILM-014 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | Protocol string echoed; `mcpCompatible` false | STR (latest) |
| REQ-FILM-015 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | Catalog equals `tool_definitions()`; names in `TOOL_NAMES` order | STR (latest) |
| REQ-FILM-016 | T | `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence`, `tests/test_tools.py::CinematicGateTests.test_malformed_films_are_refused`, `tests/test_tools.py::AudioGateTests.test_unmeasured_is_not_scored_and_overrides_are_reported`, `tests/test_tools.py::DriftVerdictTests.test_optional_metrics_need_thresholds_and_nulls_are_not_scored`, `tests/test_tools.py::CueVocabularyTests.test_ambiguous_or_malformed_vocabularies_are_refused`, `tests/test_tools.py::LookGateTests.test_caller_thresholds_are_reported_and_malformed_requests_refused` | `isError` true, assessment `tool_error`, status `error`, result null, evidence present | STR (latest) |
| REQ-FILM-017 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | `tools/call` before `initialize` gives `-32000`; `read_file` gives `-32602` | STR (latest) |
| REQ-FILM-018 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | Duplicate key, `1.5` and `NaN` give `-32700` | STR (latest) |
| REQ-FILM-019 | T | `tests/test_tools.py::CinematicGateTests.test_a_static_void_fails_and_an_uncovered_segment_is_not_scored`, `tests/test_tools.py::AudioGateTests.test_unmeasured_is_not_scored_and_overrides_are_reported`, `tests/test_tools.py::LookGateTests.test_one_failing_keyframe_fails_the_set_and_nulls_are_not_scored`, `tests/test_tools.py::AudioGateTests.test_a_mix_inside_the_contract_meets_it` | Unmeasured gives `not_scored`; a failing check gives `thresholds_not_met`; all-pass gives `thresholds_met` | STR (latest) |
| REQ-FILM-020 | T | `tests/test_tools.py::CinematicGateTests.test_a_static_void_fails_and_an_uncovered_segment_is_not_scored`, `tests/test_tools.py::AudioGateTests.test_unmeasured_is_not_scored_and_overrides_are_reported`, `tests/test_tools.py::LookGateTests.test_caller_thresholds_are_reported_and_malformed_requests_refused` | `rule_source` `caller`; `contract_overrides` lists `forbidden_heard`; `threshold_sources.palette_ab` `caller` and a `caller` Evidence entry | STR (latest) |
| REQ-FILM-021 | T | `tests/test_tools.py::CinematicGateTests.test_parity_with_filmgate_on_random_films`, `tests/test_tools.py::ReferenceBandsTests.test_parity_with_the_weighted_percentile_used_for_the_reference_bands`, `tests/test_tools.py::DriftVerdictTests.test_parity_with_driftgate_every_frame_rule`, `tests/test_tools.py::LookGateTests.test_parity_with_lookgate_on_random_frames` | 60, 60, 60 and 200 seeded trials agree with the reference rules | STR (latest) |
| REQ-FILM-022 | T | `tests/test_requirement_limits.py::RequirementLimitsTests.test_req_film_012_stream_frame_limit` | Two `ping` requests without `initialize` each return `{}` | STR (latest) |

## Tests without a requirement

None. Every test method traces to at least one requirement.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 5c37f74 | Initial matrix | Initial commit |
| 1.1 | 2026-10-30 | 9725403 | Inspection-only rows marked I | PR #4 |
| 1.2 | 2026-11-01 | e6e6405 | REQ-FILM-012 and 013 rows with named tests | PR #5 |
| 2.0 | 2026-11-08 | 852f976 | Family standard. Method-level references. REQ-FILM-002, 003, 005 and 006 no longer cite `tests/test_bridge.py` for their behaviour (the bridge test only refuses their bad arguments; that is REQ-FILM-016). Rows for REQ-FILM-014 to 022. "pass at baseline" replaced by pointers to the generated STR | docs/nasa-standard PR |

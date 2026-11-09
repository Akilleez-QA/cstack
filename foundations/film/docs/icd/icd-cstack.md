# foundation-film Cstack stdio interface control document

| Field | Value |
|---|---|
| Document ID | FFILM-ICD-CSTACK |
| Version | 2.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Interfacing entities and ownership

| Side | Entity | Owns |
|---|---|---|
| Provider | foundation-film, package `foundation_film_bridge` | Protocol string, limits, tool schemas, result meaning, `SOURCE-MANIFEST.json` |
| Consumer | Cstack host adapter for this Foundation | Process start, wall-clock timeouts, pin verification, output-schema re-validation, effect grant (`read` only) |

## 2. Interface type and transport

- Child process started with `python -B -m foundation_film_bridge`, fixed working directory (the repository root), minimal fixed environment, no shell, no arguments. Any argument makes it print a refusal to stderr and exit with status 2.
- stdin and stdout carry JSON-RPC 2.0, one UTF-8 JSON object per line, terminated by `\n`. No batches.
- Strictly sequential: one reply per request with an `id`, in order. Messages without `id` (notifications) get no reply and are not executed.
- Exit status: 0 at end of input; 2 after an oversized or unterminated line, on a broken pipe or OS error, or when arguments are given.
- Responses are compact, sorted-key, ASCII-only JSON.

## 3. Messages and data elements

| Method | Params | Before `initialize` | Result |
|---|---|---|---|
| `initialize` | exactly `{"protocolVersion": "foundation-film-jsonrpc/1"}` | allowed once | `protocolVersion`, `mcpCompatible: false`, `limits`, `serverInfo` (`foundation-film-jsonrpc-bridge`, version `0.1.0`), `capabilities: {"tools": true}`, `numericProfile`, `methods` |
| `ping` | `{}` or absent | allowed | `{}` |
| `tools/list` | `{}` or absent | `-32000` | `{"tools": [...]}`: name, description, `inputSchema`, `outputSchema` per tool |
| `tools/call` | exactly `{"name", "arguments"}`; `arguments` an object | `-32000` | `{"isError": bool, "structuredContent": {tool, assessment, formal_proof: false, runtime_goal_acceptance: false, receipt}}` |

Tools, in catalog order: `cinematic_gate`, `reference_bands`, `audio_gate`, `drift_verdict`, `cue_vocabulary_check`, `look_gate`. Every field of every tool's input and result, with type and range, is in the generated [tool catalog](../guides/reference/tool-catalog.md) (generated from `foundation_film_bridge/schemas.py`). Times are integer milliseconds (`_ms`, at most 86400000). Measures are milli-units: a producer value of 1.234 crosses the wire as 1234; loudness in milli-LUFS, levels in milli-dB, shares and WER in per-mille.

Receipt (from `foundation_film/tools.py`): `tool`, `version`, `status` (`ok` or `error`), `input_sha256` (SHA-256 of `json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`), `boundary` (`observation_only: true`, `acceptance_decision: false`, `control_action: false`), `result` (null on error), `error` (null or at most 1024 characters), `evidence` (1 to 16 entries, each with `applies_to` and `basis.kind` `cited`, `derived` or `caller`, and `status` `CHECK` or `RECORDED`).

Assessments: `reference_bands` returns `bands_measured`; the five judged tools return `thresholds_met`, `thresholds_not_met` or `not_scored`; any tool returns `tool_error` when it refuses its arguments.

## 4. Errors and result semantics

| Condition | Response | Caller action | Test |
|---|---|---|---|
| Duplicate keys, a float, `NaN`/`Infinity`, invalid UTF-8 or JSON | `-32700`, `id: null` | Fix the encoder | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` (duplicate, float, NaN) |
| Frame over 65536 bytes, nesting over 32, over 16384 nodes, string over 1024 chars, integer over 15 digits | `-32002`, `id: null` | Split or shrink the request | `tests/test_requirement_limits.py::RequirementLimitsTests.test_req_film_012_input_limits` (each limit, at and one past) |
| Line over 65537 bytes or without newline | `-32002`, then exit 2 | Restart the bridge | `tests/test_requirement_limits.py::RequirementLimitsTests.test_req_film_012_stream_frame_limit` (oversized line) |
| Not an object, extra envelope field, wrong `jsonrpc`, empty method, `null` or over-long id | `-32600`, `id: null` | Fix the envelope | none (GAP-FILM-04) |
| Unknown method | `-32601` | — | none (GAP-FILM-04) |
| Wrong params fields, unknown tool, non-object `arguments` | `-32602` | — | unknown tool: `test_wire_profile_fails_closed` |
| `tools/*` before `initialize`, or a second `initialize` | `-32000` | Initialize once | before-init: `test_wire_profile_fails_closed`; second init: none (GAP-FILM-02) |
| Wrong `protocolVersion` | `-32001` | Use `foundation-film-jsonrpc/1` | none (GAP-FILM-02) |
| Unexpected exception | `-32603`, no result | Report a problem | none (GAP-FILM-05) |
| Response over 1048576 bytes | `-32002` "Result withheld" | Send fewer frames | none (GAP-FILM-01) |
| Arguments refused by the tool | Success envelope, `isError: true`, assessment `tool_error`, receipt `status: error`, Evidence present | Read `receipt.error` | `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence` |

The input schemas are necessary, not sufficient: some rules (for example shots in time order without overlap, every shot carrying the same metric names, `cuts_with_hit` not above `cuts`) are enforced only in code and surface as `tool_error`.

## 5. Identity, versioning and compatibility

| Item | How to obtain | Checked by |
|---|---|---|
| Manifest SHA-256 and file count | `python -B tools/build_manifest.py` prints `files` and `sha256` | `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file`; CI `manifest` job (`git diff --exit-code SOURCE-MANIFEST.json`) |
| Canonical tool inventory SHA-256 | Same command, `inventory_sha256`; `--inventory` prints the canonical bytes | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` (catalog equals `tool_definitions()`) |
| Protocol | `foundation-film-jsonrpc/1` in `initialize` | REQ-FILM-014 test |
| Version | `0.1.0` in `SOURCE-MANIFEST.json`, `serverInfo.version` and each receipt | — |

Current values are in the latest [version description](../releases/README.md). A change to any shipped file outside the root `.github/` tree changes the manifest SHA-256; a change to a schema or description also changes the inventory SHA-256. Either is a new pin for the consumer.

## 6. Security and input bounds

- The provider accepts no options and reads no files. Two optional environment variables, `FOUNDATION_FILM_PLAYBOOK` and `FOUNDATION_FILM_PRODUCERS`, change only the citation text in Evidence; the consumer's minimal fixed environment normally leaves them unset. No network, subprocess or file write.
- Wire limits (also returned by `initialize`): input frame 65536 bytes, output frame 1048576 bytes, depth 32, nodes 16384, string 1024 characters, integer 15 digits, id 128 characters.
- Numeric profile: bounded integers only. Floats and non-finite constants are rejected while parsing.
- Every tool validates its own arguments field by field (`foundation_film/measures.py`) and refuses unknown fields.
- The consumer grants only the `read` effect and re-verifies the pins before dispatch and after every accepted response.

## 7. Requirements addressed

| Requirement | Section |
|---|---|
| REQ-FILM-007 | §5 |
| REQ-FILM-008, REQ-FILM-009, REQ-FILM-010 | §3 |
| REQ-FILM-011 | §2, §6 |
| REQ-FILM-012, REQ-FILM-018 | §4, §6 |
| REQ-FILM-013 | §9 |
| REQ-FILM-014, REQ-FILM-015, REQ-FILM-022 | §3, §5 |
| REQ-FILM-016, REQ-FILM-017 | §3, §4 |

## 8. Change acceptance

A change to this interface needs the full suite passing in both modes, a regenerated `SOURCE-MANIFEST.json` and tool catalog, and an updated CHANGELOG entry. Producer changes also need the full-dependency test run from the README. The consumer repins in the same change that updates its vendored copy. Owner approval is required for a tag.

## 9. Offline measurement interface

`python -B -m foundation_film.filmstats VIDEO [--fps 8] [--width 640]` prints one JSON object, `{"shots": [...]}`, on stdout. It needs NumPy, OpenCV and PySceneDetect (see the README command). Each shot has `start_ms`, `end_ms`, `camera` (`static`, `pan`, `tilt` or `push/pull`) and `metrics` (milli-unit integers, validated by `cinema.shots`). Seconds and floating measurements become milliseconds and milli-units, rounded half away from zero. The output can be passed as `reference_bands` arguments, or extended with `bands` or `rules` for `cinematic_gate`.

The producer is a local command line program outside JSON-RPC. It takes a path, emits no receipt and is not pinned behaviour of the bridge. It rejects `--fps` that is not positive and finite, `--width` below 6, an incomplete decode and a shot with no sampled frames. It does not emit Endoforge's summary, audio, palette or contact-strip files.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 5c37f74 | Sides, transport, methods, rules | Initial commit |
| 1.1 | 2026-11-01 | e6e6405 | Offline measurement interface | PR #5 |
| 1.2 | 2026-11-04 | 42a5e27 | Pin rule excludes the root `.github/` tree | PR #11 |
| 2.0 | 2026-11-08 | 852f976 | Family standard. Added `ping` (missing from the method list). Corrected the numeric rule: floats are rejected for every message while parsing, and no decimal strings are used (the old text said "bounded decimal strings"). Error table with tests and gaps, identity table, security bounds, requirements trace | docs/nasa-standard PR |

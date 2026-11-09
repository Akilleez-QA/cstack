# foundation-template data dictionary

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-DD |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

The per-argument tool tables are generated into the [tool catalog](../guides/reference/tool-catalog.md) by `python -B tools/gen_docs.py`; `tests/test_docs_trace.py` fails when it is stale. This document defines everything else a reader or a copy needs.

Not applicable: channelization, rate-group, raw or calibrated sensor, telemetry, data-recorder and partitioning data. The software has no hardware or telemetry interfaces.

## 1. Tools

| Name | Purpose | Parameters | Result | Restrictions | Source |
|---|---|---|---|---|---|
| `echo_observation` | Placeholder: echo the caller's own text as an observation | `observation` | `{observation}` | String, 1 to 256 characters; no other argument | `foundation_template/tools.py` |

## 2. Data elements

| Name | Type | Units | Range / limits | Default | Meaning | Defined in |
|---|---|---|---|---|---|---|
| `observation` | string | none | 1–256 characters | none | Caller text echoed back | `tools.MAX_OBSERVATION_CHARS` |
| Boundary | object | — | `observation_only: true`, `domain_determination: false`, `control_action: false` | fixed | What a result is not | `tools.BOUNDARY` |
| Evidence entry | object | — | `applies_to` (text), `evidence.basis` `{kind: "practice", note}`, `evidence.status` `CHECK` | — | Where a value came from; the template only uses the `practice` basis | `tools.evidence` |
| Request id | string or integer | — | string ≤ 128 characters, or integer of at most 15 digits | none | JSON-RPC id echoed in the response | `server.Bridge.dispatch` |

## 3. Records and files

Receipt (inside every `tools/call` result):

| Field | Success | Error |
|---|---|---|
| `tool` | tool name | same |
| `version` | `0.1.0` | same |
| `status` | `ok` | `error` |
| `input_sha256` | SHA-256 of the arguments (sorted keys, compact, ASCII) | same |
| `boundary` | fixed boundary object | same |
| `result` | tool result object | `null` |
| `error` | `null` | message string (see the tool catalog) |
| `evidence` | 1–16 entries | one entry: the argument check |

| Record / file | Format | Schema | Producer | Consumer | Retention |
|---|---|---|---|---|---|
| JSON-RPC lines | UTF-8 in, ASCII out, one per line | JSON-RPC 2.0, `foundation-template-jsonrpc/1` | Host / bridge | Bridge / host | Not stored |
| `SOURCE-MANIFEST.json` | JSON, sorted keys, indent 2 | `foundation-template-source-manifest/1`: `schema`, `version`, `files` (path → SHA-256) | `tools/build_manifest.py` | Host pin; `tests/test_bridge.py` | Committed |

## 4. Reference data provenance

The template embeds no reference data. A copy that embeds a table (constants, limits, generated tables) adds a row per table here, and keeps the data in JSON rather than in Python source:

| Table | Source (edition/date) | Units | Transformation | Validation test |
|---|---|---|---|---|
| — (none in the template) | — | — | — | — |

foundation-refrigeration is the worked example: every table there records its source, edition, units, transformation and validating test, and a generator writes the full provenance page from the data files.

## 5. Configuration keys

None. The bridge reads no configuration file, environment variable or option.

## 6. Operational limits

| Limit | Value | Enforced in | Test |
|---|---|---|---|
| Input frame | 65 536 bytes | `server.decode_frame`, `server.serve` | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_frame_bytes` |
| Output frame | 1 048 576 bytes | `server.encode_response` | none (GAP-TPL-002) |
| JSON depth / nodes / string | 32 / 4096 / 1024 characters | `server.decode_frame` | `tests/test_input_limits.py` |
| Integer digits | 15 | `server._integer` | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_integer_digits` |
| Request id string | 128 characters | `server.Bridge.dispatch` | none (GAP-TPL-004) |
| Evidence entries per receipt | 1–16 (schema) | `schemas.output` | `tests/test_bridge.py` (non-empty only) |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | fb9993c | Initial baseline | PR adding the NASA-standard documentation set |

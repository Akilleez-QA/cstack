# foundation-refrigeration Cstack interface control document

| Field | Value |
|---|---|
| Document ID | FREFRIG-ICD-CSTACK |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

This document covers the two external interfaces: the stdio JSON-RPC bridge that Cstack drives (§1–§8) and the local Python invariant API (§9).

## 1. Interfacing entities and ownership

| Side | Entity | Owns |
|---|---|---|
| Provider | foundation-refrigeration, package `foundation_refrigeration_bridge` | Protocol, tool inventory and schemas, receipts, input limits, source manifest |
| Consumer | Cstack host adapter `adapters/refrigeration_stdio.py` (in the Cstack repository) | Process start, pins (manifest SHA-256, file count, inventory SHA-256), output-schema validation, grants, approval |

## 2. Interface type and transport

| Item | Value |
|---|---|
| Type | Child process, stdio, JSON-RPC 2.0, one message per line, explicitly not MCP |
| Start command | `python -B -m foundation_refrigeration_bridge` from the repository root, no arguments, no shell |
| Protocol identifier | `foundation-refrigeration-jsonrpc/1` |
| Methods | `initialize`, `ping`, `tools/list`, `tools/call` |
| Request framing | UTF-8 JSON object followed by `\n`; at most 65 536 bytes before the newline |
| Response framing | ASCII JSON, sorted keys, compact separators, followed by `\n`; at most 1 048 576 bytes |
| Ordering | Sequential. One response per request with an `id`, in request order. No batches, notifications get no response, no cancellation |
| Session | `initialize` once, then any number of `tools/list` and `tools/call`. Close stdin to stop |
| Stop | Exit 0 at end of input; exit 2 after an oversized frame, a final frame without newline, a broken pipe, or any command-line argument |

`initialize` takes exactly `{"protocolVersion": "foundation-refrigeration-jsonrpc/1"}` and returns `protocolVersion`, `serverInfo` (`name`, `version`), `capabilities`, `mcpCompatible: false`, `limits`, `numericProfile`, `methods` and `execution`. The [first-session tutorial](../guides/tutorials/first-bridge-session.md) shows a real exchange.

## 3. Messages and data elements

The tool arguments are generated from `foundation_refrigeration_bridge/schemas.py` into the [tool catalog](../guides/reference/tool-catalog.md) by `python -B tools/gen_docs.py`. Each `tools/call` takes exactly `name` and `arguments`. Each result is:

| Field | Type | Meaning |
|---|---|---|
| `result.isError` | boolean | `true` for a tool error |
| `result.structuredContent.tool` | string | Tool name |
| `result.structuredContent.assessment` | string | One of the tool's assessments, or `tool_error` |
| `result.structuredContent.formal_proof` | `false` | Always false |
| `result.structuredContent.runtime_goal_acceptance` | `false` | Always false |
| `result.structuredContent.receipt` | object | Receipt `foundation-refrigeration-receipt/1`; fields in the [data dictionary](../data/data-dictionary.md#3-records-and-files) |

Numbers on the wire must be integers of at most 15 digits or finite decimal literals with a fractional part (`-?(0|[1-9][0-9]*)\.[0-9]+`, at most 24 characters). Exponents, NaN and Infinity are refused. Every physical value is a `{value, unit}` object.

## 4. Errors and result semantics

| Condition | Response | Caller action | Test |
|---|---|---|---|
| Bad frame (size, depth, nodes, string, number, duplicate key, UTF-8) | JSON-RPC error `-32700` or `-32002`, `id: null` | Fix the request | `tests/test_bridge.py::TransportTests.test_numeric_profile_and_duplicate_keys` |
| Oversized line or missing final newline | Error, then exit 2 | Restart the bridge | `tests/test_bridge.py::TransportTests.test_serve_round_trip_and_oversized_frame` |
| Call before `initialize`; second `initialize` | `-32000` | Initialize once | `tests/test_bridge.py::InventoryTests.test_handshake_and_ordering` |
| Wrong protocol version | `-32001` | Use `foundation-refrigeration-jsonrpc/1` | `tests/test_bridge.py::InventoryTests.test_handshake_and_ordering` |
| Unknown method; unknown tool | `-32601`; `-32602` | Use a listed method or tool | `tests/test_bridge.py::InventoryTests.test_handshake_and_ordering` |
| Bad envelope or id | `-32600` | Fix the envelope | none (GAP-REF-003) |
| Tool argument, unit, range or fluid problem | Result with `isError: true`, assessment `tool_error`, `receipt.error.code`, empty Evidence | Treat as no result | `tests/test_bridge.py::ReceiptTests.test_tool_errors_are_errors_not_results` |
| Internal error; unencodable or oversized result | `-32603` or `-32002`; no receipt | Report a problem | none (GAP-REF-001, GAP-REF-002) |

The full code list is in the [tool catalog](../guides/reference/tool-catalog.md#json-rpc-error-codes). A success result is an observation, never an acceptance, approval or determination.

## 5. Identity, versioning and compatibility

The consumer pins three values:

| Pin | Produced by |
|---|---|
| Manifest SHA-256 | `python -B tools/build_manifest.py` prints `{"files": <count>, "sha256": <digest>}` |
| Manifest file count | Same output |
| Canonical tool inventory SHA-256 | SHA-256 of `json.dumps(tool_definitions(), ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))`; printed in the [tool catalog](../guides/reference/tool-catalog.md) |

`tools/build_manifest.py` does not print the inventory digest (the foundation-template generator does); the value comes from the tool catalog or the [version description](../releases/README.md). Current values for main are in the latest generated version description.

Versions: `foundation_refrigeration.__version__`, `schemas.VERSION` and the manifest `version` field are all `0.1.0`. Breaking changes are: any change to the protocol identifier, method set, tool names or order, input or output schemas, receipt schema, or limits. Any change to a covered file changes the manifest pin. The consumer repins in the same change that updates its vendored copy. `tests/test_bridge.py::InventoryTests.test_fixed_seven_tool_inventory` and `tests/test_names_and_manifest.py::ManifestTests.test_source_manifest_is_exact` guard the provider side.

## 6. Security and input bounds

- Limits are listed in the [tool catalog](../guides/reference/tool-catalog.md#bridge-limits) and enforced before any tool runs (REQ-REF-013).
- Closed schemas: every object refuses unknown fields, both in the published schemas and in the tool code.
- The bridge takes no options or paths, opens no network connection and writes nothing but stdout and stderr (REQ-REF-012).
- The consumer grants only the `read` effect. No tool changes state outside the process.
- Report vulnerabilities as described in [SECURITY.md](../../SECURITY.md).

## 7. Requirements addressed

| Requirement | Section |
|---|---|
| REQ-REF-008 | §5 |
| REQ-REF-009, REQ-REF-010, REQ-REF-011 | §3, §4 |
| REQ-REF-012, REQ-REF-013 | §2, §6 |
| REQ-REF-017, REQ-REF-035 | §2, §4 |
| REQ-REF-018 | §5 |
| REQ-REF-014, REQ-REF-015, REQ-REF-016 | §9 |

## 8. Change acceptance

A change to this interface needs: an issue (change request), the full test suite passing in both normal and optimized mode, updated schemas and a regenerated tool catalog, a regenerated `SOURCE-MANIFEST.json`, and a matching Cstack change that repins the manifest SHA-256, file count and inventory SHA-256 and updates its vendored copy. Cstack's vendored copy is a byte-pinned mirror; fix documentation here and repin there.

## 9. Python invariant interface

`foundation_refrigeration.invariants.evaluate(check, claim)` is a standard-library-only local Python API. It is separate from JSON-RPC and does not use bridge receipts or decimal-string schemas. Quantity objects have exactly `value` (finite int or float, excluding bool, magnitude at most 1e9) and `unit` (a supported domain pressure or temperature unit). Claims have exactly these fields:

| Check | Claim fields | Canonical comparison |
|---|---|---|
| `pressure_relation` | `left`, `right`, `relation`, `atmosphere` | kPa(a), tolerance 1e-6 |
| `temperature_relation` | `left`, `right`, `relation` | degC, tolerance 1e-6 |
| `saturation_temperature` | `fluid`, `side`, `pressure`, `temperature`, `atmosphere` | degC, table error plus 0.001 K |

Relations are `eq`, `lt`, `gt`; strict ordering must exceed the tolerance. Atmosphere may be null for absolute pressure, but gauge quantities require an explicit `standard`, `elevation` or `measured` basis using the domain unit API's atmosphere object. Blend `side` must be `bubble` or `dew`; pure fluids also accept null. Absolute pressures must be positive and temperatures above absolute zero. Unsupported fluids and out-of-table pressures fail.

Results contain `check`, `passed`, `reason`, `library_version` and, on success, `measurements`. Unknown checks and invalid claims return `passed: false` with a reason; `evaluate` does not raise for them. Pressure measurements include atmosphere evidence; saturation measurements include table provenance and evidence. `library_version` is `refrigeration-invariants/0:` plus the SHA-256 of canonical JSON source hashes (sorted keys, compact separators). `SOURCE_HASHES` maps package-relative Python and data JSON paths to SHA-256 values captured at import. Restart consumers after source or data changes. These results are observations and do not authorize plant actions or establish compliance.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 9b459ef | Bridge interface summary | Initial commit |
| 1.1 | 2026-11-01 | 4bd3311 | Python invariant interface | PR #3 |
| 1.2 | 2026-11-04 | f51290c | Manifest excludes the root `.github/` tree | PR #9 |
| 2.0 | 2026-11-08 | 62764c7 | NASA-standard structure; transport, error, identity and security sections; corrected the claim that `build_manifest.py` prints the inventory digest; added `ping` | PR adding the NASA-standard documentation set |

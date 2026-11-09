# foundation-template Cstack interface control document

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-ICD-CSTACK |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

This document covers the one external interface: the stdio JSON-RPC bridge a host drives. Every Foundation copied from this template has an interface of this shape; a copy renames the protocol and module and replaces the tool tables.

## 1. Interfacing entities and ownership

| Side | Entity | Owns |
|---|---|---|
| Provider | foundation-template, package `foundation_template_bridge` | Protocol, tool inventory and schemas, receipts, input limits, source manifest |
| Consumer | Cstack host adapter `adapters/template_stdio.py` (in the Cstack repository); each copied Foundation gets its own adapter | Process start, pins (manifest SHA-256, file count, inventory SHA-256), output-schema validation, grants, approval |

## 2. Interface type and transport

| Item | Value |
|---|---|
| Type | Child process, stdio, JSON-RPC 2.0, one message per line, explicitly not MCP |
| Start command | `python -B -m foundation_template_bridge` from the repository root, no arguments, no shell |
| Protocol identifier | `foundation-template-jsonrpc/1` |
| Methods | `initialize`, `ping`, `tools/list`, `tools/call` |
| Request framing | UTF-8 JSON object followed by `\n`; at most 65 536 bytes before the newline |
| Response framing | ASCII JSON, sorted keys, compact separators, followed by `\n`; at most 1 048 576 bytes |
| Ordering | Sequential, one response per request with an `id`, in order. No batches; requests without `id` get no response; no cancellation |
| Stop | Exit 0 at end of input; exit 2 after an oversized or unterminated frame, a broken pipe, or any command-line argument |

`initialize` takes exactly `{"protocolVersion": "foundation-template-jsonrpc/1"}` and returns `protocolVersion`, `mcpCompatible: false`, `limits`, `serverInfo` (`name`, `version`), `capabilities`, `numericProfile` (`bounded integers only`) and `methods`. The [first-session tutorial](../guides/tutorials/first-bridge-session.md) shows a real exchange.

## 3. Messages and data elements

Tool arguments are generated from `foundation_template_bridge/schemas.py` into the [tool catalog](../guides/reference/tool-catalog.md) by `python -B tools/gen_docs.py`. Each `tools/call` takes exactly `name` and `arguments` and returns:

| Field | Type | Meaning |
|---|---|---|
| `result.isError` | boolean | `true` for a tool error |
| `result.structuredContent.tool` | string | Tool name |
| `result.structuredContent.assessment` | string | The tool's assessment, or `tool_error` |
| `result.structuredContent.formal_proof` | `false` | Always false |
| `result.structuredContent.runtime_goal_acceptance` | `false` | Always false |
| `result.structuredContent.receipt` | object | Fields in the [data dictionary](../data/data-dictionary.md#3-records-and-files) |

Numbers on the wire must be integers of at most 15 digits. Any fraction, exponent, NaN or Infinity is refused.

## 4. Errors and result semantics

| Condition | Response | Caller action | Test |
|---|---|---|---|
| Frame over a limit | `-32002` | Fix the request | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_frame_bytes` |
| Non-integer number, NaN, duplicate key, bad UTF-8 | `-32700` | Fix the request | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` |
| Oversized line | Error, then exit 2 | Restart the bridge | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_stream_frame_bytes` |
| `tools/call` before `initialize` | `-32000` | Initialize once | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` |
| Unknown tool | `-32602` | Use a listed tool | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` |
| Wrong protocol; second `initialize`; bad envelope or id | `-32001`; `-32000`; `-32600` | Fix the request | none (GAP-TPL-001, GAP-TPL-004) |
| Bad tool arguments | Result with `isError: true`, assessment `tool_error`, `receipt.error` message, one Evidence entry | Treat as no result | `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence` |
| Internal error; oversized result | `-32603`; "Result withheld" | Report a problem | none (GAP-TPL-002, GAP-TPL-003) |

## 5. Identity, versioning and compatibility

`python -B tools/build_manifest.py` prints the three pins: `{"files": <count>, "sha256": <manifest SHA-256>, "inventory_sha256": <SHA-256 of the canonical inventory>}`. The canonical inventory is `json.dumps(tool_definitions(), ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))`; `--inventory` prints it. Current values for main are in the latest [version description](../releases/README.md).

Versions: `foundation_template.__version__` and the manifest `version` field are both `0.1.0`. Breaking changes: the protocol identifier, the method set, tool names or order, input or output schemas, the receipt shape, or the limits. Any change to a covered file changes the manifest pin; the consumer repins in the same change that updates its vendored copy.

## 6. Security and input bounds

- Limits are in the [tool catalog](../guides/reference/tool-catalog.md#bridge-limits) and are enforced before any tool runs (REQ-TPL-007).
- Every object in the schemas and the tool code refuses unknown fields.
- No options, paths, network or file access (REQ-TPL-006). The consumer grants only the `read` effect.
- Report vulnerabilities as described in [SECURITY.md](../../SECURITY.md).

## 7. Requirements addressed

| Requirement | Section |
|---|---|
| REQ-TPL-002, REQ-TPL-009 | §5 |
| REQ-TPL-003, REQ-TPL-004, REQ-TPL-005 | §3, §4 |
| REQ-TPL-006, REQ-TPL-007, REQ-TPL-010 | §2, §3, §6 |
| REQ-TPL-008, REQ-TPL-011 | §2, §4 |

## 8. Change acceptance

A change to this interface needs a change request, both test modes passing, updated schemas and a regenerated tool catalog, a regenerated `SOURCE-MANIFEST.json`, and a matching host change that repins the three values. Cstack's vendored copy is a byte-pinned mirror: fix documentation here and repin there.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | fbfaadb | Bridge interface summary | Initial commit |
| 1.1 | 2026-11-03 | ab81203 | Manifest excludes the root `.github/` tree | PR #10 |
| 2.0 | 2026-11-08 | fb9993c | NASA-standard structure; corrected the numeric rule (integers only; no decimal strings); added `ping`, errors, identity and security | PR adding the NASA-standard documentation set |

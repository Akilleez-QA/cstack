# Cstack–Foundations interface control document

Baseline: Cstack `7a29c95aec2c39c139ec42fe2aa5fc3db16dd034`. Status: proposed documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

## Interface ownership and applicability

Cstack owns host composition, grants, adapters and evidence interpretation. Each Foundation owns its bridge implementation and tool contracts. The controlled Math source is `vendor/foundation-math-v014/`; `foundations/math/` is a research consumer. Changes on either side require review of both admission and result interpretation.

Foundation Engine has no active runtime interface here. It is linked in `NOTICE.md`, used as a design reference in vendored Math provenance, and named as unimplemented in `extensions/foundation_math.py`. No engine protocol, source pin or compatibility promise is allocated by this ICD. A future integration needs its own approved contract and tests.

## Semantic side

The core exchanges `CapabilityRequest` and outcome structures defined by `poodo_core/models.py` and `contracts/capability-request.schema.json` / `contracts/capability-result.schema.json`. The Math capability identifier is `foundation_math`; its extension lists the permitted operations in `TOOL_NAMES`. The inventory is `schemas/math-v014-tools.json`. Admission to a tool does not establish the caller's assumptions.

The host chooses a registered domain, source root and fixed module. Requests cannot supply commands, roots or grants. All registered Foundation capabilities attach on ToolFace and startup checks compare grants against `contracts/ADAPTERS.json`.

## Math transport

| Property | Controlled value / rule |
|---|---|
| Adapter | `adapters/math_stdio.py`, `MathStdioCapability` |
| Child module | `foundation_math_bridge` |
| Protocol identifier | `foundation-math-jsonrpc/1` |
| Encoding/framing | JSON objects over stdio; newline terminated frames |
| Envelope | `jsonrpc: "2.0"`, correlated `id`, `method`, `params` |
| Initialization | `initialize`, `protocolVersion`; accepted reply requires `mcpCompatible: false` |
| Discovery | `tools/list`; exact pinned catalog |
| Invocation | `tools/call`; `name` and `arguments` |
| Request frame cap | 65,536 bytes |
| Response frame cap | 1,048,576 bytes |
| Executor stderr cap | 16,384 bytes |
| Default deadline | 15 seconds; host constructor admits greater than zero through 60 seconds |

Each adapter exchange sends initialization and one request. It requires two complete newline-terminated replies, exact response identities and an admitted result or error envelope. This bridge is explicitly not MCP; the separate Cstack MCP adapters do not change that protocol.

Math wire decoding rejects duplicate keys, floats and invalid JSON numeric profiles. The output budget differs from the input budget so exact results and the catalog can exceed request limits. See `adapters/wire.py` for additional depth, node, string and integer limits; callers shall not infer unrestricted JSON acceptance.

## Identity and compatibility controls

The Math source manifest SHA-256 is `23219ba772c84796c007eee75458afc499b6ac257b154e78cf3068e41bfdb9a2`. `PinnedMathSource` verifies its 561 listed files. The canonical tool inventory SHA-256 is `7df9574ee6788e55bb51aec8ebf858e958c252808ec3f4c217e43f598c961ba9`, computed using `adapters.wire.encode`, not raw schema-file bytes.

The adapter compares source bytes before dispatch and after completed exchanges, and checks the live catalog against its local pinned copy. These checks bind listed bytes and observed catalog data; they do not authenticate authors or prove the running process is trustworthy.

## Result and failure semantics

A tool result has `isError` and `structuredContent`; Math admission validates the exact pinned output schema, tool identity, receipt object, assessment consistency, `formal_proof: false` and `runtime_goal_acceptance: false`. The original receipt is preserved. A completed execution can report a false polynomial identity; completion is not predicate truth.

Unknown operations or requests for formal proof are unavailable without dispatch. Invalid input can be resource-rejected before dispatch; malformed responses are protocol errors after dispatch. Source identity failure withholds admission. Cancellation, deadline and process failures carry execution certainty separately from status. No accepted partial result and no automatic retry are promised.

## Sibling domain interfaces

Template, Refrigeration, Robotics and Film adapters use `BridgeProfile` and `PinnedStdioCapability` in `adapters/foundation_stdio.py`. Their specific adapters bind protocol, module, numeric decoder, manifest/file count, catalog and receipt boundary. The shared adapter also checks the receipt input digest against canonical arguments. Math retains its own adapter and shall not be described as inheriting that shared implementation.

Sibling pins live in `adapters/template_stdio.py`, `adapters/refrigeration_stdio.py`, `adapters/robotics_stdio.py` and `adapters/film_stdio.py`; sources and manifest builders live under their respective `foundations/` directories. Changes require matched source, inventory, schema and conformance review.

## Interface change acceptance

Record old/new manifests, catalog identities, operation/schema differences and changed evidence semantics. Run adapter and domain conformance suites plus the root suite against the candidate. Incompatible upstream extractions require explicit migration design; a familiar repository name is not compatibility evidence. Keep an unmodified baseline available for comparison and rollback.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

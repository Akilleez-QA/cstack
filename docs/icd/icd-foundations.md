# Cstack–Foundations interface control document

Status: reusable documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

## Interface ownership and applicability

Cstack owns host composition, grants, adapters and evidence interpretation. Each Foundation owns its bridge implementation and tool contracts. The controlled Math source is `vendor/foundation-math-v014/`; `foundations/math/` is a research consumer. Changes on either side require review of both admission and result interpretation.

Foundation Engine is a separate domain, `foundation_engine`, served by `adapters/engine_stdio.py` over `foundation-engine-jsonrpc/1` from a partial vendor copy in `vendor/foundation-engine-v020/`: the bridge module `foundation_engine_bridge`, the schema `vendor/foundation-engine-v020/schemas/read-only-tools.json` and the upstream `SOURCE-MANIFEST.json`. The whole manifest is pinned (2,496 entries, upstream commit `70810ba455bdda1eadfdaab6bd44d43ae88f898c`), and the two vendored files must match their entries. Its two read-only tools, `validate_render_mask` and `validate_scene_output`, return the validated value itself with no receipt or assessment; the adapter admits them as tool observations after exact output-schema validation. Inputs may use finite decimal literals; exponents and nonfinite numbers are refused. The Math extension still refuses a `foundation_engine` request; Engine is not reachable through Math.

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

## Vendored Foundation interfaces

Template, Refrigeration, Robotics and Film adapters use `BridgeProfile` and `PinnedStdioCapability` in `adapters/foundation_stdio.py`. Their specific adapters bind protocol, module, numeric decoder, manifest/file count, catalog and receipt boundary. The shared adapter also checks the receipt input digest against canonical arguments. Math retains its own adapter and shall not be described as inheriting that shared implementation.

Adapter pins live in `adapters/template_stdio.py`, `adapters/refrigeration_stdio.py`, `adapters/robotics_stdio.py` and `adapters/film_stdio.py`; sources and manifest builders live under their respective `foundations/` directories. Changes require matched source, inventory, schema and conformance review.

## Interface change acceptance

Record old/new manifests, catalog identities, operation/schema differences and changed evidence semantics. Run adapter and domain conformance suites plus the root suite against the candidate. Incompatible upstream extractions require explicit migration design; a familiar repository name is not compatibility evidence. Keep an unmodified baseline available for comparison and rollback.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

## Foundation pins

Copied from `contracts/SOURCE-PINS.json`. That file is the source of truth.

| Foundation | Path | Files | Manifest SHA-256 | Inventory SHA-256 |
|---|---|---|---|---|
| `foundation_refrigeration` | `foundations/refrigeration` | 63 | `a4e096d2b1169ee23c3f111b121d9dbc593ab63a52ec20167d451ff97c21399e` | `aa89d7ea2acdc601e997de880282877c5efdfeaa510823a2902c77374507fa1b` |
| `foundation_film` | `foundations/film` | 42 | `4734c76b9d0d5b830e150bd2bb435539e202ffd81d967692cff8dacfc3b5a417` | `4432e0305a84ed9aa1b269f2378f869b5b36850001e503ed1ffc0e018dd17558` |
| `foundation_robotics` | `foundations/robotics` | 45 | `4667a558554e6a766e855be078031563b72337b8a6407eabf466d42b9df3bdb6` | `037919a5b4d2305de5a18e7d26994df2871a766ba1c2df2c1b11778d959ca599` |
| `foundation_template` | `foundations/template` | 35 | `7ce77706f1bee842dab391dfd8c0256be231be2d6b6f5483c39574718eea6158` | `2d15f784589a077908d1a8e79dc0350ec62c090f08cb25ef63b04d947ac0622f` |
| `foundation_engine` | `vendor/foundation-engine-v020` | 2496 (2 vendored) | `edee2a8ac7dabf7677dd31061c6ca34e93e321b58194cd6f234d6f8a810d241e` | `c666da976a8a93e327dcaf09689fb9ed0f7d487c59e9f06a484a1b4ad9a9a9cc` |

### Upstream source commits

The vendored snapshots exclude `.git/`. Each upstream `SOURCE-MANIFEST.json` and every listed file, including `.github/workflows/ci.yml`, are copied byte-for-byte from the public main commits below. The 2026-11-01 refresh adds the upstream CI workflows running on `ubuntu-latest`; runtime code, tool inventories and interface semantics are unchanged.

| Foundation | Upstream commit |
|---|---|
| `foundation_template` | `9ce46fa2af5dd1cb9c363a6913bae0aa4175ff47` |
| `foundation_film` | `c4110bc0241a35cf0bd16eaa6cfe116b6e45986a` |
| `foundation_robotics` | `ebd6d4d14e050a5ebda2e4961b9fd1464d1e5653` |
| `foundation_refrigeration` | `3fe90a939f85aeb4e4aa6913b0993374e115f176` |

## Local CLI approval interface

The `cstack.run/0.1` call object accepts optional `effect`, either `allow` (default)
or `ask`. An ask marks that operation as ask in the host's fixed read-only grant,
including other calls of that operation. All existing core gates remain active.
`--approver` selects the controlling-terminal adapter; `--approver=deny` is the
default; `--approver=file:PATH` reads at most 65,536 bytes of integer-only strict
JSON mapping request digests to `approve` or `deny`. Unknown modes and invalid
files fail through the driver error interface. A missing digest denies.

The adapter supplies ApprovalPort lookup and consume, with approver `cli-owner`,
a fresh UUID approval ID and five-minute expiry. Core validation binds decision,
request digest, goal and revision. The host flag and file remain outside request
JSON. Terminal prompts display the full escaped request on `/dev/tty`; only
`approve` authorizes. Missing terminal, EOF and other answers decline. A decline
stops the run before dispatch with no action/outcome, preserving earlier history.

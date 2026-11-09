# Cstack–Foundations interface control document

| Field | Value |
|---|---|
| Document ID | CSTACK-ICD-FOUNDATIONS |
| Version | 2.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b7c64b19e3966baaf1aa6793491b454e28f51446 |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## Interface ownership and applicability

Cstack owns host composition, grants, adapters and evidence interpretation. Each Foundation owns its bridge implementation and tool contracts. The controlled Math source is `vendor/foundation-math-v014/`; `foundations/math/` is a research consumer. Changes on either side require review of both admission and result interpretation.

Foundation Engine is a separate domain, `foundation_engine`, served by `adapters/engine_stdio.py` over `foundation-engine-jsonrpc/1` from a partial vendor copy in `vendor/foundation-engine-v020/`: the bridge module `foundation_engine_bridge`, the schema `vendor/foundation-engine-v020/schemas/read-only-tools.json` and the upstream `SOURCE-MANIFEST.json`. The whole manifest is pinned (2,513 entries, upstream commit `8445d319fd35115093f44a2081beb29ff108be49`), and the two vendored files must match their entries. Its two read-only tools, `validate_render_mask` and `validate_scene_output`, return the validated value itself with no receipt or assessment; the adapter admits them as tool observations after exact output-schema validation. Inputs may use finite decimal literals; exponents and nonfinite numbers are refused. The Math extension still refuses a `foundation_engine` request; Engine is not reachable through Math.

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
| `foundation_refrigeration` | `foundations/refrigeration` | 79 | `230a8faac3653e510b08d0e81614bbc44ad2721e70aeda98722c7176ea47629f` | `aa89d7ea2acdc601e997de880282877c5efdfeaa510823a2902c77374507fa1b` |
| `foundation_film` | `foundations/film` | 55 | `1abcea4f6692fa081a5839bbcd6e5eaad3ea41575b566208a2cd1afc8562d956` | `4432e0305a84ed9aa1b269f2378f869b5b36850001e503ed1ffc0e018dd17558` |
| `foundation_robotics` | `foundations/robotics` | 61 | `7452f90b3771213f5eada796fc2e489d19dada7b339d04155df39b8a85f5587d` | `037919a5b4d2305de5a18e7d26994df2871a766ba1c2df2c1b11778d959ca599` |
| `foundation_template` | `foundations/template` | 49 | `0c9c1f7f5668668806fb0073f2e772c7f96ecdaa69c28fc35e8d2da380fbe9b9` | `2d15f784589a077908d1a8e79dc0350ec62c090f08cb25ef63b04d947ac0622f` |
| `foundation_engine` | `vendor/foundation-engine-v020` | 2513 (2 vendored) | `0617efcbbb594919137ca6b748de189516ee9ec35e49f56765109cfe9fb01349` | `c666da976a8a93e327dcaf09689fb9ed0f7d487c59e9f06a484a1b4ad9a9a9cc` |

### Upstream source commits

The vendored snapshots exclude `.git/`. Each upstream `SOURCE-MANIFEST.json` and every listed file are copied byte-for-byte from the public main commits below. The 2026-11-08 repin follows the upstream documentation-standard PRs (film #12, robotics #11, template #11, refrigeration #10 and #11). Upstream manifests no longer list `.github/`, so the vendored copies no longer carry the upstream CI workflows. Tool inventories and bridge interface semantics are unchanged. Two upstream modules are new in the copies and are not reached through the bridge: `foundation_film/filmstats.py` (an optional producer CLI that needs OpenCV and PySceneDetect) and `foundation_refrigeration/invariants.py` (a local Python invariant API). Refrigeration's `exposure-limits.json` changed only in its `generatedBy` text.

| Foundation | Upstream commit |
|---|---|
| `foundation_template` | `9beaafacf4386ea577f2c638320a8112a7280664` |
| `foundation_film` | `9877f1c177421caf35fd2a452a1393fc040e3ff1` |
| `foundation_robotics` | `1324e46865d51b6c521dfdaf20f76e5d2e2b5070` |
| `foundation_refrigeration` | `684314d632c488e2d677a64296d597c07fe56e75` |

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

## Requirements addressed

CS-REQ-003 to CS-REQ-008 and CS-REQ-015 (Math adapter); CS-REQ-064 (Film, Refrigeration, Robotics and Template adapters); CS-REQ-065 (Engine adapter); CS-REQ-009 to CS-REQ-011 (process executor); CS-REQ-017 and CS-REQ-018 (local CLI approval). The tool and field tables generated from `schemas/` are in the [data dictionary](../data/data-dictionary.md). See the [verification matrix](../verification/verification-matrix.md) for the tests.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Earlier versions | See `git log -- docs/icd/icd-foundations.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard header and disclaimer; requirements-addressed section | docs/nasa-standard PR |
| 2.1 | 2026-11-08 | b7c64b19e3966baaf1aa6793491b454e28f51446 | Foundation and Engine repin: pins table, upstream commits, Engine manifest (2,513 entries); vendored copies no longer carry upstream CI workflows | PR #PRNUM |

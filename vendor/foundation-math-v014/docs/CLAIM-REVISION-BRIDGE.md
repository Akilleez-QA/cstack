# Append-only claim-revision bridge contract

The custom local `foundation-math-jsonrpc/1` bridge, not MCP, appends exactly one
tool after the fourteen unchanged existing definitions:

- `replay_claim_applicability`, with arguments exactly `{ledger: document}`.

The tool is read-only and stateless. A completed replay returns `isError: false`
and `assessment: claim_dependency_applicability_replayed`, even when records are
blocked. It includes the full adapter receipt and pure report. Invalid ledger data
returns `isError: true`, `assessment: tool_error`, and a structured error receipt
with no partial result. Invalid outer arguments remain JSON-RPC parameter errors.
The envelope always sets `formal_proof: false` and `runtime_goal_acceptance: false`.

The bridge retains its existing 65,536-byte input cap INCLUDING JSON-RPC envelope,
1,048,576-byte output cap, 80-depth, 16,384-node and 4,096-character string limits.
The more restrictive of bridge and core limits applies. A standalone-valid ledger
or report may therefore be too large for bridge use. Output overflow withholds the
whole response result. No caller-set budget, paths, commands, source execution,
network, models, external artifact fetches or evidence acceptance are reachable.

The new schema embeds only local definitions; JSON Schema validation is an aid,
not hash, chronology, graph, exact Python-type or mathematical verification.
Legacy wire handling remains unchanged for compatibility, including transport
acceptance of escaped surrogate IDs. The ledger input itself retains strict
unpaired-surrogate key/value rejection with a typed `malformed_type` error.

Repeated replay invokes the same algorithm and is not independently implemented
verification. Independent implementation refers only to the separately supplied
review oracle used during offline validation, not a new advertised proof tool.

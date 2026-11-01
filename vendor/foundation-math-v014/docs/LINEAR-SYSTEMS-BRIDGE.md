# Append-only system bridge contract

The custom stdio protocol remains `foundation-math-jsonrpc/1`, not MCP. Ten tools
are advertised. The entire first eight definitions, including descriptions,
input/output schemas, order and readOnly flags, equal the pinned v0.7 portable
snapshot `BASE-V07-PORTABLE-BRIDGE-TOOLS.json`.

The only additions are:

- `solve_rational_linear_system` with exactly `system`.
- `check_rational_linear_system_certificate` with exactly `system, certificate`.

Successful solving has assessment `rational_linear_system_solved`; successful
checking has `rational_linear_system_certificate_valid`. Both consistency and
inconsistency are successful checked mathematical outcomes, with `isError=false`.
Inspect `receipt.result.verification.outcome` to distinguish them. Invalid
certificates, malformed semantic inputs and resource failures return
`isError=true`, `assessment=tool_error`, and an error receipt without results.
Unexpected backend exceptions are generic JSON-RPC -32603 failures, not mathematical
verdicts. Extra outer fields, commands, paths, code and caller limits are rejected.

Structured output schemas distinguish the consistent and inconsistent branches,
including paired certificate/result outcomes in solve receipts. Shape-dependent
relations, reduced fractions, matrix equations and certificate soundness require
the runtime checker. Schema conformance alone is never mathematical verification.
The schema audit deliberately demonstrates structurally legal but semantically
false certificates being rejected by runtime.

Inherited framing remains strict UTF-8 JSON with duplicate-key/float/nonfinite
rejection, 65,536 input bytes, 1,048,576 output bytes, 16,384 JSON nodes and depth
80. Backend depth and other caps can be tighter. Notifications never execute
work. A standalone-valid certificate can be too large to check through the
bridge. Output overflow withholds the entire result. No increased limit or new
request-controlled I/O capability is introduced.

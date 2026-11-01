# Two appended bridge tools

This remains the custom foundation-math-jsonrpc/1 stdio bridge, not MCP. All ten
prior input/output definitions, descriptions and readOnly flags form an unchanged
ordered prefix. Initialization differs only in serverInfo.version (0.9.0-dev);
protocol, methods, limits and lifecycle remain unchanged.

11. calculate_fixed_character takes exactly {request: REQUEST}. It produces and
independently checks fixed character arithmetic. Success assessment is
fixed_character_arithmetic_checked.
12. check_fixed_character_certificate takes exactly {request: REQUEST,
certificate: CERTIFICATE}. It re-evaluates against the separately supplied request.
Success assessment is fixed_character_certificate_valid.

Both are read-only. Structured output always says formal_proof=false and
runtime_goal_acceptance=false. Any adapter failure, including E_EXPECTATION, has
isError=true, assessment=tool_error and an error receipt without a result or partial
certificate. A malformed outer argument envelope is an existing JSON-RPC -32602
error rather than an arithmetic outcome. Unexpected bridge exceptions fail closed
with -32603 and no evidence. Notifications execute no math work.

Input JSON Schema describes exact labels, structural variants and numeric bounds.
It does not establish arithmetic, request binding, table identification, rational
canonicality, duplicate-key handling, plain Python types, total tree budgets or
formal statement correspondence. Runtime validation remains authoritative.

The bridge retains 65536 input-frame bytes, 1048576 output-frame bytes, 16384 JSON
nodes, depth 80, 4096-character strings and 4096-bit integer guard. These transport
constraints apply in addition to the narrower character-domain limits. A valid
standalone request/certificate can be too large for the bridge, especially the
combined expected request and certificate. No old transport bound is enlarged.
The caller cannot override budgets or select catalogs, paths, commands or code.

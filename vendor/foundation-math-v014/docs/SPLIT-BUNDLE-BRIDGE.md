# Append-only split-bundle bridge

The custom foundation-math-jsonrpc/1 stdio protocol is unchanged and is not MCP.
There are fourteen tools. The first twelve definitions are structurally identical to
BASE-V09-BRIDGE-TOOLS.json; their implementation and responses are differentially checked
against an embedded manifest-only v0.9 baseline in ordinary and optimized Python.

New tools:

- calculate_formal_split_bundle: arguments exactly {request}; assessment
  formal_split_bundle_arithmetic_checked on success.
- check_formal_split_bundle_certificate: arguments exactly {request, certificate};
  assessment formal_split_bundle_certificate_valid on success.

Both are read-only. Success and failure always retain formal_proof=false and
runtime_goal_acceptance=false. Domain errors are isError=true with assessment tool_error.
Unexpected failures have no mathematical outcome. Notifications perform no calculation.

The inherited wire limits remain 65,536 input bytes, 1,048,576 output bytes, JSON depth
80 and 16,384 nodes. Domain request/certificate canonical limits are 65,536/262,144 bytes,
depth 16, 8,192 values and 300-bit integers. A standalone-valid certificate may not fit
a bridge frame. Rejection is never truncation or partial acceptance. The bridge exposes
no paths, commands, arbitrary group tables or code. These bounds are not an OS sandbox
or a wall-clock quota. JSON Schema is structural, not arithmetic verification.

# Bounded transport integration

Exactly one read-only bridge definition is appended: `match_hypothesis_scope`.
Its only argument is `document`. The output assessment is
`authored_premise_scope_compared` for completed comparison and `tool_error` for
invalid input. A blocked comparison is not an execution error. The old fifteen
complete definitions and old tool responses are compared with reconstructed v0.12.

The bridge remains restricted JSON-RPC, not MCP. Its original frame limits remain
65,536 input bytes including the envelope, 1,048,576 output bytes, 16,384 JSON
nodes, depth 80 and bounded strings/integers. The matcher further checks its own
stricter bounds. No limit is enlarged to accommodate the lab's 262,144-byte stdin
input cap. Duplicate keys, float/nonfinite numbers, invalid UTF-8 and surplus
arguments fail closed. Notifications still execute no work. Unexpected backend
errors do not leak traceback, source paths or partial evidence.

`python -m foundation_math hypothesis-scope-check` accepts stdin only: no path,
option, code, command, network or caller budget. It returns exit 0 for a completed
comparison and 2 for an invalid document, forbidden CLI argument or I/O failure.
Its complete ASCII JSON output is capped at 262,144 bytes excluding final newline;
overflow withholds the whole result. The direct adapter uses the unchanged core's
bounds; transport encoding adds its own independent checks.

The structural schemas deliberately do not claim to validate exact Python types,
record hashes, reference identity, contexts, endpoints, aggregate budgets, current
pins or mathematical meaning. Runtime validation does. All advertised evidence
and proof flags are fixed false in success and error schemas.

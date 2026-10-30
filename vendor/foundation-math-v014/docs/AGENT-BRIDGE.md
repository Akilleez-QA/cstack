# v0.5 local agent bridge

The original four-tool contract below is retained as the v0.5 baseline. In
v0.6 the same transport adds two matrix tools, so current `tools/list` returns
six tools; see [the matrix extension](LINEAR-ALGEBRA-BRIDGE.md). The original
four contracts and wire limits are unchanged.

This extension advances one obligation: let an external coding or research agent
invoke four bounded exact math tools without importing the implementation into
its own process, embedding a model, or obtaining credentials. It is a local
standard-library Python 3.11+ prototype, not a published release.

## Protocol identity and compatibility

The protocol identifier is **`foundation-math-jsonrpc/1`**. The executable is
`foundation_math_bridge`. It uses a **restricted JSON-RPC 2.0 envelope profile**
over newline-delimited UTF-8 stdio. It is **not an MCP server**, not a full
JSON-RPC implementation, and has not been tested with an external agent or MCP
SDK. Familiar method names do not establish MCP compatibility.

Primary specifications checked on 2026-10-24:

- [Official MCP 2026-07-28 versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning).
- [Official MCP 2026-07-28 stdio binding](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).
- [Official MCP 2026-07-28 tools contract](https://modelcontextprotocol.io/specification/2026-07-28/server/tools).
- [Official stable-release announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/).
- [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification).

The official stable MCP revision checked was 2026-07-28, not a draft proposal.
Its modern lifecycle uses per-request protocol metadata and `server/discover`,
not the old initialization handshake. This bridge deliberately does not
implement that lifecycle, MCP capabilities, cancellation, subscriptions,
continuations, HTTP, authorization or SDK interoperability. A date-version MCP
initialization is rejected; the custom initialization explicitly returns
`mcpCompatible: false`. Supporting MCP later requires a separately scoped,
version-pinned implementation and real interoperability tests, not a rename.

## Run locally

From the source root:

```sh
python -B -m foundation_math_bridge
```

Launch that fixed module as a child process with stdin/stdout pipes. No shell
is needed. No command-line arguments, file paths, executable names, environment
settings or operator-provided commands are accepted by the bridge.

For a complete reproducible session or small Python client:

```sh
python -B -m foundation_math_bridge < examples/bridge/session-requests.jsonl
python -B examples/bridge/stdio_client.py
python -B tools/run_bridge_validation.py
```

The example client uses a fixed subprocess argument vector and a timeout. An
agent host can replace the math argument objects, not the executable or command
string. Host integration is the caller's responsibility; no agent configuration
files, live model calls, network servers or external repositories are created.

## Session and framing

1. Send one request per LF-terminated UTF-8 line. Escaped newlines inside JSON
   strings are permitted; literal line breaks delimit frames. CRLF is accepted
   as JSON whitespace before the final LF.
2. Use `initialize` with exactly
   `{"protocolVersion":"foundation-math-jsonrpc/1"}` before any math tools.
   Initialization succeeds once per process. It does not require a follow-up
   notification. The response advertises methods, limits and the explicit
   non-MCP boundary.
3. `tools/list` accepts omitted params or `{}` and returns the four tools in a
   fixed order with JSON Schema 2020-12 input and output-envelope definitions.
   There is no cursor, pagination, mutable tool list or tool registration.
4. `tools/call` accepts exactly `{"name": <tool>, "arguments": <object>}`.
5. `ping` accepts omitted params or `{}` at any point, including before
   initialization, and returns `{}`.
6. Close stdin to shut down. EOF after complete frames exits 0. There is no
   shutdown method. The client owns wall-clock timeouts and may terminate the
   process if it stalls; no evidence can be inferred from missing responses.

Example requests (one JSON object per line):

```jsonl
{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"foundation-math-jsonrpc/1"}}
{"jsonrpc":"2.0","id":"tools","method":"tools/list"}
{"jsonrpc":"2.0","id":"calculate","method":"tools/call","params":{"name":"exact_scalar","arguments":{"domain":"Q","operation":"add","operands":[{"numerator":1,"denominator":2},{"numerator":1,"denominator":3}]}}}
```

The third response has `result.isError: false`,
`result.structuredContent.assessment: exact_scalar_result`, and the exact receipt
result `{"domain":"Q","numerator":5,"denominator":6}`. Full actual responses,
including initialization and tool schemas, are recorded in
`evidence/bridge-transcript-validation.json`; the matching request stream is
`examples/bridge/session-requests.jsonl`. These are generated test evidence, not
handwritten simulations.

## Restricted JSON-RPC profile

Only object requests are accepted. Batches and top-level extra fields are
rejected. Params are named objects, not positional arrays. IDs must be strings
of at most 128 characters, including the empty string, or integers with absolute
value at most 9,007,199,254,740,991. Booleans, null, fractional IDs and containers
are rejected. The response echoes a valid request ID exactly, including its
type; parse or invalid-envelope errors use null. Reusing a completed ID is
allowed and re-executes the request: IDs are correlation labels, not idempotency
keys. No unbounded history of IDs or receipts is retained.

Valid notification envelopes, including unknown method notifications, are
silently ignored and never initialize the session or execute math work. This
profile is request-only for all useful operations. A malformed envelope or
unparseable input is not a valid notification and receives an error when
possible. The server does not initiate requests or emit logging on stdout.
Requests are processed serially, even when the client pipelines lines. There is
no cancellation or concurrent execution; clients needing those features should
not treat this bridge as supporting them.

Error meanings:

- `-32700`: malformed/duplicate-key/non-UTF-8 JSON, decimals or nonfinite numbers
  outside the exact-only profile, or an unterminated final frame.
- `-32600`: invalid envelope or unsupported batch/ID.
- `-32601`: unknown method, including MCP `server/discover`.
- `-32602`: invalid params, unknown tool, or a non-identity operation submitted
  to the identity-only adapter.
- `-32603`: unexpected backend/serialization failure; details are sanitized and
  no evidence result is returned.
- `-32000`: missing initialization or duplicate initialization.
- `-32001`: unsupported custom bridge protocol version.
- `-32002`: bridge resource limit; a result too large to serialize is withheld
  in its entirety, never truncated into apparently valid evidence.

A bounded malformed line produces one error and the next line can be handled.
An oversized frame or final non-LF-terminated frame produces one error and
closes the session with exit 2. The server does not drain an unbounded oversized
stream. Broken pipes/I/O failures exit 2 when observed. An interrupted process
has no success result merely because it was started.

## Tool and mathematical contracts

`exact_scalar` accepts the existing scalar request directly: explicit Z or Q,
an allowlisted operation, and exact operands. Z division that produces a
noninteger is an error, not a coercion to Q. Integer powers are bounded; 0^0 is
undefined by this tool's contract. See
[calculator contract](../foundation_math/ADAPTERS.md).

`polynomial_identity` accepts only `operation: verify_identity` in the existing
Q-polynomial AST format. Equality means coefficient equality in the declared
formal commutative polynomial ring, with ordered algebraically independent
variables. It is not a quotient-ring identity, rational-function identity,
analytic identity or a finite sample test. Both true and false comparisons are
successful computations; false equality has assessment
`formal_polynomial_identity_not_equal`, `receipt.result.equal: false`, and an
exact nonzero coefficient witness. Here "formal polynomial" describes the ring,
not a proof-kernel run. See [polynomial contract](POLYNOMIAL-DOMAIN.md).

`finite_box_search` accepts an explicit finite integer box, rational-polynomial
constraints and one assertion. Q describes the coefficients, **not** the points
being enumerated. It returns `counterexample_found` or
`no_counterexample_in_declared_finite_domain`. The latter concerns only that
entire box under those exact constraints, never all integers, Q or R. An empty
eligible set is visible through `eligible_count: 0`.

`check_finite_box_witness` accepts exactly `request` and `assignment`. It reparses
the original request, enforces all integer-domain and constraint requirements,
and recomputes the values. It cannot accept a producer receipt or claimed
verdict in place of those inputs. `witness_rejected` is a completed negative
check, not finite exhaustion. The checker shares the search parser/evaluator;
it is independent of the producer's verdict, not an independently implemented
proof kernel. See [finite-box contract](BOUNDED-COUNTEREXAMPLES.md).

Every completed call includes `structuredContent` with the tool name, a specific
`assessment`, `formal_proof: false`, `runtime_goal_acceptance: false`, and the
full original backend receipt. Backend failures use `isError: true` and
`assessment: tool_error`; an envelope error instead has a top-level `error` and
no `result`. Neither error representation is proof success. The wrapper does
not touch the work queue, ledger, verifier registry or goal-acceptance state.
A correct false result must not be promoted merely because `isError` is false.

Input schemas describe data shape, not the entirety of semantic admission:
declared-variable binding, matching bound/assignment keys, bit budgets,
aggregate AST/work limits and bounds order are checked by the backends. Their
receipts retain exact domains, scopes, implementation identifiers and content
hashes. A hash is not a signature, proof, or authentication of a hostile
producer. Replay the intended request in a trusted process to check evidence.
Malformed witness candidates are rejected but may not be retained or hashed by
the backend; they are not claimed to have unique evidence identities.

## Resource and trust boundary

Fixed transport limits: 65,536 input bytes and 1,048,576 output bytes per frame,
excluding the LF; nesting 80; 16,384 parsed nodes including keys; strings 4,096
characters; numeric tokens at most 1,234 decimal digits and 4,096 bits. Numbers
with a decimal point or exponent, nonfinite constants and duplicate object
keys at any depth are rejected. Depth is checked before parsing. No limit is
configurable by requests. Backend bounds remain stricter for polynomials and
finite boxes and are included in tool descriptions and receipts.

The input frame envelope counts against the byte limit, so a maximally sized
standalone backend request may not fit through the bridge. Output is emitted
only after the complete bounded response is serialized, one flushed line at a
time. The bridge never falls back to float arithmetic or partial success.

No request-controlled shell, Python/Lean source execution, dynamic imports,
filesystem paths, network, credentials or model interface is exposed. Existing
backends read only their own fixed source files for receipt hashing. Recommended
`-B` invocation avoids bytecode writes. These are narrow API boundaries, **not**
an OS sandbox or a hard CPU/RSS/time guarantee: the Python interpreter,
standard library, filesystem containing the fixed source tree, and local host
remain trusted. Partial-frame senders can hold stdin open; the launching client
must impose its own timeout. Do not deploy as a hostile multi-tenant service or
add arbitrary plugins without a new isolation design.

## Verification and remaining work

Run the complete tests in both modes:

```sh
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
python -B tools/run_bridge_validation.py
python -B tools/audit_agent_bridge.py
python -B -O tools/audit_agent_bridge.py
```

[Validation evidence](AGENT-BRIDGE-VALIDATION.md) records executed counts,
independent checks and source preservation. No live model, external agent host,
MCP SDK, real Lean kernel or mathematical research problem was run by this
extension. Those remain distinct future work, not implied by successful stdio
integration tests.

# v0.7 append-only polynomial-witness bridge

The bridge now advertises eight tools. All six v0.6 definitions, including their
names, descriptions, input/output schemas, read-only flags and order, are pinned
unchanged in `BASE-V06-BRIDGE-TOOLS.json`. Two new tools are appended:

1. `construct_polynomial_witness`, accepting exactly `{"request": original_request}`.
2. `check_polynomial_witness`, accepting exactly
   `{"request": original_request,"witness": bare_witness}`.

The server version is `0.7.0-dev`. The transport remains the local custom
`foundation-math-jsonrpc/1` profile, **not MCP**. Initialization, notifications,
strict framing, ID rules, byte caps and the original six operation semantics
are unchanged. No runtime domain or proof acceptance is added.

```sh
python -B -m foundation_math_bridge
python -B -m foundation_math_bridge < examples/polynomial-witness/session-requests.jsonl
```

Each request is one LF-terminated JSON line. For example:

```jsonl
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"foundation-math-jsonrpc/1"}}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"construct_polynomial_witness","arguments":{"request":{"domain":"polynomial_ring","coefficient_field":"Q","variables":["x"],"operation":"verify_identity","operands":[{"type":"variable","name":"x"},{"type":"rational","numerator":0,"denominator":1}]}}}}
```

## Assessments

| Assessment | Meaning | `isError` |
|---|---|---|
| `polynomial_coefficient_identity` | Exact normalization gives zero difference; point verification not applicable | false |
| `polynomial_counterexample_constructed` | A constructed point received fresh exact-AST acceptance | false |
| `polynomial_witness_valid` | The supplied point and values match the separately supplied original request | false |
| `polynomial_witness_rejected` | This supplied witness failed checking; no alternative-point conclusion | false |
| `tool_error` | Malformed expected request, unsupported scope or resource/provenance failure | true |

For construction, the wrapper receipt is at `structuredContent.receipt` and the
lab outcome at `receipt.result.result`. A concrete bare witness is at
`receipt.result.result.witness`. The fresh check is at `receipt.result.verification`.
For verification, `receipt.result` itself is the accepted point-check record.
Rejected/error receipts have no `result` or accepted evidence.

The original six tools keep their former assessment/error conventions. In
particular, existing matrix-certificate rejection still uses its existing tool
error contract; the appended witness rejection convention does not change it.

## Evidence boundaries

Every returned bridge content and wrapper receipt has `formal_proof: false` and
`runtime_goal_acceptance: false`. Receipts explicitly specify Q, characteristic
zero and the unrestricted formal-ring scope. Coefficient identity evidence comes
from exact normalization, not from the bounded witness checker. The point checker
never promotes point agreement to a polynomial identity, and it does not validate
construction trace minimality or degree bounds.

The checker rejects a producer receipt, success label or hash substituted for
the bare witness. It binds the declared ring and the original request, including
its original rational encoding. It recomputes both original AST values and the
nonzero left-minus-right. Shared parser/Fraction/runtime trust is explicit.

JSON Schema 2020-12 definitions describe complete structural branches for both
new tools and receipts. They do not verify rational gcd canonicality, exact
variable-set binding, source authenticity or polynomial mathematics. Strict
runtime checks also reject floats and booleans in integer slots. Schema's
mathematical integer type alone is not that stronger JSON-token rule.

The schema is deliberately not a promise that every structurally valid request
fits all runtime caps or has an accepted witness. No caller-specified limits,
constraints, paths, backend names, code, shell commands, credentials, model
configuration or runtime goals are supported.

## Stronger construction trial bound

The first-preserving-integer algorithm obeys trials <= n + D, where D is the
normalized nonzero difference’s total degree. At the fixed n<=8, D<=32 caps
this is at most 40, and a degree-32 falling factorial with seven unused
variables attains 40. The original 264 hard budget is retained for compatibility.

Only a successful constructed mismatch adds `construction_bound` to the wrapper
receipt. Its executable `substitution_trial_bound` is n+32, not a claimed exact
n+D value. It reports actual trials, sum of chosen coordinates, and explicit
false flags for exact-degree recomputation and point-checker certification.
The output schema keeps this field out of coefficient-identity and standalone
point-check branches. The proof and limitations are in the
[total-degree argument](POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md).

## Fail-closed transport

The unchanged bridge caps are 65,536 input-frame bytes, 1,048,576 output bytes,
16,384 JSON nodes, depth 80, 4,096-character strings and 4,096-bit raw integers.
These apply in addition to narrower parser/arithmetic caps. Valid notifications
never execute a tool. Missing/extra outer fields yield `-32602`; malformed or
duplicate-key/decimal JSON yields `-32700`; transport limit exhaustion yields
`-32002`. Unexpected backend exceptions are sanitized as `-32603`, without
private paths, traceback or an evidence result.

A successful standalone receipt can contain a request/witness pair too large to
re-enter through this bridge. The host must choose an appropriate documented
interface; the server does not relax limits automatically. Only tiny synthetic
inputs are used in the transcript, tests and independent integration audit.

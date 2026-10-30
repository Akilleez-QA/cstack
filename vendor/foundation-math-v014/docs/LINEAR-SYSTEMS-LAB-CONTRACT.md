# API, schema and resource contract

## Exact scalar format

A coefficient is an integer JSON token, excluding booleans, or an object with
exactly `num` and `den`: both integers, `den>1`, `num!=0`, and gcd(num,den)=1.
Integers, including zero, must use integer tokens. Negative denominators,
non-reduced fractions, extra keys, floats, decimal strings, NaN and infinities
are rejected. Domain Z allows only integer tokens in A and b. Output witness
and solution coefficients are always rational and may use either canonical
encoding regardless of the input domain.

## Expected system

Exactly these fields are permitted:

```json
{
  "matrix": {"domain": "Z", "rows": 1, "cols": 2, "entries": [[2, 1]]},
  "rhs": [1]
}
```

The matrix schema is the frozen v0.6 MatrixSpec. Dimensions are explicit, so
zero rows do not erase the column count. `rhs` is exactly one vector, of length
`matrix.rows`, rather than an m×k object or a list of right-hand sides.

## Typed Python entry points

- `exact_systems.producer.produce(system: object, limits: Limits=Limits())`
  returns a `SystemCertificate` or raises `MathError`. It is untrusted production,
  not an acceptance API.
- `exact_systems.verifier.verify(system: object, certificate: object, limits:
  Limits=Limits())` returns an immutable `VerifiedSystem` or raises `MathError`.
  It imports neither system nor matrix producer and does not perform elimination.
- `exact_systems.api.handle_request(request: object, limits: Limits=Limits())`
  returns a JSON-like success/error response. `object` is intentional at the
  hostile-input boundary; `SystemSpec`, both certificate variants and
  `SystemRequest` are exported TypedDict contracts for callers.

Requests have exactly `operation` and `system`, plus `certificate` if and only
if `operation` is `verify`. The other allowed operation is `solve`. A solve
produces a certificate and then verifies it against the original system.
Limits are a trusted Python configuration argument, not an agent-request field.

## Certificate variants

Both have exactly `schema: "foundation-math-rational-linear-system/1"`,
`system: SystemSpec`, `outcome`, and the variant-specific fields below.

Consistent:

- `outcome: "consistent"`.
- `particular`: canonical rational coefficient list of length n.
- `matrix_certificate`: unchanged frozen `foundation-math-rational-matrix/1`
  certificate for the same A, containing the complete rational nullspace basis
  as an n×(n-r) matrix with basis vectors as columns.

Inconsistent:

- `outcome: "inconsistent"`.
- `left_nullvector`: canonical rational coefficient list of length m.
- `rhs_pairing`: canonical nonzero rational equal to `y^T*b`.

No claims or metadata may be appended to either schema. The certificate is
strictly bound to expected A,b, including the exact input-domain tag. Mutating
both embedded A and b does not change the separately supplied expected system.

## Responses and CLI

Success has `ok: true`, a `verification` object, and only for solve a
`certificate`. Every verification result has `accepted: true` scoped to
`one_explicit_linear_system`, `computational_field: "Q"`, input domain,
dimensions, outcome, and explicit false flags for `formal_proof`,
`runtime_goal_acceptance` and `family_or_generic_claim`.

For consistent results it exposes `particular`, `nullspace`, `rank` and
`nullity`. Inconsistent results expose `left_nullvector` and `rhs_pairing`;
no unsupported rank is reported. `accepted` means this certificate passed this
checker, not that a runtime mathematical goal or formal proof was accepted.

Rejection has exactly `ok: false` and `error: {code,message,path}`. It contains
no accepted result, partial solution or certificate. Lower-level functions
raise `MathError` instead of packaging it. Internal programmer errors are not
silently converted into mathematical verdicts; the CLI alone catches unexpected
exceptions and emits a generic `INTERNAL_ERROR` without a traceback.

The stdin CLI is one-shot and has no filesystem, subprocess, network or model
operation requested through its data contract. It reads at most
`max_input_bytes+1` raw bytes, rejects oversized input, parses strict UTF-8 JSON
with duplicate-key rejection, and emits one newline-terminated response.
Exit status is 0 for checked success and 2 for all errors.

## Exact default/hard resource ceilings

Callers may only lower ceilings using the frozen `Limits` value:

| Limit | Default and hard maximum | Meaning |
|---|---:|---|
| max_dimension | 16 | Every explicit matrix dimension; vector lengths are corresponding dimensions |
| max_cells | 256 | Each materialized or certificate matrix, including U and N |
| max_input_bits | 128 | Bit length of each input numerator/denominator, including b |
| max_intermediate_bits | 2048 | Bit length of every reduced rational arithmetic result and certificate coefficient; also bounds integer tokens in structural parsing |
| max_operations | 1024 | Number of row operations in a matrix certificate |
| max_work | 2,000,000 | Aggregate charged rational primitives and instrumented scans across one public operation |
| max_input_bytes | 1,000,000 | Raw CLI request bytes and compact ASCII JSON size for structured input |
| max_output_bytes | 1,000,000 | Each successful produced artifact/verification result/final response |
| max_nodes | 100,000 | Structural JSON nodes, including object keys, checked before recursive encoding |
| max_depth | 32 | Structural nesting, checked before recursive parsing/encoding |

Bit ceilings have minimum 1. Other ceilings may be zero, in which case a
nonempty operation can fail immediately. Input bits must not exceed intermediate
bits. Wrong limit types, booleans and attempts to raise a hard maximum are
rejected. Objects that are not exact JSON-like Python builtins are rejected.

A verification's combined expected-system/certificate object is structurally
bounded; it does not receive two independent request-size allowances. Before
Fraction construction, scalar tokens and the outer tree are bounded. Rational
primitives check both operands and the exact reduced result. Integer raw
multiplication inside Fraction can briefly have up to twice the operand bit
length; this is bounded and not a claim that each CPU allocation is <=2048 bits.

### Work accounting without editing the frozen engine

The frozen matrix engine owns its internal budget and does not expose its used
count. To preserve it byte-for-byte without resetting the caller's ceiling,
work is **statically partitioned**:

- Direct producer: `floor(W/2)` for matrix production, the remainder for system
  construction.
- Direct verifier: `floor(W/2)` for matrix verification (unused for an
  inconsistent witness), the remainder for system checks.
- Solve API: `floor(W/2)` for the whole producer and the remainder for the whole
  verifier, each subdividing its allotment as above.
- Verify API: the whole W is passed to the direct verifier.

Thus the sum of charged work can never exceed W. Unused allotment is not
transferred; a phase can exhaust its share even when the overall unused budget
is larger. Addition, multiplication and division each cost one unit; replay,
pivot, dimension and comparison scans cost the explicitly instrumented counts
in the source. Parsing, allocation and serialization are not charged to
`max_work`; their dimensions, bit lengths, byte counts, nodes and depth are
bounded separately. These are exact logical resource contracts, **not a
wall-clock timeout or a precise operating-system memory bound**.

Cell limits apply per matrix, not to the sum of all matrices. The system vector
is bounded by dimension, and overall request nodes/bytes are bounded. The
original matrix algorithm may construct U even for an inconsistent system;
this can trigger a resource rejection although a smaller y certificate exists.
A separately supplied small valid y can still be verified within its own caps.

Successful output caps do not suppress the small diagnostic error envelope;
for example `max_output_bytes=0` rejects success but still returns an error.
The configured input cap must accommodate an independently checked produced
certificate as well as the original request. A resource failure is always an
error, never evidence of consistency, inconsistency, formal proof or exhaustion
of mathematical possibilities.

## Frozen dependency and scope exclusions

`exact_linalg/*.py` and its five regression-test modules are byte-identical local
copies of the v0.6 artifact. Hashes and preservation reports identify exact
bytes. The independent verifier relies on the frozen matrix verifier only for
the consistent branch; the inconsistent branch uses direct dot products.

This lab adds no bridge tools, no runtime domain, no claim-ledger evidence
promotion, no package installation, no repository, no publication, no live
model and no proof-assistant execution. Multiple RHS, symbolic systems,
Diophantine solving, floating-point conditioning and family-level statements
are intentionally out of scope.

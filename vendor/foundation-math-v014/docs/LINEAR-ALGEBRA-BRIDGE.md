# v0.6 explicit rational-matrix certificate bridge

This extension advances one bounded obligation: expose generation and fresh
checking of exact matrix certificates through the existing local stdio bridge.
The four v0.5 tools retain their names, order, argument contracts and semantics;
two new tools are appended. The server version is `0.6.0-dev`. The protocol is
still **`foundation-math-jsonrpc/1`, not MCP**. The v0.5 bridge document and
validation artifacts describe the historical four-tool baseline, not this
extended six-tool listing.

No matrix domain is registered with the work-queue runtime. No frozen scalar,
polynomial, counterexample, runtime or proof-assistant backend is changed by
this bridge integration. All examples below are tiny synthetic matrices.

## Discovery and calls

Launch the fixed module from this source root:

```sh
python -B -m foundation_math_bridge
```

Initialize once with the custom protocol version, then call `tools/list` or
`tools/call`. Existing initialization, envelope, error, notification, framing and
shutdown behavior is unchanged; see [the bridge profile](AGENT-BRIDGE.md).
`tools/list` returns the original four tools followed by:

1. `certify_rational_matrix`, accepting exactly `{"matrix": MatrixSpec}`.
2. `check_rational_matrix_certificate`, accepting exactly
   `{"matrix": MatrixSpec, "certificate": MatrixCertificate}`.

Both advertise read-only JSON Schema 2020-12 input contracts and complete
matrix-specific `structuredContent` output contracts. There are no arguments
for a backend, file path, source code, command, model, credentials, custom
limits or runtime goal. The implementation calls the fixed
`foundation_math.linear_algebra.certify_matrix` and
`foundation_math.linear_algebra.check_matrix_certificate` entrypoints.

For example, send each request on one LF-terminated line:

```jsonl
{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"foundation-math-jsonrpc/1"}}
{"jsonrpc":"2.0","id":"matrix","method":"tools/call","params":{"name":"certify_rational_matrix","arguments":{"matrix":{"domain":"Z","rows":1,"cols":2,"entries":[[2,1]]}}}}
```

The successful second response contains:

- `result.isError: false`.
- `result.structuredContent.assessment: "rational_matrix_certified"`.
- The certificate at `result.structuredContent.receipt.result.certificate`.
- Fresh verification at `result.structuredContent.receipt.result.verification`.
- An explicit `2×1` Q-nullspace matrix with entries `[[{"num":-1,"den":2}],[1]]`.

For a fresh check, submit that certificate under `certificate` **together with
the original matrix** under `matrix`. Do not submit the bridge envelope,
receipt, hash, claimed rank or success label as the certificate. Successful
checking has assessment `rational_matrix_certificate_valid`; its receipt result
contains verification, not a second copy of the certificate.

## Exact input and certificate scope

`MatrixSpec` is exactly an object with `domain`, `rows`, `cols` and `entries`.
`domain` is `Z` or `Q`. Dimensions are nonnegative integers and must agree with
the row lists. Empty shapes remain explicit: `0×3` has `entries: []`, while
`3×0` has `entries: [[],[],[]]`.

An exact coefficient is an integer token or exactly `{"num": a, "den": b}`
with `b > 1`, `a != 0` and `gcd(a,b) = 1`. Zero and integers use integer tokens.
`Z` input permits only integers. Booleans, decimal JSON tokens, strings,
expressions and extra fields are rejected, never coerced. This coefficient
encoding is intentionally different from the older scalar/polynomial tools'
`numerator`/`denominator` encoding; no automatic cross-tool conversion occurs.

The certificate contains exactly `schema`, `matrix`, `rref`, `transform`,
`rank`, `pivots`, `free_columns`, `nullspace`, `operations` and `determinant`.
Its schema identifier is `foundation-math-rational-matrix/1`. For original
`m×n` matrix `A` and rank `r`:

- `matrix` must bind the identical input, including dimensions and Z/Q domain.
- `rref` is a Q matrix of shape `m×n`.
- `transform` is a Q matrix `U` of shape `m×m`.
- `nullspace` is a Q matrix `N` of shape `n×(n-r)`; columns are basis vectors.
- `operations` contains only checked invertible swap, nonzero scale and
  distinct-row nonzero-add operations.
- `determinant` is an exact coefficient for square matrices, otherwise `null`.
  The `0×0` determinant is 1.

The checker replays the row operations on `A` and the identity, checks both
replayed outputs and `U*A=R`, inspects the RREF conditions and ordered pivot
complement, checks `A*N=0` and the free-row identity that establishes independence
and completeness, and checks the determinant relation. Hashes and claimed
verdicts never substitute for those calculations.

Schemas reject unrecognized fields and structural types but are **not a
mathematical verifier**. Runtime checks additionally enforce exact row lengths,
cross-field dimensions, canonical gcd conditions, bit/work limits, legal indices,
invertibility, rank relationships and all matrix identities. JSON Schema's
mathematical integer type alone cannot express the bridge's stronger rejection
of decimal/exponent-form JSON numeric tokens; strict framing enforces that rule.
See the full [data and limits contract](linear-algebra/CONTRACT.md) and
[certificate justification](linear-algebra/CERTIFICATE.md).

## Receipt and non-promotion boundary

Every returned `structuredContent` has `formal_proof: false` and
`runtime_goal_acceptance: false`. Both success and error source receipts repeat
those flags and declare `computational_field: "Q"` and
`scope: "one_explicit_matrix"`.

A success receipt contains `schema_version`, `status`, `operation`, the scope
and trust flags, `request_sha256`, `implementation` and `result`.
`implementation` records its name, version and SHA-256 hashes of six fixed
owned source files. These hashes bind content for reproducibility, not
authenticity or proof. The result contains `ok: true` and `verification`; only
certification also returns `certificate`. Verification's `accepted: true`
means the finite exact calculation for that supplied matrix was checked.

An error receipt contains `schema_version`, `status: "error"`, the scope and
trust flags, and `error: {code, message, path}`. It has no `result`, certificate,
partial calculation, accepted claim or success provenance. The bridge reports
`isError: true` with assessment `tool_error`. Invalid certificate checking is
an error, not a theorem that an alternative rank or determinant is correct.

Z describes the **input coefficients**, never the computational field. In the
`[[2,1]]` example the rational kernel basis `[-1/2,1]` is not even an integer
vector. It is not an integer-lattice basis. No output claims symbolic/generic
rank, rank for a family, geometric identification, a theorem about any other
matrix or formal-proof/runtime acceptance.

The verifier is algorithmically separate from the producer: it neither imports
the producer nor runs elimination. They share canonical parsing, resource
accounting, Python and standard-library `Fraction` arithmetic. This is not an
independently implemented proof kernel or a diverse implementation audit.

## Limits and transport interaction

Matrix hard ceilings remain 16 rows/columns, 256 cells per matrix, 128-bit
input numerator/denominator components, 2048-bit stored intermediate/certificate
components, 1,024 row operations and 2,000,000 charged work units per stage.
Intermediate growth or work exhaustion rejects the request without partial
evidence; neither establishes a mathematical negative answer.

The inherited bridge limits are unchanged:

- Input frame: 65,536 bytes, excluding the final LF.
- Output frame JSON: 1,048,576 bytes, excluding the final LF.
- Structural nodes: 16,384; JSON nesting depth: 80; string length: 4,096.
- Raw JSON integer ceiling: 4,096 bits, before stricter matrix checks.

The matrix backend separately imposes its 1,000,000-byte payload/output limits,
100,000 nodes and depth 32. Both layers apply. Most notably, the bridge input
ceiling is lower than the standalone matrix parser's: **a certificate produced
successfully, or valid in the standalone API, is not guaranteed to fit a later
bridge check request**. The complete wrapper and JSON-RPC envelope also consume
space. A synthetic certificate with 800 cancelling legal scalings verifies
standalone but is rejected by the bridge byte cap in the regression suite.
No transport limit is raised to make it fit and no result is truncated into
apparently valid evidence.

Missing/extra outer arguments produce `-32602`. Exact coefficient/schema,
certificate and backend-limit failures produce structured tool errors.
Malformed/duplicate-key/decimal-number JSON is a `-32700` protocol error;
bridge resource exhaustion is `-32002`. Unexpected backend errors are sanitized
as `-32603` with no evidence result. A valid notification never executes either
new tool. As before, this local API boundary is not an OS sandbox or a hard
CPU/RSS/time guarantee; the launching client owns timeouts.

## Reproducible checks

```sh
python -B -m unittest discover -s tests -p 'test*bridge.py' -v
python -B -O -m unittest discover -s tests -p 'test*bridge.py' -v
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
python -B tools/validate_matrix_bridge_schemas.py
python -B -O tools/validate_matrix_bridge_schemas.py
```

The new bridge regressions cover append-only discovery, explicit schemas,
source-bound deterministic receipts, canonical rational inputs, empty shapes,
integer-to-Q non-promotion, original-matrix/domain binding, malformed and
tampered certificates, producer-independent checking, notifications, sanitized
backend failures, transport/backend size differences, and byte-identical
normal/optimized stdio sessions. They use only tiny synthetic matrix data and
standard-library tests, with no network, installs, credentials or model calls.
The separate optional schema audit requires an already-installed `jsonschema`
package; if missing it reports `unavailable` and exits 2 without installing
anything. It is not a new runtime or unittest dependency. Its 55 replayable
checks validate all advertised schemas, representative actual receipts,
structural rejection and non-promotion. Results are recorded in
`evidence/matrix-bridge-schema-validation.json` and its `-optimized` companion.

The inherited bridge audit retains its mathematical/acceptance backend pins;
v0.6 explicitly exempts only the extended `foundation_math/cli.py` dispatcher
from the former byte-identity gate. That intended baseline change is not a
claim that the historical audit file remained byte-identical.

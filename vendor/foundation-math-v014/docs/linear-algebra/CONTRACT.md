# Data, API, and bounded execution contract

## Matrix input

A matrix is exactly `{ "domain": "Z" | "Q", "rows": m, "cols": n, "entries": [...] }`.

Dimensions are nonnegative JSON integers, never booleans. The outer list must contain exactly `m` rows, each with exactly `n` entries. Empty shapes are not inferred: `0×3` has `entries: []`, while `3×0` has `entries: [[],[],[]]`. All derived matrices also have explicit dimensions.

`Z` input permits exact integer tokens only. `Q` permits an integer or exactly `{ "num": a, "den": b }`, where `b > 1`, `a != 0`, and `gcd(a,b) = 1`. Integers, including zero, must use integer tokens, not rational objects. Denominators are positive. Fractions, strings, symbolic names, expressions, booleans, floats, nonfinite numbers, tuples, and object subclasses are not input coefficient encodings. Integer tokens in `Q` remain `Q`-domain input.

Output matrices always have domain `Q`; canonical fractions use the same encoding. `Z` means integer *input coefficients*, not integer-only row operations or an integer-lattice nullspace.

## Certificate schema

`foundation-math-rational-matrix/1` requires exactly these fields:

- `schema`: the literal schema identifier.
- `matrix`: exact original matrix, including domain and dimensions.
- `rref`: a `Q` matrix of shape `m×n`.
- `transform`: a `Q` matrix `U` of shape `m×m`.
- `rank`: integer `r` in `[0,min(m,n)]`.
- `pivots`: the increasing list of pivot-column indices.
- `free_columns`: the increasing complementary column list.
- `nullspace`: a `Q` matrix `N` of shape `n×(n-r)`. Its columns are basis vectors in free-column order.
- `operations`: an ordered list of invertible elementary row operations.
- `determinant`: a canonical coefficient for a square matrix, otherwise `null`.

Each operation is exactly one of:

- `{ "op":"swap", "i":i, "j":j }`, with distinct valid row indices.
- `{ "op":"scale", "i":i, "factor":q }`, with valid row index and `q != 0`.
- `{ "op":"add", "target":i, "source":j, "factor":q }`, with distinct valid row indices and `q != 0`.

Redundant but legal nonzero row operations are accepted. Zero scalings and self-row additions are not accepted. Acceptance depends on semantic checking, not the producer's particular operation order or a hash.

## Public interfaces

- `produce(matrix: object, limits: Limits = Limits()) -> MatrixCertificate`: deterministic generation or `MathError`; no partial result on resource exhaustion.
- `verify(matrix: object, certificate: object, limits: Limits = Limits()) -> VerifiedMatrix`: independent mathematical checking or `MathError`. The expected matrix is mandatory. The result exposes dimensions, rank, pivot/free-column tuples, and exact `Fraction | None` determinant.
- `VerifiedMatrix.to_dict()`: JSON-shaped accepted result with `accepted: true`, `scope: "one_explicit_matrix"`, `computational_field: "Q"`, dimensions, rank, ordered indices, and canonical determinant.
- `handle_request(request: object, limits: Limits = Limits()) -> dict[str, object]`: checked adapter. `certify` accepts exactly `operation,matrix`; `verify` additionally requires `certificate`. `certify` verifies the output before success.
- `loads_bounded(raw: bytes, limits: Limits = Limits()) -> object`: strict UTF-8 JSON ingress, with duplicate-key, floating-point, giant-token, nesting, and payload checks.
- `python -m exact_linalg`: one bounded stdin JSON request, one compact stdout JSON response, then exit. Not JSON-RPC or MCP; no tools/server interoperability claim. No file paths or process parameters are accepted.

## Limits

The immutable `Limits` object may lower, never raise, these hard ceilings:

| Resource | Default / hard ceiling |
|---|---:|
| Matrix rows or columns | 16 |
| Cells in each matrix, including `U` and `N` | 256 |
| Input coefficient numerator/denominator bits | 128 |
| Stored intermediate/certificate numerator/denominator bits | 2048 |
| Row operations | 1024 |
| Charged arithmetic/checking work units | 2,000,000 |
| JSON input bytes | 1,000,000 |
| Successful JSON output bytes | 1,000,000 |
| Structural nodes, including dictionary keys | 100,000 |
| Nesting depth | 32 |

The input bit ceiling cannot exceed the intermediate ceiling. Limits are validated on entry; booleans are not integers. All operations use exact `Fraction` arithmetic. Each primitive multiply/add/divide charges a unit and checks its bounded operands and reduced result. Verification also charges comparisons, row operations, and matrix checks. This is a deterministic operation budget, not a wall-time/CPU instruction counter. Parsing and allocation are bounded separately by dimensions, bytes, depth, and nodes.

Reduced operands are at most the intermediate bit ceiling; one `Fraction` primitive may temporarily use roughly twice that size (addition can need one further numerator bit) before reduction and result checking. There are no unbounded-expression computations. Work exhaustion or intermediate growth rejects even a mathematically valid problem/certificate; it is not a mathematical negative answer. Producer and verifier charge different work, so a produced certificate can require a higher verifier budget within the fixed ceilings. The combined adapter succeeds only if both stages and the enclosing success response fit.

Lower `max_cells` may reject a small input when its required square row transform or complete nullspace is too large. The input is still mathematically meaningful; the requested complete certificate cannot fit that chosen limit.

The output-byte ceiling applies to successful JSON payloads, excluding the CLI newline. Error responses are small fixed-schema diagnostics (under 512 bytes), not governed by a user-selected output ceiling of zero. No partial certificate or `accepted` field is returned on an error.

## Error codes

`INVALID_LIMIT`, `INVALID_SCHEMA`, `INVALID_INTEGER`, `INVALID_DOMAIN`, `INVALID_COEFFICIENT`, `NONCANONICAL_RATIONAL`, `INVALID_TYPE`, `DIMENSION_MISMATCH`, `CELL_LIMIT`, `BIT_LIMIT`, `WORK_LIMIT`, `OPERATION_LIMIT`, `INPUT_LIMIT`, `OUTPUT_LIMIT`, `NODE_LIMIT`, `DEPTH_LIMIT`, `DUPLICATE_KEY`, `INVALID_JSON`, `INVALID_OPERATION`, `INVALID_CERTIFICATE`, `DIVISION_BY_ZERO`, and `INTERNAL_ERROR` are structured failures, never proof verdicts. Semantic certificate rejection uses `INVALID_CERTIFICATE`; earlier schema/domain/limit failures retain their specific code. The CLI sanitizes unexpected internal exceptions.

## Integer-input non-promotion example

For the `Z` input `[[2,1]]`, the returned nullspace is the single column `[-1/2,1]`. It spans the rational kernel; it is not an integer vector and therefore is not a basis of the integral kernel. The result always says `computational_field: "Q"`. Producing a lattice basis would require a separate exact integer-module algorithm and a different certificate contract; no such claim is made here.

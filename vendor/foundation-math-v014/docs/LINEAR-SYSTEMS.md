# v0.8: checked explicit rational linear systems

The new capability concerns exactly one explicit A,b over Q and one RHS. A
successful solve produces a certificate and independently verifies it against
the original inputs. A supplied certificate is checked against a separately
supplied expected system, including dimensions, the exact domain tag and all
coefficients. Neither an embedded system, a producer receipt nor a hash chooses
the expected mathematical object.

## Interfaces

Python entry points in `foundation_math.linear_systems`:

- `solve_system(system, limits=Limits())`: produce, check and return a receipt.
- `check_system_certificate(system, certificate, limits=Limits())`: fresh check.
- `calculate_system(request, limits=Limits())`: exact fields `operation`, `system`,
  and `certificate` iff operation is `verify`; other operation is `solve`.
- `calculate_system_json(raw, limits=Limits())`: strict bounded JSON entry point.

The system is `{"matrix":{"domain":"Z","rows":1,"cols":1,"entries":[[2]]},"rhs":[1]}`.
This example is consistent over Q with x=1/2. Z restricts input tokens in BOTH
A and b; it does not request integer solutions. Exact canonical rational tokens
are integers or reduced `{"num":p,"den":q}` with p nonzero and q>1. Booleans,
floats, source expressions and noncanonical fractions are rejected.

File CLI:

```sh
python -B -m foundation_math system-solve examples/linear-systems/consistent-system.json
python -B -m foundation_math system-check examples/linear-systems/consistent-system.json examples/linear-systems/consistent-certificate.json
```

`--output` creates a new receipt and never overwrites. Success, including a
verified inconsistency, exits 0; invalid input/certificates and resource errors
exit 2. Unexpected errors in this new CLI route are generic and do not expose
tracebacks. Python structured APIs intentionally allow unexpected programmer
errors to propagate. The unchanged standalone `python -B -m exact_systems`
accepts one operation-envelope request on stdin.

## Exact mathematical acceptance chain

A consistent certificate contains x0 and the unchanged matrix certificate for
A. The matrix checker replays invertible row operations and verifies UA=R,
RREF and rank r. It verifies AN=0 with N of shape n by n-r and the ordered free
rows equal to the identity. This identity submatrix proves independence, and
rank-nullity proves completeness. The system checker separately computes Ax0=b.
Thus the full solution set is precisely x0+N c for c in Q^(n-r), with unique c.
Only N has the schema's fixed free-row normalization; any valid x0 is accepted.

An inconsistent certificate contains y and a nonzero pairing. The checker
computes y^T A=0 and y^T b equal to that nonzero rational directly. If Ax=b,
then y^T b=y^T Ax=0, a contradiction. No claimed rank, producer elimination or
transformed RHS is trusted in this branch. Nonzero rescaling is valid.

Zero dimensions remain explicit. No equations gives Q^n and N=I; no unknowns
gives the empty solution iff b=0, otherwise an inconsistency certificate. A
0-by-0 system has its unique empty solution. Full column rank gives a basis
with zero columns and uniqueness when consistent.

## Receipts and limits

Success has `status: success`, `operation`, request SHA-256, a 13-file fixed
implementation hash map and the frozen checked result. Both certificate
outcomes have `computational_field: Q`, `scope: one_explicit_linear_system` and
false `formal_proof`, `runtime_goal_acceptance`, `family_or_generic_claim` flags.
An error has no `result`, certificate, partial solution or mathematical outcome.
Hashes bind content, not origin/authenticity or truth. The final wrapper receipt
is independently checked against the output cap after adding provenance.

The frozen hard/default ceilings are 16 rows/columns, 256 cells per matrix,
128-bit input coefficient components, 2048-bit reduced intermediate/certificate
components, 1024 row operations, 2,000,000 aggregate charged work units,
1,000,000 input/output bytes, 100,000 structural nodes and depth 32. Trusted
Python callers may lower these caps, never raise them. They are not request fields.

Work is statically partitioned between matrix and system stages; solve further
partitions between production and verification. Unused allotments are not
transferred. Logical work excludes separately bounded parsing/allocation and is
not a wall-clock or exact OS memory limit. Small inconsistency witnesses may be
verifiable when a producer cannot afford its transformation matrix. Resource
failure is always inconclusive, never consistency or inconsistency. See the
unchanged [lab contract](LINEAR-SYSTEMS-LAB-CONTRACT.md) for complete details.

## Trusted boundary and exclusions

All six exact-system modules and all six exact-matrix modules are byte-identical
to the independently accepted lab. The checker imports neither producer nor
combined API. It does share parsing, bounds, Python Fraction arithmetic and the
Python runtime with production. This is algorithmic/import separation, not a
formally verified or diversely implemented arithmetic kernel.

No multiple RHS, symbolic parameters, generic rank, family theorem, integer
lattice/Diophantine conclusion, numerical conditioning, runtime goal acceptance,
claim-ledger promotion or formal proof is added. The prior runtime registry,
work queue, calculators, verifier adapter and eight bridge tool definitions are
unchanged. Only original synthetic test inputs are used, not actual motivating
project/source instances. No network, installs, model calls, repository creation,
publication, credentials or Lean execution are part of this extension.

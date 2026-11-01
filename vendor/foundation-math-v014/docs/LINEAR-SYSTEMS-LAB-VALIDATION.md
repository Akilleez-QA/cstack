# Validation record

This is an isolated engineering handoff, not an integrated release or a formal
proof. Every matrix and right-hand side below was generated synthetically.

## Reproducible checks

Run `PYTHONDONTWRITEBYTECODE=1 python -B tools/run_validation.py` from the lab
root. It runs the complete local test suite and mutation audit in both normal
and optimized Python, then compares pinned dependency/source hashes. The output
and individual transcripts are in `evidence/`.

- **100 tests pass in normal Python and 100 under -O:** 37 system tests and 63
  unchanged frozen matrix regression tests. Runtime checks never depend on
  Python `assert` statements being enabled.
- **861 exhaustive systems:** all A,b with entries in {-1,0,1}, every matrix
  shape m,n in {0,1,2}. An independent oracle computes ranks from exact Leibniz
  determinants of minors, not Gauss-Jordan elimination or producer output.
  It compares rank(A) and rank([A|b]), checks the returned particular solution,
  checks every kernel column, and independently verifies kernel independence.
- **160 seeded rational systems:** dimensions 0 through 5, rational coefficients
  and RHS, checked by the same independent minor oracle. Several affine
  combinations of every returned basis are checked directly against A,b.
- **Maximum-dimension boundaries:** sparse systems with shapes 0×16, 16×0,
  16×16, 8×16 and 16×8, including explicit empty-vector/basis shapes.
- **282 numeric-leaf certificate mutations:** 275 rejected. Seven accepted
  changes were independently confirmed valid, such as altering a free
  particular coordinate for A=0 or an irrelevant left-witness coordinate.
  Requiring rejection of those valid certificates would be an incorrect test.
- **66 changed expected-system mutations:** all rejected. Expected A,b are
  supplied separately; embedded-system claims cannot rebind a certificate.
- Focused negative tests cover missing/extra fields, schema/outcome relabeling,
  altered A/b/domain/dimensions, incorrect particular solutions, incomplete or
  dependent kernels, forged rank/pivots/RREF/U/determinant, noninvertible row
  operations, false left witnesses, zero or false pairings, canonical rational
  rules, boolean/float/string inputs, duplicated JSON keys and UTF-8 errors.
- Resource tests cover every ceiling type, dimensions, per-matrix cell caps,
  input/intermediate bits, operations, aggregate work partition, exact JSON byte
  boundaries, output caps, nodes, depth, cyclic Python data and zero limits.
  Instrumented primitive charges verify the solve pipeline does not reset its
  overall work ceiling across producer/checker stages.
- Fresh-process import isolation shows the system verifier imports neither
  system producer nor matrix producer. Handwritten inconsistency witnesses work
  with the matrix checker disabled. A deliberately false producer output is
  rejected by the checked solve API.
- CLI solve/verify, single JSON-line output, exit status 2 on rejection, no
  traceback, and oversized-input handling are exercised.
- Inputs/certificates are not mutated, and returned artifacts do not alias the
  original user input. Valid noncanonical choices of particular solution and
  nonzero-scaled inconsistency witnesses remain accepted.

## Dependency and source preservation

`VENDOR-PROVENANCE.json` pins all six copied matrix package files and all five
copied matrix-test files by SHA-256. They match frozen v0.6 byte-for-byte.
The complete frozen v0.6 tree had 169 tracked-by-manifest files at the initial
snapshot and remains unchanged, including its original six-tool bridge.

Preservation checks intentionally cover only this lab and its frozen v0.6
input, not active sibling development trees. This lab makes no edits to v0.6
or v0.7; all new files are under `foundation-math-linear-systems-lab`.
No bridge integration was made.

`SOURCE-MANIFEST.json` binds this handoff's source/docs/examples/tests/tool bytes;
volatile test transcripts and evidence are excluded from that source manifest.

## Limits of this evidence

No external independent code review is claimed by the author. The minor-based
oracle is algorithmically independent of the producer, but its tests were
written within this implementation task. Parent-level independent review is a
separate gate before integration.

No Lean executable was run, no formal correspondence was checked, and no runtime
goal was accepted. Exhaustive small systems and random larger ones are not a
proof of all software behavior. Mathematically valid explicit-system results do
not automatically apply to an external problem, an entire family, a generic
rank, integer feasibility or an integral lattice.

No network, dependency installation, live model execution, repository creation,
publication, actual motivating-project coefficients/parameters/evaluation
points/jets, or instance ranks were used.

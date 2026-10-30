# Independent mathematical and implementation review

## Verdict and scope

The frozen standalone exterior-power lab is accepted for its stated bounded,
formal arithmetic scope, conditional on the fixed marked SL2(F5) character-table
identification. No defect was found in the reviewed mathematical core. The
recorded normal and optimized results are the acceptance evidence, not preliminary
trials. A later clean selected-only replay independently rechecks that evidence.

This is not a Foundation Math release or tool registration. It does not establish
an actual equivariant splitting, map, injection, research-object realization,
all-twist theorem, Lean theorem, formal-kernel result, or runtime acceptance.
No real HM instances, selected coefficients/parameters/points/matrices, instance
ranks, network or model calls, software installations or publication were used.

## Frozen identity

- Lab source-manifest SHA256: 89264e3f2d6dd2391f80bf5a1d07292a3748166bef9c60d9ab9f82c3c34d078e.
- Lab ZIP SHA256: a6c32c393e7ebc61af34ec50d1793f6905b85c4d0043847152fc22a79c59eb67.
- Lab ZIP: 371,086 bytes, 56 selected files.
- Catalog SHA256: 84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74.
- Exterior-seed SHA256: 0476eb520e3f8910828b4762fac3e88e16b12ba8f35ebe782c4e357c06ff1656.

`PINS.json` also records every reviewed runtime file's exact size and hash.
`REVIEW-MANIFEST.json` binds this review, its scripts, evidence and selected lab.

## Independent evidence

`weight_oracle.py` is independently authored and imports no lab implementation.
Its exact Laurent eigenweight product in Z[C60], followed by reduction modulo
Phi60, is independent of the producer's seed/fusion convolution, the checker's
graded Adams/Newton computation, and the author's cyclotomic Fourier oracle.
It derives character rows from explicitly marked eigenweights rather than
reading the author's arithmetic results. The README explains the mathematical
construction and its remaining identification assumption in full.

The normal and -O broad suites each compare 910 complete certificates, including
request binding, result coefficients/class values, ranks, degrees, determinants,
parities, assumptions and scope. Covered families are:

- All 81 marked character values, all 81 fusion products, all 9 irrep seed
  polynomials, full orthogonality, dimensions, central signs and class sizes.
- All 9 classes at powers 0 through 25: 234 explicit power-class checks,
  with independent Adams trace evaluations across all 9 irreducible rows.
- All 164 genuine representations of dimension at most 8, every exterior order
  through rank+1, and all 219 multisets of 1 through 3 physical irreps.
- Maximum allowed repeated multiplicities for all 9 irreps and rank/order-zero
  and above-rank controls, with explicit physical W/Wp and A/V preservation.
- All 378 unordered two-block bundles from the 27 atoms formed by 9 irreps and
  degrees {-1,0,1}, and all 81 ordered irrep pairs at degrees {-16,+16}.
- 32 deterministically selected mixed multiblock bundles within the stated bounds,
  all exterior orders through rank+1. This is a sampled stress family, not an
  exhaustive rank-24 bundle claim.
- 45 direct-sum identities, binomial dimensions, graded-degree formula, determinant
  character and line degree, and dual/complement identities.
- 16 formal H0 comparison requests, including degree-zero and negative-degree
  cutoffs, source/target zero, order zero, above-rank zero, twist boundaries and
  the symmetric-degree-400 boundary.

Additional normal/-O focused tests verify the negative extreme line degree -384,
certificate byte bounds, data-depth/value bounds, exact integer bit bounds and
rejection of an equivalent but noncanonical rational encoding. The positive
extreme +384 is in the broad suite.

The exact input/certificate boundary checks include 53 malformed requests against
each public entrypoint; 16 malformed/type/oversized JSON payloads; 19 certificate
mutations; a separate external-request binding mutation; 2 successful CLI flows
and 6 structured CLI rejections. Cycles, bools, floats, unknown physical labels,
extra actual-map/proof fields, custom dictionaries, excess orders, excess blocks,
excess rank and out-of-range twists are rejected. The verifier imports neither
the producer nor fusion module. No production correctness check relies on assert.

All 14 distributed request/certificate pairs separately agree with the independent
oracle and checker in normal and optimized modes.

## Source mutations

All 16 independently defined semantic source mutants are detected in both modes,
with a pristine control for every test shape. Mutants change Newton signs or
division; replace Adams with scalar multiplication or pointwise powers; confuse
identity and center powers; omit the graded Adams exponent; swap W/Wp or A/V;
lose repeated copies; change producer line-degree exponents or a fusion cell;
change module or bundle center parity; omit degree-zero H0; reverse the signed
comparison; or accept an oversized representation rank.

A syntax/import/unexpected runtime crash is not accepted as detection. The
recorded detections are exact-oracle mismatch, a domain rejection of a valid
input/certificate, or acceptance of the expressly forbidden rank. The author's
separate 10 targeted source mutations and 17-test aggregate also pass in both
modes. These are selected fault models, not proof that every defect is detectable.

## Exact scope of the illustrative obstruction

The actual supplied operands are U=S4 tensor O(-1) and
T=(W direct-sum Wp) tensor O(-1). Writing R=(W direct-sum Wp) tensor O(1)
is consistent only when recognizing that T=R(-2); the API adds no hidden shift.

At twist 6:

- Both ordinary H0 representations are A+2D+2P+V.
- The Lambda^2 target-minus-source difference is D-P-1.

At twist 1, however, the ordinary difference is already W+Wp-S4. Thus the
example proves that the second exterior comparison is stronger than the one
ordinary comparison at twist 6, not that it detects a failure missed by all
ordinary twists. This qualification is essential and is preserved here.

The comparison twist is applied after exterior formation. It is
H0((Lambda^k E)(t)), not H0(Lambda^k(E(t))). A negative multiplicity difference
is only a conditional obstruction under separately justified actual geometric
hypotheses; a nonnegative result is never map-existence or injectivity evidence.

## Freeze, portability and original baseline

The author supplied a stable core, then a frozen selected archive. The reviewer
safely extracted only its explicitly selected files, independently checked their
bytes and hashes, and ran the selected-only author aggregate and deterministic
ZIP rebuild. The final mathematical runtime, tests and examples remained
unchanged throughout review.

A packaging-only issue was identified: inherited PYTHONOPTIMIZE could make an
advertised normal stage optimized. The author hardened child environments and
checks actual reported modes. The final frozen aggregate was independently
launched with PYTHONOPTIMIZE=2 and still reports tests/mutations modes (0,0) and
(1,1). `freeze-transition.json` proves the change was limited to three packaging
scripts, validation documentation, author evidence and the source manifest.

A reviewer-only malformed-input fixture initially computed dimensions before
submitting an intentionally unknown label. That fixture was corrected, its
boundary family passed independently, and the final broad suites were rerun.
The failed preliminary harness executions are not counted as accepted evidence.

The original v0.13 baseline is byte-for-byte unchanged across its complete
460-file, 12,998,300-byte regular-file set. An independent AST read confirms the
same 16 bridge tool names. The original historical test suite was not rerun;
this is preservation evidence, not a new claim about those historical tests.

The portable reviewer artifact contains only its selected code/evidence and the
56-file frozen lab, without the original baseline checkout or other workspace
dependencies. Its replay verifies its own full manifest, executes independent
normal/-O tests, mutants, examples and focused boundaries, reruns the selected
lab aggregate, and reproduces the exact pinned lab archive. Replay uses no
network or installations. Recorded timings are observations, not performance
guarantees.

## Remaining obligations

1. The physical catalog-to-group identification remains a pinned mathematical
   assumption, not a theorem proved by hashing, orthogonality or these programs.
2. Arithmetic testing covers precisely the finite families listed above, not
   every admissible input of rank 24 or every possible implementation defect.
3. No automatic Foundation Math acceptance, Lean proof or runtime bridge is added.
4. Any actual research application must independently establish its equivariant
   splitting, geometric hypotheses and interpretation of necessary comparisons.

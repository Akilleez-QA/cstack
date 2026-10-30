# Independent polynomial-witness integration review

## Disposition

No unresolved defect was found in the reviewed v0.7 wrapper, two appended bridge
routes, strict schemas, or new CLI routes. This is a bounded engineering and
mathematical-computation review, not a formal proof, security sandbox, or claim
that all accepted inputs have been exhaustively tested.

The reviewer authored only `tests/test_v07_independent_review.py`,
`tools/audit_polynomial_witness_integration.py`, and this report. Integration
source changes were made by the implementer. Only original tiny synthetic
polynomials were used by this new review. No research-instance inputs,
credentials, installs, network calls, or repository operations were used.

## Verification performed

- All 29 independent integration regressions pass normally and with `-O`.
- The independent deterministic audit passes 9,184 explicit checks in each
  mode, using 100 expression requests (36 coefficient identities and 64
  concrete mismatches), plus all 728 nonzero bivariate quadratics with
  coefficients in {-1, 0, 1}. Dense coefficient and original-AST evaluation oracles
  are implemented in the audit, not imported from the producer.
- The complete integrated suite was independently rerun normally and with
  `-O`: 466 tests, no failures, and one inherited real-Lean test skipped because
  Lean is not available. These complete reruns include the final strict
  escaped-duplicate-key regression.
- Optional schema checks used already installed `jsonschema` 4.26.0. No install
  or runtime dependency was added. All eight advertised schema pairs validate;
  actual new-tool success, identity, rejected-witness and error receipts conform.
- Both CLI and fresh stdio-process normal/optimized transcripts match exactly.
  The audit transcript has seven frames including one silent notification,
  producing six responses with SHA-256
  `6f1af7b8d4b8928d515180e8b6d2931a5b484dd4763868afb6f765188b66b60e`.
- All six inherited tool definitions are compared against independently
  recorded canonical SHA-256 pins, not merely against copied metadata.
- All nine witness-lab Python files are directly pinned. Legacy runtime,
  scalar, polynomial, finite-box and matrix source files remain preserved.
  Independent readback of both frozen external snapshots matched every stored
  file: 169 v0.6 files and 47 witness-lab files, with no mismatches.

The audit emits the exact source hashes and current counts as JSON. Rerun:

```sh
python -B -m unittest discover -s tests -p test_v07_independent_review.py -v
python -B -O -m unittest discover -s tests -p test_v07_independent_review.py -v
python -B tools/audit_polynomial_witness_integration.py
python -B -O tools/audit_polynomial_witness_integration.py
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
```

## Independent challenge of the stronger trial bound

The sharper theorem for the same sequential algorithm is valid: for nonzero
normalized p of total degree D, the chosen coordinates satisfy sum a_j <= D,
and the actual trial count is n + sum a_j <= n + D. The current constructor
caps therefore imply at most 40 trials, with no changed frozen implementation.
See the independently read [complete proof](POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md).

The key argument survives the relevant pitfalls:

- Failure at an earlier coordinate means the entire residual vanishes as a
  polynomial in the remaining variables, not merely at one sampled point.
- Monic division works over the coefficient ring. After removing earlier
  root factors, their value at a distinct integer root is a nonzero rational
  unit, so the next factor divides the quotient as well.
- Nonzero highest homogeneous parts cannot cancel their product in the
  polynomial domain. Removing a_j root factors costs exactly a_j total
  degrees; the chosen specialization can only lower the quotient's degree.
- Telescope D_next <= D_current - a_j down to the final nonzero constant.
  Empty products, unused variables, nonzero constants and zero variables
  cause no exception. Zero polynomials use the separate identity branch.

The independent sparse oracle checks every preceding zero specialization and
per-step degree inequality for 728 nonzero bivariate quadratics. It finds 72
sharp n+D cases and 752 strict extra degree drops. Focused tests also check:

- Degree-32 falling factorial with seven unused variables attains exactly 40
  trials. A 40-trial user limit succeeds and a 39-trial limit fails closed.
- The sum of eight 32nd powers has old current/initial degree bounds of 264,
  but only nine actual trials and new conservative executable cap 40.
- High syntactic degrees can cancel to a degree-one normalized difference.
- Bound metadata performs no second normalization and does not claim actual D.
- n comes from the original validated request, and selected coordinates from
  the accepted point check. Contradictory producer count metadata is withheld.
- A valid nonminimal supplied point may exceed the constructor's coordinate-sum
  bound. The fresh checker still accepts its true mismatch without attaching
  constructor metadata.

Only nonzero construction successes add `construction_bound`. It reports the
conservative cap n+32, not actual n+D; the legacy hard limit remains 264.
`exact_difference_degree_recomputed` and `point_checker_certifies_bound` remain
false. This is an improved bound on substitution trials, not a measured speedup,
arithmetic-complexity bound, independently certified trace or Lean proof.

## Trust and evidence boundaries checked

1. Every wrapper outcome names unrestricted formal Q-polynomials,
   characteristic zero, and explicitly denies formal-proof and runtime-goal
   acceptance. The original runtime registry and acceptance code are unchanged.
2. Coefficient identity means exact zero normalization. It is neither failed
   point search nor an independently point-checked identity proof. The identity
   branch has `verification.status = not_applicable`, no witness and no trials.
3. Every constructed mismatch is freshly checked against the original AST.
   Tests substitute a false producer witness and prohibit producer/normalizer
   calls during fresh checking. No unchecked mismatch result is promoted.
4. Supplied wrapper receipts, claimed acceptance, forged hashes, altered exact
   values, false points, wrong rings and rebinding attempts do not substitute
   for a witness. Raw and normalized request bindings remain distinct; an
   equivalent rational literal representation is still a different original
   request. Hashes provide integrity bindings, not authentication.
5. Fresh checking accepts truthful alternative points, not just the producer's
   first point. A manually constructed point for x^33 is accepted even though
   normalization hits its degree cap. This is deliberate: the checker proves
   only a concrete mismatch by bounded original-AST evaluation and does not
   establish construction success, trace minimality, or degree-bound claims.
6. Rejected witness evidence is distinct from resource failure. The bridge
   returns `polynomial_witness_rejected` with `isError = false`; resource or
   expected-request errors return `tool_error` with `isError = true`. Neither
   means that no other witness exists. Error/rejection wrappers carry no
   mathematical result, implementation receipt, or successful request hash.
7. Strict bounded snapshots reject non-JSON objects, floats, overlarge integers,
   excessive nodes/depth and cycles. Duplicate escaped JSON fields, exact raw
   byte limits, complete output-envelope limits and CLI request/witness limits
   are exercised. A failed output/provenance check withholds the full result.
8. New bridge input schemas admit only fixed request/witness fields. No caller
   paths, code, commands, limit overrides or acceptance flags are exposed.
   Notifications execute neither new tool. Unexpected bridge failures and
   provenance failures do not disclose exception details. CLI output uses
   exclusive creation and cannot overwrite its own input.

## Issue found and resolution

Appending the two tools exposed old six-tool-only assertions and last-two-tool
matrix selectors in inherited development tests/tooling. The reviewer reported
this immediately without changing integration source. The implementer updated
v0.7 discovery expectations and selected the matrix tools by name. Subsequent
full normal/optimized tests and matrix schema validation passed. The actual six
inherited tool contracts and both frozen source snapshots were not modified.

## Limits of this review

The producer and checker share the typed parser, canonical hashing, Python
`Fraction`, interpreter, and resource-enforcement helpers. Independent control
flow does not make them a diverse proof kernel. Source hashes record reviewed
bytes, not correctness or provenance authenticity. Schema checking is structural
and does not verify coefficient arithmetic or witness truth. A passing finite
suite is not an exhaustive theorem, and Lean was not run.

## Reviewed source hashes

- `docs/POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md`: `c61ce7e673bdf81fa7470b4630b205677cc69711f38a50d11908fdd50b34bd7e`
- `foundation_math/cli.py`: `5d5f4f8376d0097a3e743fdf29400e3ab126b17ec26328737834753d0cc29b91`
- `foundation_math/polynomial_witness.py`: `69246c388588a34406dd28e363660df350c20f1fd4fb5207e32a2a87172666cc`
- `foundation_math_bridge/polynomial_witness_schemas.py`: `3c82616dc81ad7588cd3b8ef18d0df52da36b82b05c06e195e020557aee47c10`
- `foundation_math_bridge/schemas.py`: `7cfbafdca107a1986f9d48573650858c7879588f4d67876dd168923b2d1028a0`
- `foundation_math_bridge/server.py`: `5a69f0fb47cfad4ad3e77a0e17e65a11c7ef758288f06727ebd0ea0fa62272e4`
- `polynomial_witness/_vendor/calculator.py`: `146ec4fc9fca0c3400331c06595894fd9cb6a23668abae5c7b8d196e06bad54e`
- `polynomial_witness/_vendor/polynomial.py`: `b700a069e0af9609a7b9e63d6a8185d9b430630d6d2f55f5a6ac2e5155022b9b`
- `polynomial_witness/api.py`: `b5d43b961ea87df91ab65248c53ffb8a6917d6b31c63bb295c0e8d0308ecf01b`
- `polynomial_witness/checker.py`: `b2c0a826e0769ec3c65f082c3115b455ef9841154229d1a820e19f528a00891c`
- `polynomial_witness/contract.py`: `d7d3aa19dcb6d1fccff25e3ce94723d4e7fb6ed56802a8986fd7eb2b83ba50dc`
- `polynomial_witness/producer.py`: `a26f8c10f085bebe3fb42cc3ca0581670067a75007634182336bf4c902da0129`
- `tests/test_v07_independent_review.py`: `b50a2545dde656d8c8f00d0a015d12af5c882e6a8997a8aefc8ab7671f7af7c1`
- `tools/audit_polynomial_witness_integration.py`: `95e99bd4924cc308800ef6c4f1975f49529398bd28e9597e77f29304458d9c24`

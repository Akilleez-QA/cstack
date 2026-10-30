# Local validation record

The final local validation command is:

```sh
python tools/run_validation.py
```

It runs both normal and optimized (`-O`) unit tests, independently implemented
oracle checks in both modes, all CLI examples, frozen-source provenance checks,
and source/evidence hash matching. Results are written in `evidence/validation.json`.
No safety check depends on Python `assert`; test and oracle checks survive `-O`.

## Executed coverage

- **48 unit tests in each mode.** Zero polynomials, constants, empty-variable
  rings, unused variables, a false-square identity, exact rational constants,
  falling factorials with roots 0 through 31, sparse multivariate products,
  dynamic degree drops, deterministic output, and detached output metadata.
- **300 independent semantic cases in each mode:** 106 exact identities and
  194 nonidentities. These include 19 named cases, exhaustive testing of 81
  bivariate polynomials with four coefficients in {−1,0,1}, and 200 seeded
  synthetic expression pairs.
- The oracle directly evaluates ASTs on tiny syntax-degree-bounded grids,
  independently finds the first nonzero point, and recovers actual residual
  degrees by scalar finite differences. This testing oracle deliberately uses
  a grid; the production constructor does not.
- **25 witness tamper controls**, **14 cap/error controls**, and **19 malformed
  ingress controls** in each independent audit, plus unit-test boundary cases.
- Checker independence is tested with producer functions and polynomial
  normalization/arithmetic functions replaced by functions that fail. The
  concrete-point checker still accepts a valid witness. Import-only testing
  also verifies that importing the checker does not load the producer.
- **17 JSON CLI examples**, including successful witnesses, exact coefficient
  identities, standalone verification, and deliberately rejected scope/degree
  requests.
- Frozen `polynomial.py` and `calculator.py` source hashes remain equal to
  their original snapshot hashes. Both oracle evidence files bind the final
  runtime source bytes.

Representative constructed results:

| Synthetic input | Point | Mismatch | Trials |
|---|---|---|---:|
| (x+y)² = x²+y² | x=1, y=1 | 2 | 4 |
| ∏(x−i), i=0,…,31, equals 0 | x=32 | 32! | 33 |
| Product of eight declared variables equals 0 | all 1 | 1 | 16 |
| Product of three four-root falling factorials equals 0 | all 4 | 13,824 | 15 |
| 1/2 = 1/3 in the empty-variable ring | empty assignment | 1/6 | 0 |

The eight-variable product's 16 substitution trials contrast with a 256-point
binary Cartesian grid; the algorithm keeps a nonzero symbolic residual rather
than trying all complete assignments. This is an illustrative trial count,
not an asymptotic runtime benchmark.

## Evidence and limitations

- `evidence/unit-tests-normal.txt` and `unit-tests-optimized.txt` retain actual
  test output and counts.
- `evidence/audit-normal.json` and `audit-optimized.json` retain independent
  cases, negative controls, boundary findings and source hashes.
- `evidence/example-replays.json` retains actual CLI responses and exit codes.
- `SOURCE-MANIFEST.json` hashes the local code, documentation, provenance and
  synthetic examples; generated evidence is excluded to avoid self-reference.
- `VENDOR-PROVENANCE.json` identifies the two byte-frozen source dependencies.

The review found no blocking correctness defect in this scope. Two wording
clarifications were applied: small per-variable bounds belong to constructed
witnesses, not arbitrary accepted nonminimal points; the `not_applicable`
identity verification field is supplied by `construct`, not standalone
`produce`. A transient syntax typo in an example-generation command was fixed
before any example files were written; all final example replays succeed with
their documented success/rejection statuses.

This is finite software validation and source review, not exhaustive correctness
or proof-assistant verification. The identity branch relies on the shared frozen
normalizer, not an independent identity certificate. The checker shares the typed
parser, canonical hashing, Python integers/Fraction and runtime. Trace correctness
is tested but not part of concrete-witness acceptance. No external CAS, network,
model, credentials, installation, repository changes or application research
objects were used.

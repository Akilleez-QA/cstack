# v0.4 bounded-counterexample validation

This is a local development snapshot for parent review, not a publication or a
claim of formal verification. Reviewed and exercised on 2026-10-24.

## Executed tests

- Full integrated suite: **232 tests run, 231 passed, 1 skipped**, both normally
  and with Python `-O`.
- The one skip is the real-Lean arithmetic smoke test. The availability check
  returned `unavailable`, `verification: not_run`, `formal_proof: false`.
- The 44 new standalone unit tests pass in both modes. The inherited v0.3 suite
  is still present. Nine integration tests cover CLI routes, witness checking,
  output non-overwrite and the boundary against runtime proof promotion. Nine
  additional independent adversarial regressions cover domain/constraint binding,
  point counts, forged witness evidence, runtime non-promotion and the lowered
  host serialization limit.
- A separately implemented reduced-integer-pair/gcd oracle passes **383 search
  requests and 1,180 fresh witness checks** in each mode.
- The independent audit additionally passes 57 malformed object requests,
  22 JSON controls, 19 assignment controls, 7 resource controls and 7
  self-consistently rehashed tamper controls in each mode.
- Source snapshots were stable across each validation run.

The independent oracle does not import production parsing, evaluation or hashing
internals and does not use Fraction. Its deterministic corpus includes generated
small boxes, all relation types, constrained/vacuous cases and constant cases.
This is independent executable testing, not exhaustive input-space validation or
a mathematical proof of software correctness.

## Critical acceptance controls

1. A successful finite-box search does not register that domain as an accepted
   runtime proof goal. The v0.3 domain registry and verifier remain unchanged.
2. x*x - x = 0 exhausts the finite integer box {0,1}, but the formal polynomial
   identity in Q[x] remains rejected by the runtime. Including the bounded
   receipt in a proposal's rationale cannot change that result.
3. x*x - x >= 0 exhausts [-3,3] on integers. The rational point 1/2 yields -1/4
   under separate rational arithmetic, but the integer checker rejects it as
   out of domain rather than accepting it as a witness.
4. False assertions outside the constraints are not counterexamples. Empty
   eligible sets are exposed by `eligible_count: 0`.
5. Unsupported syntax, malformed requests and resource errors never become
   `no_counterexample_in_declared_finite_domain`.
6. Checker calls recompute from the original request and assignment; supplied
   producer verdicts do not authorize witness acceptance. Hashes alone cannot
   authenticate or establish the mathematical evidence.

## Post-lab review correction

Independent integration QA found that the direct object APIs could raise during
final receipt hashing when the host integer-to-decimal conversion limit was
lowered to 640 digits. The bounded arithmetic result could fit the 4,096-bit
value cap while exceeding this host representation limit. JSON wrappers had
caught the same error, but the direct APIs did not.

The v0.4 copy now treats final result/evidence serialization as part of the
fail-closed computation: it returns `representation_limit`, `result: null`,
`result_sha256: null`, and `complete: false`. Representable error receipts retain
a recomputed evidence hash. If the host cannot even serialize the bounded error
metadata, the evidence hash is explicitly null rather than invented. No process-
global conversion or recursion limit is changed. The frozen lab and earlier
source trees are preserved rather than silently rewritten.

## Scope and remaining limitations

Search and witness checking share production parser/evaluator code. The checker
is separate from producer output, not an independently implemented proof kernel.
Exact completeness applies only to the declared finite integer box. Syntactic
and intermediate resource bounds conservatively reject some expressions that
would simplify to small results. Malformed/noninteger/oversized assignments are
not captured or hashed, as documented in the API contract.

No live model, real Lean proof, actual HM instance, external write, install,
credential operation, Git repository or publication was used. The host, Python,
Fraction and stable implementation source remain part of the trust base.

## Reproduction and evidence

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/run_counterexample_validation.py
python -m foundation_math lean-status
```

Machine-readable reports and test logs are in `evidence/`. The full source
inventory is `SOURCE-MANIFEST.json`. The immutable v0.3 base inventory is retained
as `docs/BASE-V03-SOURCE-MANIFEST.json`, whose SHA-256 is
`97a30118a3b75595451f6075d3d134f44c1bb1ed37358685ccb330eb2f00276d`.
The integration core includes a post-lab host-representation hardening fix:
`6ae3f45d62563f7283491059913a3ecdf93326bc641ebb64b2c42a58292c42a0`.
The frozen standalone lab remains unchanged; its earlier core hash is
`204617bbe6fccaa011927b4c2ffadf668efa0ea7f188bb6d10678cf4b17c7f3d`.
`COUNTEREXAMPLE-VENDOR-PROVENANCE.json` binds the unchanged parser snapshot.
These hashes are content identifiers, not signatures or proofs.

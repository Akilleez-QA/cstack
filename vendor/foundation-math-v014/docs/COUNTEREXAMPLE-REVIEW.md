# v0.4 independent bounded-counterexample review

Reviewed on 2026-10-24. This focused review covers the finite integer-box search,
fresh witness checking, their integration, and the boundary against promoting
bounded evidence into runtime theorem acceptance. It is not a full security
audit, exhaustive correctness proof, formal-kernel check or new mathematical
result.

## Verdict

No outstanding blocker was found for the documented, local bounded tool after
one reproduced receipt-serialization defect was corrected. Evidence remains
restricted to the specified finite integer box and constraints. Finite exhaustion
does not establish an unrestricted identity or universal theorem.

## Executed evidence

- Full suite, normal Python: **232 tests run, 231 passed, 1 skipped**.
- Full suite, Python `-O`: **232 tests run, 231 passed, 1 skipped**.
- The skipped case is the optional real-Lean arithmetic smoke test. No real Lean
  proof was executed or established by this review.
- Added **9 independent regression tests** in
  `tests/test_counterexample_runtime_adversarial.py`.
- Those tests include **36 relation/constraint combinations**, independently
  enumerated using ordinary integer arithmetic. They check ordering, cardinality,
  visits, eligibility, first witnesses and completeness on three-variable boxes,
  including a declared variable not used in the predicates. They also perform
  **72 fresh endpoint witness checks** for those requests.
- Independently reran `tools/independent_audit.py` after the correction in both
  modes. Each run passed **383 search requests and 1,180 witness checks**, plus
  malformed-input, resource and self-consistently rehashed tamper controls:
  **487 named audit checks passed, zero failed**.
- The audit's mathematical oracle uses independently implemented reduced integer
  pairs, gcd and cross-products, not production parser/evaluator/hash internals
  or `fractions.Fraction`. It remains finite test evidence, not a proof kernel.

Reproduce from the integration tree:

```sh
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python tools/independent_audit.py
python -O tools/independent_audit.py
```

## Defect reproduced and corrected

The direct object APIs could raise a Python integer-to-string `ValueError` while
finalizing a receipt under a host decimal-conversion limit of 640 digits. A valid
zero-variable request with a product of ten rational literals, each with numerator
`(1 << 250) - 1` and denominator 1, produces an approximately 2,500-bit value.
That is within the tool's 4,096-bit evaluation limit but exceeds the stricter
host's decimal representation limit. Both search and witness checking leaked the
exception from final receipt hashing. JSON wrappers happened to catch it.

The corrected finalization path returns a structured `representation_limit`
error, clears the result and result hash, clears completeness, and binds the
error evidence when representable. It never changes the interpreter's global
limit. The isolated regression verifies both object APIs return JSON-serializable
error receipts and that the host limit remains 640. Normal and optimized tests
pass against the corrected source.

## Adversarial boundaries checked

1. An early witness is not finite exhaustion. A witness at the final point may
   have `complete: true`, but its outcome remains `counterexample_found`.
2. The empty Cartesian product contains one assignment. False assertions can
   yield a witness `{}`; impossible constraints instead produce explicit vacuous
   finite exhaustion with zero eligible points.
3. Witness checking binds the supplied original request. Changed bounds or
   constraints invalidate stale witnesses and change request hashes.
4. A forged receipt can be self-consistently rehashed without becoming credible.
   The checker does not accept a receipt as an assignment and recomputes the
   candidate's assertion and constraints rather than trusting producer flags.
5. Work-budget exhaustion after partial enumeration is an error with no result
   and `complete: false`, never a successful no-counterexample outcome.
6. Executable-looking expression text and unsupported call nodes are rejected;
   they do not start subprocesses or shell commands.
7. Exhausting `x*x - x = 0` on the integer box `{0, 1}` does not prove that formal
   identity in Q[x]. Even a rehashed receipt falsely claiming universal/formal
   proof, placed in proposal rationale, cannot change runtime rejection.

## Preserved acceptance boundary

The integration's `domains.py`, `orchestrator.py`, `polynomial.py`, `calculator.py`
and `lean_adapter.py` match their v0.3 base-manifest hashes byte for byte. The
runtime's domain allowlist still excludes `finite_integer_box`; search receipts
are not imported as goal acceptance or formal proof. The retained v0.3 source
inventory was also checked against its base manifest without discrepancies.

## Remaining limitations

- Search and fresh checking share production parsing/evaluation code. Fresh
  checking is independent of producer verdicts, not an independent proof kernel.
- Completeness concerns only the explicitly bounded integer domain, not all
  integers, rational numbers, real numbers or a larger box.
- The coefficient field Q does not make rational assignments admissible.
- Hashes bind content, not identity, authenticity, loaded-code attestation or
  mathematical truth. Stable trusted code and host infrastructure remain assumed.
- Resource limits are conservative, including intermediate values and syntactic
  degree. Failure is not evidence of exhaustion or of a false assertion.
- No live model, actual HM-instance experiment, installation, credential action,
  remote publication or real Lean verification was performed by this review.

## Reviewed source pins

- `bounded_counterexample/core.py`: `6ae3f45d62563f7283491059913a3ecdf93326bc641ebb64b2c42a58292c42a0`
- `bounded_counterexample/_vendor/polynomial.py`: `b700a069e0af9609a7b9e63d6a8185d9b430630d6d2f55f5a6ac2e5155022b9b`
- `bounded_counterexample/_vendor/calculator.py`: `146ec4fc9fca0c3400331c06595894fd9cb6a23668abae5c7b8d196e06bad54e`
- `foundation_math/counterexample.py`: `da0c0a8c7993e65825794a321aca847bdc208d880c0bbb09abd256415a87c3c8`
- `foundation_math/domains.py`: `54ad911521b8828fe9daab85e6f686b73f1eb7c4892890c2f034334631989b0d`
- `foundation_math/orchestrator.py`: `9744c44f132294c1933bc726bf8eaeffc3f56ed79c469153d1bef085d4f45114`
- `tests/test_counterexample_runtime_adversarial.py`: `44d3a946abcb862f06b905744435349d5e3c38b8467c3000a77b6b4b67af00cc`
- `tools/independent_audit.py`: `cc1a900bbedd71b76b0e97377c22959444783bc0b930e23b7c991e661ef3d96a`

Later changes require proportionate re-review and fresh validation. These pins
identify reviewed bytes; they are not signatures or correctness certificates.

# v0.3 local readiness review

Reviewed on 2026-10-24. This is a focused implementation and acceptance-boundary
review, not a full security audit, formal proof of software correctness, or new
mathematical result.

## Verdict

No confirmed defect or blocking regression was found for the documented local,
deterministic v0.3 domain-aware work queue. The code is ready for continued local
experimentation within that scope. It is not an autonomous theorem prover or a
hostile multi-tenant execution service.

## Executed evidence

- Full suite, normal Python: **170 tests run, 169 passed, 1 skipped**.
- Full suite, Python `-O`: **170 tests run, 169 passed, 1 skipped**.
- The skipped test is the real-Lean arithmetic smoke test. Lean availability
  returned `unavailable`, with `verification: not_run` and `formal_proof: false`.
- The new independent adversarial suite has **12 passing tests**. Its generated
  acceptance control checks 25 constructed rational-coefficient distributivity
  identities and 25 deliberately false variants, for **50 goal-level cases**.
- Eight scalar workflows were compared against the unchanged v0.1 implementation
  in both modes, for **16 matching comparisons**. Compared fields were goal
  status, proof status, result, attempt count and task states. These include the
  original successful and rejected examples and six scalar arithmetic cases.
- File inventories of the delivered v0.1 and v0.2 source snapshots were unchanged
  across that compatibility check. Tests did not modify those snapshots.
- The verification receipt's acceptance-source hashes matched `domains.py` and
  `orchestrator.py`; its goal-request hash matched the full canonical request.

Reproduce the self-contained tests from this tree with:

```sh
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python -m foundation_math lean-status
```

The independent regression file is `tests/test_domain_runtime_adversarial.py`.
The cross-version comparison used the separately retained v0.1 snapshot, so it is
additional local evidence rather than a prerequisite for this tree's test suite.

## Acceptance boundaries checked

1. A successfully executed polynomial comparison with `equal: false` does not
   establish the identity, even when the provider correctly predicted false.
2. Admission and verification bind the full raw goal AST, operation, coefficient
   field, ordered variable list and candidate result. Case-distinct variables
   and exponent coordinates are not silently aliased. Algebraically equivalent
   but differently encoded proposals cannot substitute for the pinned goal.
3. A formal-proof requirement stays unsatisfied after a successful scalar,
   polynomial-identity, polynomial-addition or polynomial-multiplication check.
   The verifier records the exact success but blocks goal acceptance.
4. Injected provider status/evidence flags, fabricated Lean receipts and attempts
   to change the detached problem's requirement do not promote acceptance.
   A mocked Lean adapter is not called by this queue and cannot close the goal.
5. An attacker-rehashed receipt chain can remain internally hash-consistent while
   containing the wrong ring or a forged `equal: true` result. Trusted replay
   still rejects both cases. This exercises semantic verification separately
   from integrity checking.
6. Inherited scalar workflows retain their exact results, rejection behavior,
   task states and non-formal proof status.

No new implementation defect was reproduced during this v0.3 review. Existing
component regressions and the new independent controls all passed.

## Remaining limitations

- No live model was run. The provider fixture remains deterministic.
- No real Lean kernel check was run. The queue intentionally does not consume
  Lean receipts, and formal-proof requirements remain blocked.
- Replay shares the calculator implementation; it is not an independent proof
  kernel. Generated examples and test oracles provide finite software evidence.
- Source hashes and receipt chains are integrity bindings, not signatures,
  loaded-code attestations, provenance verification or mathematical truth.
- Natural-language goal/assumption correspondence remains unchecked. Polynomial
  equality over the specified Q-ring does not prove a broader geometric claim.
- The host, trusted Python integrations and stable source tree are trusted. This
  is not a sandbox for arbitrary plugins, source changes or native executables.
- Expanded evidence can exceed the queue's 64 KiB receipt limit even if a
  standalone polynomial request succeeds. The runtime fails closed in that case.

## Reviewed code and tests

- `foundation_math/domains.py`: `54ad911521b8828fe9daab85e6f686b73f1eb7c4892890c2f034334631989b0d`
- `foundation_math/orchestrator.py`: `9744c44f132294c1933bc726bf8eaeffc3f56ed79c469153d1bef085d4f45114`
- `foundation_math/polynomial.py`: `66d61b69e274565d187f1a0bc836a4102a94a6e88898f6611fbd549dd97a0648`
- `foundation_math/calculator.py`: `146ec4fc9fca0c3400331c06595894fd9cb6a23668abae5c7b8d196e06bad54e`
- `tests/test_domain_runtime.py`: `f7c6361f8f15fcfe0d7958ace49af9b0939a927a13f654f31ac8a7d74d50d6ce`
- `tests/test_domain_runtime_adversarial.py`: `2a0ebcf9c5c8d44eca47c0e7faf44550d936da4a3dcdff97ee2536f48c22ebf0`

These SHA-256 pins bind the review to the listed source bytes. Later changes
require proportionate re-review and test reruns.

# Validation record: v0.3 domain-aware runtime

Checked 2026-10-24 against the source files in `SOURCE-MANIFEST.json`. This
extension is a new local tree; delivered v0.1/v0.2 trees were not edited. Scalar
calculator, CLI and restricted Lean adapter source remain unchanged from v0.2.
The polynomial algorithm is unchanged; its only code extension is a public
parser-only validation function, plus its adapter version label.

## Executed against v0.3

- `python -m unittest discover -s tests -v`: **170 tests, 169 passed, 1 skipped**.
- `python -O -m unittest discover -s tests -v`: **170 tests, 169 passed, 1 skipped**.
- The new runtime suites contain 34 tests: 22 implementation regressions and
  12 independently authored adversarial regressions. Parameterized cases include
  50 independently constructed true/false identity controls, scalar operation
  compatibility, complete ring/AST binding, provider mutation and fake proof
  metadata, canonical expected polynomial values, explicit formal requirements,
  rehashed receipt tampering, and bounded expanded-output failure.
- The inherited polynomial suite retains its separate 322-case integer
  convolution oracle and 27 parameterized distributivity cases.
- `PYTHONDONTWRITEBYTECODE=1 python tools/audit_polynomial.py .`: the independent
  integer-pair/gcd oracle passed all **3,000 requests**, including canonical
  sides, differences, witnesses, hashes and malformed-input probes.
- All seven new workflow CLI fixtures matched their documented expected exits:
  true distributivity 0; false identity 1; polynomial formal requirement 1;
  unsupported cancellation 2; unsupported quotient relations 2; altered ordered
  ring 1; scalar formal requirement 1.
- Local Markdown links resolve. The v0.2 source manifest's 58 entries were
  rehashed with no changes.

The optional real-Lean smoke is the one skipped test. `lean-status` reports
`unavailable`; no real Lean proof was checked. Stub-backed tests remain simulated
adapter plumbing and cannot satisfy formal goals. The runtime never invokes Lean.

## Acceptance and failure behavior exercised

A false identity has a successful calculator receipt but a rejected verifier,
including when the provider correctly predicts `equal: false`. A true exact
result under a formal-proof requirement has `exact_check_passed: true` but
`requirement_satisfied: false`, a blocked verifier, and no accepted result.

Replay compares the complete deterministic calculation receipt. Adversarial
replacement of a ring or equality flag fails even after the test reconstructs a
valid receipt hash chain. Source hashes bind the two acceptance modules as well
as the backend source; assertions check those hashes against the current files.
They do not authenticate the source or attest to the loaded interpreter.

A newly exercised expansion boundary was fixed: a bounded polynomial input can
produce evidence larger than the queue's 64 KiB per-record limit. Publication now
fails closed, records the failed attempt, and never crashes the task loop or
publishes a partial successful result. The regression runs normally and with
optimization enabled.

## Independent readiness review

The independent source/test review and precise readiness boundary are recorded in
[READINESS.md](READINESS.md). Independent review is software evidence, not a
formal proof of the implementation or of any informal mathematical claim.

## Inherited validation

The delivered v0.1 baseline ran 98 tests (97 passed, one real-Lean skip). The
separate delivered v0.2 polynomial extension ran 136 tests (135 passed, one skip),
including its independent 3,000-request oracle. These historical records are not
substitutes for the current v0.3 runs above.

## Remaining limits

The exact runtime verifier reuses its calculator backend; it is not an independent
proof kernel. Informal goal/assumption correspondence is unchecked. Hash chains
check integrity, not authorship, authenticity, or all mutable report summary
claims. The queue is in-memory and single-process; providers are trusted Python
integration code, not sandboxed hostile plugins. Standalone arithmetic support
may exceed the stricter queue receipt limit.

No live model-provider call, model credential, network service, real Lean kernel
pass, remote CI, external repository creation, publication or deployment was
performed. This is a local executable-tool improvement, not a new mathematical
proof claim.

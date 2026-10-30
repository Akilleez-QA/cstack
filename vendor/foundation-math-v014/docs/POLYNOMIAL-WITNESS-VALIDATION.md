# v0.7 validation and preservation

The portable-release aggregate gate works from a clean manifest-only extraction:
It regenerates its legacy bridge transcript before optional schema validation.
Its preservation check covers all 142 inherited source inventory entries, including
the intentionally regenerated manifest; 27 historical generated evidence files
are explicitly excluded, not claimed checked. See the
[portable release note](PORTABLE-RELEASE-VALIDATION.md). The original frozen
v0.7 tree and its independent review are retained unchanged.

The final aggregate gate is:

```sh
python -B tools/run_polynomial_witness_validation.py
```

The runtime and unit tests use only the standard library. Optional schema
checks use `jsonschema` only if it is already installed, otherwise explicitly
report unavailable without installing it. No network, repository, credentials,
model calls or application research instances are used.

## Executed results

- Full suite, normal and optimized: **470 tests run, 469 passed, 1 skipped**
  in each mode. The inherited real-Lean test is skipped because Lean is not
  installed; no real proof-kernel acceptance is claimed.
- Independent integration review: **29 adversarial tests** and **9,184 explicit
  audit checks per mode**, using 100 tiny synthetic requests: 36 coefficient
  identities and 64 concrete mismatches. The audit includes binding, scope,
  rejection, original-six-tool pins, schema cases and byte-identical normal/-O
  stdio transcripts.
- The stronger total-degree theorem was independently reviewed, including
  monic factor division over the remaining-variable coefficient ring, nonzero
  rational units, additive total degree and telescoping. An additional
  exhaustive oracle covers **728 nonzero bivariate quadratics** with coefficients
  in {−1,0,1}, checking each specialization’s degree decrease. It finds 72
  sharp n+D cases and 752 strict extra degree drops. The maximum-size sharp
  degree-32 example with seven unused variables uses exactly **40 trials**;
  a caller limit of 39 fails inconclusively. No extra default normalization
  or frozen-lab edit was added to report the conservative n+32 metadata.
- Frozen witness-lab oracle: **300 semantic cases per mode**, including 106
  identities and 194 nonidentities; 25 witness tamper controls, 14 cap/error
  checks and 19 ingress checks. Its grid and finite-difference calculations are
  test-only oracles; production construction does not enumerate a grid.
- All **17 frozen standalone JSON examples** replay with their documented
  success/rejection exit codes. The new seven-request bridge example exercises
  discovery, construction, coefficient identity, valid checking, witness
  rejection and unsupported scope in both modes.
- Original bridge audit and matrix integration gate pass in both modes.
  Optional preinstalled schema validators pass: 64 new witness checks, 59
  matrix checks and 36 legacy structural checks per mode. The independent
  integration audit additionally includes 48 schema checks.
- The nine standalone witness runtime modules are byte-identical to the
  reviewed lab. All original six complete bridge tool definitions are pinned
  unchanged. All 22 inherited mathematical/runtime modules, excluding only the
  intentionally extended CLI dispatcher, are unchanged.
- Portable documentation/evidence scans and frozen-source manifest checks pass.

## What the integration review checks

The independent reviewer tests exact original-request/ring binding, raw versus
normalized hashes, fake success receipts, forged assignments/values, booleans,
extra fields, malformed bytes, unsupported constraints/fields, output and input
caps, cyclic Python data, suppressed partial results, source-provenance failures,
notifications and sanitized internal bridge exceptions.

The review checks nonminimal but truthful small integer witnesses, confirms
that equal point values do not establish identity, and demonstrates that the
fresh AST checker can accept a valid point for x^33 even though construction
correctly exceeds the frozen normalizer's degree cap. This difference is
intentional phase separation, not an evasion of constructor limits.

Exact coefficient identities remain normalization evidence. The fresh point
checker is explicitly not applicable to that branch. No output becomes a
formal proof, a new runtime goal domain or an accepted research conclusion.

## Intentional derivative changes

Frozen input trees were not edited. Changes to inherited files in this new tree
are restricted to the README/provenance note, CLI dispatcher, bridge version,
schema append hook and routes, and old discovery tests/development tooling that
assumed six total tools or selected the last two as matrix tools. The matrix
schema validator now selects matrix tools by exact names. Their mathematical
contracts and implementations are unchanged. The derivative source manifest
is regenerated separately from the frozen base manifest.

The v0.7-only bound metadata is constructor evidence, not a fresh point-checker
claim. Its executable cap is n+32; the exact theorem is n+degree(p). This is a
stronger analysis of the existing algorithm, not a measured runtime speedup.

The initial full integration test run exposed three count/ordering failures
and two positional matrix-schema errors caused by those historical six-tool
assumptions. They were corrected in this derivative and the full suite was
rerun successfully in both modes; no frozen test or source tree was changed.
The initial failure log is retained with its source-root path redacted.

## Reproducible records

- `evidence/v07-validation.json`: aggregate results and current manifest hash.
- `evidence/v07-tests-{normal,optimized}.txt`: actual final full-suite output.
- `evidence/v07-integration-audit-{normal,optimized}.json`: independent checks
  and source hashes.
- `evidence/v07-witness-lab-audit-{normal,optimized}.json`: independent oracle
  corpus, tamper/resource controls and source hashes.
- `evidence/v07-source-preservation.json`: permitted inherited changes,
  preserved runtime modules and exact six-tool prefix.
- `evidence/v07-example-transcript.json`: original requests' digest and actual
  normal/-O identical bridge responses.
- `evidence/v07-privacy-check.json`: portability scan results.
- `SOURCE-MANIFEST.json`: code, documentation, schemas and synthetic examples;
  generated evidence excluded to avoid self-reference.

The frozen v0.6 source manifest has SHA-256
`e11e09b92c66687bf5bab2b88927ee5205e50beb1832a9a555af789e6f63e54f`.
The reviewed standalone witness lab manifest has SHA-256
`273b8c1847daf7930b3f04325791b9bac19963018e51d83972b3c633597ab45f`.
These establish content references, not authenticity or mathematical correctness.

No unresolved blocking defect was found in the independent integration review.
This remains finite software validation with shared parser, exact arithmetic
and runtime trust, not a proof of all possible inputs or a formal proof kernel.
See [the detailed review](POLYNOMIAL-WITNESS-REVIEW.md) for limitations and
[the mathematical root-bound argument](polynomial-witness/ALGORITHM.md) for
why construction exists when computation stays within its resource caps.

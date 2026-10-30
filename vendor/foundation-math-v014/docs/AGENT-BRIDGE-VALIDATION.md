# v0.5 agent bridge validation

This is the historical v0.5 validation record, not a statement that every file
is unchanged in v0.6. The v0.6 CLI is intentionally extended; its current
15-backend preservation gate and matrix/bridge results are documented in
[LINEAR-ALGEBRA-VALIDATION.md](LINEAR-ALGEBRA-VALIDATION.md).

Executed on 2026-10-24 with Python 3.12.14. This is bounded local software testing
and review, not formal verification, proof-kernel testing, MCP conformance,
external-agent interoperability, or an OS-sandbox assessment.

## Results

- Full standard-library suite, normal: **276 tests run, 275 passed, 1 skipped**.
- Full standard-library suite, `-O`: **276 tests run, 275 passed, 1 skipped**.
- New bridge regressions: **44 passed** in each full-suite run.
- The existing real-Lean arithmetic smoke test was skipped because a trusted
  native Lean backend was unavailable. No real Lean proof was run or claimed.
- Independent bridge audit: **2,288 explicit checks passed in each mode**.
  These include 150 scalar-oracle cases, 96 dense-coefficient polynomial
  comparisons, 90 exhaustive two-variable finite-box oracle cases, fresh and
  rejected witnesses, mathematical no-promotion controls, resource exhaustion,
  wire rejection and an actual child-process transcript. Checks are individual
  assertions, not theorem counts. Oracle code is separately implemented but
  still shares Python's standard-library Fraction arithmetic and interpreter.
- The fixed **10-request / 10-response stdio transcript** was byte-identical
  normally and under `-O`, including initialize, tool list, scalar result, false
  identity, finite exhaustion, counterexample, fresh witness check, changed
  assertion rejection, unknown tool error and ping.
- Optional development-only schema validation: **28 checks passed** using the
  already installed `jsonschema` 4.26.0. All eight advertised input/output
  schemas, six sample input/output pairs and eight invalid identifier variants
  were checked. No package was installed. This validator is not a bridge or
  self-contained-test dependency; it is not an MCP SDK interoperability test.

The independent review found one low-severity schema/runtime discrepancy:
regular-expression `$` accepted an identifier ending in a newline while the
backend correctly rejected it. The schema now uses an absolute-end assertion;
the fix has both a unit regression and independent schema-validator checks.
No remaining issue was found within the tested scope. That is not a guarantee
of defect absence.

## Evidence files and reproduction

- `evidence/bridge-tests-normal.txt`
- `evidence/bridge-tests-optimized.txt`
- `evidence/bridge-transcript-validation.json`
- `evidence/bridge-independent-audit-normal.json`
- `evidence/bridge-independent-audit-optimized.json`
- `evidence/bridge-schema-validation.json`
- `evidence/bridge-base-preservation.json`

From the source root:

```sh
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
python -B tools/run_bridge_validation.py
python -B tools/audit_agent_bridge.py
python -B -O tools/audit_agent_bridge.py
python -B examples/bridge/stdio_client.py
```

Optional, only if the development validator is already available:

```sh
python -B tools/validate_bridge_schemas.py
```

The fixed transcript records the local Python version and source hashes through
backend receipts. Different hosts may have different receipt bytes; same-host
normal/optimized equality was checked. Test duration values in text logs are
observations, not performance guarantees.

## Acceptance boundary exercised

- False polynomial identities remain successful comparisons with `equal: false`
  and a coefficient witness, never accepted identities.
- Exact polynomial equality remains confined to the declared Q-polynomial ring.
  Quotient relations cannot be silently injected.
- Finite exhaustion cannot establish universal or formal proof or modify
  runtime goal-acceptance state; errors and partial search do not mean exhaustion.
- Fresh checks bind the original request, integer box, all constraints and
  assertion; changed assertions/constraints, out-of-domain candidates and
  fabricated producer verdicts do not pass as witnesses.
- Unknown tools/methods, executable strings, request-controlled paths, extra
  fields, malformed UTF-8/JSON, duplicate keys, decimal/nonfinite numbers,
  oversized/deep/node-heavy input and invalid IDs fail closed.
- Oversized output is wholly withheld as an error. Backend exceptions are
  sanitized, not converted into success or reflected as private path details.
- Notifications are silent and cannot execute work. Sequential IDs round-trip
  exactly. Responses are flushed before stdin closes; clean EOF, oversize EOF,
  truncated frames, command-line rejection and caller termination are tested.

## Source preservation and trust

The input snapshot manifest SHA-256 is
`82bb4dfdf9b934f58fb1508f3cb94ac6eddb4970802391e16592dfd132b8735b`.
It is preserved as `docs/BASE-V04-SOURCE-MANIFEST.json`. All 103 inventoried input
files still match in the separate original tree. In this derivative tree,
only README and roadmap documentation differ among those original inventoried
files; the **16 mathematical backend files** and all existing tests, examples,
acceptance gates and prior evidence are byte-identical. The derivative has its
own `SOURCE-MANIFEST.json`; that file is an integrity inventory, not a signature
or mathematical certificate.

The implementation is intentionally a custom local JSON-RPC profile named
`foundation-math-jsonrpc/1`, not MCP. No dependency installation, live model,
network server, credentials, external account writes, repository creation,
publishing or real Lean execution was performed. The optional schema validator
was preinstalled and only used for development validation. Local stdio clients
still own process launch, trust, wall-clock timeouts and termination. The host
and fixed source tree remain trusted.

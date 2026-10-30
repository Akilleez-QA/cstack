# v0.6 local validation: exact rational matrices

This record covers a separate local derivative of the frozen v0.5 bridge, adding explicit rational-matrix certificate API/CLI operations and two bridge tools. It is software validation, not formal verification, proof-repair evidence, or a published release.

## Final verified scope

- Full inherited and new unittest suite: **389 run, 388 passed, 1 skipped**, normally and with `python -O`.
- The sole skip is the existing real-Lean smoke test. Lean status is `unavailable`, `verification: not_run`, `formal_proof: false`. No actual Lean kernel check is claimed.
- Standalone matrix core: 63 tests in its prior audited snapshot, including **2,331** enumerated/seeded synthetic matrices checked against independent signed-permutation and Laplace/minor oracles; **190** shape-preserving semantic certificate mutations rejected; 22 manually authored verifier tests.
- Matrix API/CLI integration: 12 tests, including canonical request/source bindings, forged receipt/certificate rejection, exact combined output limit, no overwrites, runtime-domain non-admission, portable provenance, and complete original-tool-contract equality.
- New matrix bridge: 23 tests. Together with the 44 inherited bridge tests, 67 bridge tests pass. The bridge rejects unsupported/extra input, notifications never run math, and too-large standalone-valid certificates do not bypass wire limits.
- Independent integration reviewer: 15 new tests. No mathematical promotion, binding, resource, or runtime-preservation defect was found in the reviewed scope.
- Inherited deterministic bridge audit: **2,287 checks** pass in both modes. Only the intentionally extended CLI is exempted from the old 16-file preservation gate; all **15** other inherited backend files remain pinned. This is an explicit audit baseline change, not a claim that the old audit source is unchanged.
- The complete original four tool definitions are identical as data to the frozen v0.5 snapshot. The two new tools are appended.
- All **six** `exact_linalg` runtime files are byte-identical to the audited standalone lab.
- Ten-request original bridge transcript and five-request new matrix transcript reproduce identically under normal and optimized Python. The new transcript includes production, fresh verification, and semantic forgery rejection.
- Optional preinstalled JSON Schema validator: **55** new matrix/schema checks pass normally and with `-O`; **32** inherited/schema checks also pass. This uses already available `jsonschema` 4.26.0, with no install, runtime dependency, or unittest dependency.

## Reproduce

```sh
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
python -B tools/run_linear_algebra_validation.py
python -B -O tools/run_linear_algebra_validation.py
python -B tools/audit_agent_bridge.py
python -B -O tools/audit_agent_bridge.py
python -B tools/run_bridge_validation.py
python -B tools/validate_matrix_bridge_schemas.py
python -B -O tools/validate_matrix_bridge_schemas.py
python -B tools/validate_bridge_schemas.py
python -B -m foundation_math lean-status
```

The optional schema tools report unavailable rather than install a missing dependency. All normal runtime and unittest checks use only the standard library.

## Evidence and preservation

The `evidence/v06-*` files record complete suite logs, matrix validation, inherited bridge audit/transcript/schema replay, Lean availability, and source preservation. Matrix-specific schema evidence is separately named `evidence/matrix-bridge-schema-validation{,-optimized}.json`.

`docs/BASE-V05-SOURCE-MANIFEST.json` and `docs/LINEAR-ALGEBRA-LAB-SOURCE-MANIFEST.json` retain source references for the unchanged prior snapshots. `docs/BASE-V05-BRIDGE-TOOLS.json` retains the complete original four tool definitions with their source pins. `SOURCE-MANIFEST.json` pins this derivative's deliverables; the preservation report lists every intentionally modified inherited file and refuses unexpected changes.

The inherited vendor-provenance source labels were made portable in v0.6 only. No vendor code or code hash changed. Frozen v0.5 and the standalone lab remain unmodified. Historical v0.5 reports are clearly labeled and are not substituted for current evidence.

## Non-promotion checks

Every matrix receipt states `computational_field: Q`, `scope: one_explicit_matrix`, `formal_proof: false`, and `runtime_goal_acceptance: false`. A Z input is an integer-coefficient restriction embedded in Q, never an integral-module guarantee. The synthetic `[[2,1]]` regression produces `[-1/2,1]` and explicitly prevents lattice promotion.

A fresh check always requires the separately supplied expected matrix and the full certificate. It recomputes the finite exact checks; neither a request hash, source hash, producer success label, schema-valid shape, nor a rehashed forged receipt is accepted as mathematical evidence. Domain labels, dimensions, original matrix coefficients, trace, RREF, pivots, free columns, nullspace and determinant are all bound.

## Remaining limitations

- No symbolic or generic rank, parameter family, real/complex floating-point mode, integer-lattice basis, geometric-family result, or source-problem claim.
- No new runtime goal domain or formal-proof acceptance. No live model or external-agent/MCP interoperability claim.
- Independent verifier logic shares the strict parser, resource primitives, Python and `Fraction` arithmetic with the producer. The interpreter/host/source tree are trusted; this is not an OS sandbox or formal verification of the implementation.
- Work and bit limits can reject mathematically valid calculations. The operation counter is not a wall-clock bound. Bridge input frames remain 65,536 bytes, so some standalone-valid certificates cannot fit a bridge check request.
- Hashes bind reproducibility artifacts, not authenticity or loaded-code integrity. Use a trusted stable runtime and explicitly supplied expected matrix.

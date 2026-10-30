# Standalone lab validation record

This is the independently tested pre-integration lab record. In this integrated
source tree, use `python -B -m unittest discover -s tests -v` and its `-O`
variant, or `python -B tools/run_linear_algebra_validation.py`. The original
lab-only reproduction command and artifact names below describe that prior
snapshot, whose source manifest is retained in
`docs/LINEAR-ALGEBRA-LAB-SOURCE-MANIFEST.json`. Current integrated evidence is
described in `docs/LINEAR-ALGEBRA-VALIDATION.md`.

Validation is local to this standalone lab, on Python 3.12.14. No external service, package installation, live model, repository publication, or proof-assistant execution was used.

## Reproduce

```sh
python tools/validate.py /tmp/linear-algebra-normal.json
python -O tools/validate.py /tmp/linear-algebra-optimized.json
```

Each command runs the complete unittest suite and both CLI-format example requests through the checked adapter. The report records actual test counts and deterministic example-response hashes. Optimized mode must match ordinary mode except for the `optimized` flag. Files in `validation/` record the tested snapshot.

## Coverage

- 1,599 exhaustive integer matrices over entries `{-1,0,1}` at shapes `0×0`, `0×3`, `3×0`, `1×1`, `1×3`, `3×1`, `2×2`, `2×3`, and `3×2`.
- 160 deterministic seeded rational matrices with each dimension in `0..4`.
- Rank checked against independent enumeration of nonzero square minors, determinants against signed permutation expansion, and nullspace equations independently recomputed without runtime arithmetic helpers.
- 22 independently authored verifier tests using manually constructed certificates rather than the producer. These test all three row operations, determinant signs/factors, singular matrices, rectangular matrices, and dimension-aware empty matrices.
- Shape/type-preserving semantic corruption: forged rank with consistent counts, wrong pivots, wrong free columns, wrong RREF, wrong transform, wrong/deleted operation trace, singular transform still satisfying `U*A=R`, non-RREF matrices with an honest identity trace, false kernel vectors, zero/duplicated/rescaled kernel columns, and wrong square/nonsquare determinant claims.
- Input-domain binding and the integer-input non-promotion regression `[[2,1]] -> [-1/2,1]` over `Q`, explicitly not an integral-lattice basis.
- Exact large-integer cancellation that would be unreliable with floats.
- Explicit dimensions, all empty shapes, and the maximum supported `16×16` identity and zero matrices.
- Strict rejection of booleans, floats, nonfinite JSON, expressions, symbolic strings, foreign Python objects, unreduced/signed/integer-valued rational objects, unknown fields/domains/schema versions, and duplicate JSON keys.
- Every limit category, exact output-size boundary, matrix-derived cell limits, lowered work/operation limits, giant integer tokens, cyclic/deep objects, deep JSON, invalid UTF-8/surrogates, intermediate arithmetic growth despite small final values, and bounded error responses.
- One-shot CLI success/failure, exit status, output parity under `-O`, input-size limit, no traceback leakage, and independent verifier import without producer import.
- Static regression gates: standard-library import allowlist; no runtime `assert`, float literals, expression evaluation, dynamic imports, file opening, shell or model execution.

## Trust limits

Passing tests and bounded fuzzing are not formal verification, complete security analysis, or an operating-system sandbox. The independent verifier shares parsing, budget primitives, `Fraction`, and the Python runtime with the producer. Resource rejection is not a negative mathematical answer. Exact rank and nullspace acceptance apply only to the explicit matrix, never symbolic/geometric families or a different research problem.

## Independent audit and final result

A separate reviewer found no mathematical acceptance or guardrail defect and did not change the runtime. It added ten audit tests with:

- All 512 binary `3×3` matrices and 60 fresh seeded rational matrices, checked by an independent Laplace-expansion/minor oracle, prefix-column ranks for pivot selection, and independent nullspace rank.
- 190 shape/type-preserving coefficient and operation-trace mutations, all rejected.
- Empty dimensions through 16, valid nonproducer identity traces, exact work/output/operation boundary checks, escaped duplicate JSON keys, and bounded determinant-trace growth even when final matrices remain small.

Final complete suite: **63 tests passed normally and 63 passed under `python -O`; zero failures, errors, or skips**. The 2,331 enumerated/seeded oracle cases comprise 1,599 exhaustive ternary small matrices, 160 seeded rational cases, 512 binary `3×3` matrices, and 60 additional rational cases. Additional manual, boundary, and mutation fixtures are separate from that count.

Both checked example responses match byte-for-byte between normal and optimized modes. The machine-readable reports in `validation/normal.json` and `validation/optimized.json` record the exact response hashes. `SOURCE-MANIFEST.json` hashes every deliverable except itself and interpreter caches.

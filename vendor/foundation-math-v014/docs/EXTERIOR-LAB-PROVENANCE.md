# Provenance and retained baseline

Read-only source baseline: `foundation-math-hypothesis-scope-v013`. Its current README, AGENTS contract, character-ring contract/producer/verifier/catalog, split-bundle contract/producer/verifier, and relevant mathematical contracts informed this local extension. No source or bridge registry in that baseline was changed. A complete byte/size inventory was recorded before work; the post-build comparison records preservation of every regular file and the exact file set. This is file preservation evidence, not execution of all historical tests.

The character catalog is copied byte-for-byte from v0.13 `character_ring/catalog.json`, SHA256 `84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74`. The inherited mathematical contract pins the physical convention sources:

- Physical splitting/conventions, commit `db51525015bb7c5e825833d550d08dedf6f6ea96`: https://github.com/Akilleez-QA/read-em-and-weep/blob/db51525015bb7c5e825833d550d08dedf6f6ea96/research/hm/order-four-quadratic-load/ACTUAL-EQUIVARIANT-SPLITTING-AND-GAUSS-PERSISTENCE.md
- Rank-two conventions, same commit: https://github.com/Akilleez-QA/read-em-and-weep/blob/db51525015bb7c5e825833d550d08dedf6f6ea96/research/hm/order-four-quadratic-load/RANK-TWO-GAUSS-PLATEAU-NECESSARY-BOUND.md
- Primary-terminal physical product conventions, commit `504b7eb800407dfc7e6340c98c72cdd553939f54`: https://github.com/Akilleez-QA/read-em-and-weep/blob/504b7eb800407dfc7e6340c98c72cdd553939f54/research/hm/primary-terminal-slope-obstruction/PROOF.md

These links are inherited provenance, not new network reads, new proof imports, or authorization to access research instances. Only the supplied formal catalog and abstract representation/bundle expressions enter this implementation. No actual HM coefficients, points, parameters, matrices, ranks, private data, or model experiments were imported.

The exterior seeds are explicit finite derived arithmetic data. Their SHA256 is `0476eb520e3f8910828b4762fac3e88e16b12ba8f35ebe782c4e357c06ff1656`; that pin is enforced by the producer. The checker does not consume those seeds. The separate source manifest pins all shipped runtime, test, documentation, example, and evidence files. The archive pin is recorded outside the archive to avoid self-reference.

The sixteen existing bridge names remain: exact_scalar, polynomial_identity, finite_box_search, check_finite_box_witness, certify_rational_matrix, check_rational_matrix_certificate, construct_polynomial_witness, check_polynomial_witness, solve_rational_linear_system, check_rational_linear_system_certificate, calculate_fixed_character, check_fixed_character_certificate, calculate_formal_split_bundle, check_formal_split_bundle_certificate, replay_claim_applicability, match_hypothesis_scope. No seventeenth bridge tool is registered by this lab.

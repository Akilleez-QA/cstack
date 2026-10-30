# Validation and reproducibility

All evidence uses synthetic universal/formal representation and split-bundle inputs. No active research coefficients, selected points, parameters, jets, matrices, instance ranks or model experiments are evaluated. No source-domain scan or old37-Q enumeration is performed.

## Author checks

run_tests.py currently reports601 checks, including161 scalar certificate mutations and36 malformed-request cases, each rejected by both independently implemented request boundaries. Additional negative controls cover booleans/floats, duplicate JSON keys, nonfinite numbers, oversized integers, strings, lists, cyclic data, deep wire nesting, cross-operation certificates and mismatched external requests with identical mathematical results. It checks the explicit negative-H¹ fixture, Euler-collision examples, all physical labels, low-degree and extreme-degree boundaries, Hom orientation, Schur dimension, zero bundles, duplicate blocks, zero multiplicities, maximum domain bounds and detached requests.

The verifier-only import control prohibits importing either producer and either request-contract module. The CLI is replayed from an unrelated working directory and a cross-request certificate must fail. These checks do not rely on Python assert. Normal and python -O results are identical, recorded in evidence/tests-normal.json and evidence/tests-optimized.json.

## Independent checks

review/ contains a separately authored mathematical review, exact binomial-polynomial character oracle and black-box tests. The oracle does not import the author arithmetic, fusion table or request validator. The review covers every physical irrep at every reachable shifted degree from-128 through128, all irreducible Hom label pairs at selected boundary degrees, Serre duality, direct sums, the critical examples, strict data limits, every scalar certificate leaf, and equal-result/different-request substitution.

review/adversarial_controls.py also performs source-level fault injections in temporary review-owned copies. Eight faults are required to fail in normal and -O modes: H¹ off-by-one, unsigned Euler, W/Wp substitution, trusting the embedded request, wrong Serre shift, reversed Hom orientation, skipping certificate equality, and false Lean promotion. See review/ results for exact final counts and source binding. Finite sweeps are implementation controls; the all-integer Euler identity is proved in MATHEMATICS.md and independently in review/MATHEMATICAL-REVIEW.md.

## Delivery reproducibility

RELEASE-FILES.json is the complete explicit release membership list. ARTIFACT-MANIFEST.json hashes those files and is the only additional archive member. build_release.py never gathers release contents recursively; unlisted scratch files, pycache, archives or later extras cannot enter the ZIP. ZIP entry ordering, timestamps, permissions and storage mode are fixed.

Run python reproduce.py. It verifies the manifest, executes author, independent and source-fault controls in normal and optimized modes, creates two byte-identical archives, extracts exactly the manifest-selected members into a temporary standalone directory, replays all three suites in both modes, checks that files have not drifted, and rebuilds the same ZIP. It clears PYTHONPATH and supplies only the isolated package to the review. No sibling tree is required. The final delivery replay receipt is deliberately outside the archive to avoid a self-referential ZIP hash.

Imported character engine bytes are identical to the frozen v0.9 files and agree with its accepted source-manifest hashes; SOURCE-MANIFEST.json and evidence/source-preservation.json record that check. The frozen source and research packets are not edited.

## Interpretation

PASS means the tested standalone software and certificates agree with their finite contracts and fixed mathematical assumptions. It does not establish catalog-to-group identification, an actual object's equivariant splitting, a particular map rank, an embedding, Lean/kernel checking, or Foundation Math runtime acceptance. Releasing a ZIP is not runtime promotion.

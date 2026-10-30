# Validation scope

The bounded test families are exhaustive only in their stated domains:

- All nine irreps, every exterior order 0 through dimension+1, plus above-rank boundary controls.
- Every genuine nine-label representation of dimension <=6 (62 decompositions), all its exterior orders through rank+1.
- Every multiset of one, two, or three irreducible summands (219 multisets), including repeated summands, all orders through rank+1.
- Every unordered two-block multiset from nine irreps times degrees {-1,0,1} (378 cases), all orders through rank+1, with degree, determinant, and dual/complement checks.
- Direct-sum lambda identity for all 45 unordered pairs of irreps, every order.
- Class-power and Adams checks for all nine classes and all orders 1..25; compositions/products on the stated subrange.
- Third cyclotomic oracle: all nine irreps plus four repeated/mixed representations, all nine classes (117 class-level cases), every coefficient.
- Rank-24/order-25, empty representation/bundle, extreme degree 384, exact twist boundaries, physical W/Wp and A/V distinctions, and conditional H0 scope controls.

Identities include Lambda0=1, Lambda1 identity, binomial dimensions, central parity, determinant character and degree, direct sums, and dual/complement identity. Bundle center parity includes the standard line-degree central sign, separately from module parity.

Mutation tests alter Newton signs, Newton denominators, Adams behavior, class-power center handling, Adams line degrees, module parity, bundle parity, physical W/Wp labeling, repeated-copy handling, and a fusion cell. Every mutant runs a targeted existing test in a fresh temporary copy and must reach a test failure. A crashed runner or absent mutation target is not counted as detection. Certificate mutation tests independently alter signs, denominators, module labels, degree, parity, determinant, request, catalog, and scope.

The full suite and all source mutations run under normal and `python -O`. Correctness checks in production do not use Python `assert`. The import-separation subprocess uses an explicit exit check, not an assert that disappears under optimization.

## Portability and integrity

The archive contains only selected pinned files, no caches, credentials, virtualenv, Git state, baseline checkout, or external dependencies. ZIP timestamps and permissions are fixed, ordering is stable, and compression is disabled for cross-zlib reproducibility. Rebuilding from the clean extracted artifact yields the same bytes. The source manifest binds all shipped inputs. The artifact manifest pins its archive and source manifest outside the archive.

The aggregate verifies file digests before starting tests. It launches test processes with bytecode writing disabled and finite timeouts. Child PYTHONOPTIMIZE is forced to zero before explicit -O flags are applied; the aggregate requires actual reported modes 0 and 1, regardless of the launcher environment. Portable replay extracts only explicitly listed, bounded, flat relative paths, reruns normal/-O tests and mutations, and compares the exact rebuilt ZIP. When an original baseline path is provided, a complete before/after file inventory comparison confirms no original files or sixteen-tool implementation bytes changed.

Algorithmic agreement, hashes, mutation detection, and independently authored review are not formal-kernel proofs. No Lean installation or validation is claimed. The original v0.13 historical aggregate is not rerun here; its original bytes and tool count are retained. The new tests do not automatically widen Foundation Math's accepted theorem or runtime domain.

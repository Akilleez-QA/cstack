# Why this certificate checks one exact rational matrix

Let the explicit input be an `m×n` matrix `A` over the rational numbers. Integer input is embedded in the rationals. The verifier does not perform pivot search or independently run elimination. It checks the following finite exact calculation.

## 1. Invertible row-operation trace

The verifier starts from `A` and the `m×m` identity matrix. For each operation it checks exact fields, legal indices, distinct rows where required, and nonzero scale/add factors. It applies the operation to both working matrices.

A swap is invertible; a nonzero row scaling is invertible; adding a multiple of a distinct row is invertible. Therefore the product `U` of all operation matrices is invertible. At the end, both replayed matrices must agree entrywise with the supplied `R` and `U`. The verifier also computes the product `U*A` directly and checks `U*A = R`.

The invertible log is essential: `U*A=R` alone would not prove equal rank if a forged singular `U` annihilated information. No hash, producer identity, or success label substitutes for replay.

## 2. RREF and rank

The verifier scans each supplied row without reducing it. Nonzero rows must precede zero rows. Each leading nonzero entry must be 1; leading columns must increase strictly; every other entry in each leading column must be zero. These are the reduced-row-echelon conditions. The checked leading columns must equal the declared pivots, their count the declared rank, and the free columns exactly their ordered complement.

A checked RREF with `r` nonzero rows has rank `r`: those rows are independent by their pivots, and the remaining rows vanish. Since `U` is invertible, `rank(A)=rank(R)=r`.

## 3. Nullspace membership, independence, and completeness

The supplied matrix `N` has exactly `n-r` columns. The verifier computes `A*N` and requires zero. It also requires the rows of `N` indexed by the free columns, in their declared order, to form the identity matrix.

Consequently the columns of `N` are independent: a zero linear combination restricts on the free rows to the coefficient vector itself. Completeness can be seen without treating membership as sufficient: for any `x` in `ker(A)`, subtract the combination of columns of `N` with coefficients equal to the free coordinates of `x`. The difference remains in the kernel and has zero free coordinates. As `U*A=R`, the RREF equations force all its pivot coordinates to vanish as well. The difference is zero. Thus the columns span exactly `ker(A)`.

This is a rational-vector-space basis. It need not be an integral lattice basis even when the input entries are integers.

## 4. Determinant

For a square matrix the verifier accumulates `det(U)` from the operation log: a swap contributes `-1`, a row scaling its nonzero factor, and a row addition contributes `1`. This accumulated product is nonzero.

A square full-rank RREF is the identity, so its determinant is 1. A rank-deficient square RREF has a zero row, so its determinant is 0. The verifier checks the exact relation `claimed_det(A) * det(U) = det(R)`. The nonzero multiplier uniquely determines the determinant claim. Non-square inputs must carry `null`, not an invented determinant.

## 5. Empty dimensions

For `0×n`, rank is 0, there are no pivots or row operations, all columns are free, and `N` is `I_n`. For `m×0`, rank is 0, `N` is `0×0`, and `U` is the identity when produced (other valid invertible logs can verify). For `0×0`, the empty determinant and empty identity determinant are 1. Explicit dimensions prevent these cases from being conflated.

## Trust and scope

The mathematical checking algorithm was written independently of the producer and does not import it. It shares canonical parsing, resource accounting, and standard-library `Fraction` arithmetic, so this is not a diverse-implementation audit of the parser, Python runtime, or rational arithmetic. The verifier has more explicit defensive-checking lines than the compact producer; “smaller” refers to avoiding the search/elimination procedure, not a claim of lower source line count or a formally minimal trusted kernel.

Acceptance is exclusively about the explicit supplied rational matrix. It does not establish rank for unspecified parameters, a generic member of a family, a geometric identification, a theorem in another project, or runtime acceptance by a proof assistant. No actual data from a separate research problem is used here.

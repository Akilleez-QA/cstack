# Mathematical review of the formal domain

## Conditional statement being checked

Fix the supplied marked complex character table of G=SL2(F5). The table-to-group identification is an explicit mathematical input. Fix its physical determinant-one doublet W. A=Sym²W and V is the other three-dimensional irreducible; Wp is not W. For a supplied finite nonnegative block multiset, the program computes cohomology of that formal split bundle, not a splitting inferred from an actual source object.

For a block U⊗O(a) and requested twist t, put m=a+t. Under the determinant-one convention, the usual projective-line formula gives H⁰=U⊗SymᵐW and H¹=0 for m≥0; both are zero for m=−1; and H⁰=0, H¹=U⊗Sym^(−m−2)W for m≤−2. Using W rather than W* is justified by the determinant-one self-duality of this chosen doublet, not an interchange with the other doublet. These equalities are representation-class equalities, with characteristic-zero semisimplicity as an assumption.

The Euler result is H⁰−H¹ in the representation ring and can be proper virtual even though the input bundle and each cohomology group are genuine. For multiplicity n of U(a), rank contributes n dim U and degree contributes n a dim U. At every twist,

    dim H⁰ − dim H¹ = rank · (t+1) + degree.

The scalar equality is a necessary cross-check, not sufficient to identify a character or either cohomology group. Direct-sum additivity and H¹(F(t)) ≅ H⁰(F*(−t−2))* give independent structural tests.

## The genuine-Euler trap

For F=O(−10)⊕O(−8)⊕V(−8) and t=8, the shifted degrees are −2,0,0. Therefore H⁰(F(8))=1⊕V, H¹(F(8))=1, and χ_G(F(8))=V. Its rank is 5 and its degree is −42, so χ=5·9−42=3. A genuine Euler class V does not imply H¹ vanishes and does not make H⁰ equal V.

## Same equivariant Euler classes at every twist

For the chosen determinant-one W there is the equivariant sequence

    0 → O(−2) → W⊗O(−1) → O → 0.

Twisting and taking equivariant Euler characteristics yields, for every integer t,

    χ_G(O(t)) + χ_G(O(t−2)) = χ_G(W⊗O(t−1)).

Thus O⊕O(−2) and W⊗O(−1) have the same equivariant Euler characteristic at all twists, not just the finite test range. At t=0 the first has H⁰=1 and H¹=1, while the second has H⁰=H¹=0. They also have the same rank and degree. Equivariant Euler classes at all twists do not reconstruct the split object or separate its H⁰ and H¹.

A second purely character-level justification sets E(m)=SymᵐW for m≥0, E(−1)=0, and E(m)=−Sym^(−m−2)W for m≤−2. The usual symmetric-character recurrence, together with the three transition cases m=0,−1,−2, gives E(t)+E(t−2)=W E(t−1) for every integer t. This is a proof for arbitrary t. The finite test sweep checks implementation consistency only.

## Equivariant Hom dimension

For blocks U(a),V(b), the relevant group is

    Hom_G(U(a),V(b)) = (U*⊗V⊗H⁰(O(b−a)))^G.

It vanishes for b−a<0. Otherwise its dimension is the trivial-character coefficient of U*⊗V⊗Sym^(b−a)W. All rows of this catalog are real characters, so U* has the same character as U. This does not make every representation real as a vector-space representation, and it does not identify inequivalent labels. Additivity then handles sums, with the product of source and target multiplicities.

In particular Hom_G(W(−3),W(−3)) has dimension 1 by irreducibility. This is a dimension of a space of maps, not a rank of a particular map. No specific map, injection, image, kernel, or embedding is supplied or certified by the calculator.

## Evidence boundary

The independent oracle computes exact arithmetic in Q(sqrt(5)), spells out the marked class characters, and uses closed binomial symmetric-character polynomials. It does not import the producer, checker, fusion table, or author contract. Agreeing implementations and mathematical explanation establish useful conditional algorithmic evidence. They are not a machine-checked theorem, do not verify actual coefficients, parameters, points, jets, matrices, or ranks, and do not establish acceptance by Foundation Math or another runtime.

# Supplied equivariant split bundles on P¹

## Input assumptions, not discovered geometry

Fix G=SL₂(F₅), over C, and the accepted physical irreducible catalog. Its identification with this group and physical marking is an explicit mathematical input, not proved by hashing, orthogonality, or successful software checks. W is the chosen two-dimensional determinant-one representation; Wp is the other two-dimensional irreducible. A=Sym²(W); V is the different three-dimensional irreducible. Neither same dimensions nor the self-duality below identify these labels.

The base is P(W) with its standard G-action and standard linearization of O(1). Since det(W)=1, W≅W* equivariantly and the canonical bundle has the standard equivariant identification K≅O(-2), with no determinant-character factor. Our convention therefore identifies H⁰(O(n)) with Symⁿ(W) for n≥0; choosing P(W) as lines first gives Symⁿ(W*), which is equivariantly isomorphic to Symⁿ(W).

A request supplies the formal direct sum F=⊕ᵢ(Uᵢ⊗O(aᵢ))^⊕mᵢ, with mᵢ≥0. The specified equivariant splitting is an assumption, not a conclusion. Abstract Birkhoff–Grothendieck splitting alone must not be substituted for a specified equivariant splitting. These data are not evidence that an active research bundle has this type. All example objects are universal/formal. No actual coefficients, chosen points, parameters, jets, matrices, instance ranks, model experiments, or source-domain enumeration are used.

## Exact fixed character catalog

Ordered labels are (1,W,A,S4,D,T6,P,Wp,V). Their dimensions are (1,2,3,4,5,6,4,2,3), and center signs are (+,-,+,-,+,-,+,-,+). The nine class sizes are (1,1,30,20,20,12,12,12,12), summing to120. Write φ=(1+√5)/2 and φ̄=(1-√5)/2. The W row is

(2,-2,0,1,-1,φ,-φ,φ̄,-φ̄).

With S₀(x)=1, S₁(x)=x, Sₙ₊₁(x)=xSₙ(x)-Sₙ₋₁(x), rows 1,W,A,S4,D,T6 are S₀,…,S₅ evaluated on this row. The P row is (4,4,0,1,1,-1,-1,-1,-1); Wp=W·P-T6; V=S₆(W)-P. This gives the entire table in the supplied catalog.json. Its SHA256 is 84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74.

Every class value is represented exactly in Q(√5): (a,b) denotes a+b√5 with rational a,b, and multiplication is (a,b)(c,d)=(ac+5bd,ad+bc). JSON represents a rational pair by [a_numerator,a_denominator,b_numerator,b_denominator], in reduced form with positive denominators. There are no floating-point tolerances. The inner product is (1/120)∑ᶜ |C|χ(C)ψ(C); conjugation does not change this real-valued catalog. Thus every irreducible is character-self-dual, even when it has a quaternionic structure.

The vendored character checker validates the pin, full table, physical definitions, orthogonality, dimensions, center signs, and all81 stored fusion products against exact inner products. These are algebraic consistency checks conditional on the fixed catalog-to-group identification, not a proof of that identification. CATALOG-SOURCE-PINS.json preserves provenance from the accepted character lab; no source theorem about a research bundle is imported as a runtime hypothesis.

## Cohomology, including negative degrees

Let n=aᵢ+t. The standard cohomology of O(n) on P¹ is:

- n≥0: H⁰(O(n))=Symⁿ(W), H¹(O(n))=0.
- n=-1: both groups vanish.
- n≤-2: H⁰(O(n))=0, H¹(O(n))=Sym^(-n-2)(W).

For the last line, equivariant Serre duality gives H¹(O(n))≅H⁰(O(-n-2))* because K≅O(-2). The determinant-one isomorphism W≅W* identifies the dual symmetric power with the displayed symmetric power. Tensoring by the fixed representation U and additivity over direct sums give

Hʲ(F(t)) = ⊕ᵢ Uᵢ⊗Hʲ(O(aᵢ+t))^⊕mᵢ.

In particular H¹ is not obtained by ignoring negative-degree blocks. Both H⁰ and H¹ have nonnegative irreducible multiplicities, while the signed Euler character χ_G(F(t))=[H⁰]-[H¹] may be properly virtual. Its signed dimension is rank(F)(t+1)+degree(F). Rank(F)=∑mᵢdim(Uᵢ), degree(F)=∑mᵢdim(Uᵢ)aᵢ, and degree(F(t))=degree(F)+t rank(F). The checker independently verifies this ordinary Riemann–Roch dimension identity for every requested twist.

Critical formal control: F=O(-10)⊕O(-8)⊕(V⊗O(-8)). At t=8, the first summand contributes H¹=1, the others contribute H⁰=1+V. Hence H⁰=1+V, H¹=1, and χ_G=V. Rank is5 and degree is-42; F(8) has degree-2, so Euler dimension is3 as required.

## Equal Euler characters do not identify cohomology or splittings

The standard equivariant evaluation sequence is

0 → O(-2) → W⊗O(-1) → O → 0.

Indeed evaluation W*⊗O→O(1) has kernel det(W*)⊗O(-1); det(W*) is trivial and W*≅W. Tensoring by O(-1) gives the displayed sequence. Its long exact cohomology sequence, after any integer twist t, implies

χ_G(O(t)) + χ_G(O(t-2)) = W·χ_G(O(t-1)).

Thus O⊕O(-2) and W⊗O(-1) have identical equivariant Euler characters at every integer twist, not merely the finitely supported API twist range. At t=0 the split lines have (H⁰,H¹)=(1,1), while W⊗O(-1) has (0,0). The exact sequence need not split equivariantly or ordinarily; it proves an Euler identity, not a splitting identity. The same identity follows by extending the Sₙ recurrence to eₙ=Sₙ for n≥0, e₋₁=0 and eₙ=-S₋ₙ₋₂ for n≤-2.

## Optional Hom operation and its exact limitation

For supplied formal F=⊕UᵢO(aᵢ)^mᵢ and E=⊕VⱼO(bⱼ)^nⱼ,

Hom(F,E)=H⁰(F*⊗E)=⊕ᵢⱼ (Uᵢ*⊗Vⱼ⊗H⁰(O(bⱼ-aᵢ)))^(mᵢnⱼ).

Use the same H⁰ rule above, with no contribution when bⱼ-aᵢ<0. The Hom character is the representation of all sheaf maps; its trivial-irrep multiplicity is dim_C Hom_G(F,E). The source dual has the same character for this real-valued fixed catalog. This calculation says nothing about the rank of a chosen map, its degeneracy locus, a kernel, or the existence of an embedding. The API accepts no map and reports no map rank or embedding verdict.

For W⊗O(-3) to itself, dim Hom_G=1 by Schur's lemma, while all sheaf maps form the4-dimensional representation W*⊗W=1+A. The1-dimensional equivariant map parameter space is not a rank-one map assertion. Zero and nonzero choices already behave differently; any further map-level conclusion needs additional justified data and reasoning outside this API.

## Algorithmic independence and claim boundary

The producer uses the accepted integer fusion table and determinant-one symmetric recurrence, then renders exact class values. The new checker does not import the producer or request contract. It validates the external request independently, computes cohomology/Hom as exact pointwise class functions, and decomposes them by weighted inner products through the separately audited character verifier. It compares the entire canonical certificate to its independently rebuilt object. A certificate's own embedded request is never authoritative. Exact-type/data guards reject bool-as-int, floats, extra fields, unknown labels, cycles, excess depth and oversized values. The checker result explicitly has runtime_acceptance=false, lean_proof=false and geometric_realization=false.

The independent review adds a separately authored binomial symmetric-power oracle. No form of arithmetic agreement is a Lean proof, a formal-kernel theorem, an automatic Foundation Math acceptance, or actual geometric realization. No runtime registry or frozen v0.9 files are changed by this lab.

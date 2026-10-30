# Mathematical contract and proof obligations

## Fixed marked input

G = SL2(F5), over C, with irreducibles in order (1,W,A,S4,D,T6,P,Wp,V), dimensions (1,2,3,4,5,6,4,2,3), and central signs (+,-,+,-,+,-,+,-,+). W is the specified determinant-one faithful doublet. Wp is the other doublet, A = Sym²(W), and V is the other triplet. The exact v0.13 catalog is copied byte-for-byte and pinned. Its identification with the physical group and marking is assumed, not proved by software.

Ordered class sizes are (1,1,30,20,20,12,12,12,12). W traces are (2,-2,0,1,-1,phi,-phi,phi_bar,-phi_bar), where phi=(1+sqrt(5))/2 and phi_bar=(1-sqrt(5))/2. These nine traces are distinct and distinguish the nine supplied classes. Class orders are (1,2,4,6,3,10,5,10,5).

## Exact field, class powers, and Adams operations

A field value is (a,b), meaning a+b sqrt(5), with a,b rational. Products are (a,b)(c,d)=(ac+5bd,ad+bc). Wire values are `[a_num,a_den,b_num,b_den]`, with reduced positive denominators. Fractions are never approximated.

For x = trace_W(g), let p_0=2, p_1=x, p_k=x p_(k-1)-p_(k-2). Since det W=1, p_k = trace_W(g^k). Matching p_k against the nine distinct W traces gives the power class exactly. For any character chi, psi^k(chi)(C)=chi(C^k). It is **not** the pointwise kth power of chi, nor k times chi.

Newton's identity gives e_0=1 and

`n e_n = sum(k=1..n) (-1)^(k-1) e_(n-k) psi^k(chi)`.

Division by n occurs in the rational field; exact inner products then recover nonnegative integral multiplicities. Every output is reconstructed from those multiplicities. The checker does not accept dimension, center sign, or integrality alone as identification.

For a split expression E = direct-sum U_i tensor O(a_i), use formal degree z and character chi_E(z)=sum_i chi_(U_i) z^(a_i). Adams acts on **both** character and degree:

`psi^k(chi_E(z)) = sum_i psi^k(chi_(U_i)) z^(k a_i)`.

The graded Newton identity yields the exact split exterior coefficients. Every nonzero degree term in each requested order is retained. Computing only the explicit requested-order prefix is exact coefficient extraction, not approximation. No degree cutoff is used. Orders above rank give zero, including the supported rank-24/order-25 boundary.

## Independent integer-fusion construction

The producer multiplies finite lambda polynomials of irreducible summands, using the inherited pinned integer fusion table. Exterior seed polynomials have coefficients:

- 1: (1,1)
- W: (1,W,1)
- Wp: (1,Wp,1)
- A: (1,A,A,1)
- V: (1,V,V,1)
- S4: (1,S4,1+D,S4,1)
- P: (1,P,A+V,P,1)
- D: (1,D,A+P+V,A+P+V,D,1)
- T6: (1,T6,1+2D+P,2S4+2T6,1+2D+P,T6,1)

Seeds were initially generated from the exact class formula and then frozen. They are **not independent mathematical inputs** that prove themselves: the checker recomputes every result without reading them, and the third cyclotomic oracle independently validates each seed at every class. The producer/checker are algorithmically separate but share the catalog identification assumption. They were not initially independently authored; independent review is separately requested.

For m copies of U tensor O(a), multiply m copies of `sum_k [Lambda^k U] z^(ka) t^k`. Replacing m copies by a scalar multiple of one polynomial is wrong. Polynomial multiplication realizes Lambda^k(V+W)=sum_i Lambda^i(V) tensor Lambda^(k-i)(W).

## Determinants, duality, and parity

Every irrep has real-valued character, so its dual has the same character, including quaternionic irreps. The only one-dimensional catalog irrep is trivial; in particular the top exterior character of every irrep is 1. The explicit checker and independent oracle verify this in all nine cases.

For E of rank r and degree d, det E = 1 tensor O(d). For 1<=k<=r,

- rank Lambda^k E = binomial(r,k);
- degree Lambda^k E = binomial(r-1,k-1) d;
- Lambda^(r-k) E = (Lambda^k E*) tensor det E.

Lambda^0 E = O, and Lambda^1 E = E. For the zero bundle, det(0)=O and only Lambda^0 is nonzero. A result bundle's `determinant.line_degree` is the degree of that result, not the line degree of each constituent.

A homogeneous module with central sign s has Lambda^k sign s^k. Mixed parity inputs need not yield a homogeneous result. For U tensor O(a), the center action on the equivariant bundle fiber has sign sign(U)(-1)^a, because O(1) has standard linearization. The API separately reports module central parity and bundle central parity. Mixing them loses information.

## Formal H0 comparison and its precise implication

The base is P(W) with standard linearization. Since W is self-dual with determinant one, H0(O(n)) = Sym^n(W) for n>=0 and zero for n<0. Apply this degree by degree after exterior-power formation. The twist t is applied **after** the exterior power: `(Lambda^k E)(t)`, not `Lambda^k(E(t))`.

If an actual G-equivariant injection of vector bundles U -> R(-2) on this integral smooth curve is separately established, then its exterior powers are injective (for k>rank U the source is zero). Generic injectivity and torsion-freeness also show this for an injective sheaf morphism of locally free sheaves, without requiring locally free cokernel. Twisting preserves injections; H0 is left exact. Semisimplicity of finite-dimensional complex G-modules implies every source irreducible multiplicity must be <= its target multiplicity. Thus a negative difference is a conditional obstruction **provided that the supplied equivariant splittings and the hypothetical injection interpretation are valid**.

No API input establishes those hypotheses. `passes` means only that one finite necessary multiplicity test passes. It neither constructs an actual map nor proves injection, generic rank, coherent image, torsion-free cokernel, embedding, or existence. Selected twists are never claimed exhaustive over all integers. Even passing all selected orders and twists can be vacuous: for O(-2) versus O(-3), t=0 produces no positive-order H0 obstruction, although their ordinary Hom space is zero.

The stronger formal example in the README has a first-order equality at t=6 and an order-two difference D-P-1. Its U and R are illustrative formal expressions only; there are no supplied actual HM coefficients, selected points, parameters, matrices, or instance ranks.

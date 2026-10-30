# A zero composite is not a rank-preservation theorem

This is a universal proof-repair regression over P¹_Q. The variables x,y are
homogeneous coordinates, not selected numerical data from a research instance.
No chosen coefficients, matrices, point/jet evaluations, or historical
experiments are used.

## The proposed inference, and its counterexample

An invalid general inference is:

> For an exact sequence 0 → K → E → Q → 0, if Hom(S,K)=0, then every
> lift S → E of a map S → Q has the same rank as its projection.

Take the Euler sequence on P¹_Q:

```
0 → O(−2) ─a→ O(−1) ⊕ O(−1) ─b→ O → 0,
a = column(−y, x),      b = row(x, y).
```

Set S=E=O(−1)⊕O(−1), choose the lift ℓ=id_E, and take its projection
f=b∘ℓ=b. Then ℓ has rank 2 everywhere, whereas f has rank 1 everywhere.
Nevertheless,

```
Hom(S,O(−2)) = H⁰(P¹_Q,O(−1))² = 0.
```

The vanishing follows from the absence of homogeneous polynomials of negative
degree, equivalently from the elementary chart calculation below. Thus the
proposed inference fails even with locally free sheaves, a genuine short exact
sequence, and a unique global lift when a lift exists.

## What the executable certificate checks

The JSON example `examples/polynomial/euler-sequence-composite.json` asks
whether the single universal polynomial identity

```
x*(−y) + y*x = 0  in Q[x,y]
```

holds. The adapter computes a zero coefficient difference and returns
`equal: true`. This certifies the **algebraic composition formula** within the
adapter's computation scope. It does not certify bundle exactness, surjectivity,
Hom vanishing, ranks, chart coverage, or informal/formal correspondence. Those
are distinct obligations addressed by the written argument below, not by a
polynomial receipt or by Lean.

## Written chart argument for exactness

The standard affine charts U_x={x≠0} and U_y={y≠0} cover P¹_Q. On U_x put
t=y/x. With the standard local frames x⁻¹ for O(−1) and x⁻² for O(−2), the maps
are column(−t,1) and row(1,t). The first is injective because its second entry
is 1. The second is surjective because its first entry is 1. Its kernel consists
exactly of pairs (−tc,c), the image of the first map.

On U_y put u=x/y. Using local frames y⁻¹ and y⁻², the maps are column(−1,u)
and row(u,1). The first is injective; the second is surjective; its kernel is
exactly the set of pairs (−c,uc). Exactness on the two charts proves exactness
of the displayed sequence, and the same unit entries show that b has rank 1
on every fiber. The identity ℓ has rank 2 on every fiber.

For completeness, a global section of O(−1) would be a polynomial f(t) times
x⁻¹ on U_x and a polynomial g(u) times y⁻¹ on U_y. On the overlap,
y⁻¹=t⁻¹x⁻¹, hence f(t)=t⁻¹g(t⁻¹). The left side has only nonnegative powers of
t and the right only strictly negative powers, so both vanish. This proves
H⁰(P¹_Q,O(−1))=0 directly, without a separate imported cohomology calculation.

## The type error to prevent

Hom(S,K)=0 concerns **global bundle morphisms from the whole source S to K**.
It implies that the map Hom(S,E)→Hom(S,Q) is injective: two existing lifts of
the same f differ by a global map S→K, and hence must be equal. It says that
a lift is unique, not that its projection has equal fiberwise/generic rank.

In the example, ker(f)=K is a rank-one subbundle of S, and the identity lift
maps that kernel nontrivially into K. That restriction K→K is not a global
morphism S→K. Conflating the two source types is the faulty step. In fact the
exact sequence cannot split globally, since a splitting would provide a
nonzero projection S=E→K, contradicting the Hom vanishing just proved.

Reusable obligations for future reasoning:

1. Record exact source and target of every Hom group and restriction map.
2. Check the composite identity separately from exactness and rank claims.
3. Do not infer pointwise/generic injectivity from a global Hom vanishing.
4. When a rank-preservation step is needed, prove that the lifted image has
   zero intersection with the kernel, or supply another sufficient hypothesis.

This counterexample refutes only the stated general inference. It does not
decide any particular research classification or show that every specialized
rank assertion is false. The chart proof is human-readable mathematics and is
not claimed to be checked by the polynomial backend or a proof assistant.

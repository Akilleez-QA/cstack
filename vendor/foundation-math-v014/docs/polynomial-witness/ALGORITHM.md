# Sequential exact specialization

## Statement and hypotheses

Let p = L − R be a polynomial over Q in an ordered list of distinct,
algebraically independent variables x₁,…,xₙ. There are no extra constraints
on those variables. If p is nonzero, the algorithm below constructs a tuple of
nonnegative integers a with p(a) ≠ 0. Each coordinate is at most the degree of
the current residual polynomial in that coordinate.

The implementation first obtains p by exact sparse coefficient normalization.
If all coefficients vanish, it reports the coefficient identity L = R in the
declared ring, without running any point search. No inference of identity is
made from a finite sample of equal evaluations.

## Algorithm

Start with residual p₀ = p. For j = 1,…,n:

1. Let dⱼ be the degree of the nonzero residual pⱼ₋₁ in xⱼ. An absent variable
   has degree 0, including when the residual is a nonzero constant.
2. Try integers a = 0,…,dⱼ in order, substituting xⱼ = a and exactly collecting
   like monomials in the remaining variables.
3. Keep the first a for which the resulting residual is nonzero; record aⱼ = a
   and pⱼ = pⱼ₋₁|xⱼ=a.

This is a sequence of at most dⱼ+1 trials at step j. It never enumerates a
Cartesian product of candidate coordinate sets. Substitution deletes one
exponent coordinate's contribution and combines equal remaining monomials;
terms can disappear but their count cannot exceed the preceding term count.

## Why a choice always exists

Write a current nonzero residual as a polynomial in the variables after xⱼ,
with coefficients that are univariate polynomials in xⱼ:

pⱼ₋₁ = Σₘ cₘ(xⱼ) m.

The earlier variables have already been assigned, and every nonzero surviving
monomial has zero exponent in those positions. At least one coefficient
cₘ is a nonzero polynomial in Q[xⱼ], of degree at most dⱼ. If substituting a
annihilates the entire residual, every coefficient cₘ(a) is zero, in particular
this chosen nonzero cₘ.

A nonzero polynomial over a field of degree d has at most d distinct roots.
For completeness, if c(a)=0 then division by the monic linear polynomial
x−a gives c=(x−a)q. Every other root b≠a of c satisfies
0=(b−a)q(b), so q(b)=0 because Q is a field and b−a≠0. Induction on degree,
starting from a nonzero constant with no roots, proves the bound.

Consequently at most dⱼ of the dⱼ+1 distinct integers 0,…,dⱼ can annihilate
that chosen coefficient, and at most dⱼ can annihilate the whole residual.
A preserving candidate therefore exists at every step.

The invariant “the residual is nonzero” holds initially and is preserved by
this choice. After the final variable, the residual is a nonzero rational
constant, exactly p(a₁,…,aₙ). Thus L(a) and R(a) differ. The empty-variable
case already is a rational constant; it returns the empty assignment if
nonzero. A constant with unused declared variables assigns 0 to each.

## Bounds, and what they do not imply

The actual number of trial substitutions is at most
Σⱼ(dⱼ+1). If Dⱼ is the degree of the original normalized p in xⱼ, substitution
of earlier variables cannot increase xⱼ degree, so dⱼ≤Dⱼ. Thus the trial
count is also at most Σⱼ(Dⱼ+1), and each coordinate aⱼ≤dⱼ≤Dⱼ.

With this lab's adapter caps n≤8 and total degree≤32, each coordinate is
between 0 and 32 and the coarse trial bound is 8×33=264. This is a
substitution-trial bound, not a claim of polynomial time in arbitrary succinct
input descriptions. Normalization may expand an expression dramatically;
coefficient bit sizes and exact-arithmetic cost matter. The implementation
uses independent phase caps on AST shape, normalization, substitutions and
concrete evaluation. A cap can halt the algorithm even though the mathematical
existence theorem still guarantees a witness. A resource error must never be
reported as nonexistence, identity, or finite-search exhaustion.

## Independent checking scope

For a supplied witness, the checker starts with a separately supplied original
request. It revalidates the typed syntax, hashes and ring, then directly evaluates
both original expression trees using Fraction arithmetic. It checks both claimed
values, their claimed difference, and that the difference is nonzero. It does
not use the producer's normal form or trial trace. Shared trust remains in the
typed parser, canonical hashing, Python integers/Fraction, and runtime.

The checker intentionally does not prove first-choice minimality, trace facts,
or per-variable degree bounds. Those are producer metadata audited by tests.
It also never certifies a coefficient identity from point agreement. Identity
results rely on the frozen exact coefficient-normalization adapter instead.

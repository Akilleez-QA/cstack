# A sharp total-degree trial bound

Let p be a nonzero formal polynomial over Q in n declared, ordered variables,
and let D be its normalized total degree. The existing algorithm tries the
integers 0, 1, … in the next variable and keeps the first substitution that
leaves a nonzero polynomial in the remaining variables. If it chooses a_j at
step j, then:

    sum_j a_j <= D
    total substitution trials = n + sum_j a_j <= n + D.

This strengthens the sum of individual variable-degree bounds. It is a bound
on trial substitutions, not normalization time, bit complexity, total arithmetic
operations, or measured wall-clock speed. It analyzes the same algorithm; it
does not change the frozen producer.

## Proof by total-degree decrease

Before step j, the nonzero residual is p_(j−1), of total degree D_(j−1).
Write it as a polynomial in x_j over the coefficient ring
R = Q[the remaining unassigned variables].

Because a_j is the first preserving integer, substituting x_j = i annihilates
the entire residual for each i = 0, …, a_j−1. Division by the monic polynomial
x_j−i is valid over any coefficient ring, and its remainder is exactly the
evaluation at i. Thus x_j−i divides the residual.

All these factors can be divided out together. One direct argument avoids
assuming unique factorization: after earlier factors are removed, evaluate
at the next root i. The previously removed product evaluates to a product
of nonzero differences of distinct integers. That product is a nonzero
rational constant, hence a unit in R. The quotient must therefore still
vanish at i, and monic division removes the next factor. Induction gives

    p_(j−1) = (product over i=0,...,a_j−1 of (x_j−i)) q_j.

For a_j=0 the empty product is 1. Both factors are nonzero. Total degree is
additive for nonzero polynomial products over Q: their highest homogeneous
parts have a nonzero product because the polynomial ring is an integral
domain. The falling-factorial factor has degree a_j, so

    total_degree(q_j) = D_(j−1) − a_j.

At the chosen integer x_j=a_j, the falling-factorial factor evaluates to a_j!,
a nonzero rational constant. Consequently the new residual is

    p_j = a_j! q_j(a_j, remaining variables).

It is nonzero by the selection rule. Substitution of a constant cannot
increase total degree: it removes powers of that variable from monomials,
and cancellations can only lower degree. Therefore

    D_j <= D_(j−1) − a_j.

Telescope this inequality over all variables. The final residual is a nonzero
constant, so D_n=0, and sum_j a_j <= D. Trying exactly the integers 0 through
a_j costs a_j+1 trials. Summing proves the claimed n+D bound.

The separate root-bound existence argument guarantees that each preserving
integer is found within the current variable degree. This total-degree
argument does not replace that existence proof; it sharpens the aggregate
count after existence is established.

## Boundary cases and sharpness

- A nonzero constant has D=0. Every unused declared variable receives 0 and
  uses one trial. With no declared variables there are zero trials.
- Zero polynomials are a separate exact coefficient-identity branch. Their
  degree is not D in this argument, and no point search runs.
- For p equal to the falling factorial x₁(x₁−1)…(x₁−D+1), with n−1 unused
  declared variables, the chosen point is (D,0,…,0). It uses exactly D+n
  trials, so the bound is sharp.
- At the present caps n<=8 and D<=32, successful construction needs at most
  40 trials. Degree 32 in one variable with seven unused variables attains 40.
- Extra degree loss under specialization only makes the inequality stronger.
  No equality at each step is assumed.

Characteristic zero, distinct integer constants, nonzero residuals and
unrestricted formal variables are essential to this formulation. No claim is
made for quotient rings, constrained loci, finite fields or rational functions.

## Executable metadata without repeated normalization

The frozen lab does not expose the exact normalized total degree D in its
receipt. The v0.7 wrapper does not normalize a second time solely to obtain it.
Instead, only successful nonzero construction receipts add `construction_bound`:

- `normalizer_total_degree_cap: 32` is a cap, **not the actual degree**.
- `variable_count` is n and `substitution_trial_bound` is the conservative n+32.
- `sum_chosen_coordinates` is sum a_j and `actual_substitution_trials` is n+sum a_j.
- `legacy_hard_trial_cap: 264` records the unchanged lab compatibility ceiling.
- `exact_difference_degree_recomputed: false` and
  `point_checker_certifies_bound: false` make the evidence boundary explicit.

The wrapper checks these count relations and withholds a result if they
contradict the cap corollary. It does not silently claim the point checker
verified a trace or degree. A false-square request, for example, reports
conservative bound 34 with actual count 4; the bound does not claim its degree
is 32. The sharper exact n+D theorem is proved above and audited separately.

The 264 hard budget remains unchanged for compatibility, even though the
proved worst-case count is 40. Other resource limits can still interrupt
normalization, substitution or checking before success. The new bound is not
an assertion that all admitted inputs will finish or that elapsed runtime
improved. Fresh checking of a supplied point, including a high-degree AST
outside constructor normalization caps, does not receive this constructor-only
bound metadata.

## Reproduce the sharp boundary

```sh
python -B -m foundation_math polynomial-witness examples/polynomial-witness/sharp-40-trials.json
```

The constructed point has x=32 and all seven unused coordinates equal to zero.
Its mismatch is 32!, and both actual trials and the reported conservative cap
are 40. This fixture is synthetic; no application polynomial is involved.

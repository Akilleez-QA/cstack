# Mathematical certificate justification

## Object and scope

Fix explicitly supplied `A` in Q^(m×n) and `b` in Q^m, including the
nonnegative dimensions. All multiplication and equality are exact rational
operations. The API admits only explicit rational entries, not symbols, unknown parameters
or numerical approximations. All inputs used to develop and test this lab were
synthetic, not project-specific instances. The API does not detect provenance;
its statement concerns only the supplied A and b, with no automatic
correspondence to an external project or theorem.

A certificate embeds a copy of the system for binding, but verification takes a
**separate expected system** and compares every coefficient, dimension and input
domain before accepting any claim. Domain Z requires integer input tokens for
both A and b; every conclusion below remains over Q.

## Consistent certificate

The certificate contains a rational vector x0 and a frozen matrix certificate
for A. The independent frozen verifier checks:

1. An elementary row-operation transcript, with only swaps of distinct rows,
   multiplication by a nonzero rational, and addition of a nonzero multiple of
   a different row. Each operation is invertible over Q. The transcript is
   replayed on both A and I_m, producing R and U.
2. Exact agreement of replayed matrices with the claimed R and U, plus the
   independent identity `U*A=R`.
3. The defining RREF conditions. If r is the number of pivots, `rank(A)=r`
   because U is invertible and R has exactly r nonzero pivot rows.
4. A proposed `N` of size n×(n-r), with `A*N=0`. The rows of N corresponding
   to the ordered nonpivot columns of R must be the identity of size n-r.

The fourth check proves linear independence: if `N*c=0`, the selected free
coordinates give `c=0`. Rank-nullity gives `dim ker(A)=n-r`, so these n-r
independent kernel vectors form a complete Q-basis. Membership alone would not
be enough; dependent or incomplete lists are rejected.

The system verifier separately computes `A*x0` from the expected A and compares
it to the expected b. No producer-derived transformed RHS is trusted for this
step. Thus x0 is a solution. For any rational c,

`A*(x0+N*c) = A*x0 + A*N*c = b`.

Conversely, any solution x has `A*(x-x0)=0`, so completeness of N implies
`x-x0=N*c`. The solution set is exactly this affine space; its rational
parameter c is unique because N is independent. The checker accepts any valid
x0, not merely the producer's free-coordinates-zero choice.

The frozen matrix certificate also contains a determinant check where square;
it remains part of that unchanged certificate schema, but is not a logical
requirement of the new system theorem.

## Inconsistent certificate

The certificate contains a rational vector `y` of length m and a claimed
rational value delta. The independent checker computes both products directly
against expected A,b and requires

`y^T*A=0`, `y^T*b=delta`, and `delta!=0`.

If a solution x existed, associativity gives
`delta=y^T*b=y^T*(A*x)=(y^T*A)*x=0`, a contradiction. Therefore no rational
solution exists. This certificate needs no rank claim, row-operation transcript,
producer, elimination, or matrix certificate. Scaling y and delta by the same
nonzero rational preserves a valid certificate and is accepted.

## Why the producer finds one of the two outcomes

The frozen producer constructs invertible U and RREF R with `U*A=R`. The system
producer computes `c=U*b` exactly.

- If some row i>=r has `c_i!=0`, row i of R is zero. Taking y to be row i of U
  gives `y^T*A=0` and `y^T*b=c_i!=0`.
- Otherwise, take all free coordinates of x0 to be zero and each pivot
  coordinate to be the corresponding c_i. The pivot-row form of R gives
  `R*x0=c`. Multiplication by U^(-1) yields `A*x0=b`.

This is an algorithmic completeness argument **conditional on sufficient
configured resources**. An input within dimension/bit limits can still exhaust
intermediate-bit, work, operation, structural or byte budgets. Such exhaustion
returns an error, never either mathematical outcome or a partial certificate.
Soundness does not depend on the producer implementing this argument correctly:
solve always runs the independent checker before exposing success.

## Zero dimensions and degenerate cases

- m=0, n>0: there are no equations. The particular vector is zero and N=I_n;
  all Q^n is the solution space.
- m>0, n=0: the only candidate x is the empty vector. The system is consistent
  exactly when every b_i=0. Otherwise a coordinate row vector gives a witness.
- m=n=0: the unique empty vector solves the empty system; N is 0×0, with zero
  nullity. The frozen determinant convention is det(empty)=1.
- A=0: consistency is exactly b=0; if consistent N=I_n.
- Full column rank: N has n rows and zero columns, retaining the explicit shape;
  any solution is unique. Overdetermination alone does not imply inconsistency.
- Rank deficiency alone does not imply inconsistency or consistency.

## Evidence boundary

The checker is executable Python, not a formally verified kernel. Its arithmetic,
parser, schema/budget checks, frozen verifier and Python runtime remain in the
trusted computing base. Producer and oracle tests strengthen engineering
evidence but are not unrestricted proofs. No correspondence to an informal
external problem, a generic/family theorem, integer solutions, or a runtime
proof obligation is asserted or automatically registered.

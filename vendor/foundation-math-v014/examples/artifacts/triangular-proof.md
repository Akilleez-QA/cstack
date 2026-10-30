# Toy claim: the first n positive integers

This is a proof draft, not an independently reviewed or formally checked result.
All variables and operations below are in the ordinary integers.

## Claim toy.triangular

For every integer n >= 0,

    2 * sum(k for k = 1, ..., n) = n * (n + 1).

The sum is defined to be zero when n = 0.

Proof draft by induction on n:

- Base case n = 0: both sides are zero.
- Inductive step: suppose 2 * S_n = n * (n + 1), where
  S_n is the sum from 1 to n. By the definition of the sum,
  S_(n+1) = S_n + (n+1). Therefore

      2 * S_(n+1)
        = 2 * S_n + 2 * (n+1)
        = n * (n+1) + 2 * (n+1)
        = (n+1) * (n+2).

  This is the desired identity for n+1. Mathematical induction gives the
  identity for all integers n >= 0.

## Claim toy.first_ten

The sum of the integers from 1 to 10 is 55.

Deduction from toy.triangular: substitute n = 10, giving 2 * S_10 = 110.
Cancellation in the integers gives S_10 = 55.

## Scope and trust

This argument uses the induction principle and ordinary integer arithmetic.
The accompanying executable checks only the finite range 0 through 1000.
That check can catch some transcription errors, but cannot establish the
universal claim, validate the induction principle, or substitute for review.

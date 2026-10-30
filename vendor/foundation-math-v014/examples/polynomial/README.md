# Polynomial examples

Run `python -m foundation_math polynomial examples/polynomial/NAME.json`.

- `distributivity`: `(x+1/2)(y+2/3) = xy+(2/3)x+(1/2)y+1/3`; true, exit 0.
- `false-square-identity`: `(x+y)² = x²+y²`; false, exit 1, coefficient witness
  2 at exponent tuple `[1,1]` (the monomial xy). Powers are expanded into the
  allowed multiplication AST, not parsed from strings.
- `euler-sequence-composite`: `x(−y)+yx=0`; true, exit 0. Only a polynomial
  composition certificate; the separate written chart argument in
  `docs/EULER-SEQUENCE-PITFALL.md` handles bundle exactness and the rank pitfall.
- `rejected-division`: attempts `x/x=1`; rejected, exit 2, because the domain
  is a polynomial ring, not a localization or rational-function field.

All examples use universal indeterminates. No chosen instance coefficients,
point evaluations, model providers or external services are needed.

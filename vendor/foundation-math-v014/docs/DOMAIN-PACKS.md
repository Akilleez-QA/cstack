# Domain packs and the agentic calculator

A domain pack makes the meaning of a calculation explicit enough that agents and independent checkers can agree on what was done. It is not a prompt containing subject vocabulary.

## Required interface

1. **Objects**: canonical representations, equality semantics, allowed coefficients and parameters.
2. **Operations**: typed inputs/outputs, side conditions, failure behavior and cost bounds.
3. **Obligations**: what must be proved before an operation is valid.
4. **Certificates**: data sufficient for a smaller checker when feasible.
5. **Verifier**: implementation, version, supported scope and trusted dependencies.
6. **Adversarial examples**: a wrong domain, missing hypothesis, boundary value, invalid certificate and resource-limit case.
7. **Transfer contract**: the theorem relating a computed representation to the original mathematical object.

## Distinct kinds of checking

- **Exact scalar arithmetic**: rational inputs produce rational results; an integer-domain division with a nonintegral result is rejected.
- **Polynomial identities**: a normal-form checker can verify equality in a declared polynomial ring. It does not automatically certify equality on a quotient, a localization or a scheme.
- **Finite enumeration**: a checker validates every item only after a proof establishes that the domain is complete.
- **Linear algebra**: field, characteristic, basis and matrix provenance are part of the claim. Floating-point rank and exact rank are different operations.
- **Numerics**: precision, conditioning and certified enclosures matter. A small residual is not an existence theorem.
- **Formal logic**: the formal statement, proof term, imports and axioms define what was checked.

The seed implements exact scalar arithmetic and the focused
[Q-polynomial identity domain](POLYNOMIAL-DOMAIN.md), with exact coefficient
witnesses and bounded inputs. v0.3 integrates both through the
[typed work queue](DOMAIN-RUNTIME.md), including explicit evidence requirements.
The remaining domains are extension contracts, not supported capabilities.

## Side conditions are work items

A request to cancel a factor creates a nonzero-factor obligation or a case split. A request to invert a matrix creates an invertibility obligation. A theorem import creates hypothesis-matching obligations. The orchestrator should schedule these explicitly rather than burying them in the proposer’s explanation.

## Certificate-producing computation

Separate the expensive search from the cheap check when possible. A searcher may propose a factorization, witness, exhaustion bound or proof term. The checker validates the proposed certificate independently of how it was found. A negative search result means only that the stated search did not find a witness unless its completeness was proved.

## Lean bridge

A domain pack may translate supported objects and obligations to Lean declarations. Preserve a correspondence map from the original problem to those declarations. A successful kernel check proves the formalized statement; the translation and its applicability remain explicit review obligations. Do not claim that a narrow arithmetic Lean adapter already formalizes general algebraic geometry or arbitrary mathematical prose.

# Architecture: the agentic mathematician

## A narrow reusable core

The core owns the problem contract, work graph, evidence identities, task ownership, budgets and state transitions. It should not contain a theorem-specific search strategy or assume every mathematical domain has the same decidable questions.

A problem is not a prompt alone. It includes the statement, mathematical universe, coefficient field or ring where relevant, quantifiers, permitted assumptions, imported results, intended equivalence relation, exclusions and a checkable finish condition.

## Roles and boundaries

| Role | Produces | Cannot authorize |
| --- | --- | --- |
| Planner | A bounded obligation graph and proposed attacks | Treating an unsolved dependency as established |
| Proposer | Conjectures, reductions, proof candidates | Promotion based on fluent prose |
| Calculator | Exact results or explicitly approximate observations | Claims outside the input domain or coverage |
| Critic | Counterexamples, missing hypotheses, rival explanations | Silent changes to the target theorem |
| Verifier | Scoped evidence about a pinned artifact | Verification of a different revision |
| Formalizer | A formal statement and proof candidate | Equivalence to the informal statement by assertion |
| Integrator | Compatible accepted results and remaining obligations | Merging conditional claims into an unconditional theorem |

These are roles, not a requirement to spend one model invocation on every box. Cheap deterministic checks should precede expensive reasoning. Independent mathematical review needs a genuinely independent derivation or test path, not a second copy of the author's output.

## Tool requests carry domains

The calculator interface should carry:

- domain and object type, including exact versus approximate semantics;
- operation and operands in a structured representation;
- assumptions and side conditions;
- resource budget and precision policy;
- expected certificate or result type;
- backend/version and environment identity.

For example, division in integers, rationals, a finite field and interval arithmetic are different contracts. A nonzero rational denominator is a side condition. A finite-field modulus needs a field-validity contract. A symbolic cancellation needs a nonzero assumption or a split into cases. Unsupported domains must fail explicitly rather than silently fall back to floats.

## Verification interfaces

A backend returns evidence, not a universal truth flag. Evidence includes the exact input, output, command or operation, backend identity, artifact digest, covered domain, declared assumptions and limitations. Formal checking additionally records the elaborated target, imports, axioms and trusted components.

The orchestrator stores tool evidence separately from agent narrative. A rejected or timed-out check cannot be converted to success by an agent's explanation. A retry gets a new attempt identity; it does not erase the earlier result. Corrections invalidate dependent claims until rechecked.

## Execution boundary

The initial prototype accepts structured proposals and uses deterministic local tools. A model-provider adapter is a separate component, not an implicit API call. Future provider execution must preserve the same contracts, permission boundaries and budgets.

Lean source and general-purpose computer-algebra inputs are executable code, not harmless data. Production deployments need process and filesystem isolation, resource limits, network restrictions, and a controlled toolchain. A Python subprocess timeout alone is not a security sandbox.

## Executed v0.3 boundary

The fixed `DomainHandler` protocol separates goal admission, candidate validation,
deterministic calculation and mathematical acceptance for scalar Z/Q and formal
Q-polynomials. The core owns evidence requirements and task-state transitions.
See [DOMAIN-RUNTIME.md](DOMAIN-RUNTIME.md) for exact API and receipt semantics.

A complete deterministic receipt is compared with replay of the pinned goal,
not just a returned value or success label. An identity requires literal boolean
true. `formal_proof` requirements cannot be satisfied by this runtime; they remain
blocked even after exact agreement. The Lean adapter remains separate, and
free-text assumptions do not change the formal domain or prove correspondence.

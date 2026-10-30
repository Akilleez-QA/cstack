# Roadmap

## Seed: inspectable local vertical slice

- Structured problem and task contracts.
- Deterministic queue and evidence handling.
- Exact integer/rational calculator.
- Lean invocation adapter with honest unavailable/failure outcomes.
- Dependency-aware claim ledger and negative tests.
- Small examples and reusable lessons.

Acceptance: commands reproduce their recorded outcomes; unsupported operations fail clearly; narrative alone cannot close a proof obligation. Final implementation and test coverage must be checked against this list before describing it as delivered.

## Local agent tool boundary (v0.5)

A fixed stdio JSON-RPC bridge now exposes exact scalar computation, polynomial
identity comparison, finite-box counterexample search and fresh witness checks.
It is a custom protocol, not MCP; no live provider or external agent integration
was executed. The immutable mathematical backends and acceptance gates are
unchanged. See [AGENT-BRIDGE.md](AGENT-BRIDGE.md).

## Next: actual agent execution

Completed focused extensions: an exact Q-polynomial domain with typed ASTs,
addition/multiplication, identity normalization and mismatch coefficient witnesses;
and typed queue integration with complete goal/receipt binding and explicit
exact-computation versus formal-proof requirements. See
[POLYNOMIAL-DOMAIN.md](POLYNOMIAL-DOMAIN.md) and
[DOMAIN-RUNTIME.md](DOMAIN-RUNTIME.md). Neither extension advances the
live-provider or general formalization items below by implication.

- Provider-neutral model interface with explicit model/tool budgets.
- Planner, proposer and critic loops that emit structured proposals.
- Counterexample-first attack selection.
- Domain packs with typed objects and side-condition generation.
- Isolated calculator and Lean workers.
- Formal statement comparison and axiom/dependency audits.

Acceptance: an end-to-end problem produces a reviewable obligation graph and independently checked result, including failures and unresolved obligations. No provider integration is claimed by the deterministic seed.

## Later: research-scale operation

- Parallel complementary attacks with leases and conflict detection.
- Certificate-producing finite enumeration and symbolic reduction.
- Reusable verified libraries and method applicability contracts.
- Proof dependency invalidation after corrections.
- Resource-aware scheduling that avoids duplicate or exhausted experiments.
- Evidence-grounded progress visualization and public-safe publishing.

A benchmark result, tool feature or closed subcase does not establish general mathematical competence. Evaluate each added domain against explicit tasks, adversarial cases and reproducible baselines.

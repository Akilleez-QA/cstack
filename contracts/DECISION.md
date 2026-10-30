# ADR 001: POODO core and domain capability extensions

Cstack is a local-first prototype with a reusable POODO control core. Foundation Math is its first domain capability pack. Film, Refrigeration, Robotics and Template are vendored under `foundations/` with their own adapters. Foundation Engine is linked only and has no adapter yet. None of them is a subclass of Math.

The application core owns goals, phases, decisions, authorization enforcement, capability routing and the authoritative evidence ledger. Domain extensions own their subject's meaning, constraints and acceptance criteria. Core policy cannot widen domain evidence or equate tool success with proof.

Use a small concrete PoodoCore base with a thin FoundationMath subclass and compositional DomainExtension hooks. Keep concrete execution, storage and protocol adapters outside the core. Each extension declares a compatible contract version and passes shared conformance/negative tests.

The first integration is a non-MCP harness calling Foundation Math's existing foundation-math-jsonrpc/1 stdio bridge without modifying its 19 tools. The alternative direct-import path would couple the core to Math internals. A real MCP adapter remains separately versioned work: modern 2026-07-28 lifecycle and legacy 2025-11-25 lifecycle are not interchangeable.

Endoforge is the intended generative UI and disposable-software engine. Foundations power generated artifacts with domain knowledge, exact primitives, constraints and checks. POODO governs synthesis, evaluation, activation, disposal and retention; lower execution runtimes remain replaceable. This is a composable ports arrangement, not a rigid linear stack. Endoforge generation is not implemented in this slice.

The first success surface is a synthetic exact calculation routed through a goal, precommitted decision and explicit capability grant, plus an honest negative mathematical result. Neither automatically closes the goal. An unrelated fake domain proves the core does not depend on Math's numeric assumptions.

Revisit the decision when a real second domain requires core changes, a verified alternative runtime cannot preserve the capability contract, an extension needs control-policy overrides, or validation exposes evidence promotion, source drift or hidden effects. Preserve failed attempts and revisions. Do not hide uncertain execution outcomes by retrying them automatically.

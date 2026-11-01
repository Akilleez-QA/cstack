# Software engineering procedures

Use only within an invoked POODO run when software implementation, investigation, architecture, or release work is in scope and a procedure below can answer a material question. Select the applicable procedure; reading this file does not require performing every procedure. Using a script to analyze a non-software problem is not sufficient reason to apply software-development workflows.

POODO retains its domain-independent phases, evidence states, authority, predictions, contradiction handling, and canonical ledger. These procedures produce inputs to those phases. They do not start another controller, restart a completed phase, add an option-enumeration requirement, or authorize external actions. For mixed work, bind each procedure to the software workstream; assess non-software outcomes on their own success surfaces.

## Trace the relevant system

Start at the entry point exercised by the requirement or failure. Follow calls, data transformations, state transitions, domain representations, and external boundaries until the relevant behavior is explained or a connection remains unresolved. Record exact symbols and files, state ownership, persistent effects, and the consumer-visible result. Include failure, cancellation, concurrency, and recovery paths only where they could affect the question.

Separate inspected source structure from observed execution. An import graph does not establish that a path ran; instrument or exercise the bound artifact when runtime behavior is load-bearing. Record unresolved edges rather than filling them from naming conventions.

## Recover historical constraints

When a proposed change depends on why the current design exists, inspect relevant commits, prior names, substantive review discussion, and linked records that are available and authorized. A last-touch commit may identify an editor without establishing the original rationale.

Translate supported findings into constraints: behavior to preserve, behavior authorized to change, approaches to avoid, and unresolved risks. Retain each finding's provenance and uncertainty. Historical intent informs the current decision; it does not override a newer requirement or prove current behavior.

## Compare interface designs

For a consequential ownership or boundary change, write representative caller usage before deriving types, signatures, module responsibilities, state ownership, validation boundaries, and invariants. Compare structurally different feasible designs selected from the existing Orient alternatives. Use the scope's existing criteria; do not repeat the twenty-path exploration for each method or worker.

Review whether callers must orchestrate internal stages, multiple modules encode the same policy, several writers mutate canonical state, public interfaces expose storage or transport internals, or lists require manual synchronization. A forwarding layer must have a specific adaptation or policy responsibility. Treat these as review questions, not universal prohibitions.

Repeated independent deviations of the same kind can disconfirm the sketch: accumulating special cases, type escape hatches, callers importing internals, or unexpected shared-state coordination. Record the mismatch and revisit the affected design decision instead of silently changing its contract.

## Investigate a defect

Bind the reported failure to its trigger, artifact, inputs, environment, and intended user surface. Reproduce there when accessible and authorized. If access is missing, retain the unverified report and use the smallest reachable probe; report what that probe cannot establish.

Choose observations that distinguish competing mechanisms. Add focused instrumentation where the relevant state is not observable. Link each proposed patch to the hypothesis and evidence that justify it; remove unsupported speculative changes when that hypothesis is refuted. Keep cause unresolved if the observations do not discriminate.

When an economical regression test captures the original failure, observe it fail before the implementation change and pass afterward. Do not impose tests or separate failing-test commits on routine edits without a meaningful failure oracle. Retest the original consumer surface for the outcome claim; a unit test supports its narrower tested boundary.

## Implement and partition changes

Validate untrusted representations at the relevant boundary and convert them to domain types. Rely on internal invariants only where their enforcement and ownership are established. Check migrations and alternate writers before treating an invariant as universal. Keep implementation-specific wire and framework details behind the interface where feasible.

Partition parallel changes by writable files, branches, canonical state, and external effects. Assign one integration owner where workers share a dependency. Prefer independent write targets before introducing serialization. For retryable operations, specify duplicate execution and partial-failure behavior; reconcile current state before replaying an interrupted external action. Use the host's actual tools and concurrency limits, preserving current configuration and authorization.

## Verify behavior and release dependencies

Bind each result to its repository, base and head revisions, material inputs, test method, environment, and tested artifact. Include the built or running artifact's identity when a runtime claim depends on it. Repository identity is required when PR numbers or branch names are reused across projects. Worker output is a scoped observation or analysis, not an automatic outcome verdict.

Exercise the consumer boundary with an independently grounded expected behavior or invariant. Check that the oracle could detect a plausible defect or ineffective implementation. Shared implementation/validator assumptions limit independence; legitimate type, absence, invariant, and metamorphic checks retain their narrower claims.

For consequential release verification, use a non-author reviewer when available and record the actual independence and coverage. CI completion supports the checks it ran. It does not establish untested user, business, device, or field outcomes.

If the patch, base dependency, material input, or runtime identity changes, mark affected results stale and rerun the necessary checks. Matching source or patch hashes supports identity within their defined scope; it cannot establish runtime equivalence. Do not reuse a development-server verdict without identifying the running artifact.

For dependent delivery units, advance only through the verified dependency frontier. Stop at the first unmet required checkpoint, even when a descendant passes. Re-read the forge's actual state after an interrupted merge request or watcher notification. After each authorized landing, refresh the base, dependency graph, current patch, mergeability, and required checks before proceeding. No fixed forge, stack tool, cloud reviewer, merge strategy, or automatic merge permission is assumed.

## Return to the POODO ledger

Return the workstream and acceptance IDs, artifact/input/environment identities, method, evidence locators, criterion results, coverage gaps, and contradictions to the existing ledger. Distinguish delivery state from outcome state using POODO's terminal claim contract. New observations may reopen an affected decision; workers cannot advance the authoritative phase themselves.

Selected procedures are adapted from [pstack 0.15.15 at the pinned source revision](https://github.com/cursor/plugins/tree/df581122cde17e6e27686b5a448bde23e4ad4318/pstack). Attribution and the upstream license are preserved in [the third-party notice](../THIRD_PARTY_NOTICES.md). There is no runtime dependency on that package.

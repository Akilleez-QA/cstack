# ADR 005: The software factory's control system, with eight port lanes of replaceable adapters

Status: **Proposed** (2026-10-25). the owner has answered the four open questions (see "the owner's answers"); he still accepts or rejects the ADR as a whole. Nothing below is built until its own PR lands; each item names one. Merging follows AGENTS.md rule 5.

## Context

the owner's direction on 2026-10-25:

- "The whole point of founder stack is that everything is replaceable."
- "POODO and Endoforge as core."
- "The digital software factory needs a control system, with Grok Bot HMI."
- Paperclip is no longer used, and neither is OpenClaw. Both remain harvest sources on the parts wall.

the owner's founder stack (`~/.codex/founder-stack/`; Mac backup, newest file 2026-08-08) puts eight lanes around a core of doctrine and policy. Every outside tool attaches to one named port on one lane.

The mapping onto cstack is parts-wall/oss/founder-stack/ARCHITECTURE-MAP.md (not included), added in PR #65 (open). It was checked against `main` on 2026-10-25. One of its status rows is now stale: ADR 003 is on `main` (#62). It found:
- Truth and Evidence are covered.
- HMI, Runtime, Supervisor and Tool are partial.
- Learning and ReadModel have no port.
- Six places hard-wire a vendor, one of them (Tailscale WhoIs) planned but not yet built.
- Founder stack allowed one exception to replaceability: Paperclip, accepted as a strategic dependency. That exception did not survive.

The current framing, "the POODO core runs on Endoforge" (`AGENTS.md`, parts-wall/STAGING.md (not included)), treats Endoforge as a runtime underneath POODO. This ADR moves Endoforge into the core instead (see "Supersedes and amends").

"Lane" below always means a **port lane**. Endoforge's own "execution lanes" (Wasmtime, native Rust; forge/endoforge/docs/execution/EXECUTION-PLAN.md (not included)) are a different thing.

## Decision

### 1. The core is the factory plus its control system

Read cstack as a process plant:

| Plant term | Cstack |
|---|---|
| The process | **Endoforge**: the digital software factory's lifecycle (generate, qualify, preview, activate, dispose) and its rules |
| The basic process control system (BPCS): setpoints, permissives, control interlocks | **POODO** (`poodo_core/`): goals, phases, decisions, authority, ask/deny, budgets, evidence rules |
| The operator interface | **HMIFace**. Grok Bot is the current adapter. |
| Field devices | Adapters on the other lanes: Foundations, model runtimes, ledger stores, tools |

**What the core is.**
- **The core is POODO plus Endoforge's lifecycle model.** POODO governs that lifecycle: generation grants nothing, and qualification, activation and disposal are POODO decisions.
- **The model runtimes are not core.** Codex CLI, local Qwen and the Wasmtime and native lanes are RuntimeFace adapters behind `EndoforgePort`.
- **`EndoforgePort` is a core seam, not a lane.** It is the contract between POODO and the Endoforge lifecycle, and it is reserved and empty today (`ports.py:46-52`). It sits beside `DomainExtension` and `Cancellation`.

**Where the code is today.**
- `forge/endoforge/tools/factory_runtime/` and `factory_campaign/` call the Codex CLI and Qwen through `subprocess`.
- Nothing in `forge/` imports `poodo_core`.
- So "POODO governs Endoforge" is not yet true in code. Until item 12 lands, that code sits outside the core boundary.
- The **Endoforge core path** will be `forge/endoforge/core/` (created by item 12), held to the same rule as `poodo_core/`.

**What stays the same.**
- **The hexagon's dependency rule stands** (INTERFACES.md, "Ownership and dependency direction"):
  - the core imports no provider, transport, vendor CLI, UI, Foundation or subprocess module;
  - `bootstrap.py` is the only composition root;
  - driving adapters call the core's public API.
- **The eight lanes classify the ports and adapters.** They don't add new sides to the hexagon.

### 2. Eight port lanes

Each port protocol in `poodo_core/ports.py` sits in at most one lane. Records and core methods are the lane's contracts, not ports.

| Lane | Plant role | Port protocol on main | Contracts in this lane | Current adapter(s) | Status |
|---|---|---|---|---|---|
| **HMIFace** | Operator interface | none. Driving entry is `PoodoCore`'s public API. | MCP tools 1:1 with core operations (ADR 003) | `cli.py`. Grok Bot via the MCP stdio server (#57–60, open). | partial: no cockpit |
| **TruthFace** | Setpoints, recipes, permissives | `ApprovalPort` | `GoalContract`, `AuthorityGrant`, `ApprovalRecord`, `CostBudget`, `LivenessRecord`; the AOR registry | approval store (merged); Friday channel (#47, open); `aors/fleet.json` | covered: no blocker graph |
| **RuntimeFace** | Final control elements | none yet (item 11). Model runtimes will attach behind `EndoforgePort`. | `adapters/execution.py` bounds | codex-task (merged); Endoforge step harness (#46, open); snapshots (#48, open) | partial: no execution router |
| **EvidenceFace** | Sensors and historian | `LedgerPort` | `CapabilityOutcome`, certainty, receipts | `MemoryLedger` (merged); WitnessedLedger (#25, open); claim gate | covered |
| **SupervisorFace** | Monitoring, alarms and protection (see below) | `CostPort` | liveness (`record_liveness`, a host call into the core) | spread across core, `provider_policy`, shields and host scripts | partial |
| **ToolFace** | Instruments and field devices | `CapabilityPort` | `CapabilityRequest`, tool pins | Foundation bridges (merged); MCP client (#49, open) | partial |
| **ReadModelFace** | Historian trends and reports | none | none | Friday morning brief (prose) | gap |
| **LearningFace** | Lessons learned, feeding management of change | none | the `learning` ledger kind (unused) | none | gap |

Core, no lane: `DomainExtension`, `Cancellation` and `EndoforgePort`.

The plant reading gives three rules.

1. **Protection is independent of control.**
   - Two things inside POODO are BPCS interlocks: budget pauses and ask/deny. They live in the control system by design.
   - Founder-stack invariant 8, "No runtime may be its own only watchdog", applies to the protection layer, which sits outside every runtime. That layer has two parts:
     - **The emergency stop that acts.** Shields-up and the kill switch, which ADR 004 allows on a local intent without quorum. They are akin to a safety instrumented system's trip.
     - **Watchers that only report and alarm.** This is independent alarm management (ISA-18.2), not a safety system.
   - No protection element runs inside the runtime it protects, or is owned only by that runtime's bot. Alarms reach the owner by a path that doesn't pass through the watched runtime.
2. **Changes go through management of change** (OSHA PSM 1910.119(l)).
   - MOC is a procedure, not a lane. It covers:
     - changes to doctrine, skills and role files;
     - adapter swaps that are not like-for-like;
     - changes to grants, AOR effects, budgets and other setpoints.
   - Each is an ask-class decision approved by `owner-via-approver` (ADR 003). An AI never approves it.
   - Doctrine edits are PRs today, under AGENTS.md rule 5. Bringing doctrine paths under ask-class approval needs that rule amended. This ADR proposes the amendment; it does not make it.
3. **LearningFace feeds MOC and never executes.** A promoted learning takes effect only through a separate, approved TruthFace or RuntimeFace change.

### 3. The replaceability test

A test-only composition root mirrors `bootstrap.py`. For each lane with a port, it replaces the lane's adapter with a fake and runs a named list of tests. The lane passes when all three hold:

1. Those tests pass with the fake.
2. A static import check shows `poodo_core/` and the Endoforge core path import no adapter, vendor, network or subprocess module.
3. `git diff --quiet -- poodo_core/ forge/endoforge/core/` holds for the change that adds the fake.

For lanes with authority paths, "pass" also means the following are exercised with the fake:
- approval pending;
- approval declined;
- budget refusal;
- `unknown` certainty after dispatch.

| Lane | Fake | Replaces | Testable |
|---|---|---|---|
| TruthFace | a fake approver writing `ApprovalRecord`s | Friday | now |
| ToolFace | the existing fake capabilities and a fixture MCP server | Foundations, third-party servers | now; the MCP part once #49 lands |
| EvidenceFace | `MemoryLedger` | WitnessedLedger | once #25 lands (until then `MemoryLedger` is the only adapter) |
| HMIFace | an in-process MCP client script | Grok | once #58 lands |
| SupervisorFace | a fake cost port and a fake admission port | host limits | after item 5 |
| RuntimeFace | a fake code writer | Codex | after item 11 |

**Hard-wired lanes.** A lane that cannot pass is hard-wired and goes on the backlog in decision 8. A new lane port lands only together with its fake and its test.

**The adapter inventory.** `contracts/ADAPTERS.json` has one row per attachment, keyed by adapter id. An adapter on two lanes has two rows. Each row records:
- the lane and the port;
- the vendor;
- `kind`: `python_module`, `repo_path` or `external_command`;
- the path or command;
- the fake used in the lane's test;
- `behind_port` or `hard_wired`;
- the strategic-dependency ADR, if any.

**The inventory test.**
- It scans `adapters/*.py`, `tools/*.py`, `extensions/*.py` and `products/hmi/**/lib/*`.
- It fails when a scanned file has no row.
- It fails when a `python_module` or `repo_path` row names a path that does not exist.
- `external_command` rows (`gh`, `codex`, `grok`, host scripts) are listed but not checked for existence.

### 4. Strategic dependencies only by explicit ADR

No adapter may become irreplaceable unless an ADR accepts it as a strategic dependency. That ADR must name:
- the replaceability test it is exempt from;
- why;
- a review date;
- the exit plan.

**No strategic dependencies are accepted today.** Paperclip's withdrawal is the precedent that an acceptance can be revisited and reversed.

Founder-stack invariants 12 and 13 are restated without a vendor name:
- Each TruthFace port has exactly one canonical adapter at a time, chosen by ADR.
- No read model, cockpit or report may override or obscure that adapter, and each must cite its source and freshness.

### 5. Authority stays per lane, and flows inward only

- **Grants carry a lane.** `AuthorityGrant` gains a `lane`. The core refuses a grant whose lane doesn't match the attachment's lane in the inventory. ReadModelFace and LearningFace grants can never include `execute`. All of this is item 3.
- **Multi-lane adapters.** An adapter on several lanes holds one grant per attachment, and cannot use one to gain authority on another.
- **Context flows inward.** The host feeds adapters bounded context and capabilities. Adapters never reach back for memory, truth, credentials or execution power.
- **No keys.** Adapters are fed a signing capability, never a key (ADR 004).
- **Approvals come only from the owner, out of band.** HMI text, MCP elicitation answers, hook returns and tool output never create or carry an approval. the owner's answer arrives out of band, through the Friday channel or the phone passkey co-sign (#39).

### 6. An independent watcher for every runtime, and for the alarm path

| Watched | Watcher (on another host, not owned only by the watched runtime's bot) | Needs first |
|---|---|---|
| Grok Bot (box) | ADR 004 witnesses' stale-checkpoint alarm; a dead-man check on Grok Bot's board check-ins, written by Chief of Staff (not Grok Bot) on host-a; a read-only ledger evaluator | witness service deployed (ADR 004 plan item 4); #25 |
| Codex workers | codex-guard's ledger gate; the evaluator | #25 |
| Endoforge runtimes (#66 launcher) | the evaluator; Endoforge's planned external watchdog (WP16) | #25 |
| Atomizer swarm | the evaluator; `system-safety-status` | #25 |
| **Friday** (approval and alarm path) | the phone board's own push raises an alarm when Friday's brief or check-in goes stale | Friday channel (#47) |

A watcher only reports and alarms. Only the emergency stop acts.

### 7. What this ADR does not adopt from founder stack

- A tracker or any external product as truth.
- An AI as the promotion gate.
- Founder authority declared in a file (the delivery-scope guard's `authorizedBy: founder`).
- Autonomous assign, wake and kill loops (the Work Governor), against "a retry is a new explicit attempt".
- Routing artifacts as authority. They are evidence; the intent comes first (ADR 004).
- "Degraded but running" applied to authority. Authority fails closed.
- Raw credentials fed to adapters.
- Single-host leases with no device dimension.

Here the ADR knowingly departs from the architecture map. The map says to keep the hexagon and use the octagon only as a taxonomy. This ADR keeps that for the lanes, but moves Endoforge's lifecycle into the core. Every conflict with ADR 003 or ADR 004 above is resolved in favour of ADR 003 or ADR 004.

### 8. Delivery plan

Each item is one PR of about 400 changed lines or fewer. Merging follows AGENTS.md rule 5.

1. `contracts/ADAPTERS.json` and the inventory test.
2. Replaceability tests:
   - **2a:** TruthFace.
   - **2b:** ToolFace.
   - **2c:** EvidenceFace, after #25.
   - **2d:** HMIFace, after #58.
3. `lane` on `AuthorityGrant`, capability descriptors and AOR effects, with the per-attachment check. The "read-only lanes never execute" test starts as a placeholder until item 8.
4. An IdentityPort, with Tailscale WhoIs as its first adapter, keyed on node ID and tag. It lands before any WhoIs code. It is independent of the other items.
5. A SupervisorFace admission port, consulted at `start_goal` and `execute`, with refusals recorded like `budget_refused`:
   - **5a:** host capacity limits per AOR: open goals, live attempts and approval-queue size, plus a live cap where 0 means paused.
   - **5b:** resource leases (GPU, browser, provider, shared worktree), keyed per device and recorded in the ledger.
6. The watchers in decision 6, one per PR, each after its "Needs first".
7. GoalContract 0.2, with migration fixtures (INTERFACES.md):
   - **7a:** stop condition, risk class, evidence requirement, owning lane and scope.
   - **7b:** host-set never-dispatch risk classes: verification, release gates, security-critical work, truth mutation, billing and plant control.
   - **7c:** a requirement compiler that only proposes. `admit_goal` and the owner accept.
   - **7d:** red-team findings enter as deduplicated `proposal` events.
8. ReadModelPort:
   - **8a:** the port: projections with `source`, `as_of` and `confidence` that can never write truth.
   - **8b:** three projections:
     - goals assigned without a live path;
     - the evidence-backed closure rate;
     - how often the owner has to repair something by hand.
   - **8c:** a cockpit view in Grok Bot (the cockpit for now) and in the Friday brief.
9. LearningPort. Promotion candidates become `learning` events, and promotion goes through MOC.
10. A proposed AGENTS.md rule-5 amendment putting doctrine paths under ask-class approval. This one is for the owner and Chief of Staff.
11. Unwire the vendors:
    - **11a:** RuntimeFace code-writing port, with Codex as its adapter.
    - **11b:** split `no_direct_code.py` into a pure classifier plus per-vendor hook shims.
    - **11c:** route GitHub work state through a TruthFace adapter.
    - **11d:** rename codex-guard as an execution guard. It is in `products/hmi/`, so Grok Bot owns this one.
12. The Endoforge core boundary:
    - **12a:** create `forge/endoforge/core/` (the lifecycle model and rules), with the import check.
    - **12b:** define `EndoforgePort`.
    - **12c:** move the factory runtimes behind it as RuntimeFace adapters.

## the owner's answers (2026-10-25)

1. **GitHub is the current TruthFace adapter for code work state,** not a strategic dependency. It must pass the replaceability test like any other adapter (item 11c).
2. **Grok Bot also holds the emergency stop** (shields and kill switch), as well as being the HMI. Decision 6 is unchanged: Grok Bot's watchers stay independent of it, on other hosts and not owned by Grok Bot. Grok Bot's emergency stop is therefore an HMIFace adapter and the acting part of the protection layer at once, so it has two attachment rows in `ADAPTERS.json`.
3. **Field OS is a product (an expression) and a dedicated device, not the cockpit.** Grok Bot is the cockpit for now, and may be extended later. So:
   - the cockpit view in item 8c is a Grok Bot view;
   - Field OS's device gets a row in `aors/fleet.json` with its own owner bot, like every tailnet device (ADR 003).
4. **All gap lanes proceed after items 1–3.** Admission (item 5), read models (item 8), LearningPort (item 9) and the rest run in parallel, each as its own PRs, subject to the "Needs first" order in decision 6.

## Consequences

- **What a swap touches.** Once a lane passes its replaceability test, swapping that lane's adapter touches only adapter code, its generators and `bootstrap.py`.
  - Swapping Grok Bot also touches `tools/grok_profiles.py`, the MCP launcher and `products/hmi`, until items 2d and 11d land.
  - Swapping the identity source becomes possible only after item 4.
- **The costs:** an inventory to keep current, one fake per lane, and a written ADR before any vendor becomes load-bearing.
- **Founder stack's design becomes the port layout,** with the departures in decision 7.

## Supersedes and amends

These amendments apply on acceptance:

- **`AGENTS.md`, lines 7 and 9.** Replace "The POODO core sits at the centre and runs on Endoforge" with "POODO and Endoforge's lifecycle are the core: Endoforge is the factory, POODO its control system". Keep "POODO is the reasoning core".
- **parts-wall/STAGING.md (not included), diagram and line 28.** Show Endoforge's lifecycle inside the core, with its model runtimes on the Runtime lane. Keep the staging target ids, and give each a lane.
- **ADR 001** (`contracts/DECISION.md`): clarified, not reversed. It already makes Endoforge the engine POODO governs, and keeps lower runtimes replaceable.

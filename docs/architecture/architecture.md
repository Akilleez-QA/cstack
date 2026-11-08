# Cstack software design description

Status: reusable documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

## Purpose and design boundary

Cstack composes a control core with trusted domain extensions and bounded capability adapters. The core records goals, decisions, attempts and evidence while the host owns concrete implementation selection. This description covers the Foundation integration and its control path. Source files refer to ADR identifiers, but the inspected export does not contain those ADR documents.

## Engine layering and current implementation

The target design makes Endoforge the core engine for running coding agents with checks, caching and evidence receipts. POODO runs on Endoforge as the control and reasoning layer in `poodo_core/`. Domain extensions and adapters connect that layer to sibling Foundations, which own domain meaning and acceptance.

```mermaid
flowchart TB
    P[POODO: control and reasoning] -->|EndoforgePort: witnessed evidence| E[Endoforge local ledger]
    P -->|decision, grant| R[Endoforge workcells: compile, gates, kernel]
    R -->|proposals as data, through the host| P
    R -->|receipts| L[Endoforge run ledger]
    R -->|declared imports, in process| K[Foundation kernels]
    P --> A[Domain extensions and adapters]
    A --> F[Foundations]
```

Two parts are implemented. `poodo_core/ports.py` specifies `EndoforgePort`, implemented by `adapters/endoforge_ledger.py`; bootstrap binds host-configured local storage and a fresh session for CLI runs, and the CLI reports `endoforge_implemented: True` only when bound. The workcell runtime runs one `cstack_forge` goal through a POODO decision into the vendored EndoForge `IsolatePool`, gates and run ledger (`adapters/endoforge_workcell.py`, `adapters/workcell/`). Running many coding agents at once and EndoForge's caching remain future work. The [Endoforge ICD](../icd/icd-endoforge.md) records storage guarantees, the runtime boundaries and their limits, and [the explanation](../guides/explanation/endoforge-vendoring.md) walks through a run.

POODO retains policy and execution admission; Endoforge is allocated witnessed storage only. The adapter validates the entire chain and outcome bindings on each operation, returns detached documents, and acknowledges single-write appends after fsync. A lifetime file lock excludes competing writers; hosts serialize calls and preserve the bound file identity. Local durability provides no external witness or suffix-rollback detection. The pinned lifecycle slice has no applicable storage primitive. `LedgerPort` remains separate. The file adapter implements CS-REQ-024–026 under the CS-REQ-020–023 port contract; CS-REQ-027–030 govern configured routing.

Configured cores witness decisions at creation and again before dispatch, including host approval records. Declines are witnessed before refusal. Precommit errors prevent dispatch and latch further witnessed work; outcomes are witnessed before normal completion. Outcome failures leave attempts consumed and budget/capacity holds unsettled for host reconciliation. Bootstrap owns storage lifetime; request data cannot select it. Unconfigured cores and AOR hosts retain their existing composition.

## Decomposition and allocation

| Element | Implementation | Responsibility |
|---|---|---|
| Composition root | `bootstrap.py` | Registers domains, selects roots, checks grants and constructs cores |
| Control core | `poodo_core/` | Phase, authority, decision and evidence lifecycle |
| Contracts | `contracts/`, `schemas/` | Structured host/core and bridge data contracts |
| Domain extensions | `extensions/foundation_*.py` | Descriptors, admission and interpretation with stated evidence limits |
| Math adapter | `adapters/math_stdio.py` | Dedicated pinned v0.14 protocol and schema enforcement |
| Shared Foundation adapter | `adapters/foundation_stdio.py` | Profile-driven pins, schema checks and receipt binding for the vendored Film, Refrigeration, Robotics and Template Foundations |
| Engine adapter | `adapters/engine_stdio.py` | Pinned partial copy of the Foundation Engine bridge; two read-only validators admitted as tool observations |
| Forge runtime | `extensions/cstack_forge.py`, `adapters/endoforge_workcell.py`, `adapters/workcell/` | One governed EndoForge run per call, registered in `bootstrap.RUNTIMES`, separate from Foundations |
| Witnessed evidence | `adapters/endoforge_ledger.py` | `EndoforgePort` file adapter: hash-chained, fsynced, exclusively locked |
| Process executor | `adapters/execution.py` | Fixed module launch, deadlines, cancellation, output bounds and cleanup |
| Math backend | `vendor/foundation-math-v014/` | Vendored exact/formal tools and bridge |
| Engine backend | `vendor/foundation-engine-v020/` | Bridge, tool schema and upstream source manifest only |
| EndoForge slice | `vendor/endoforge/` | Lifecycle, run ledger, gates and evaluator, `IsolatePool` and capacity planner, byte-pinned |
| Local domains | `foundations/template/`, `foundations/refrigeration/`, `foundations/robotics/`, `foundations/film/` | Domain bridges, public example logic, tests and source manifests |
| Research consumer | `foundations/math/` | `fm_research` claim DAG and exact-kernel research layer over vendored Math |

## Control and data flow

1. The host selects a registered domain and creates a ToolFace grant for fixed operations and the selected goal.
2. The composition root checks the grant against `contracts/ADAPTERS.json` and binds the core to a ledger.
3. The caller supplies structured goal and request data. Core phase, revision, authority and decision checks precede execution.
4. The adapter checks source identity and probes the bridge catalog when needed. The executor launches a fixed bridge module from the trusted source root.
5. The bridge receives an initialization frame followed by a catalog or tool request. The adapter validates framing, correlation, schemas and evidence ceilings.
6. The core records the outcome and domain interpretation. A tool observation does not automatically accept the goal.

The Math adapter is intentionally separate from the shared sibling adapter: shared receipt-binding behavior must not be assumed to apply identically to Math. The per-domain schemas and adapter implementations govern the exact accepted structures.

## Registration and replacement

Math and Template are registered unconditionally. Engine, Refrigeration, Robotics and Film are registered when their directories exist. The forge runtime is registered separately in `bootstrap.RUNTIMES`, so AOR sessions, which compose `DOMAINS`, never gain run authority. An unknown domain fails rather than falling back. The registry carries the capability class, extension class, source root, tool names, adapter identity and grant identity. Host construction accepts alternate roots; external JSON cannot select a root or add a domain.

Replacing a domain requires compatible descriptor, operations, inventory attachment, source pins, schemas and conformance evidence. Updating a source directory alone is insufficient. The research layer in `foundations/math/` is a separate consumer, not the Math stdio bridge root.

## Reasoning method source

`reasoning/poodo/` contains the upstream POODO 3.1 skill and supporting material, distinct from the executable `poodo_core/`. The scoped source pin records a partial mirror; the legacy README and license remain deferred. Retired software-engineering extensions and old guide paths are archived under `TODELETE/reasoning/poodo/`; current guides use upstream `docs/guides/` paths.

## External relationships

[Foundation Math](https://github.com/Akilleez-QA/foundation-math) is the named upstream for the byte-pinned historical distribution. Its current standalone extraction is narrower than this vendor tree; there is no demonstrated drop-in compatibility with upstream main.

[Foundation Engine](https://github.com/Akilleez-QA/foundation-engine) is partially vendored. `vendor/foundation-engine-v020/` holds only its Python bridge, the read-only tool schema and the upstream `SOURCE-MANIFEST.json`, pinned at upstream commit `70810ba455bdda1eadfdaab6bd44d43ae88f898c` in `contracts/SOURCE-PINS.json`. `adapters/engine_stdio.py` and `extensions/foundation_engine.py` expose two read-only validators, `validate_render_mask` and `validate_scene_output`. The engine's TypeScript runtime isn't included. The Math adapter still refuses a `foundation_engine` request (CS-REQ-015); Engine is its own domain.

[EndoForge](https://github.com/Akilleez-QA/endoforge) is vendored as a fixed slice in `vendor/endoforge/`; see [the source pin](../icd/icd-endoforge-pin.md).

## Failure containment and state ownership

The claim-gate CLI has no approved-atoms Registry provider in this checkout. Requests using `--atoms` fail closed through its structured error path (CS-REQ-016); the CLI does not import an external checkout or skip atom validation. The programmatic `gate` function still accepts an explicitly supplied registry with a `resolve` method.

Malformed or over-budget data is rejected or quarantined. A failed source check prevents acceptance; timeouts and interrupted exchanges preserve uncertainty rather than retrying automatically. Process execution bounds are admission controls for trusted local tools, not a hostile-code sandbox.

`build_core` prevents duplicate live bindings to a ledger object or canonical path in one process. Hosts must serialize core calls across threads and provide exclusive cross-process store ownership. `build_domain` uses a fresh in-memory ledger; AOR sessions can select witnessed storage through host configuration. Durability is therefore a composition property, not a universal guarantee.

## Assurance and review limits

Review import direction, grant checks, evidence interpretation and process cleanup when changing the boundary. The tests exercise bounded behavior and rejection cases; they do not establish general mathematical truth or suitability for physical control. No refrigeration control, safety or compliance determination is provided by the example domains.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

## Standalone CLI approval

The driver translates optional ask effects into restrictions on the fixed host
grant. Bootstrap supplies the ApprovalPort, named approver and clock to the core.
TerminalApprover prepares exact request-bound answers; PoodoCore validates and
consumes them before capability dispatch. Denial stops the run. Atomic exclusive
marker creation and directory fsync persist consumption across adapter instances;
records and the run ledger remain in memory. A new invocation creates new approval
IDs and requires a fresh answer. File answers are trusted host configuration.

## Refrigeration acceptance composition

The CLI accepts trusted launch options `--config` and `--approver=file:<approval-store>`. Bootstrap distinguishes SQLite stores by their file header, preserving JSON answer files and terminal/deny modes. It opens the existing SQLite approval store through ApprovalReader, fixes the approver identity to `owner-via-approver`, and marks the domain's grant operations as ask. Requests cannot select policy or mint approvals. The reader and Endoforge port close on exit. The acceptance harness records a synthetic host verdict with ApprovalWriter before launching a separate CLI process; Foundation execution and evidence persistence use production adapters.

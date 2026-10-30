# ADR 003: Fleet AORs as POODO authority, with Grok Bot as the HMI

Status: **Accepted in part, as built** (2026-10-25).
Supersedes the draft on PR #3; items marked "Not built" are still proposals and need their own ADR update before code lands.

## Context

Fleet AORs define ownership and effect limits. POODO authority is host supplied.
Requests, hooks and tool text cannot create or enlarge that authority (`contracts/INTERFACES.md`, "Core records").
Grok Bot owns `products/hmi/`: the sentinel checker, shields-up and kill switch, and phone control board (`AGENTS.md`, "Fleet ownership").
That ownership does not establish a working POODO driving adapter.
This record resolves security finding F10: main cites ADR 003, but its draft remained on held PR #3.

## Decision as built

### AOR registry and loader

`aors/README.md` identifies `aors/fleet.json` as host configuration for bot AORs and device ownership.
`adapters/aor_registry.py` defines immutable `Fleet`, `Bot`, `Device` and `Effects` records.
Loading the registry grants nothing; bootstrap derives authority from it.

- `EFFECTS` lists `read`, `write_slice`, `execute`, `config`, `send`, `payment`, `post`, `filing` and `delete`.
- Classes are `allow`, `ask` or `deny`. `_check_gated()` rejects `allow` for `send`, `payment`, `post`, `filing` and `delete`, including device guest effects.
- The configured approver is `owner-via-approver` (`aors/README.md`).
- `load_fleet()` uses a host-fixed path and rejects files larger than `MAX_BYTES` (1,048,576 bytes).
- `parse_fleet()` validates against `contracts/aor.schema.json` with `Draft202012Validator`. Validation fails closed.
  It rejects duplicate bot IDs/slugs and device hostnames, invalid reporting/route targets, unknown device owners, conflicting slice ownership and owned slices with denied write access.
  The root slice `/` means paths no other bot owns.
- `aors/README.md` names `tools/generate_aors.py` as the generator from `ops/agent-roles` and `AGENTS.md`. Review the generated diff; regeneration does not replay reviewed card fixes.
- Device rows live in `fleet.json`; there is no aors/devices/ (not included) directory.
  The README's guest rule gives a non-owner `read` plus asked effects only. Unassigned device owners remain `CHECK`.
  The loader validates device records and gated effects; loading alone is not guest-effect enforcement.

Built in: PR #10 (1c522ac), with PR #11 (a86681b) follow-up; files: `adapters/aor_registry.py`, `aors/README.md`.

### Ask and deny authority

`poodo_core/policy.py` supplies `AuthorityGrant`, not an ordered ruleset.

- `permits()` requires an explicit matching domain, capability, operation and goal ID. No matching grant means no authority.
- `denies()` matches domain, capability and denied operation, without goal scoping. A deny in any grant refuses at decide and execute.
- Ask in any grant for the capability makes approval mandatory; another allowing grant cannot bypass it (`contracts/INTERFACES.md`, "Ask and deny authority (ADR 003)").
- `AuthorityGrant.__post_init__()` requires immutable tuple scopes. Ask operations must be a subset of granted operations. Denied and granted operations must be disjoint within one grant.
  Grants require nonempty operations and goal IDs, and an integer `max_calls` from 1 through 64.
- **Correction to the draft:** "last matching rule wins; no match means ask" is NOT what was built. Explicit grants, deny precedence and approval requirements govern authority.
- The first denial per exact request is recorded; refusal records are bounded (`contracts/INTERFACES.md`).

Built in: PR #14 (ca8dd27), ADR plan PR 3; files: `poodo_core/policy.py`, `contracts/INTERFACES.md`, `contracts/SOURCE-PINS.json` (`poodo_core_adr_003`).

### Digest-bound single-use approvals

`poodo_core/policy.py` defines immutable `ApprovalRecord` fields:
`approval_id`, `decision_id`, `request_sha256`, `goal_id`, `goal_revision`, `approver`, `verdict`, `not_after`.
`ApprovalRecord.__post_init__()` validates identifiers, a 64-character lowercase hexadecimal digest, a positive integer revision, an `approved` or `declined` verdict, and a positive integer expiry.

`contracts/INTERFACES.md`, "Ask and deny authority (ADR 003)", specifies the execution gate:

- The host record must bind the exact decision, request digest, goal revision and configured approver.
- An approval must be unexpired by the host's integer clock. `ApprovalPort.consume()` must confirm durable single use.
- Missing approval raises `ApprovalPending`, recorded once. Nothing is dispatched or consumed.
- A bound decline is honoured even after expiry. It is recorded, consumes the decision and raises `ApprovalDeclined`. It never becomes tool output.
- Ledger capacity is reserved before spending an approval, so a capacity failure cannot burn an approval or lose a decline.
- Requests, hooks and tool text cannot create, select or alter approvals.

Built in: PR #14 (ca8dd27); files: `poodo_core/policy.py`, `contracts/INTERFACES.md`, `contracts/SOURCE-PINS.json` (`poodo_core_adr_003`).

### Durable approval store

`adapters/approval_store.py` separates host-only `ApprovalWriter.record()` from the core's `ApprovalReader` port (`lookup()` and `consume()` only).
The writer accepts only `ApprovalRecord` and records one final answer per decision, with unique approval and decision IDs. Rows are never deleted.
`ApprovalReader.consume()` uses one atomic SQLite update. Only an approved, unexpired, unconsumed record succeeds, once across processes and restarts.
The store uses a private SQLite database, documented as a mode-0600 file, and a host clock returning integer epoch seconds.
This separates code paths, not hostile processes sharing an OS user. Any process running as that user can write the database directly.
The store does not establish a working Friday approval channel.

Built in: PR #45 (eeb234c), carrying PR #21 to main; #21 itself merged only into a stack branch; file: `adapters/approval_store.py` (`ApprovalWriter`, `ApprovalReader`).

### Goal liveness

`contracts/INTERFACES.md`, "Goal liveness (PR 6)", defines host-supplied `record_liveness(LivenessRecord)`.
It binds the current goal revision, next-action owner, required `waiting_on` (`agent`, `approval` or `external`), reason and optional `review_by` deadline.
Changes append `liveness_set` with the prior record; repeating the same record appends nothing.
`liveness(goal_id)` reports no live path for missing or stale records, expired waits, or approval waits without a pending ask for that revision and the configured approver as owner.
`goals_without_live_path()` lists open goals lacking a live path and their reasons.
Liveness reports; it does not gate phases, close goals or grant authority.

Built in: PR #22 (9cb2855), labelled "PR 6" in `contracts/INTERFACES.md`; file: `contracts/INTERFACES.md` (liveness API contract).

### Budget hard stop

`poodo_core/policy.py` defines `CostBudget`, optional `AuthorityGrant.aor_id` and `BudgetPaused`.
`CostBudget` requires identifiers for AOR and unit, and an integer limit from 1 through `MAX_COST` (`10**15`).
`contracts/INTERFACES.md`, "Budget hard stop (PR 9)", specifies:

- Once any budget or grant AOR is configured, every grant must name a budgeted AOR and a host `CostPort` must exist, or startup fails.
- Unknown, invalid, unbounded or failing estimates refuse at decide and execute. An estimate exceeding the remaining limit also refuses. `budget_refused` records are bounded per exact request.
- Execute checks cost before spending approval and reserves ledger room for settlement and pause. The action holds the estimate as `cost_reserved`.
- After the outcome, `budget_settled` releases a hold for non-dispatch, charges the host's actual price, or retains the whole hold when actual cost is unknown.
- Committed spend reaching the limit pauses the AOR (`budget_paused`). New decisions and executions, including already-decided calls, refuse.
- Only host `lift_budget_pause(aor_id, new_limit)` with a limit above committed spend lifts it. Starting or revising goals does not.
- Requests, hooks and tool text cannot set prices, budgets or pauses. Cores without budgets retain their prior behaviour.

Built in: PR #28 (9d64611), labelled "PR 9" in `contracts/INTERFACES.md`; files: `poodo_core/policy.py`, `contracts/INTERFACES.md`.

## Not built

| Draft item | Status | Where it stands |
|---|---|---|
| Durable hash-chained ledger (item 4 / plan PR 4) | Not built; superseded | `contracts/DECISION-004-private-witnessed-ledger.md`, "Convergence with ADR 003 PR 4", requires `LedgerPort` to adopt the witnessed ledger directly, without a wrapper. PR #20 (ADR PR 4a) and PR #25 (WitnessedLedger, PR 4c) are held, not on main. ADR 004 says enforcement is off by default. |
| Friday approval channel | Not built | PR #47 is open. The durable approval store alone is not this channel. |
| MCP stdio adapter, one per AOR, with Tailscale identity (item 6 / plan PR 5) | Not built | No PR exists. `contracts/INTERFACES.md`, "MCP and formal verification", requires a stated tested protocol revision and actual client interoperability. |
| `products/hmi/` consumption (item 6 / plan PR 6) | Not built | No PR exists. Grok Bot owns this slice (`AGENTS.md`). This plan PR 6 is distinct from the liveness label "PR 6". |
| Kill switch as host authority (item 7) | Not built | No host-policy shields hook in `poodo_core` on main. HMI shields ownership in `AGENTS.md` does not supply that hook. |

## Open questions

- Who may approve an ask beyond the configured `owner-via-approver` delegation? Broader per-AOR delegation remains undecided.
- Has the owner completed the one-time review of generated effect classes? `aors/README.md` retains `CHECK` for open decisions and `APPROVED` with `approved_on` for later sign-off.

## Consequences

Host grants and exact approvals provide enforceable authority checks, not prompt-only permission (`poodo_core/policy.py`, `contracts/INTERFACES.md`).
Durable approval consumption survives restarts within the documented same-user trust boundary (`adapters/approval_store.py`).
Liveness exposes stalled goals; configured budgets stop spending. Neither establishes fleet-wide HMI or witnessed-ledger integration (`contracts/INTERFACES.md`, `contracts/DECISION-004-private-witnessed-ledger.md`).

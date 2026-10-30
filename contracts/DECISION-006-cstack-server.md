# ADR 006: The cstack server: one host process for the cockpit, built from T3 Code's server patterns

Status: **Proposed** (2026-10-27). Phase 1 (the read side) is in this PR; every later phase lands as its own PR of about
400 changed lines or fewer. Merging follows AGENTS.md rule 5.

## Context

the owner, 2026-10-27: "we dont actually want to run t3 we run cstack but there a lot of capability there we need,
harvest it"; "so we need our own server".

- T3 Code (pingdotgg/t3code, MIT) runs one server per machine. It owns an event log, command receipts and an effect
  outbox, and publishes one live state stream (a snapshot plus sequenced updates with a resume cursor) to web, desktop and
  phone clients. It authorises every call by scope, takes an MCP endpoint for agents, and links machines by pairing code.
  The parts wall holds 66 T3 parts (parts-wall/oss/t3code/CAPABILITIES.md (not included)), re-harvested at 1cf14a498f through the
  plant-connector lens.
- Cstack has the core (POODO, ADR 005) and per-bot MCP stdio hosts (ADR 003). It has read models over the ledger
  (`adapters/read_models.py`, items 8a and 8b), but no process that a cockpit, a phone or another box can connect to.
- ADR 005 already names the gaps this fills: ReadModelFace (item 8), the cockpit view (8c), IdentityPort (4), admission
  and resource leases (5), and the independent watchers (decision 6).

## Decision

1. **One cstack server per device** (tools/cstack_server.py (not included)), a driving-side host. It composes adapters the same way
   `tools/cstack_mcp.py` does and imports nothing into the core. It is not a second core: every write it ever carries goes
   through `PoodoCore`'s public API, and approvals never pass through it (ADR 005 decision 5).
2. **Patterns ported from T3 Code, never its runtime.** We do not run T3. Each phase names the parts-wall part it ports:

| Phase | What lands | Ported from (parts wall) | ADR 005 item |
|---|---|---|---|
| 1 (this PR) | Host read models plus a sequenced projection store: snapshot, resume after a sequence, fresh snapshot when too far behind; GET-only HTTP and SSE on loopback; the plant-room cockpit | `oss-t3code-shell-stream-live-state`, `oss-t3code-client-thread-state-model` | 8a, 8c |
| 2 | Durable intent: an event log with a global sequence, idempotent command receipts and an effect outbox with leases, under the ADR 004 witnessed ledger. Operator controls (capacity ramp, conductor pause) become commands decided by the core, then performed after commit | `oss-t3code-event-sourced-intent-then-effects` | 5, 8 |
| 3 | Scoped access: tokens bound to an identity from the IdentityPort (Tailscale WhoIs first), scopes per route, short-lived stream tickets; remote viewers only after this | `oss-t3code-scoped-pairing-auth`, `oss-t3code-remote-session-surface-scopes` | 4 |
| 4 | Mode ceiling: a grant, a delegated child or a linked box can only narrow its runtime mode | `oss-t3code-mode-ceiling-narrowing` | 3 |
| 5 | An MCP endpoint on the same server for agents and Grok Bot, beside the per-bot stdio hosts, with tool access classes | `oss-t3code-orchestrator-mcp-toolkit`, `oss-t3code-mcp-tool-access-classes` | 2d |
| 6 | Linked devices: the Grok box and other boxes dial out with a pairing code; linked work is fenced and labelled with its origin | `oss-t3code-peer-links-outbound-pairing` | 4, 6 |
| 7 | Resource meters per worker, usage windows per provider account, settlement on merge | `oss-t3code-resource-monitor-sidecar`, `oss-t3code-provider-usage-windows`, `oss-t3code-outcome-based-thread-settlement` | 5b |

3. **Read before write.** Phase 1 serves GET only. The first write path (phase 2) arrives with its receipts, its fakes
   and its replaceability tests, never before.
4. **The first write path: the cockpit relay** (the owner, 2026-10-27: "an orchestrator relay agent that can run messages from
   me to the teams working"). `POST /api/relay` appends the owner's message to an append-only outbox
   (`adapters/relay_outbox.py`); a relay agent session (`products/hmi/plant-room/RELAY.md`) claims it, delivers it to a team
   session and records receipts and replies, which come back as the `relay` projection. Guards: loopback peer, this
   server's Host, same-origin Origin and Sec-Fetch-Site, a per-run token only the page can read, 4000 characters, 30 a
   minute, idempotent on a client id. Messages are not approvals: the agent refuses one that grants an approval.
   Codex and Grok Bot are reached directly, not by fleet mail (the owner: "fleet mail doesnt work that great"): Codex by a
   read-only `codex exec` through codex-pool, Grok Bot by a mailbox the Grok box pulls through the forced-command
   snapshot gate it already uses (no new key or port on host-a; workshop/box/relay (not included)).

## Consequences

- The plant room, a phone board and Grok Bot can all read one stream, with each projection's source, freshness and
  confidence visible.
- The server is one more hard-wired ReadModelFace row in `contracts/ADAPTERS.json` until a ReadModelPort exists.
- Gaps the read side shows today: no POODO state root on host-a (`~/.local/state/cstack` is absent, so ledgers are
  in memory only); the HMI control board is not deployed; no conductor job is running.

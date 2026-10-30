# Plant connect: T3 Code re-harvested for the live control room (2026-10-27)

the owner asked to re-harvest T3 Code for what connects the playable plant ("cstack, operated like a plant") to real
work, then: "we dont actually want to run t3 we run cstack", "so we need our own server". So every section reads a
read model on the cstack server (`tools/cstack_server.py`, DECISION-006), and T3 Code is a source of patterns ported
into it, never a runtime. T3 Code was fast-forwarded b3d382e100 -> 1cf14a498f (443 commits, 25-27 Oct; MIT) and
re-harvested onto the parts wall (`parts-wall/oss/t3code/CAPABILITIES.md`, "Plant-connector re-harvest").

Read models (projection names in `adapters/host_read_models.py`): workers, gpu_queue, safety, capacity, throttle,
agent_sessions, codex_pool, conductor_jobs, merge_train, poodo_state, plus the ledger projections when a POODO export exists.

## The map: plant section -> live read -> command -> T3 piece

| Plant section | Live read (ours; now a server read model) | Command path (class) | T3 piece harvested |
|---|---|---|---|
| HMI gauges: workers | `workers list --json` (74 ms; live/, hosts/) | none (registry only reports) | shell stream status mapping (idle/working/waiting/failed) |
| HMI gauges: GPU | `system-safety-status` (36 ms), `~/.local/state/gpu-queue/*.ticket` | none safe (SIGTERM a ticket pid) | resource telemetry: no GPU in T3; ours is better |
| HMI gauges: queue | ticket dir: prio 0 short lane, else long lane; `history.jsonl` | none | - |
| HMI mode selector | conductor `state.json` phase/paused/stopped; T3 `runtimeMode` per thread | `endoforge job pause|resume` (operator), T3 `thread.runtime-mode.set` (operator) | runtime modes + mode ceiling (`T3-Mode-Limit`, `delegatedTaskModes` rank) |
| E-stop (Shields) | `<state-root>/SHIELDS_UP` presence; HMI board `/api/state/<machine>` (cloud) | touch/remove `SHIELDS_UP` (STOP, the owner only) | `thread.stop {stopDelegatedTasks}`, `orchestration.stopWorkflow` |
| POODO relays | POODO ledger events (precommit/denied/approved/budget_refused...) once a state root exists; `runtime_watch.py` | `friday_approvals.py answer <id> yes|no --sha256` (APPROVE, the owner only) | runtime requests: `pendingRuntimeRequest` + `runtime-request.respond` |
| Witnessed ledger | ADR 004 node log JSONL (`products/hmi/ledger`) when wired; today none | append only | event log + command receipts + outbox-with-leases pattern |
| Crew pods (bots) | `aors/fleet.json` (34 bots, effects allow/ask/deny), fleet mail via `gh` (slow) | `gh issue create` labels `fleet-mail`, `to:<slug>` (SEND) | thread shell rows as crew activity |
| Fleet mail tube | open fleet-mail issues per `to:<slug>` (gh, 1-5 min) | as above | `t3_thread_send` modes auto/queue/steer/restart |
| Intake window (Grok Bot) | T3 scheduled tasks + webhook deliveries (`/api/hooks/:hookId/:token`) | `scheduledTasks.runNow` (operator) | scheduled tasks + localhost webhook ingress |
| Endoforge atomize/lanes/recombine | conductor `state.json` atoms {status, lane{engine codex|claude, unit}}, `events.jsonl`; T3 shell rows (provider = lane) | `endoforge job go|lock|budget|stop` (operator, `--by --words`) | shell stream + `delegate_task` (isolation worktree, wait/async) |
| Conductor crane | conductor phase + escalations | `endoforge job patch` | orchestrator MCP toolkit (merged action tools) |
| Collect gate | conductor `gates/<atom>-i<iter>.gate.json` | none | changed-files fast gate (on the wall already) |
| Merge train + CoS gate | `journalctl --user -u cstack-merge-train*` JSON summaries; timers | `systemctl --user start cstack-merge-train[-lowrisk]` (MERGE, the owner only) | PR links + `changeRequestsCreatedBy` + outcome-based settlement |
| Shipping trucks | merged PRs per product path (merge-train summaries) | none | - |
| Capacity dial | `~/.local/state/fleet/CAPACITY`, `DRAIN`, `fleet-disconnect status --json` (moderate) | `fleet-disconnect ramp N | drain | resume` (operator) | provider usage windows (session/weekly %) |
| Throttle / governor | `heavy-run --limits` (static), `runs.log`, slot locks; memguard `actions.jsonl` | none | - |
| Worker registry board | `workers list --json` + Claude sessions (whitelisted fields of `claude-code-sessions/*/local_*.json`) + `~/.codex-pool/cooldown/*` | none | usage-limit failover (Waiting, not Failed) |
| Grok box (SSH outbound only) | `~/.local/state/workers/hosts/<host>.json` pushed snapshots (`workers push --ssh`) | none from here | peer links: the box dials out (MCP OAuth + pairing code), never inbound |
| Hermes (standby) | none yet (studying) | none | usage-limit provider failover |
| Measured effect -> learning | conductor ratchet + SCORED events, merge-train merged counts, gpu/heavy history | none | - |

Command classes: (operator) safe local controls the operator page may offer; (STOP/APPROVE/MERGE/SEND) gated, armed only
by the owner in the page and logged; v1 of the bridge is read-only and lists every command it would offer.

## T3 Code: ported, not run
The T3 column names the pattern each section's server phase ports (DECISION-006 table). The shell stream's protocol was
proven against an isolated `t3 serve` on 2026-10-27 (snapshot, then a live update moving the cursor 2 -> 3), which is
why phase 1 copies its cursor semantics; the plant does not connect to T3.

## Gaps found (worth their own fixes)
1. POODO keeps only in-memory ledgers on this machine: `~/.local/state/cstack/` does not exist, so the witnessed
   ledger and approvals have nothing durable to show. The plant shows the POODO cabinet as "no ledger wired".
2. The HMI control board is not deployed and no shields engine is installed (`/var/lib/shields` empty).
3. No conductor job is running and the worker registry is empty: the live plant will mostly show idle lanes until work
   runs, which is correct.
4. `gpu-queue.py --stats` deletes stale tickets: never poll it; list the ticket dir.
5. `codex-pool status` would spend quota: read `~/.codex-pool` files instead (both accounts cooling until 2 Nov).

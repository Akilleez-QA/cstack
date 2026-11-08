# The server, the driver and the adapters

Cstack is built hexagonally. The POODO core in `poodo_core/` sits in the middle and imports no concrete adapter, subprocess, transport or provider. Everything that touches the outside world is an adapter in `adapters/`, chosen and wired by the host in `bootstrap.py`. This page explains the two ways in (the CLI driver and the MCP server), the ways out (capability adapters), and what the host keeps for itself.

## Two ways in

Cstack has two driving adapters. Both build cores through `bootstrap.py`, and neither lets request data choose a domain root, a grant, a path or an approval.

### The CLI driver: `cli.py`

`cli.py` runs one structured document (`cstack.run/0.1`) to completion and prints one result. It is for scripted runs, examples, acceptance tests and forge goals. It is local and single-run: not MCP, not a network server. Each invocation builds a fresh core with an in-memory core ledger (a durable one under `<workcell.ledger>.core/` for forge goals), binds the witnessed ledger if `cstack.config.json` configures one, and closes it at exit. The [tutorial](../tutorials/first-run.md) walks through it, and [the command reference](../reference/commands.md#clipy-the-local-run-driver) lists its options.

### The MCP server: `tools/cstack_mcp.py`

`tools/cstack_mcp.py` is the long-running way in. A host starts one per bot, from its own MCP client configuration:

```text
python -B tools/cstack_mcp.py --aor example --device example-host --state-root /tmp/cstack-state
```

It speaks newline-delimited JSON-RPC 2.0 on stdin and stdout (`adapters/mcp_stdio_server.py`), offering MCP revisions 2025-11-25, 2025-06-18 and 2024-11-05. It has no network listener.

What makes it safe to hand to a bot:

- **The bot is fixed at launch.** `--aor` names one entry in `aors/fleet.json`; the device comes from `--device` or the machine's tailnet name. No tool argument can name a bot, device, path, grant or approval.
- **The tool table is closed.** `aor`, `start_goal`, `advance`, `decide`, `execute` and `ledger` map one-to-one to core operations. `--fleet-mail` adds `mail_send`, `mail_inbox`, `mail_reply` and `mail_close`. The host assigns every goal, request and decision id.
- **Effects resolve strictest first.** Each effect class (`read`, `execute`, `send` and the rest) is `allow`, `ask` or `deny`, taken from the bot's registry entry, then the device's guest rules when the bot doesn't own the device, then shields-up. An `ask` waits for the owner through the scheduled approval channel (`tools/scheduled_approvals.py`), which refuses to run inside an MCP server.
- **State is the host's.** Ledgers and approvals live under `--state-root` (default `~/.local/state/cstack`). With a `ledger.json` there, the session writes through the witnessed ledger of DECISION-004; without one, it says its ledger is memory only.

An AOR session composes Foundations (`bootstrap.DOMAINS`) only. The forge runtime is in `bootstrap.RUNTIMES`, so being on the registry gives a bot no run authority.

### The cockpit

DECISION-006 and the docstrings of `adapters/host_read_models.py` and `adapters/relay_outbox.py` refer to a "cstack server" cockpit. That server isn't in this repository. What is here are its read-only projections (`adapters/read_models.py`, `adapters/host_read_models.py`, printed by `tools/read_models.py`) and the relay's append-only outbox (`adapters/relay_outbox.py`). An outbox message is an intent, not authority, and approvals never pass through it.

## Ways out: capability adapters

The core reaches a domain only through a `CapabilityPort`, under a host grant, after its phase, revision, authority, lane, capacity, budget and approval checks. Each registered domain has one adapter:

| Domain | Adapter | Protocol and root |
|---|---|---|
| `foundation_math` | `adapters/math_stdio.py` | `foundation-math-jsonrpc/1` to the bridge in `vendor/foundation-math-v014` |
| `foundation_template`, `foundation_refrigeration`, `foundation_robotics`, `foundation_film` | `adapters/foundation_stdio.py` with one profile each (`template_stdio.py`, `refrigeration_stdio.py`, `robotics_stdio.py`, `film_stdio.py`) | Each Foundation's own JSON-RPC bridge under `foundations/` |
| `foundation_engine` | `adapters/engine_stdio.py` | `foundation-engine-jsonrpc/1` to the bridge in `vendor/foundation-engine-v020`, a partial copy: the bridge, its schema and the upstream manifest |
| `cstack_forge` (runtime) | `adapters/endoforge_workcell.py` | JSON lines to a Node supervisor running `IsolatePool`. See [how Cstack runs EndoForge](endoforge-vendoring.md) |

None of the Foundation bridges is MCP. Each adapter:

1. checks the Foundation's source manifest against `contracts/SOURCE-PINS.json` before dispatch, and again after a completed exchange;
2. starts a fixed module from the fixed root through `adapters/execution.py`, with no shell and no request-controlled argument or environment, under a deadline and output caps;
3. checks the live tool catalog against its pinned copy;
4. validates the reply's schema, tool identity, receipt and evidence flags, and keeps the original receipt.

A tool result is a bounded observation. `formal_proof` and `runtime_goal_acceptance` are always false, and no result closes a goal. A subprocess is an admission control for trusted local tools, not a sandbox for hostile code.

`adapters/mcp_stdio_client.py` is the other direction: a `CapabilityPort` that calls an external MCP tool server, with the server, its tools and their pinned schemas fixed by the host. It is tested against MCP revision 2025-11-25 only. See [the interfaces](../../../contracts/INTERFACES.md#mcp-and-formal-verification).

`contracts/ADAPTERS.json` lists every adapter attachment with its lane and status. `bootstrap.check_grants` refuses to build a core whose grant doesn't match it.

## What the host keeps

These adapters serve the host, not a domain:

| Concern | Adapters |
|---|---|
| Core ledgers | `memory_ledger.py` (bounded, in process), `durable_ledger.py` (appends and syncs each event so a later core can replay it), `witnessed_ledger.py` and `ledger.py` (the DECISION-004 signed, witnessed log) |
| The witness for evidence | `endoforge_ledger.py`: the `EndoforgePort` file adapter behind `endoforge.path` |
| Approvals | `terminal_approver.py` (CLI terminal and JSON-file answers), `approval_store.py` (the durable owner's yes or no), `private_sqlite.py` (safe private database files) |
| Fleet | `aor_registry.py`, `aor_session.py`, `fleet_mail.py` |
| Read models and relay | `read_models.py`, `host_read_models.py`, `relay_outbox.py` |
| Wire formats | `wire.py`: exact JSON profiles with bounded depth, size and numbers |
| Other | `adapter_inventory.py`, `provider_policy.py`, `workspace_snapshots.py`, `memory/` |

## Replacing an adapter

An adapter is replaceable when its replacement implements the same port, describes the same capability and lane, passes the same conformance tests and carries its own pins. Changing a source directory alone doesn't qualify. Start from the [architecture](../../architecture/architecture.md), the [Foundation interfaces](../../icd/icd-foundations.md) and [the change procedure](../../configuration/configuration-management.md#change-procedure).

Return to the [explanation index](README.md).

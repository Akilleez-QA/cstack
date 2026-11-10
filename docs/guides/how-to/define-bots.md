# How to define your bots

Each bot in Cstack has an area of responsibility (AOR): what it owns, what it doesn't, which parts of the repository it may write, and which effects need your approval. The registry is one host-owned file, `aors/fleet.json`. This guide changes it and starts one bot's session.

## 1. Edit the registry

Copy the example entry in `aors/fleet.json` and set, for each bot:

| Field | Meaning |
|---|---|
| `slug` | Short name, used on the command line |
| `owns`, `not` | What the bot is and isn't responsible for, in words |
| `slices` | The repository paths it may write |
| `effects` | One of `allow`, `ask` or `deny` for each effect class: `read`, `write_slice`, `execute`, `config`, `send`, `payment`, `post`, `filing`, `delete` |
| `reports_to` | The bot it reports to, or `null` |

Keep every external effect (`send`, `payment`, `post`, `filing`, `delete`) at `ask`, so it routes to the one human approver. The example bot does:

```json
"effects": { "read": "allow", "write_slice": "deny", "execute": "allow", "config": "allow",
             "send": "ask", "payment": "ask", "post": "ask", "filing": "ask", "delete": "ask" }
```

Choose branch lanes that fit your own workflow; the registry doesn't fix them.

## 2. Validate it

```sh
python -B -c "from adapters.aor_registry import load_fleet; print(load_fleet('aors/fleet.json').approver)"
```

```text
owner-via-approver
```

This checks the file against `contracts/aor.schema.json`. Loading the registry grants nothing by itself; `bootstrap.py` derives each session's authority from it.

## 3. Start a bot's session

```sh
python -B tools/cstack_mcp.py --aor example --device example-host --state-root /tmp/cstack-state
```

This starts an MCP server on stdin and stdout for one bot. Point your agent's MCP client configuration at this command. The host picks the bot (`--aor`) and the device; nothing the bot sends can change them. Asked who it is (the `aor` tool), the session answers with the registry entry (trimmed):

```text
{"approver": "owner-via-approver", "bot": {"id": "00000001", "name": "Example", "slug": "example"}, "device": "example-host", ..., "ledger": "memory (not durable: no ADR 004 roster configured)", ...}
```

The ledger is memory only until you configure a witnessed ledger under `--state-root`. [The server, the driver and the adapters](../explanation/server-and-adapters.md) explains the tool table, how effects resolve and where state lives. `tools/agent_profiles.py` generates MCP wiring and one agent profile per bot; see the [command reference](../reference/commands.md).

Return to the [how-to guides](README.md).

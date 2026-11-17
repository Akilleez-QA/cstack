# Areas of responsibility

`fleet.json` is the host-owned bot registry. Copy the example entry and choose, for each bot, a `slug`, what it `owns` and does `not` own, the repository `slices` it may write, its `effects` per effect class (`read`, `write_slice`, `execute`, `config`, `send`, `payment`, `post`, `filing`, `delete`, each `allow`, `ask` or `deny`) and `reports_to`. Keep every external effect (`send`, `payment`, `post`, `filing`, `delete`) at `ask`, so it routes to the one human approver.

Validate the registry against `contracts/aor.schema.json` before use:

```sh
python -B -c "from adapters.aor_registry import load_fleet; print(load_fleet('aors/fleet.json').approver)"
```

Loading the registry grants nothing; `bootstrap.py` derives each session's authority from it. The nine starter agents (chief, scribe, oracle, sage, smith, warden, lab, keeper, archivist) each have an entry here with full access to read, write their own slices, execute and configure, and every external effect at `ask`; their definitions live in `agents/` (see [the starter agents](../docs/guides/explanation/starter-agents.md)). A bot reaches its AOR through `tools/cstack_mcp.py --aor SLUG`; see [the server, the driver and the adapters](../docs/guides/explanation/server-and-adapters.md) and [ADR 003](../contracts/DECISION-003-agent-aors-and-hmi.md).

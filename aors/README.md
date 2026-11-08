# Areas of responsibility

`fleet.json` is the host-owned bot registry. Copy the example entry and choose, for each bot, a `slug`, what it `owns` and does `not` own, the repository `slices` it may write, its `effects` per effect class (`read`, `write_slice`, `execute`, `config`, `send`, `payment`, `post`, `filing`, `delete`, each `allow`, `ask` or `deny`) and `reports_to`. Keep every external effect (`send`, `payment`, `post`, `filing`, `delete`) at `ask`, so it routes to the one human approver.

Validate the registry against `contracts/aor.schema.json` before use:

```sh
python -B -c "from adapters.aor_registry import load_fleet; print(load_fleet('aors/fleet.json').approver)"
```

Loading the registry grants nothing; `bootstrap.py` derives each session's authority from it. A bot reaches its AOR through `tools/cstack_mcp.py --aor SLUG`; see [the server, the driver and the adapters](../docs/guides/explanation/server-and-adapters.md) and [ADR 003](../contracts/DECISION-003-agent-aors-and-hmi.md).

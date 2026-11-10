# How to use a real model for forge goals

A forge goal asks a model transport for source code, compiles it in an EndoForge workcell and checks it. The examples use the stub transport, which replays a recorded answer. This guide switches to a real model.

## What you need

- A working clone with `cstack.config.json` (see the [tutorial](../tutorials/first-run.md)).
- Claude Code installed, with a subscription login: `claude auth status` reports `"loggedIn": true`. No API key is used.

## 1. Point the host configuration at the Claude transport

In `cstack.config.json`, set:

```json
"transport": "adapters/workcell/claude-transport.mjs"
```

The transport is chosen only by `workcell.transport` in host configuration. Request data can't choose it.

## 2. Run the goal without the stub

```sh
python -B cli.py < examples/forge/saturation-goal.json
```

The transport runs `claude -p` with no tools, no MCP servers, no settings, no session persistence and an environment that carries no API key variables. It refuses a session that reports any of them. The model gets its full instructions in `prompt.text`. The ledger records the proposer as `claude-code:<model>`.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `CSTACK_CLAUDE_MODEL` | `opus` | The model |
| `CSTACK_CLAUDE_COMMAND` | `claude` | The executable |
| `CSTACK_CLAUDE_CONFIG_DIR` | none | An existing Claude config directory |
| `CSTACK_CLAUDE_TIMEOUT_MS` | `300000` | The per-call limit |

The [environment reference](../reference/environment.md) lists every variable.

## What happens on failure

- Each run gets its own task and candidate, so you can run the same goal again.
- A goal's decision binds one request. A different request under the same decision is refused.
- A lost workcell or supervisor is recorded as `outcome_unknown`, never as a pass, and isn't retried. Rerun it with `python -B cli.py --resume DECISION_ID`.
- A lost controller is reconciled against the run ledger by the next run, which lists anything unresolved.
- A kernel can propose a decision only as data, through its host; the core accepts or refuses it. A run with a refusal records no pass.

Workcells aren't an OS sandbox. Cgroup limits apply only where the host delegates them; the receipt says `cgroup: unavailable` where it doesn't.

`tools/check_readme.py` runs this goal only where `claude auth status` reports a login, and reports it as skipped elsewhere. See [how Cstack vendors and runs EndoForge](../explanation/endoforge-vendoring.md) and [the EndoForge interface](../../icd/icd-endoforge.md).

Return to the [how-to guides](README.md).

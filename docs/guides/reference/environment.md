# Environment variable reference

Every environment variable the Cstack code reads, outside the vendored Foundations, with its default. Request data never sets any of these.

## Model transports

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `CSTACK_STUB_TRANSPORT_SCRIPT` | `adapters/workcell/stub-transport.mjs` | none; the stub fails without it | A JSON file `{"responses": [...]}` naming source files, relative to the script, returned in order |
| `CSTACK_CLAUDE_MODEL` | `adapters/workcell/claude-transport.mjs` | `opus` | The model passed to `claude -p --model` |
| `CSTACK_CLAUDE_COMMAND` | same | `claude` | The Claude Code executable |
| `CSTACK_CLAUDE_TIMEOUT_MS` | same | `300000` | Per-call limit in milliseconds |
| `CSTACK_CLAUDE_CONFIG_DIR` | same | none | An existing Claude config directory, passed on as `CLAUDE_CONFIG_DIR` |

The Claude transport passes on only `PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`, `USER` and the `XDG_RUNTIME_DIR`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` and `XDG_DATA_HOME` directories, plus `CLAUDE_CONFIG_DIR` when set. It sets `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. It refuses a session that reports an API key source, any tool or any MCP server.

## Workcell runtime

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `ENDOFORGE_LEDGER_JOURNAL` | `vendor/endoforge/tools/ledger_writer.py` | `$XDG_STATE_HOME/endoforge/ledger-journal`, with `XDG_STATE_HOME` defaulting to `~/.local/state` | The ledger writer's journal directory. The workcell adapter always sets it to `<workcell.ledger>.journal`, overriding any inherited value, so a forge run writes nothing under `~/.local/state/endoforge` |
| `ENDOFORGE_DUMP_LIST` | `vendor/endoforge/core/runtime/dump-list.mjs`, `vendor/endoforge/tools/dump_list.py` | auto: on only if `<state>/memguard/dump-list.d` exists, `<state>` being `XDG_STATE_HOME` when absolute, else `~/.local/state` | `1` forces memguard dump-list registration on for the workcell pool and the ledger writer, `0` turns it off. When on, each writes `<pid>-<name>.json` in that directory and sheds spare memory on `SIGUSR2`. The workcell adapter passes it through from the host environment |
| `ENDOFORGE_LEDGER_STATS` | `vendor/endoforge/tools/ledger_writer.py` | none | A file the writer's standalone loop writes its statistics to, as JSON, when it closes |

## State directories

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `XDG_STATE_HOME` | `adapters/terminal_approver.py` | `~/.local/state` | Consumed CLI approval markers go in `$XDG_STATE_HOME/cstack/cli-approvals` |

`tools/cstack_mcp.py` keeps AOR state in `~/.local/state/cstack` unless `--state-root` is given; it doesn't read `XDG_STATE_HOME`.

## AOR sessions and the MCP server

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `LEDGER_ENFORCE` | `bootstrap.build_aor_session` | off | `1` turns on enforcement for the witnessed ledger in AOR sessions |
| `CSTACK_MCP_SERVER` | `tools/scheduled_approvals.py` | unset | `tools/cstack_mcp.py` sets it to `1` for itself and its children. Host-only tools refuse to run when it is set |

## Memory store

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `CSTACK_MEMORY_DB` | `adapters/memory/store.py` | none; `--db` or this is required | A private path outside the repository, by convention ending in `.memory.db`. The file is created mode 0600, must be a regular file you own, and is never opened through a symlink |
| `CSTACK_MEMORY_DENYLIST` | `adapters/memory/confidentiality_wall.py` | unset: no terms blocked | A file of terms the confidentiality wall blocks, one per line; `#` starts a comment. Set but empty is an error |

## CI and tests

| Variable | Read by | Default | Meaning |
|---|---|---|---|
| `PYTHON` | `ci/run-local.sh`, `tools/e2e_refrigeration.sh` | `python3` | The interpreter the suites use |
| `CSTACK_ENDOFORGE_CLONE` | `tests/test_endoforge_pin.py` | unset; the test skips | A fetched EndoForge clone, to check the pin is on its `origin/main` |
| `CSTACK_MCP_SDK_ESM` | `tests/test_mcp_stdio_client.py` | unset; the test skips | An installed `@modelcontextprotocol/sdk` `dist/esm` directory |

Return to the [reference index](README.md).

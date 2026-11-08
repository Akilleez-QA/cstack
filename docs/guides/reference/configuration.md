# Configuration reference

Cstack's host configuration is one JSON file, `cstack.config.json`, at the checkout root unless `cli.py --config` names another. Copy it from `cstack.config.example.json`. It is trusted host input: request data never selects a path, a transport or a grant.

`bootstrap.endoforge_session` reads two sections, `endoforge` and `workcell`. Nothing in this repository reads the other keys in the example; they are placeholders for your own host tooling.

## Read by the code

### `endoforge`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `endoforge.path` | string | none; the section is optional | The witnessed ledger file, relative to the config file's directory unless absolute. Its parent directory must exist. The example uses `endoforge.jsonl` |

Without an `endoforge` section the run is unconfigured: no witnessed ledger, `endoforge_implemented: false`, and the `workcell` section is ignored. A config file that exists but isn't a JSON object, or a section with an empty or non-string path, fails the run rather than falling back. The ledger holds an exclusive lock for the run and is closed at exit.

### `workcell`

Used only by `cstack_forge` goals, and only when `endoforge` is configured. Unknown keys are refused.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `ledger` | string, required | none | The EndoForge run ledger (SQLite), relative to the config file. `<ledger>.core/` and `<ledger>.journal/` are created beside it |
| `transport` | string | none | A JavaScript module exporting `generate(prompt)`, relative to the config file. `adapters/workcell/stub-transport.mjs` replays recorded answers; `adapters/workcell/claude-transport.mjs` runs Claude Code. Without one, a run fails with `no model transport is configured` |
| `foundation_imports` | list of strings, required | none | Foundations a kernel may import, by domain id. A request may declare a subset; it can't add one |
| `decision_operations` | object | `{}` | Per Foundation, the operations a kernel may propose as decisions. A Foundation with none refuses proposals (`no_decision_grant`) |
| `decision_ask_operations` | object | `{}` | Per Foundation, operations that need approval. Coder proposals for them are refused (`approval_not_routed_to_coders`), because approvals don't reach coder cores |
| `isolation` | `process` or `thread` | `process` | How `IsolatePool` hosts each cell. Cgroup limits apply only to `process` cells, and only where the host delegates cgroups |
| `size` | positive integer | `1` | Number of workcells in the pool |
| `jobTimeoutMs` | positive integer | `120000` | Wall-clock limit for one job. V8 has no instruction fuel, so this is what stops a hung kernel |
| `cgroupRoot` | string | none | A delegated cgroup directory for `process` cells |

Fixed by the code, not configurable: one Node supervisor per run, at most 8 candidates (`max_candidates`) and 64 cases per run, at most 16 decision proposals per run, and result limits of 30 s wall time, 16 MiB memory and 4096 Foundation calls (`fuel`) per round.

The example:

```json
"workcell": {
 "ledger": "forge.sqlite",
 "transport": "adapters/workcell/stub-transport.mjs",
 "foundation_imports": ["foundation_refrigeration", "foundation_template"],
 "decision_operations": {"foundation_template": ["echo_observation"]},
 "isolation": "process"
}
```

## Not read by the code

| Key | Example value | Note |
|---|---|---|
| `owner`, `contact_email`, `github_org` | placeholders | For your own records |
| `approver` | `owner-via-approver` | The approver identity is fixed in code: `owner-via-approver` for AOR sessions and SQLite approval stores, `cli-owner` for the CLI's terminal and JSON-file approvals |
| `hosts`, `tailnet_cidr`, `scratch_dir` | placeholders | For your own host tooling |
| `fleet_file` | `aors/fleet.json` | A test checks that it names an existing file. `tools/cstack_mcp.py` takes `--fleet` instead |
| `merge_train` | `{"wip_limit_per_lane": 10, "policy": "low-risk"}` | `tools/merge_train.py` takes `--policy` on its command line, default `all` |

## Other host files

| File | Read by | Meaning |
|---|---|---|
| `aors/fleet.json` | `adapters.aor_registry.load_fleet`, `tools/cstack_mcp.py` | The bot registry, validated against `contracts/aor.schema.json` |
| `contracts/SOURCE-PINS.json` | Adapters, the workcell runtime, pin tests | Expected hashes of every vendored source. Changed only by a reviewed pin change |
| `contracts/ADAPTERS.json` | `bootstrap.check_grants` | Which adapter provides each capability, and on which lane |
| `<state-root>/ledger.json` | `bootstrap.build_aor_session` | Optional witnessed-ledger setup for AOR sessions (writers, log, roster) |

Return to the [reference index](README.md).

# Command reference

Every entry point in this repository, with its options and defaults as the code defines them at `e02a0c4`. Run any Python tool with `--help` for the same list.

## `cli.py`: the local run driver

```text
python -B cli.py [--approver[=deny|file:PATH]] [--config PATH] [--resume DECISION_ID] < run.json
```

`python -B .` from the checkout root runs the same driver through `__main__.py`. It is a single-run local driver, not MCP and not a network server.

| Option | Default | Meaning |
|---|---|---|
| `--approver` | `deny` | How an `ask` call is approved. Bare `--approver` prompts on `/dev/tty`, and only the exact answer `approve` approves. `deny` declines every ask. `file:PATH` reads a JSON object that maps request SHA-256 digests to `"approve"` or `"deny"`; a missing digest denies. A file that starts with the SQLite header is read as an ApprovalWriter store instead, and then every operation of the goal's domain asks, with approver `owner-via-approver` |
| `--config` | `cstack.config.json` next to `cli.py` | Host configuration. A missing default file means no witnessed ledger and no workcell |
| `--resume` | none | Run again a decision whose earlier outcome is unknown. A host choice; request data can't ask for it |

Input, on stdin, at most 65,536 bytes:

| Field | Rule |
|---|---|
| `schema` | `cstack.run/0.1` |
| `goal` | A `GoalContract`: `goal_id`, `revision`, `domain_id`, `objective`, `assumptions`, `exclusions`, `acceptance_version`, `acceptance_criteria` |
| `checkpoints` | Exactly four: observe, orient, decide, orchestrate. Each has exactly `checkpoint_id`, `rationale`, `research_references`, `option_ids`. Decide needs 20 distinct option ids |
| `calls` | 1 to 64. Each has exactly `request` (a `poodo.capability-request/0.1`), `precommitment` (`expected_observation`, `success_boundary`, `failure_meaning`, `oracle_id`, `oracle_version`) and optionally `effect`: `allow` (default) or `ask` |

Numbers follow the goal domain's driver profile. Refrigeration and forge documents may use finite decimal literals. Every other domain uses the integer-only decode in `adapters/wire.py`. No profile takes exponents, `NaN` or `Infinity`, and duplicate keys are refused.

Output, on stdout, exit 0: one `cstack.run-result/0.1` document.

| Field | Meaning |
|---|---|
| `run_status` | `completed`, or `stopped` when a call was refused or storage failed |
| `stopped` | `null`, or the decision, its `execution_certainty` (`not_dispatched` or `unknown`), the reason and the decisions not dispatched after it |
| `goal` | The goal snapshot. `closed` is always `false`; a run never closes a goal |
| `events` | The core ledger for this run |
| `outcome_unknown` | Outcomes whose execution certainty is `unknown` |
| `endoforge_implemented` | `true` when host configuration bound the witnessed ledger |
| `mcp_compatible` | Always `false` |
| `reconciled`, `unresolved_attempts`, `witness_quarantined`, `reconciled_outcome_unknown` | Present only when non-empty: what this session found and reconciled from earlier sessions |

Errors, on stdout, exit 2: one `cstack.driver-error/0.1` document with an `error` code:

| Code | When |
|---|---|
| `workcell_not_configured` | A `cstack_forge` goal on a host with no `workcell` section |
| `invalid_forge_request` | A forge call's arguments don't have the closed shape; `detail` says what is wrong |
| `decision_reuse_refused` | A different request under a goal and decision that already bound one |
| `witness_chain_broken` | A complete record in the witnessed ledger fails its chain; nothing runs |
| `invalid_or_unsupported_request` | Anything else: bad JSON, wrong schema, oversized input, bad approver mode, unreadable config |

## Python tools

All run from the checkout root as `python -B tools/<name>.py`. None reads request data as configuration.

| Tool | What it does | Options and defaults |
|---|---|---|
| `check_readme.py` | Clones the repository and runs every README command; fails if a README command has no check | `--source` (this checkout), `--branch`, `--github-remote` (`https://github.com/Akilleez-QA/cstack`) |
| `check_links.py` | Checks links and backticked repository paths in `AGENTS.md`, `contracts/*.md` and the other scanned maps. Exit 1 lists each broken reference | `--json`. Deliberate exceptions go in `ci/link-allowlist.txt` with a reason |
| `pin_endoforge.py` | Rebuilds `vendor/endoforge/` from one EndoForge commit on `origin/main` and records the pin | `--source` (required), `--commit` (required), `--allow-unmerged`. See [repin EndoForge](../how-to/repin-endoforge.md) |
| `pin_workcell.py` | Records the hash of every file in `adapters/workcell/` as `workcell_runtime` in `contracts/SOURCE-PINS.json` | None |
| `build_export_manifest.py` | Rewrites `EXPORT-MANIFEST.json`: every tracked file with its SHA-256 and size | None |
| `cstack_mcp.py` | Starts the MCP stdio server for one bot's AOR. See [the server](../explanation/server-and-adapters.md) | `--aor` (required), `--state-root` (`~/.local/state/cstack`), `--device` (the tailnet name from `tailscale status`), `--fleet` (`aors/fleet.json`), `--fleet-mail`, `--fleet-mail-repo` (`your-org/cstack`), `--fleet-mail-extra` (repeatable, default `worker`), `--fleet-mail-budget` (20 per hour) |
| `merge_train.py` | Merges open PRs in dependency order. Needs `gh` signed in; exits 2 without it | `--dry-run`, `--policy` (`all` or `low-risk`, default `all`), `--wip`, `--max-passes` (12) |
| `claim_gate.py` | Checks a bot's report claims against its POODO ledger | `--report` and `--ledger` (required). `--atoms`, `--atom-refs` and `--consumer` exit 2: no approved-atoms Registry is included |
| `scheduled_approvals.py` | Lists asks waiting on the owner and records an answer. Refuses to run inside an MCP server | `--state-root` (required), `--approvals`, `--json`, `--full`; to answer: `DECISION_ID yes\|no --sha256 DIGEST [--ttl 3600] [--bot SLUG]` |
| `read_models.py` | Prints the read-model projections for one exported ledger | `--state-root` (required), `--format` (`json` or `brief`, default `json`), `--approver` (`owner-via-approver`), `--max-age-hours` (24) |
| `runtime_watch.py` | Read-only watcher: last event, unsettled attempts, unknown outcomes, refusals, goals without a live path | `--stale-after`, `--config`, `--state-root`, `--export`, `--sqlite`, `--require` (all repeatable where it makes sense), `--now`, `--brief` |
| `witness_watch.py` | Read-only watcher for witness staleness | `--stale-after` (required), `--origin`, `--roster`, `--replicas`, `--checkpoints`, `--deadman-*`, `--config`, `--now`, `--brief` |
| `agent_profiles.py` | Generates MCP wiring and one agent profile per bot from `aors/fleet.json` | `--fleet`, `--out`, `--uv`, `--state-root`, `--check` |
| `generate_aors.py` | Generates `aors/fleet.json` from a fleet's own records; every entry starts as CHECK | `--roles`, `--agents`, `--devices`, `--output` (all required) |
| `e2e_agent.py` | End-to-end proof: a real agent CLI drives one AOR through the MCP server, in a temporary directory | `--slug` (`example`), `--agent`, `--uv`, `--approve` (`rules`), `--enable-in-config`, `--model`, `--max-turns` (40), `--timeout` (900), `--skip-goal`, `--keep` |
| `snapshot_step.py` | Wraps one command in workspace snapshots and prints a JSON receipt | `REPO -- COMMAND...`, `--timeout` (3600), `--label` |
| `fuzz_ports.py` | Fuzzes the Film and Robotics JS ports against the pinned Python | `--count` (20000), `--seed` (1), `--scan`, `--cap` (400), `--keep` (60), `--libm` (100000), `--boundaries` |
| `measure_foundation_routes.py` | Measures each Foundation route with the spawn counter | `--calls` (20), `--pyodide`, `--stdio-child` |
| `spawncount.py` | Counts real process creation under a command, by ptrace. Linux only | `--out` (required), `COMMAND...` |
| `tty_approve.py` | Runs a bare `--approver` command on a pseudo-terminal and types `approve` | `COMMAND` |

`tools/e2e_refrigeration.sh` runs the refrigeration CLI acceptance with a disposable config, approval store and ledger, and prints `endoforge_implemented`, `approval_id`, `ledger_events` and `verify_chain`. `PYTHON` selects the interpreter.

`tools/measure_routes_pyodide.mjs` is the Pyodide half of the route measurement; `measure_foundation_routes.py --pyodide` calls it.

## Memory store

```text
python -B -m adapters.memory [--db PATH] COMMAND
```

Commands: `ingest ROOT [--label L]`, `search QUERY [--status S] [--limit N]`, `list [--status S] [--limit N]`, `show FACT_ID`, `stats`, `confirm FACT_ID --by NAME [--note T] [--ledger-ref HEX]`, `reject FACT_ID --by NAME --note T [--ledger-ref HEX]`. Output is JSON; errors go to stderr with exit 2. Details in [the memory adapter](../../../adapters/memory/README.md).

## CI scripts

| Script | What it does |
|---|---|
| `bash ci/run-local.sh [SUITE...]` | Runs the named suites, default `python links refrigeration gitleaks trufflehog`. See [run CI checks locally](../how-to/run-ci-locally.md) |
| `bash ci/run-local.sh --setup` | Installs `ci/requirements.txt` into `$PYTHON` |
| `bash ci/scan-secrets.sh` | TruffleHog over the working tree, failing on any finding outside `.trufflehog-exclude-paths.txt` |

Return to the [reference index](README.md).

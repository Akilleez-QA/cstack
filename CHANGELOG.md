# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html). There is no tagged
release yet; entries name the pull requests that made them.

## [Unreleased]

### Changed

- Vendored EndoForge repinned to `main` at `68eaa75`; the slice gains `vendor/endoforge/tools/durable.py` (portable durable sync: `F_FULLFSYNC` on macOS, else `fdatasync`, else `fsync`; endoforge #163) and `vendor/endoforge/core/runtime/isolate-wasm-tooling.mjs` (29 files). Forge goals now run on macOS, where the old ledger writer's `os.fdatasync` call made the ledger bridge exit 70. No Cstack-called interface changed.
- `cli.py` reports `run_status: completed` only when every dispatched call executed and responded; otherwise `not_executed`, `failed`, `outcome_unknown` or `stopped`, with a new top-level `not_completed` list giving each such outcome's status, assessment and limitations (CS-REQ-088).
- `tools/agent_profiles.py` now writes Claude Code project subagents to `.claude/agents/` from `agents/`; the unread `.agent/` output and its `mcpInheritance` field are removed. `--check` also fails on undeclared fields and on targets that would drop wiring. `tools/e2e_agent.py` writes its own temporary agent CLI wiring.
- `tools/cstack_mcp.py` refuses to start without the durable ledger `cstack init` sets up, and says which command to run; `--allow-memory-ledger` keeps the memory ledger for tests and throwaway development. Tailscale is now optional: the device name comes from `--device`, the name `cstack init` recorded, or the tailnet name. `cryptography` moved from `ci/requirements.txt` to `requirements.txt`.
- Re-vendored the four pinned foundations at the commits that merged the 2026-11-09 backfill-review fixes: refrigeration `f78905d`, film `52fa82c`, robotics `d61de96`, template `0dcf469` (template gains one test file, 50 entries). Upstream changed only docs, tests and tools; no bridge or schema changed, so inventory hashes are unchanged. `poodo_skill` moves to `aeba967` (its 45 synced files are byte-identical; the new upstream release-docs test file is listed as deferred). `EXPORT-MANIFEST.json` rebuilt. EndoForge stays pinned until its rounds 8-10 merge.
- README and docs index rewritten for a first-time reader: purpose, a real approval run, a top-down diagram and install first; the NASA control documents sit behind one "Engineering records" section. Material moved out of the README went to new how-to guides (approve asks, define bots, use a real model, add a domain, merge train) and an explanation of Foundations and pins. The README's Measured table moved to `docs/verification/measured-2026-11.md`, with every figure tied to a commit on `main` (assurance finding F-7) (#80).


### Added

- Starter agent organization: an engine-neutral agent definition format (`contracts/agent.schema.json`), nine starter agents in `agents/` with AOR entries in `aors/fleet.json`, a single-writer hand-off table and concurrency policy (`agents/org.json`), six area-of-life templates, a guard hook that applies AOR effects to Claude Code built-in tools (`tools/agent_guard.py`), the twenty-option rule fixed in every definition with an options-record check (`tools/check_options.py`), and CS-REQ-080 to CS-REQ-083.
- `cstack init` (`tools/cstack_init.py`, `adapters/local_setup.py`): one command sets up a private state folder, the device name and a durable witnessed ledger for every bot; safe to run again, with `--check` for a read-only health report. Requirements CS-REQ-084 to CS-REQ-086; guide [Set up Cstack](docs/guides/how-to/set-up.md).
- Cstack family documentation standard published in `docs/standards/` (standard, checklist, templates) as the canonical copy for the family.
- NASA-organized control documents: software management plan, compliance matrix, test plan and procedures, generated data dictionary, generated test report and version description for the `main` baseline, assurance record, user manual map, limitations page; problem-report and change-request issue templates and a peer-review PR template.
- Requirements CS-REQ-036 to CS-REQ-077 for behaviour existing tests already check; every requirement allocated to a design component; full bidirectional trace.
- `tools/check_trace.py`, run as the `trace` suite in `ci/run-local.sh` and in CI; `tools/gen_data_dictionary.py`; `tools/gen_release_docs.py`.

- Diátaxis guides: a first-run tutorial, how-to guides for running the CI checks locally and repinning EndoForge, a reference of commands, configuration and environment variables, and explanations of EndoForge vendoring and the server and adapters.
- Claude Code model transport for forge goals, `adapters/workcell/claude-transport.mjs` (#70).
- Project code name Mjölnir for Cstack and the EndoForge core it vendors (#69).
- Film and Robotics as in-process workcell kernels: JavaScript ports compared with the pinned Python on every path, with a seeded fuzz and boundary scan (`tools/fuzz_ports.py`) (#59 to #64).
- Workcell runtime: one `cstack_forge` goal runs from a POODO decision through EndoForge `IsolatePool` workcells, real gates and ledger, to a witnessed receipt (#48).
- Refrigeration and Template as in-process kernels, checked against the pinned Python, with a spawn counter (`tools/spawncount.py`) (#47).
- Kernels propose decisions only as data, bounded per run, and the core accepts or refuses them (#49, #52).
- A kill during a run is recorded as `outcome_unknown`; a lost controller is reconciled once by the next session; `cli.py --resume` reruns an unknown decision (#46, #50).
- The acceptance for end-to-end wiring, frozen before the work (#44).
- Foundation Engine as a domain: two read-only validators from a pinned partial vendor copy (#33, #34).
- Refrigeration CLI acceptance with a host approval and EndoForge evidence (#30).
- Configured POODO evidence routing through `EndoforgePort` and a durable file adapter (#24, #27, #28).
- Fail-closed CLI approver for `ask` calls (#25).
- Template export, control core for goals, scoped authority and evidence, Foundation adapters and pins.

### Changed

- Control documents carry the family metadata header and a self-assessed classification statement (Class E analog, not safety-critical) in place of "No NASA software classification … is asserted".

- `tools/check_links.py` also scans the README, CONTRIBUTING, CHANGELOG, NOTICE, every document under `docs/` and the area READMEs.
- Vendored EndoForge repinned to `main` at `ea7b8d6`; the slice gains `vendor/endoforge/core/runtime/dump-list.mjs` and `vendor/endoforge/tools/dump_list.py` (27 files), which the updated `IsolatePool` and ledger writer import for memguard dump-list registration, off unless `ENDOFORGE_DUMP_LIST=1` or the memguard dump-list directory exists. No Cstack interface change (#79).
- Vendored EndoForge repinned to `main` at `6dffea9` (P-68 capacity changes), via `f6711a7` and `da47ad9`; the slice now holds the gates, ledger, `IsolatePool` and capacity planner (#45, #68, #71, #73).
- `tools/pin_endoforge.py` pins only commits on EndoForge `main` unless `--allow-unmerged` is given, and the vendored ledger writer journals beside the run ledger instead of under the user's state directory (#72).
- Every README command passes on a fresh clone, checked by `tools/check_readme.py` (#43, #51, #53, #58).
- Vendored Foundations and the POODO skill snapshot refreshed to their public `main` heads (#23, #26).
- Vendored Film (`7601fc5`, 55 files), Refrigeration (`069ea9e`, 79), Robotics (`e6abce6`, 61) and Template (`a57f14c`, 49), the Foundation Engine manifest (`8445d31`, 2,513 entries) and the POODO snapshot (`4a111aa`, 8 of 45 listed files changed) repinned after the upstream documentation PRs, refrigeration's `exposure-limits.json` provenance fix and the manifest-copy trace-check fix in Refrigeration, Robotics and Template (each #14). Tool inventories unchanged; upstream CI workflows are no longer in the copies; Foundation Math v0.14 and `foundations/math/` unchanged (#78).

### Fixed

- Durable ledger events, relay messages and fleet mail budgets survive a torn or cut-short write (#65, #66, #67).
- The durable ledger keeps no in-memory event when opening its file fails, so a retry starts a clean chain; a session that ends with an `unknown` outcome keeps its core ledger as `.recovered`, so later sessions still list the attempt in `unresolved_attempts`. Both found by the 2026-11-09 backfill review of PRs merged without automated review.
- Candidates are bound to their task and decisions to one request; a changed judge is refused; refusals and kernel faults fail the candidate; decimal inputs are taken exactly (#54, #55, #56).
- Recovery on the forge path: the ledgers agree and torn tails are quarantined (#57).
- The claim gate fails closed without an approved-atoms Registry (#22).

### Known limits

- Running many coding agents at once and EndoForge's caching aren't wired into Cstack.
- Workcells are V8 isolates, not an OS sandbox; cgroup limits apply only where the host delegates them.
- The witness is a local fsync, not an independent quorum.
- Foundation Engine's TypeScript runtime isn't included; only its bridge validators are.
- Foundation kernels for Math aren't shipped in workcells.

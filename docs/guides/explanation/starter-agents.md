# The starter agents

Cstack ships nine named agents, each wired to one of the family's tools, so a new user gets the stack's expert working practice without first learning its parts. This page explains how they are defined, how they reach Claude Code, and what is enforced where.

## The roster

| Agent | Job | Tools it wields |
|---|---|---|
| Chief | Takes the request, routes it, briefs the person; answers conductor escalations | Its own Cstack server (goals and the ledger), fleet mail |
| Scribe | Writes the spec (CONTRACT.md, tests.json, job.json, atoms.json) before any build | EndoForge job validation |
| Oracle | Consequential decisions through POODO in full | POODO skill and tool |
| Sage | Expected values from the pinned Foundations | Foundations |
| Smith | Builds from a frozen spec and returns a candidate with its receipt | EndoForge job and conductor |
| Warden | Independent verification from a fresh context | EndoForge gates, escape harness, `tools/claim_gate.py`, `tools/check_trace.py` |
| Lab | Precommitted experiments: id, PRECOMMIT, RESULT | EndoForge experiment ids and escape harness |
| Keeper | Health, capacity, budget burn and pins | `tools/runtime_watch.py`, `tools/witness_watch.py`, pin tools |
| Archivist | Turns lessons into checks; library, skills, memory review | Its own Cstack server |

The names are for addressing and trust; the role, the tools and the hand-off table do the work. In EndoForge "oracle" means a test oracle; the Oracle agent is the decision agent, and its definition says so.

## Three sources, one generator

- `agents/<slug>.md` is the engine-neutral definition: a JSON front block validated by `contracts/agent.schema.json`, then the agent's own working practice in Markdown.
- `agents/org.json` (schema `contracts/agent-org.schema.json`) holds the concurrency policy, the owner-only steps, the single-writer artifact table and the suggested AOR for each template. `agents/PRACTICE.md` holds the practice every agent shares.
- `aors/fleet.json` holds the authority. Each agent names its AOR by slug, and its id must equal the AOR's id.

`tools/agent_profiles.py` checks the three against each other and writes `.claude/agents/<slug>.md`, the Claude Code project subagents. The generated files are committed, carry a "Generated" marker and are marked `linguist-generated` in `.gitattributes`. `--check` fails when:

- a generated file differs from what the sources produce, or an unmarked file sits in `.claude/agents/`;
- a definition field has no declared disposition for the target engine, so it would be dropped silently;
- the target would drop a wiring field. Claude Code ignores `mcpServers`, `hooks` and `permissionMode` in plugin subagents, so `--target claude-plugin` always fails, and so does a repository that is a plugin root.

Each target declares every field as native, partial, body (rendered into the instructions) or unsupported. Partial and unsupported fields that an agent uses are listed in its generated instructions under "Not fully honoured by this engine". For Claude Code these are routines (no scheduler), the delegation list (enforced only for an agent run as the main thread with `claude --agent`), delegation depth beyond 0 (a global setting) and `different_model_preferred`.

## The hand-off table

Every artifact in `agents/org.json` has exactly one writer, its readers, its format and its transport: a ledger event, fleet mail, or a file in a slice the writer's AOR owns. Each agent's `handoff.returns` must be exactly the artifacts it writes, and each named reader must list the artifact in `handoff.accepts`. This is how the rules "Scribe writes the spec, Smith never does", "Lab writes PRECOMMIT and RESULT, Warden reviews them" and "Archivist writes checks, Warden runs them" are enforced rather than described.

## Where authority is enforced

1. **Cstack MCP server.** Each agent's own `cstack-<slug>` server (`tools/cstack_mcp.py --aor <slug>`) applies the AOR to every goal, decision and execution, as before.
2. **Tool lists.** The generated `tools` list grants built-in tools by effect class (read, write, execute), the agent's own MCP servers only, and `Agent` only to agents that may delegate.
3. **Guard hook.** A `PreToolUse` hook runs `tools/agent_guard.py --aor <slug>` on Edit, Write, NotebookEdit and Bash (and on reads when reading is not `allow`). It denies writes outside the agent's slices and any write to `aors/`, `agents/`, `.claude/`, `.mcp.json` or the generator and guard themselves; for Bash it parses the command line (through pipes, lists, subshells, command substitution, `sh -c`, `eval`, `xargs` and `find -exec`), names each program by its basename, and asks the person before a send, post or delete, before any command it can't read (inline `python -c` or `node -e` code, a shell reading its input, a computed program name), and before a write whose path it can't place; it denies Bash writes into the same protected paths; it fails closed. It reads the command and is not a sandbox: a script or build the agent runs can still do anything its process can, so the MCP server and an OS sandbox stay the authority.

The registry forbids `allow` for send, payment, post, filing and delete, so these stay `ask` for every agent. Chief is not on the approval path.

## Working limits

`agents/org.json` sets at most three agents active on one task, routing through Chief, no broadcast to every agent, and one live instance per bot; the Cstack session already refuses a second live session for the same bot and domain. Every agent that starts or advances a goal runs POODO's twenty-option step itself and records the options, so the person never has to learn the rule. The schema fixes `poodo.options` at 20 and `poodo.research_gate` at `required`; an agent varies only its research and red-team `effort` (light, standard or thorough; Oracle is thorough) and declares when it escalates.

### Why twenty options

The count is deliberate. Asking a model for twenty options that differ in how they work pushes it past its most probable first answer, which early assumptions shape and which is often a local minimum, into the long tail of the distribution, so more of the space is actually evaluated. Rephrasings and padding defeat this, so the options must differ in mechanism, evidence, risk, reversibility or authority and include unconventional, diagnostic, conservative, reversible, defer-or-stop and escalation options. `tools/check_options.py` checks an options record: exactly twenty, distinct ids, every required kind, no shared mechanism and no near-verbatim pair (word overlap of 0.6 or more). It cannot judge that two differently worded options work the same way, so a reviewer still reads the record. The core separately refuses Orient-to-Decide without twenty distinct option ids and Observe-to-Orient without a research record (`poodo_core/core.py`).

## Adding your own agent

```sh
python -B tools/agent_profiles.py --new money --slug house-money --name "House Money"
```

This writes the definition (here `house-money.md` in `agents/`) from `agents/templates/money.md`, adds its report artifact to `agents/org.json`, and prints a suggested AOR entry with every gated effect at `ask`. Adding that entry to `aors/fleet.json` is the owner's step; until then the generator refuses the agent. Templates: assistant (drafting only), money, research, home-ops, security, and domain-specialist (pass `--foundation`).

## Running them

Start Claude Code at the repository root. The servers use `uv` and `$CLAUDE_PROJECT_DIR`; project subagents with inline servers and hooks load only in a trusted workspace. `endoforge`, `foundations` and `poodo` are referenced by name and must be configured as MCP servers (they are separate workstreams). Fleet mail uses `CSTACK_FLEET_MAIL_REPO` (default `your-org/cstack`). The Cstack server resolves the device from the tailnet name, so the machine must be listed in `aors/fleet.json` devices.

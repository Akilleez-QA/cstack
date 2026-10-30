# Code goes through Codex (fleet policy)

**Rule (the owner, 2026-10-25):** "prevent grok bots from doing code, force them to execute through the codex CLI." Grok bots plan, review and open PRs; Codex CLI writes the code. That moves the heavy coding load off Grok's rate limits and onto the Codex subscription.

**Scope.** This policy applies only to bots put under the Grok `PreToolUse` hook (and any bot wired to the Claude Code shim). It does **not** restrict the owner or the interactive Claude Code app; they are not under this hook. Under it, a bot may write code **only** through Codex via `codex-task`. Writing code through any other agent CLI (`claude`, `hermes`, `cursor-agent`, `gemini`, `aider`, `opencode`, `goose`, `amp`, `crush`, `qwen-code`, `llm`, `ollama run …`, and `npx`/`bunx`/`uvx`/`pipx run` forms of them) is denied, because it would route around the shields (`CODEX_BLOCKED`) and the ledger gate. Clearly read-only invocations (`claude --version`, `hermes --help`) stay allowed; anything the classifier cannot resolve statically is denied (fail closed). See "What this is (a tripwire, not a boundary)" below.

## What is here

| File | Installed at | Purpose |
|---|---|---|
| `no_direct_code.py` | `/opt/cstack/no_direct_code.py` (root, 0755) | Grok `PreToolUse` hook shim, **for Grok bots only** (never wire it into Codex: it would block Codex's own `apply_patch` edits). It blocks edits of code files and of Codex control files (`*.rules`, `.codex/`, `AGENTS.md`, `AGENTS.override.md`), and shell commands that write them or change repositories, checked per simple command and inside `bash -c`, `sh -c`, `eval` and command substitutions. It blocks `codex` launched any way but `codex-task` or `codex-guard.sh codex …`, a direct guard launch with sandbox-widening flags, and **any other agent CLI** (see Scope) launched as a code writer — detected per simple command, through wrappers (`env`, `nohup`, `timeout`, `setsid`, `sudo -u`, absolute paths, quote/backslash splits like `cl''aude`/`\claude`, `command`/`exec`, `PATH=… claude`) and inside `bash -c`/`sh -c`/`eval` and substitutions. It fails closed on anything it cannot resolve statically (dynamic command names, decoded commands, bare shells running scripts/stdin). Each block tells the bot to use `codex-task`. |
| `code_write_policy.py` | `/opt/cstack/code_write_policy.py` (root, 0644) | The pure, vendor-neutral classifier the shims share: a normalized call (`{kind: edit\|shell\|other, path?, command?}`) in, `allow` or `deny` plus a reason out. No stdin, stdout or vendor names. |
| `codex_route.py` | `/opt/cstack/codex_route.py` (root, 0644) | Data: the sanctioned code writer (Codex via `codex-task`/`codex-guard.sh`), its control files, widening flags and the remedy text. Swapping the writer changes this file only. |
| `claude_code_pretooluse.py` | not installed | Claude Code `PreToolUse` shim over the same classifier, for a Claude Code bot put under this policy (matcher `Write\|Edit\|MultiEdit\|NotebookEdit\|Bash`). It blocks with exit 2 and the reason on stderr. |
| `requirements.toml` | `/etc/grok/requirements.toml` (root, 0644) | Grok's root-owned policy layer. Grok **enforces** hooks from it, so bots cannot disable them. |
| `codex-task` | `/usr/local/bin/codex-task` (root, 0755) | The one way to get code written: `codex-task <repo> "<task + checks>"` (exactly two arguments; a task starting with `-` is refused). It runs the fixed command line below through the fixed guard path `/workspace/ops/shields/lib/codex-guard.sh` (never taken from the environment), so shields-up and the ledger gate stop it. Evidence (`events.jsonl`, `last-message.md`) goes to `~/.local/state/codex-task/run.*`; it prints the Codex thread id. After a successful run it commits Codex's diff on a new branch (see "Commit step"). |
| `install.sh` | — | Idempotent installer. Dry run by default; run with `--apply` as root. It pins Codex CLI (`CODEX_VERSION`, default 0.164.0) and never overwrites a different existing policy file. |

The command line codex-task runs (checked against `codex exec --help`, 0.164.0):

```bash
codex-guard.sh codex exec --cd "$repo" --sandbox workspace-write \
  --ignore-user-config --ignore-rules --strict-config \
  -c 'approval_policy="never"' -c 'approvals_reviewer="user"' \
  --json -o "$run/last-message.md" -- "$task" </dev/null >"$run/events.jsonl"
```

- `--` keeps the task from being parsed as a flag (`--dangerously-bypass-approvals-and-sandbox` would otherwise win over `--sandbox`).
- `--ignore-user-config` and `--ignore-rules` stop `~/.codex/config.toml` and user or project `.rules` files from applying. An execpolicy `allow` rule runs its command **outside** the sandbox.
- `approvals_reviewer="user"` stops an `auto_review` config from swapping headless `never` for a model approver.

Exit codes: 0 done; 64 usage; 65 not a git checkout; 66 no such directory; 69 guard missing; 70 Codex exited 0 with no completed turn; 73 dirty tree before the run, or the commit step could not run; 75 shields up (from codex-guard) or a Codex usage limit (stderr `codex-task: quota`, with the reset time when Codex gives one). Otherwise Codex's own status.

## Classifier and vendor shims (ADR 005 item 11b)

The policy is decided once, in `code_write_policy.classify(call, route)`; each hook vendor gets a thin shim that maps its JSON to the normalized call and the decision back. `tests/test_code_write_policy.py` runs the same normalized cases through the classifier and every shim and requires the same decision. A shim that cannot load the classifier or route blocks every call.

There is **no Codex shim**, on purpose. Codex's hook schemas (`parts-wall/primitives/ai-agents/oss-codex-hooks-and-notify/files/`) match the ones embedded in codex 0.164.0 exactly, and Codex's PreToolUse input is the same shape (`tool_name`, `tool_input`), so a shim would be about 20 lines. But this policy says "the caller does not write code; Codex does". Applied to Codex it would deny every `apply_patch` edit, which is Codex's whole job. A Codex hook only makes sense for a different policy, such as the repo-scope guard on the parts wall (deny `git push`, `gh`, writes outside the repo). That policy gets its own classifier when it is built; it can reuse this split.

## Commit step

Inside Codex's `workspace-write` sandbox `.git` is read-only, and the hook stops bots from running `git add` or `git commit`. So after Codex exits 0 with a completed turn, **codex-task itself** commits, outside the sandbox:

- It refuses to start on a dirty tree (exit 73), so the commit holds Codex's diff and nothing else.
- It creates a new branch `<bot-slug>/<yyyymmdd>-codex-<last 8 hex of the thread id>`. It never reuses an existing branch and never commits on `main` or the starting branch.
- The commit message is `codex: <first task line>`, then the full task and the trailers `Codex-Thread`, `Codex-Version`, `Codex-Base`, `Codex-Evidence` and `Requested-By`.
- The bot slug comes from `CODEX_TASK_BOT` (for example `grok-bot`) and must be on the roster (`aors/fleet.json` plus `aors/branch-slugs.json`, checked by `workers slug`). There is no fallback: an unset or unknown name exits 64 (a `null/...` branch reached GitHub on 2026-10-27). It is used for naming and the worker registry only and grants no authority.
- The run is registered with the worker registry (`forge/endoforge/tools/throttle/workers`): `workers list` shows it, its bot and task while it runs, and dead if it dies without ending.
- If Codex changed nothing, there is no commit and the exit is 0.

### Pushing

After the commit, codex-task pushes the bot's own branch to `origin` by exact refspec (`refs/heads/<bot>/<date>-codex-<id>`): never forced (no `+`), never `main`. the owner, 2026-10-27: worker branches stranded on the box were part of "this architecture in cstack might need refinement". `CODEX_TASK_PUSH=0` keeps the branch local. A push that fails (no credentials on this host, say) leaves the commit on the branch, says so on stderr, and still exits 0. The bot's own `git push` stays blocked by the hook; only codex-task pushes, and only its branch.

## Install on the Grok VM box (Grok VM maintenance)

The box is not reachable from host-a: it SSHes out to the rig, never the other way. Run this on the box itself:

```bash
cd /workspace/cstack && git pull --rebase
sudo workshop/box/codex/install.sh          # dry run: shows every change
sudo workshop/box/codex/install.sh --apply
```

Then **the owner** signs Codex in, once per device, with his ChatGPT account:

```bash
codex login --device-auth
```

The same steps work on host-a and any other fleet device whose bots run Grok.

## What bots see

A blocked tool call returns a reason like:

> Blocked: `git commit` changes a repository. Grok bots do not write code directly. Run the change through Codex instead: `codex-task <repo-dir> "<what to change and how to verify it>"`…

Still allowed:
- reading anything;
- running tests and status commands, including read-only `git apply --check`/`--stat` and `--dry-run` forms;
- `codex-task`, and `codex-guard.sh codex …` without sandbox-widening flags;
- editing notes and prose (`.md`, `.txt`);
- committing the notebooks repo with `git -C /workspace/ops …` (the path is resolved first, so `/workspace/ops/../x` is not the notebooks repo);
- writing `/tmp` logs.

## What this is (a tripwire, not a boundary)

This hook is a **tripwire**: it catches mistakes and casual bypasses, not a determined adversary. Recent research is blunt about why a denylist cannot be the boundary — GuardFall (Adversa AI, 30 Jun 2026; [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-guardfall-ai-coding-agent-shell-injection/)) bypassed 10 of 11 open-source agent command guards (Hermes among them) by shell rewriting, and CmdNeedle (arXiv 2606.15549) found 69–98.6% of 1,709 real denylists fragile. So this classifier parses with a real shell tokeniser (`shlex`, `posix=True`), walks substitutions, `bash -c`/`sh -c`/`eval` and `env`/`nohup`/`timeout`/`setsid`/`sudo` recursively, and **denies anything it cannot resolve statically** instead of guessing. That closes the quote-removal, wrapper and path-via-variable rewrites and the obvious decode-and-run paths, but a determined shell can still smuggle a write (see Limits).

**The real boundary must be OS-level** (below). Treat the tripwire as defence in depth, never as the thing that makes the box safe.

### codex-guard program check

`codex-guard.sh` runs **codex only**. Any other program (its first argument) is refused with **exit 76** — distinct from shields-up `75` and ledger-deny `77` — with the message `codex-guard: refusing to run '<prog>': this guard launches codex only`. An empty argv (codex-pool's `CODEX_POOL_GUARD` pre-flight) and a path whose basename is `codex` (e.g. `/usr/bin/codex`) are allowed. The only production callers pass `codex` (`codex-task`) or an empty argv (`codex-pool`), so nothing legitimate is broken; `codex-pool` only ever launches `codex` itself.

## OS-level follow-up (Grok VM maintenance; not implemented here)

The durable fix is to make writing code through another agent CLI impossible, not merely tripwired. Steps for the box:

1. **No agent-CLI credentials for the bot user.** The Grok bot's user must not hold API keys, OAuth tokens or logged-in sessions for `claude`/`hermes`/`gemini`/etc. Only Codex is signed in, and only for the owner's account via `codex login --device-auth`.
2. **Egress allowlist.** Permit outbound HTTPS to model APIs only through the guard/Codex path (extend the poller's nftables allowlist in `products/hmi/shields/lib/shields-local.sh`). A bot that launches another agent CLI then cannot reach its model endpoint.
3. **Remove or root-own the binaries.** Don't install other agent CLIs on the box; if present, make them non-executable by the bot user. The policy files and `codex-task`/guard are already root-owned.
4. **Keep the hard boundary on the receiving side.** GitHub branch protection (the owner merges) and ADR 004's ledger gate stay the authority; the box the bots run on is treated as untrusted.

## Limits (honest)

- **This is a guard rail, not a sandbox.** A shell command can still smuggle a write, for example `python -c "open('x.py','w')…"` or `bash -c` with an encoded payload. The hook catches the common paths.
- **Residual agent-CLI bypasses after this change (known, accepted):** a non-shell interpreter that embeds its own agent call (`python3 -c "import subprocess; subprocess.run(['claude', …])"`, `node -e …`, `perl -e …`) — the interpreter is allowed and we don't read its program text; a write-then-run split across two tool calls where the written launcher isn't named for an agent; `npx -p <agent> <other>` or `pnpm dlx`/`yarn dlx <agent>` (only `npx`/`bunx`/`uvx`/`pipx run` are parsed); an agent reached over SSH or a container (`ssh host claude …`, `docker run … claude …`); and a genuinely read-only subcommand that isn't `--version`/`--help` (e.g. `ollama list`) is denied as a false positive, by design (fail closed). The OS-level follow-up closes the first and fourth of these; the rest are the cost of a static tripwire.
- **The hard boundary is on the receiving side:** GitHub branch protection (the owner merges) and ADR 004's gates on hosts the bots don't control.
- **The hook's input and output follow Grok's Claude-Code-compatible hook contract.** It prints a `deny` decision and exits 2.
- **Not yet verified inside a live Grok session.** Grok on host-a was signed out at the time of writing. The unit tests exercise the hook directly. After `grok login`, check that it fires by asking a bot to edit a `.py` file; the attempt should be refused, with the `codex-task` instruction.
- **Codex quota.** Codex has its own rate limits. `codex-task` does not retry on its own. It exits 75 with `codex-task: quota`, and the bot decides when to try again.
- **Sandbox preflight.** Codex's Linux sandbox needs user namespaces. `install.sh` runs `codex sandbox -- /bin/true` and warns if it fails, which is common in containers.
- **Not yet constrained at the root.** A root-owned `/etc/codex/requirements.toml` (allowed approval policies, sandbox modes, reviewers, forbidden rules) is the stronger fix for direct `codex-guard.sh codex …` launches. It is a follow-up; today the hook's flag check covers them.
- **The ledger gate sees the new argv.** codex-guard encodes the full argv as the ledger action, so intents registered for the old command line no longer match.

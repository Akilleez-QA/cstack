# Getting started

## Requirements

Use an agent host that can read a skill directory and its linked files. Full POODO use needs a web research tool. Filesystem access enables durable ledgers; subagents and native goal tools are used only when available and authorized.

Python is needed only for the validators: use Python 3.10 or newer and the pinned PyYAML dependency in `requirements-dev.txt`.

## Local Codex installation

These commands are for a POSIX shell. Keep the complete directory so relative references continue to resolve. Install only if the destination does not already contain another POODO copy:

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/Akilleez-QA/poodo.git "$HOME/.agents/skills/poodo"
```

`git clone` refuses to overwrite a nonempty directory. If POODO is already installed, inspect and preserve your local changes before choosing an update strategy.

Codex discovers skills in `~/.agents/skills`; restart it if the skill does not appear. With the Codex CLI, `codex --search` turns on the live web search POODO needs for full use. Invoke it with `$poodo`. The bundled metadata disables implicit invocation. These locations and invocation controls are documented in [OpenAI's skill guide](https://learn.chatgpt.com/docs/build-skills).

## Local Claude Code installation

```sh
mkdir -p "$HOME/.claude/skills"
git clone https://github.com/Akilleez-QA/poodo.git "$HOME/.claude/skills/poodo"
```

Claude Code reads personal skills from `~/.claude/skills/<name>/SKILL.md`, and you run one directly with `/<name>`, so invoke this one with `/poodo` followed by your request. Claude Code ignores `agents/openai.yaml`. This repository's `SKILL.md` does not set `disable-model-invocation: true`, so Claude Code may also load POODO on its own when a request looks relevant. To allow only `/poodo`, add `disable-model-invocation: true` to the front matter of your copy; Claude Code's [skills documentation](https://code.claude.com/docs/en/skills) says that setting stops Claude from invoking the skill itself.

## Other clients

This repository provides a local skill checkout. It is not a published marketplace plugin. Other Agent Skills clients may use different discovery paths and ignore Codex metadata.

## How the install was checked

- Codex (2026-11-08, Codex CLI 0.167.0, no model call): the two commands above ran in a throwaway home folder. Codex's prompt lists only skills it may start on its own, and POODO opts out of that, so a second scratch copy switched `allow_implicit_invocation` on. `codex debug prompt-input` then listed `poodo` from `~/.agents/skills/poodo`. No agent session was run.
- Claude Code (2026-11-08, Claude Code 2.1.319): the folder and `/poodo` syntax follow Claude Code's skills documentation, read on that date. A POODO copy installed at `~/.claude/skills/poodo` is reported to be listed and run with `/poodo`. That copy is an older, locally modified version that already sets `disable-model-invocation: true`. A fresh clone of this repository was not tested in Claude Code, nor was its behaviour without that line.

## First use

Give the agent a concrete problem, desired outcome, and authority boundary (in Claude Code, start with `/poodo` instead of `Use $poodo to`):

```text
Use $poodo to compare keeping our synchronous export process with moving it
to a background queue. We want exports to finish reliably without blocking
the app. Inspect the repository and research the relevant mechanisms.
Propose a decision and verification plan; do not change production.
```

Expect a short framing exchange, evidence gathering, alternatives, and an explicit decision or evidence boundary. POODO can summarize the decision without printing every internal working artifact or all 20 paths.

## Request Mega Observe

See the [full protocol](../../../references/mega-observe.md) and [example](../../../examples/mega-observe.md). Request this mode by name and establish the problem, scope, resource ceiling, and quality contract before launching it. Installing POODO does not start research or authorize spending.

## Check the package

From the checkout root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_skill.py
python -m unittest discover -s evals -p 'test_*.py' -v
python scripts/check_capsule.py evals/fixtures/valid-capsule.yaml
```

No model API key is needed for these checks. They do not run a behavioral evaluation.

## Updates and removal

Before updating, inspect `git status` and preserve edits. On a clean checkout, use `git pull --ff-only`. Review the diff before the next invocation. To uninstall, move the skill directory outside the host's skill discovery paths and restart the client if necessary. Keep any personal ledgers separately.

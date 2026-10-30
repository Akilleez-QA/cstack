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

Codex discovers skills in `~/.agents/skills`; restart it if the skill does not appear. Invoke it with `$poodo`. The bundled metadata disables implicit invocation. These locations and invocation controls are documented in [OpenAI's skill guide](https://learn.chatgpt.com/docs/build-skills).

This repository provides a local skill checkout. It is not a published marketplace plugin. Other Agent Skills clients may use different discovery paths and ignore Codex metadata.

## First use

Give the agent a concrete problem, desired outcome, and authority boundary:

```text
Use $poodo to compare keeping our synchronous export process with moving it
to a background queue. We want exports to finish reliably without blocking
the app. Inspect the repository and research the relevant mechanisms.
Propose a decision and verification plan; do not change production.
```

Expect a short framing exchange, evidence gathering, alternatives, and an explicit decision or evidence boundary. POODO can summarize the decision without printing every internal working artifact or all 20 paths.

## Request Mega Observe

See the [full protocol](../references/mega-observe.md) and [example](../examples/mega-observe.md). Request this mode by name and establish the problem, scope, resource ceiling, and quality contract before launching it. Installing POODO does not start research or authorize spending.

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

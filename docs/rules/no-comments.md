# No code comments

the owner's rule, 2026-10-29: **no code comments in Cstack code.**

## Why

Agents leave dialogue artifacts in comments ("as you asked", "now we do X"). They also write comments that justify a hack ("we do not do Y here"). The comment makes the hack look deliberate, so the next agent copies it and the hack spreads. This follows the thread by Erik Dunteman (@poteto).

## What to do instead

- **Name things clearly.** A function, variable or test name carries the meaning a comment would.
- **Put the why in the PR body and the commit message.** They are tied to the change and reviewed with it.
- **Put durable design notes in docs.** If the reason must outlive the PR, write it under `docs/` and link it from the PR.

## Allowed exceptions

Only comments that are syntax, with no prose:

- shebangs
- license headers
- tool directives, for example `# type: ignore`, `# noqa`, `// eslint-disable-next-line rule-name`

## Existing comments

Existing comments stay for now. Do not delete them in unrelated PRs. Removing them is a separate proposal for the owner.

## Review

Reviewers reject PRs that add comments.

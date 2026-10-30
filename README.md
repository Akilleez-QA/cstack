# Cstack

Cstack is a template for running a fleet of AI bots under one human approver. Copy it, name your bots, plug in your own domains, and every action a bot takes goes through a control core that records goals, scoped authority and evidence.

Status: early template. The numbers below were measured on the release commit; anything not listed here is not claimed.

## What is inside

| Path | What |
|---|---|
| `poodo_core/`, `contracts/`, `schemas/` | The control core: goals, phases, authority grants, decisions, attempts and evidence receipts, with the JSON contracts they obey |
| `adapters/`, `extensions/`, `bootstrap.py` | Capability ports: bounded stdio bridges from the core to each domain, registered once in `bootstrap.DOMAINS` |
| `aors/`, `tools/` | The bot layer: areas of responsibility per bot, AOR sessions over MCP, fleet mail, approvals, a witnessed ledger, and the merge train |
| `products/hmi/` | The human side: shields-up and kill switch, ledger, phone control board |
| `foundations/math`, `foundations/template` | The worked example domain and the empty domain to copy |
| `foundations/refrigeration`, `foundations/film`, `foundations/robotics` | Example domains carrying public engineering logic only |
| `reasoning/poodo` | The POODO reasoning method the core enforces |
| `vendor/foundation-math-v014` | Foundation Math, byte-pinned |
| `ci/`, `.github/` | The local CI script and the GitHub workflow that calls it |

Related projects:
- EndoForge, software creation as a runtime operation: https://github.com/Akilleez-QA/endoforge
- Foundation Engine, the GPL-3.0-only engine: https://github.com/Akilleez-QA/foundation-engine
- Foundation Math: https://github.com/Akilleez-QA/foundation-math
- POODO: https://github.com/Akilleez-QA/poodo

## Measured

CI: local only. GitHub Actions billing is blocked on this account, so there is no CI badge; the results below come from `python -B -m unittest discover -s tests` run locally on Linux with Python 3.14.8 at the release commit.

| Suite | Tests | Result |
|---|---|---|
| `tests/` | 531 | OK, 2 skipped |
| `foundations/film` | 23 | OK |
| `foundations/math` | 18 | OK |
| `foundations/refrigeration` | 58 | OK, 5 skipped (upstream reference sources not shipped) |
| `foundations/robotics` | 34 | OK |
| `foundations/template` | 4 | OK |
| `tools/check_links.py` | 73 paths | 0 broken |
| gitleaks 8.30.1 | whole tree | 0 findings |
| trufflehog | whole tree | 0 verified |

## Quickstart

Python 3.11 or newer on Linux or macOS.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r ci/requirements.txt
cp cstack.config.example.json cstack.config.json
python -B cli.py < examples/scalar-and-negative.json
python -B -m unittest discover -s tests
bash ci/run-local.sh python links
```

## Define your bots

1. Edit `aors/fleet.json`. Each bot has a `slug`, the `slices` of the repo it owns, what it does not own, and `effects`. Anything that sends, pays, posts, files or deletes is `ask`, which routes to the one human approver.
2. List branch lanes in `aors/branch-slugs.json`. Branches are named `<bot-slug>/<yyyymmdd>-<topic>`.
3. Run `python3 tools/generate_aors.py --check` to validate the registry against `contracts/aor.schema.json`.

## Wire the merge train

`tools/merge_train.py` merges open PRs in dependency order. A PR merges only when its body lists the local checks that were run, it stays inside its bot's slice, and it merges cleanly. It never deletes branches or force-pushes. `python3 tools/merge_train.py --wip` shows open PRs per lane. Run it from a timer against a fresh worktree of `main`.

## Add a domain

Copy `foundations/template`, rename it, add tools and their pins, and register it in `bootstrap.DOMAINS`. The refrigeration, film and robotics domains show three complete examples.

## Not included

No business data, no customer or site data, and no engineering, safety or compliance determination. The example domains are references to learn from, not certified tools.

## Licence

GPL-3.0-only. See `LICENSE` and `NOTICE.md`.

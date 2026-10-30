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

## Foundations

Cstack uses [Foundation Math](https://github.com/Akilleez-QA/foundation-math) as a byte-pinned tool backend. `bootstrap.py` selects `vendor/foundation-math-v014/`; `adapters/math_stdio.py` binds its custom stdio bridge, and `extensions/foundation_math.py` supplies the domain contract. `foundations/math/` is a separate research layer over that vendor tree. Template, Refrigeration, Robotics and Film under `foundations/` are local sibling domains with their own bridges and manifests; they are not Foundation Engine runtime modules.

The vendored distribution is v0.14, as recorded in `NOTICE.md`. Its `SOURCE-MANIFEST.json` SHA-256 is `23219ba772c84796c007eee75458afc499b6ac257b154e78cf3068e41bfdb9a2`; the adapter checks all 561 listed files. The canonical tool catalog SHA-256 is `7df9574ee6788e55bb51aec8ebf858e958c252808ec3f4c217e43f598c961ba9` (adapter encoding, not raw schema-file bytes). These bind bytes, not authentic provenance or mathematical truth.

[Foundation Engine](https://github.com/Akilleez-QA/foundation-engine) is linked, not included (`NOTICE.md`). Vendored Math's `docs/PROVENANCE.md` credits its reusable-core/optional-capability pattern and states that engine runtime code is not incorporated. Cstack has no registered `foundation_engine` domain or engine commit pin; the extension lists that sibling contract as unimplemented.

To update a Foundation, identify the candidate commit or artifact, compare its source manifest, catalog, schemas and receipt semantics, then change the source and corresponding adapter pins together in a reviewed branch. Local sibling manifest builders are under each domain's `tools/build_manifest.py`. Run the root and domain unittest suites and review byte changes before accepting new pins. The current upstream Math README describes a selected extraction of v0.14, not the full historical distribution; upstream main is not a demonstrated drop-in replacement. No automatic upgrade command is provided here.

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

## Commercial licensing

This project is available under the GNU General Public License v3.0 only (GPL-3.0-only). If you want to use it in a product or service under different terms, commercial licenses are available from Refrigeration.AI. Contact craig@nh3.biz.

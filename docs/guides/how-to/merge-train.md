# How to run the merge train

`tools/merge_train.py` merges open pull requests in dependency order. It is meant to run from a timer against a fresh worktree of `main`, so bots' pull requests land without a human merging each one.

It works in passes: pull requests based on `main` first, then each merged pull request's children, retargeted to `main`. A pull request merges only when:

- it is not a draft,
- its branch's first segment is a bot slug from `aors/fleet.json` or a lane in aors/branch-slugs.json (a lane list the tool reads if present). This check applies only when both files exist; this repository ships no lane list, so it is off until you add one,
- its branch and files are in scope (see below),
- its body lists the local checks that were run,
- it passes the policy: with `--policy low-risk`, every file must be Markdown or under `docs/`, and none under `contracts/`, and
- GitHub reports it as mergeable, with no conflicts with `main`.

It squash-merges, never deletes branches and never force-pushes.

## What the train will merge without review

Scope depends on the branch name. This is `in_scope()` in `tools/merge_train.py`:

| Branch | Merged by the train when | Always left for review |
|---|---|---|
| `worker/*` | every file is under `examples/` or `docs/` (including `examples/interface/*`) | Any file outside `examples/` and `docs/` |
| `coordinator/*` | no file is under the four paths on the right | `poodo_core/`, `adapters/`, `contracts/`, `examples/interface/*` |
| Any other branch | never | Everything |

Coordinator branches are trusted more than worker branches. With the default `--policy all`, the train merges a coordinator pull request that changes `tools/`, `tests/`, `bootstrap.py`, `cli.py`, `extensions/`, `vendor/`, `.github/` (including the CI workflow) or `foundations/`, without review. Only `poodo_core/`, `adapters/` and `contracts/` are left for review on every branch.

If you run the train unattended and want those paths reviewed, run it with `--policy low-risk`, which merges only Markdown and `docs/` changes, or keep `coordinator/*` branches for work you have already reviewed. The tool's own docstring says `tools` and `tests` are never merged by the train; for coordinator branches the code above is what applies. Its docstring also lists `examples/interface/*`, but a `worker/*` branch that changes only files there is in scope, because `examples/` is an iteration path.

## What you need

`gh` installed and signed in, and a GitHub remote. Without them the tool says so and exits 2.

## Run it

Count open pull requests per lane against the work-in-progress limit (10):

```sh
python3 tools/merge_train.py --wip
```

```text
  1  docs
```

Plan a run without merging anything, limited to low-risk pull requests:

```sh
python3 tools/merge_train.py --dry-run --policy low-risk
```

```text
{
 "merged": [],
 "retargeted": [],
 "skipped": {
  "80": "out of scope (platform core or other bot)"
 }
}
```

The dry run prints what it would do, as JSON. Here the only open pull request is on a `docs/` branch, which is neither `worker/*` nor `coordinator/*`, so it is out of scope. Drop `--dry-run` to merge. Other options are in the [command reference](../reference/commands.md): `--policy` is `all` (default) or `low-risk`, and `--max-passes` defaults to 12.

Return to the [how-to guides](README.md).

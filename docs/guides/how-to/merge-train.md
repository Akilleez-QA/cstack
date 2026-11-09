# How to run the merge train

`tools/merge_train.py` merges open pull requests in dependency order. It is meant to run from a timer against a fresh worktree of `main`, so bots' pull requests land without a human merging each one.

It works in passes: pull requests based on `main` first, then each merged pull request's children, retargeted to `main`. A pull request merges only when:

- its body lists the local checks that were run,
- its branch is in scope: `coordinator/*` branches, and `worker/*` branches whose files all sit in the iteration paths listed in the tool's docstring, and
- it merges cleanly.

Platform-core paths (`poodo_core/`, `adapters/`, `contracts/`, `tools/`, `tests/` and others) are never merged by the train; they wait for review. It squash-merges, never deletes branches and never force-pushes.

## What you need

`gh` installed and signed in, and a GitHub remote. Without them the tool says so and exits 2.

## Run it

Count open pull requests per lane against the work-in-progress limit (10):

```sh
python3 tools/merge_train.py --wip
```

```text
  1  chore
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
  "78": "draft"
 }
}
```

The dry run prints what it would do, as JSON. Drop `--dry-run` to merge. Other options are in the [command reference](../reference/commands.md): `--policy` is `all` (default) or `low-risk`, and `--max-passes` defaults to 12.

Return to the [how-to guides](README.md).

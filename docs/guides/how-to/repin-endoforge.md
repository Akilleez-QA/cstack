# How to repin EndoForge

Cstack runs a fixed slice of [EndoForge](https://github.com/Akilleez-QA/endoforge) copied into `vendor/endoforge/`. This guide moves that copy to a newer EndoForge commit. Why it works this way is in [how Cstack vendors and runs EndoForge](../explanation/endoforge-vendoring.md).

Do a repin on its own branch and in its own pull request. Don't mix it with other changes.

## 1. Pick a commit on EndoForge `main`

Fetch an EndoForge clone and choose the commit. It must be reachable from the clone's `origin/main`:

```sh
git -C ../endoforge fetch origin
git -C ../endoforge log --oneline -5 origin/main
```

See what changed in the files Cstack vendors since the current pin:

```sh
OLD=$(python -B -c "import json; print(json.load(open('contracts/SOURCE-PINS.json'))['endoforge']['commit'])")
SLICE=$(python -B -c "import sys; sys.path.insert(0, 'tools'); import pin_endoforge; print(' '.join(pin_endoforge.SLICE))")
git -C ../endoforge diff --stat "$OLD" origin/main -- $SLICE
```

`SLICE` in `tools/pin_endoforge.py` is the fixed list of vendored files. An empty diff means a repin would change only the pin record, not the vendored bytes. Read EndoForge's own [interface documents](https://github.com/Akilleez-QA/endoforge/tree/main/docs/interfaces) and [changelog](https://github.com/Akilleez-QA/endoforge/blob/main/CHANGELOG.md) for anything in that diff that changes an interface Cstack uses: `IsolatePool` options and results, the `Ledger` and `FrozenEvaluators` classes, the gates and evaluator, and the ledger writer's `ENDOFORGE_LEDGER_JOURNAL` variable.

## 2. Rebuild the vendored slice

From the Cstack checkout root, with the full commit hash:

```sh
python -B tools/pin_endoforge.py --source ../endoforge --commit FULL_COMMIT
```

The tool:

- reads each file from the commit with `git show`, never from the working tree, and makes no network call;
- removes Python comment tokens and copies every other file byte for byte;
- writes `vendor/endoforge/SOURCE-MANIFEST.json` with the upstream and exported hash of each file;
- replaces `vendor/endoforge/` and updates the `endoforge` record in `contracts/SOURCE-PINS.json`: `commit`, `source_manifest_sha256`, `source_manifest_entry_count`, `on_main: true` and `main_commit`, the clone's `origin/main` at the time.

It refuses a commit that isn't reachable from `origin/main` and prints the reason. `--allow-unmerged` pins it anyway as a deliberate exception; the record then says `"on_main": false, "allow_unmerged": true`. Don't merge that to Cstack `main` without saying why in the PR.

Repinning to the commit already pinned reproduces `vendor/endoforge/` byte for byte. Only `main_commit` changes, to the clone's newer `origin/main`. That is a quick way to check your clone and the tool before a real repin.

## 3. Check the result

```sh
git diff --stat
CSTACK_ENDOFORGE_CLONE=../endoforge python -B -m unittest tests.test_endoforge_pin
```

`tests/test_endoforge_pin.py` checks the commit, manifest digest, file count and every exported file hash, checks that the record carries one of the two `on_main` forms, runs the vendored import-boundary test, and, with `CSTACK_ENDOFORGE_CLONE` set, checks that the pin is reachable from `main_commit` and from the clone's `origin/main`. CI doesn't set that variable.

Then run the forge path and every suite:

```sh
CSTACK_STUB_TRANSPORT_SCRIPT=examples/forge/saturation-stub.json python -B cli.py < examples/forge/saturation-goal.json | python -c 'import json,sys; d=json.load(sys.stdin); print(d["run_status"], [e["data"]["outcome"]["assessment"] for e in d["events"] if e["kind"]=="outcome"])'
python -B -m unittest discover -s tests
bash ci/run-local.sh python links trace
```

The forge goal must print `completed ['candidate_passed']`. It needs a `cstack.config.json` copied from `cstack.config.example.json`. The workcell tests (`tests/test_workcell_*.py`) run the real pool, gates and ledger, so a breaking change upstream shows there.

## 4. Update the records

In the same pull request:

1. Regenerate the export listing: `python -B tools/build_export_manifest.py`.
2. Update [the source-pin ICD](../../icd/icd-endoforge-pin.md): the commit, the upstream PR it came from and anything the slice gained or lost.
3. Update [the interface ICD](../../icd/icd-endoforge.md) if a boundary Cstack relies on changed.
4. Add a line under `Unreleased` in [CHANGELOG.md](../../../CHANGELOG.md).

## If the workcell runtime changed too

`adapters/workcell/` is pinned separately, in the `workcell_runtime` record. If you changed any file there to fit the new EndoForge, record the new hashes:

```sh
python -B tools/pin_workcell.py
```

Every forge run checks both pins before it starts and stops with `NotExecuted` if either differs. A pin proves the bytes are the ones reviewed. It doesn't prove they are correct, and a local writer who changes the pins too isn't caught.

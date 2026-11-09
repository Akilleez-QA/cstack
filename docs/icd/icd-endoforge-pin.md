# Endoforge source pin

| Field | Value |
|---|---|
| Document ID | CSTACK-ICD-ENDOFORGE-PIN |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

The source is Endoforge commit `ea7b8d651ce23acd100f5a5d81d6e8fda0d604a3`, on `main` (the merge of Akilleez-QA/endoforge#131). Since the previous pin, `6dffea9`, the slice gained `core/runtime/dump-list.mjs` and `tools/dump_list.py`, which `IsolatePool` and the ledger writer import for memguard dump-list registration (Akilleez-QA/endoforge#111); it lost nothing.
`vendor/endoforge/` holds the lifecycle model, its import-boundary test, the ledger and frozen evaluator, the real gates and evaluator, `IsolatePool` and its workcell, the capacity planner (`core/runtime/capacity/`, code name Mjölnir), the group-commit ledger writer its bridge runs, the dump-list registration modules both import, the guard, and the checks the gates import.
It can't run coding agents by itself; [the interface](icd-endoforge.md) says how Cstack runs it.

The manifest SHA-256 is recorded in `contracts/SOURCE-PINS.json` with the commit and file count.
`vendor/endoforge/SOURCE-MANIFEST.json` records upstream and exported file hashes.
Python comment tokens are removed during export; other source text is retained byte for byte.
The pin test checks identity and exact file membership.

Rebuild from a clone that holds the commit. The tool reads committed source, not the working tree:

```sh
python -B tools/pin_endoforge.py --source ENDOFORGE_CLONE --commit FULL_COMMIT
```

It rewrites `vendor/endoforge/` and the pin record. Review both, then run every suite.
The tool refuses a commit that isn't reachable from the clone's `origin/main`, so fetch the clone first. It reads local refs and makes no network call. The pin record says `"on_main": true` and the `origin/main` commit it was checked against as `main_commit`.
`--allow-unmerged` pins an unmerged commit as a deliberate exception; the record then says `"on_main": false, "allow_unmerged": true`.
The pin test checks that the record carries one of these forms. With `CSTACK_ENDOFORGE_CLONE` set to a fetched EndoForge clone, it also checks that an `on_main` pin is reachable from `main_commit` and from that clone's `origin/main`; CI doesn't set it. The same stripping reproduces the earlier lifecycle file's bytes, commit `4ede82329c64f3f72026dea57ac66095324ec1c4`.

The slice is the fixed list in `tools/pin_endoforge.py`. It includes all of `core/runtime/capacity/`, because the module's CLI is its interface for non-Node callers (EndoForge's [capacity ICD](https://github.com/Akilleez-QA/endoforge/blob/main/docs/interfaces/capacity-icd.md)). Since P-68, `IsolatePool`'s default size is `availableParallelism()` again and it no longer imports the planner. It excludes EndoForge's `tools/` other than `vendor/endoforge/tools/factory_quality/index.mjs`, `vendor/endoforge/tools/ledger_writer.py`, which the isolate ledger bridge imports, and `vendor/endoforge/tools/dump_list.py`, which the ledger writer imports, and it excludes the agent pool and all experiments. The pin doesn't prove the content is correct, and `main` moves on upstream; a change needs a new pin.

AssemblyScript 0.28.20 and its dependencies (binaryen, long; all Apache-2.0) are third-party npm packages, locked in `adapters/workcell-toolchain/package-lock.json`, not vendored. `adapters/workcell/compiler.mjs` checks their hashes before every run.

## Requirements addressed

CS-REQ-070 (EndoForge pin) and CS-REQ-069 (forge part pins). See the [verification matrix](../verification/verification-matrix.md) for the tests.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Earlier versions | See `git log -- docs/icd/icd-endoforge-pin.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard header and disclaimer; requirements-addressed section | docs/nasa-standard PR |

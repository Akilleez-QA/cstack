# Endoforge source pin

The source is Endoforge commit `13b434f08cc9c5f455d4bbbd31cd2d25c22bf0a4`, on the unmerged public draft branch `workcell-host-call`.
`vendor/endoforge/` holds the lifecycle model, its import-boundary test, the ledger and frozen evaluator, the real gates and evaluator, `IsolatePool` and its workcell, the guard, and the checks the gates import.
It can't run coding agents by itself; [the interface](icd-endoforge.md) says how Cstack runs it.

The manifest SHA-256 is recorded in `contracts/SOURCE-PINS.json` with the commit and file count.
`vendor/endoforge/SOURCE-MANIFEST.json` records upstream and exported file hashes.
Python comment tokens are removed during export; other source text is retained byte for byte.
The pin test checks identity and exact file membership.

Rebuild from a clone that holds the commit. The tool reads committed source, not the working tree:

```sh
python -B tools/pin_endoforge.py --source ENDOFORGE_CLONE --commit FULL_COMMIT
```

It rewrites `vendor/endoforge/` and the pin record. Review both, then run every suite. The same stripping reproduces the earlier lifecycle file's bytes, commit `4ede82329c64f3f72026dea57ac66095324ec1c4`.

The slice is the fixed list in `tools/pin_endoforge.py`. It excludes `tools/` other than `tools/factory_quality/index.mjs`, the agent pool and all experiments. The pin doesn't prove the content is correct, and the draft branch can change upstream; a change needs a new pin.

AssemblyScript 0.28.20 and its dependencies (binaryen, long; all Apache-2.0) are third-party npm packages, locked in `adapters/workcell/package-lock.json`, not vendored. `adapters/workcell/compiler.mjs` checks their hashes before every run.

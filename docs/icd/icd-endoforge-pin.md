# Endoforge source pin, slice 1

The source is Endoforge commit `4ede82329c64f3f72026dea57ac66095324ec1c4`.
The copy in `vendor/endoforge/` contains only the lifecycle model and its import-boundary test.
It cannot run coding agents and is not wired to POODO.

The manifest SHA-256 is `1cbda3d9357b44e926666287ba95dc9b5f6035148d5f3be868d8a2d361d26b10`.
`contracts/SOURCE-PINS.json` records this identity and the three-file count.
`vendor/endoforge/SOURCE-MANIFEST.json` records upstream and exported file hashes.
Python comment tokens are removed during export; other source text is retained.
The pin test checks identity and exact file membership; no runtime adapter enforces this pin yet.

Rebuild with the companion Akilleez export-tool change, using the Cstack profile:

```sh
python -B tools/open_export/export.py --manifest tools/open_export/cstack/manifest.json --source endoforge=ENDOFORGE_CLONE --out NEW_EXPORT
```

The output directory must be absent. The export reads committed source at the full pin,
not the clone's working tree. Review and copy only the vendor slice and its pin record.
The allowlist excludes all tools, including the private-domain invariant producer.
Remaining runtime, checks, cache and receipt slices require separate review.

Upstream main was resolved on 2026-11-01. The three selected paths remain
`core/__init__.py`, `core/lifecycle.py` and `tests/test_endoforge_core_boundary.py`.
The upstream `core/ledger`, `core/engine`, `core/runtime` and `TODELETE/` trees
are outside this lifecycle-only selection. No selected file required relocation
or retirement. The boundary test is exported from the same commit without local edits.

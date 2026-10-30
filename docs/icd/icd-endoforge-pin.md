# Endoforge source pin, slice 1

The source is Endoforge commit `cebd463ea9828dfd9bbf09181a631ee604eac8cf`.
The copy in `vendor/endoforge/` contains only the lifecycle model and its import-boundary test.
It cannot run coding agents and is not wired to POODO.

The manifest SHA-256 is `29fada77034402d8898190ecb419b43618f253b72746436c5af05c22535c8b23`.
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

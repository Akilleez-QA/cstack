# Reproduce the packaging-only release

The single current aggregate is:

    PYTHONDONTWRITEBYTECODE=1 python -B tools/run_snapshot_validation.py

It verifies current selected source and accepted lab pins, checks unchanged
runtime and all fifteen tool contracts, restores the exact v0.11 selected tree and
original ZIP using only donors and snapshot, independently rebuilds that ZIP with
the unchanged historical builder, runs the unchanged full v0.11 aggregate fresh,
then runs current runtime tests, packaging tests and independent integration
review in normal and optimized Python. Real Lean remains explicitly unavailable
and skipped; its tests are not silently counted as passing. Preinstalled optional
schema validation can run; no installation or network is attempted.

The delivery gate is:

    python -B tools/reproduce_snapshot_release.py --output delivery-replay.json

It builds deterministic current ZIPs, copies only the selected delivered members
into a temporary tree with no previous evidence, runs the complete current
aggregate through both normal and optimized entry modes, checks unchanged source
and byte-identical rebuild, then exercises a source-drift rejection. Only the
release ZIP contents are needed. A fresh historical replay, including its nested
historical vendor replays, is performed rather than trusting shipped results.

Both accepted lab fixes are regression-covered, including real production-budget
byte/entry overflow and JSON floating-point exponent overflow. The independent
integration reviewer supplies its own portable checks; the previously accepted
lab review is background evidence, not a substitute for integration review.

## Measured storage overhead, not a synthetic release claim

The delivery receipt contains byte measurements made from the exact final v0.12
selected bytes with the same serializer. Non-snapshot members, including current
manifest, selection, implementation and documentation, are held fixed. A common
assembly omits the snapshot payload; the actual release adds it; a counterfactual
assembly instead adds the exact regenerated full v0.11 ZIP. Those common and
counterfactual assemblies are measurement-only, not alternative valid releases.
This comparison isolates payload overhead rather than claiming metadata-adjusted
alternative-release sizes. The receipt reports all archive hashes, raw snapshot
bytes, both incremental compressed overheads, their difference, and the actual
total release growth over the original v0.11 ZIP (including new packaging
implementation, tests, review and documentation). The actual
assembly hash must equal the delivered ZIP hash.

No synthetic lab saving is reused as a measured release claim. No future linear
growth, compression ratio, speed or cross-platform promise is made. Exact final
measurements belong to generated delivery evidence outside the selected source,
so their output hash cannot create a self-referential source-manifest cycle.

Selected textual documentation/data and nested historical archives receive a
bounded privacy/portability scan. This checks explicit credential/path markers,
not every possible secret. Source code contains deliberate adversarial strings
and is reviewed separately. Generated local evidence is not shipped.

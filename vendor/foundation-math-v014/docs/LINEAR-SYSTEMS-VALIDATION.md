# v0.8 portable proof/testing validation

The one advertised aggregate command for this derivative is:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_linear_systems_validation.py
```

Run from the source root on Python 3.11+. No install, network, model or credential
is used. `jsonschema` is optional and used only if already installed; absence is
reported as unavailable, not passed. A real Lean run remains unavailable/skipped
when Lean is absent, not silently treated as formal verification.

## Source-only reproduction

Copy exactly the relative files and bytes listed in `SOURCE-MANIFEST.json`, plus
the manifest itself, into a fresh empty directory. Do NOT copy `evidence/` or any
sibling source/review tree. The aggregate verifies every manifested source,
checks the full inherited inventory and the 12 unchanged lab runtime files,
regenerates the old bridge transcript from shipped requests, and then produces
all required evidence itself. It neither rewrites the source manifest nor reads
historical evidence. The old generated evidence names in pinned inventories are
explicitly reported as unshipped and unchecked, not mistaken for missing source.

The prior v0.7 aggregate remains preserved as historical source and supplies two
small portable helper functions used by tests. It is version-specific and is not
the advertised v0.8 aggregate. Earlier README version sections document their
historical versions. Use the v0.8 command above for this tree.

`tools/freeze_linear_systems_sources.py` is a development-only source manifest
writer, not a verification or acceptance step. It excludes all generated evidence.
Running it on modified source creates a new unreviewed candidate; it cannot renew
an independent review of older bytes. The aggregate checks, not rewrites, hashes.

## Checks

The aggregate runs the complete unittest suite normally and with `-O`, including
the frozen engine regressions, 861 lab exhaustive small-system and 160 seeded
rational-system oracle tests, corruption, external input binding, strict JSON,
resource limits, CLI behavior and producer isolation. The copied system test's
one provenance test now checks pinned shipped source, not external sibling paths.

It additionally runs in both modes:

- The unchanged standalone system numeric-leaf mutation audit: 282 mutations,
  275 rejected and seven accepted genuinely valid changes; 66 altered expected
  system mutations rejected.
- A new independent integration audit: 860 exhaustive ternary systems across
  selected shapes up to 2 by 2 and 200 seeded rational systems of dimensions 0
  through 4. Recursive Laplace-minor ranks and direct products are independent of
  backend elimination and test helpers. Both Python APIs and both bridge routes
  are exercised on each system. Affine combinations, basis independence,
  annihilators and external RHS binding are checked.
- Existing matrix, polynomial-witness and original bridge audits.
- All four generations of structural schema audits when preinstalled jsonschema
  is available, including semantic rejection and no partial/promotion branches.

All eight standalone system request fixtures replay normally and with `-O`,
with identical transcripts. The new API/CLI/bridge tests check output caps after
receipt wrapping, combined-input caps, malformed JSON, error privacy, notification
silence, immutable previous tool definitions and unchanged runtime domains.
Generated reports containing source hashes are checked for stale bindings, and
document/evidence portability scans reject local private paths and secret markers.

Finite testing and independent review are distinct from formal proof. The exact
checker validates a certificate for one supplied system, not all Python behavior,
a family theorem or any actual source instance. The trusted runtime/arithmetic
and stated resource limitations remain.

## Deliberate inherited changes

The full base manifest is pinned, and every inherited shipped source is checked.
Only these base files may differ: README and provenance documentation; CLI;
bridge version, schemas and dispatcher; three bridge/discovery test files;
the portable extraction test's package copy inventory; the matrix validation
script's discovery count; the polynomial integration audit's discovery count and
its two-tool slice. The eight definitions and all preexisting math runtime files
except the explicitly extended CLI remain byte-identical. Every actual changed
path is emitted in `evidence/v08-source-preservation.json`.

External base/lab preservation is a separate coordinator/reviewer check. The
portable aggregate cannot claim to have checked unshipped trees merely from their
pinned inventories. See `evidence/v08-validation.json` for exact current counts
and manifest binding; independent review binds its own exact subject hash.

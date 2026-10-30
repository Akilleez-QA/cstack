# v0.10 portable validation

The single advertised aggregate is:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_split_bundle_validation.py
```

Its inputs are only SOURCE-MANIFEST.json and the explicitly selected files in
RELEASE-FILES.json. No historical generated evidence, sibling trees, network, installs,
models or actual research instances are needed. The aggregate authenticates and replays
the frozen v0.9 aggregate, checks the accepted split-bundle lab with its author suite,
independent exact class oracle and eight source mutation controls, runs the current full
unit suite and integration audits normally and under -O, validates schemas if the
optional preinstalled jsonschema package is available, checks source preservation and
privacy, and runs the shipped independent integration review. No dependency is installed.

The release gate is `python -B tools/reproduce_split_bundle_release.py`. It builds a
selected-only ZIP twice, verifies exact membership and fixed metadata, extracts to an
isolated directory containing no sibling checkout or historical evidence, executes the
aggregate under both ordinary and optimized isolated Python, checks identical reports,
rebuilds a byte-identical ZIP and tests source-drift rejection. Its external receipt is
not embedded in the archive whose hash it records.

Intentional inherited edits are limited to README/provenance, CLI dispatch, the bridge
version/discovery/dispatch, five test inventory or import-copy adjustments, and four
inventory checks in historical validation helpers. All twelve original tool definitions
and all inherited arithmetic/runtime source files except CLI dispatch remain byte-identical.
The accepted character and split-bundle engines and fixtures also remain byte-identical.

The negative-H¹ fixture, all-twist Euler collision and Hom-space-versus-map-rank distinction
are retained. Request binding is tested even for reordered/equivalent presentations.
Malformed, oversized, mutated, producer-corrupted and unexpected-failure controls fail
closed without acceptance. The full suite's real Lean test is explicitly skipped because
Lean is unavailable. Stub plumbing tests do not claim a real Lean theorem. Passing
software checks and conditional mathematical review do not establish geometric realization,
map rank, catalog-to-group identification or runtime goal acceptance.

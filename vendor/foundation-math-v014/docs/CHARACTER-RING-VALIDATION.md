# Portable v0.9 validation and integration-only changes

From the source root run only this advertised aggregate:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_character_ring_validation.py
```

It verifies the exact source manifest and immutable base/lab archives, checks every
inherited source against the v0.8 manifest with an explicit change allowlist, checks
the seven unchanged character package files and fourteen unchanged universal example
files, and compares all ten original bridge definitions. No source is rewritten.
Fresh reports go under evidence/, excluded from the source manifest.

The aggregate runs the full integrated unittest suite, legacy bridge/matrix/
polynomial witness/linear system audits, character schemas when jsonschema is already
installed, and all-ten-tool differential replay in normal and optimized Python.
No package is installed if optional jsonschema is absent; that check is explicitly
unavailable. Differential replay uses a freshly extracted authenticated manifest-only
v0.8 snapshot, 93 calls per mode, successful cases and malformed/missing/extra/null
controls for all ten tools, plus inherited rejection and boundary fixtures. It compares
full prior responses and all ten definitions. Initialization's version is the sole
allowed initialization difference. These are finite controls, not a formal proof of
program equivalence; byte-preserved backends provide additional preservation evidence.

The exact accepted character ZIP is retained in vendor/ and authenticated. For lab
replay only its source-manifest entries plus the three independent review programs
are extracted. Historical evidence and saved review results are NOT extracted or
used as test results. Its authored aggregate, independent 2596-check normal/optimized
review and standalone replay all run afresh. The top-level new runtime additionally
receives a static forbidden-evaluator/network scan, privacy/portability scan and
manifest recheck after all tests. Original system fixtures still replay in both modes.

The delivered archive itself is made only from SOURCE-MANIFEST.json and its entries.
It is extracted to a fresh temporary root with PYTHONPATH/PYTHONHOME removed; the
single command above is run there. The delivery report records the tested ZIP's exact
SHA-256/size and source manifest hash. No sibling tree, historical evidence, network,
installation, credential, external model, repository creation, upload or publication
is required. Independent integration review is external to the source snapshot and
binds its assessment to the final source/ZIP hashes, avoiding circular manifests.

## Every intentional inherited-source change

- README.md: adds current v0.9 commands/scope and identifies older aggregates as historical.
- docs/PROVENANCE.md: appends current immutable input pins and archive rationale.
- foundation_math/cli.py: adds only two early-routed character commands and help entries;
  historical command branches are unchanged. The early route preserves structured
  lab E_USAGE/error-stream/exit semantics rather than argparse's textual errors.
- foundation_math_bridge/__init__.py: changes only the release version.
- foundation_math_bridge/server.py: imports the explicit adapter, appends two allowlisted
  names and dispatch branches; all prior branches and transport/lifecycle rules stay unchanged.
- foundation_math_bridge/schemas.py: appends two definitions after the prior ten.
- tests/test_agent_bridge.py and tests/test_linear_algebra_bridge.py: extend expected
  discovery names/counts to twelve; old-tool semantic assertions are untouched.
- tests/test_linear_systems_integration.py: expects twelve tools and pins system tools
  at positions 8:10, rather than assuming they are the last two; old contract checks remain.
- tests/test_portable_validation.py: copies the new character dependency into its
  selected-only fixture so the inherited bridge can import its explicit adapter.
- tools/audit_linear_systems_integration.py, tools/audit_polynomial_witness_integration.py
  and tools/run_linear_algebra_validation.py: update only current discovery counts and
  descriptive count labels; existing synthetic semantic audits remain unchanged.

All other inherited source files are byte-preserved. SOURCE-MANIFEST.json is replaced
by the derivative's new inventory; the exact prior manifest is retained in docs/ and
inside its source-only ZIP. New files are the adapter, two-tool schemas, focused tests,
current aggregate/freezer, pinned-archive support, differential checker, character
schema validator, unchanged lab package/examples, input archive/manifests/review docs,
and current scope/bridge/validation documentation. The accepted producer/verifier and
all external frozen trees are not edited. Lab test writers run only in temporary copies.

## Evidence limits

A passed test, review, hash or consistency check does not prove the table identifies
the physical group. It does not supply a Lean theorem, actual geometric realization,
formal statement correspondence, unrestricted group calculus, arbitrary mathematical
problem solution/refutation, or runtime acceptance. Genuine is an arithmetic property
of nonnegative multiplicities under the fixed table assumption. All such distinctions
remain in executable receipts, tests and documentation.

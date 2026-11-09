# How-to guides

Task recipes. Run every command from the repository root.

## Run the tests

```sh
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI runs the same two commands with `uv run --no-project --python 3.12`. One test can be run alone, for example `python -B -m unittest tests.test_thermo.GoldenTests`.

## Rebuild the source manifest

After changing any file outside `.github/`:

```sh
python -B tools/build_manifest.py
```

It prints the file count and manifest SHA-256. Commit the new `SOURCE-MANIFEST.json`. `tests/test_names_and_manifest.py` fails until you do, and so does the CI manifest job. Leave no scratch files in the tree: every file enters the manifest.

## Check the requirement trace and links

```sh
python -B tools/check_trace.py
```

It prints each problem and a summary line, and exits 1 if anything is wrong. The test suite runs the same check.

## Regenerate the reference pages

After changing schemas, tool code, error codes, limits or data files:

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
```

`python -B tools/gen_docs.py --check` exits 1 if a page is stale.

## Produce a test report and version description

On a clean tree at the commit you want to record (TP-1 in the [test plan](../../verification/test-plan.md)):

```sh
uv run --no-project --python 3.12 python -B tools/gen_reports.py --label unreleased
python -B tools/build_manifest.py
```

Use the tag name as the label at a release.

## Check a claim with the invariant API

```sh
python3 -B -c '
from foundation_refrigeration.invariants import evaluate
claim = {"fluid": "NH3", "side": None, "pressure": {"value": 33.49, "unit": "psig"},
         "temperature": {"value": 20, "unit": "degF"}, "atmosphere": {"basis": "standard"}}
result = evaluate("saturation_temperature", claim)
print(result["passed"], result["reason"])
'
```

Output at the baseline commit: `False temperature differs from Foundation saturation reference`. The table gives −6.66412 degC at 33.49 psig, 0.0025 K from 20 degF (−6.66667 degC), because 33.49 psig is rounded; the allowed difference for NH3 is 0.0022 K (table error plus 0.001 K). With `"value": 33.4852` the same call prints `True claim satisfies Foundation-backed invariant`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `-32000 Initialize the bridge before using tools` | `tools/list` or `tools/call` sent before `initialize` | Send `initialize` first, once |
| `-32001 Unsupported bridge protocol` | Wrong `protocolVersion` (for example an MCP version) | Use `foundation-refrigeration-jsonrpc/1` |
| `-32700 Numbers must be finite decimal literals without exponent` | A number like `1e3` or `20.` | Write `1000` or `20.0` |
| `-32602 Invalid parameter fields` | Extra or missing fields in `params` | `tools/call` takes exactly `name` and `arguments` |
| Tool error `invalid_quantity` | A bare number, an unknown unit, a boolean, or a value beyond limits | Use `{"value": ..., "unit": ...}` with a listed unit |
| Tool error `side_required` | A blend (R404A, R410A, R507A, R448A) without `side` | Add `"side": "bubble"` or `"dew"` |
| Tool error `outside_table_range` | Temperature or pressure beyond the table | See the ranges in [reference data](../../data/reference-data.md#saturation-tables); the bridge never extrapolates |
| Tool error `unknown_fluid` | A refrigerant with no table | Supported fluids are listed in the [data dictionary](../../data/data-dictionary.md#2-data-elements) |
| `test_source_manifest_is_exact` fails | A file was added, changed or left behind | Remove scratch files, then `python -B tools/build_manifest.py` |
| `test_generated_reference_documents_are_current` fails | Schemas, code or data changed without regenerating | `python -B tools/gen_docs.py` |
| Bridge exits 2 immediately | A command-line argument was given | Start it with no arguments |

All codes are listed in the [tool catalog](../reference/tool-catalog.md#tool-error-codes).

## Recover after an error

Tool errors and JSON-RPC errors leave the session usable; send the corrected request. After an oversized frame or a final line without newline the bridge exits 2: start a new process and initialize again. The bridge keeps no state on disk, so there is nothing to back up or restore.

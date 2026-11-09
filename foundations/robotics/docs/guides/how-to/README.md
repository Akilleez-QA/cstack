# How-to guides

Run every command from the repository root. `python` means Python 3.11 or newer.

## Run the tests

```sh
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI runs both on Python 3.12 (see the [test plan](../../verification/test-plan.md)).

## Also check results against the output schemas

The tests validate every receipt against its `outputSchema` only when `jsonschema` is importable. CI does not install it. To include the check:

```sh
uv run --no-project --python 3.12 --with jsonschema python -B -m unittest discover -s tests -t .
```

## Rebuild the source manifest

Run after changing any file outside the root `.github/` tree, documentation included:

```sh
python -B tools/build_manifest.py
```

It rewrites `SOURCE-MANIFEST.json` and prints the file count, the manifest SHA-256 and the tool inventory SHA-256. A host that vendors this repository repins from that output. `python -B tools/build_manifest.py --inventory` prints the canonical catalog bytes.

## Check traceability and links

```sh
python -B tools/check_trace.py
```

It prints a JSON summary and exits 1 with one line per problem: a requirement without a matrix row, a missing test, a test that traces to nothing, an unallocated requirement or a dead link. The test suite runs it too.

## Regenerate reference pages

After changing `foundation_robotics_bridge/schemas.py`, `foundation_robotics/data/defaults.json` or `foundation_robotics/data/calibration.json`:

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
```

`python -B tools/gen_docs.py --check` exits 1 if a generated page is stale.

## Produce a test report and version description

```sh
python -B tools/gen_reports.py --label <label>
python -B tools/build_manifest.py
```

The label names the files, for example `main-<short commit>` or a release tag. Add the new files to [reports](../../verification/reports/README.md) and [releases](../../releases/README.md) indexes. With `gh` signed in, issue and pull-request counts are filled in; without it they read "not queried".

## Override a threshold

Every judged tool accepts `thresholds`, an object of up to 8 keys from that tool's own list (see the [defaults table](../../data/defaults.md)). For example, loosening the squash tolerance to 100 permille:

```json
{"frames": [{"scale_permille": [1180, 780, 1180]}], "thresholds": {"volume_error_max": 100}}
```

The verdict becomes `thresholds_met`, `result.threshold_sources` reports `{"volume_error_max": "caller"}`, and a `CHECK` Evidence entry records that the caller supplied it. An unknown key or a non-integer value refuses the call.

## Send z-up coordinates

Tools that take positions (`gait_check`, `balance_check`) accept `"up_axis": "z"` for Blender-style coordinates. The default is `"y"` (three.js style).

## Troubleshoot an error

- A JSON-RPC `error` object means the message never reached a tool. Look up the code in [ICD §4](../../icd/icd-cstack.md#4-errors-and-result-semantics).
- `isError: true` with assessment `tool_error` means the tool refused its arguments; `receipt.error` says which field and why.
- `not_scored` means at least one check could not be measured from what you sent (for example a stride with no cycle time). Supply the missing value.
- `Unsupported bridge protocol` means `protocolVersion` was not `foundation-robotics-jsonrpc/1`.
- The bridge exits with status 2 if it is given any command-line argument or an oversized line; restart it.

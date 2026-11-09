# How-to guides

Task recipes. Run every command from the repository root.

| Guide | Task |
|---|---|
| [Start a new Foundation](start-a-new-foundation.md) | Copy and rename this template, replace the placeholder tool, adapt the documentation set |

## Run the tests

```sh
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI runs the same commands with `uv run --no-project --python 3.12`.

## Rebuild the source manifest

```sh
python -B tools/build_manifest.py
```

Run it after changing any file outside `.github/`. It prints `{"files": N, "sha256": "...", "inventory_sha256": "..."}`; `--inventory` prints the canonical tool inventory instead. Commit the new `SOURCE-MANIFEST.json`. Leave no scratch files in the tree: every file enters the manifest.

## Check the trace and links

```sh
python -B tools/check_trace.py
```

## Regenerate the tool catalog

```sh
python -B tools/gen_docs.py
```

`--check` exits 1 if the catalog is stale.

## Produce a test report and version description

On a clean tree (TP-1 in the [test plan](../../verification/test-plan.md)):

```sh
uv run --no-project --python 3.12 python -B tools/gen_reports.py --label unreleased
python -B tools/build_manifest.py
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `-32000 Initialize the bridge before using tools` | `tools/call` before `initialize` | Send `initialize` first, once |
| `-32001 Unsupported bridge protocol` | Wrong `protocolVersion` | Use `foundation-template-jsonrpc/1` |
| `-32700 Only bounded integers are in this numeric profile` | A number with a fraction, an exponent, NaN or Infinity | Send integers only |
| `-32602 Invalid parameter fields` | Extra or missing fields in `params` | `tools/call` takes exactly `name` and `arguments` |
| Tool error `observation must be a string of 1 to 256 characters` | Empty, too long or not a string | Send 1 to 256 characters |
| `test_source_manifest_lists_every_file` fails | A file was added, changed or left behind | Remove scratch files, then rebuild the manifest |
| `test_generated_reference_documents_are_current` fails | Schemas or tool code changed | `python -B tools/gen_docs.py` |
| Bridge exits 2 immediately | A command-line argument was given | Start it with no arguments |

## Recover after an error

Tool errors and JSON-RPC errors leave the session usable. After an oversized or unterminated frame the bridge exits 2; start a new process. The bridge stores nothing, so there is nothing to back up.

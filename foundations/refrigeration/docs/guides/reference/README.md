# Reference

| Reference | Contents |
|---|---|
| [Tool catalog](tool-catalog.md) | Every tool, argument, type, unit and limit; tool and JSON-RPC error codes; bridge limits. Generated from the schemas |
| [Data dictionary](../../data/data-dictionary.md) | Data elements, receipt fields, files and operational limits |
| [Reference data provenance](../../data/reference-data.md) | Source, edition, units, range and digest of every embedded table. Generated from the data files |
| [Interface control document](../../icd/icd-cstack.md) | The stdio JSON-RPC protocol and the Python invariant API |
| [Requirements](../../requirements/requirements.md) | What the software shall do, with IDs |

## Commands

| Command | Purpose |
|---|---|
| `python -B -m foundation_refrigeration_bridge` | Start the bridge (no arguments accepted) |
| `python -B -m unittest discover -s tests -t .` | Run all tests (add `-O` for optimized mode) |
| `python -B tools/build_manifest.py` | Rewrite `SOURCE-MANIFEST.json`; prints `{"files": N, "sha256": "..."}` |
| `python -B tools/check_trace.py` | Check requirement trace and Markdown links; exit 1 on any problem |
| `python -B tools/gen_docs.py [--check]` | Regenerate (or check) the tool catalog and reference data pages |
| `python -B tools/gen_reports.py --label <label>` | Run the suites and write a test report and version description |
| `uvx --from CoolProp==8.0.0 python -I tools/compute_golden.py --date YYYY-MM-DD` | Regenerate the CoolProp golden points (offline, needs network to install CoolProp) |

## Bridge exit status

| Exit | Meaning |
|---|---|
| 0 | stdin closed after complete frames |
| 2 | A frame over 65 536 bytes, a final frame without newline, a broken output pipe, or any command-line argument |

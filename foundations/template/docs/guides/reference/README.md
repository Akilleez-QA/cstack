# Reference

| Reference | Contents |
|---|---|
| [Tool catalog](tool-catalog.md) | Every tool, argument and limit; tool error messages; JSON-RPC error codes. Generated from the schemas |
| [Data dictionary](../../data/data-dictionary.md) | Data elements, receipt fields, files and limits |
| [Interface control document](../../icd/icd-cstack.md) | The stdio JSON-RPC protocol |
| [Requirements](../../requirements/requirements.md) | What the software shall do, with IDs |

## Commands

| Command | Purpose |
|---|---|
| `python -B -m foundation_template_bridge` | Start the bridge (no arguments accepted) |
| `python -B -m unittest discover -s tests -t .` | Run all tests (add `-O` for optimized mode) |
| `python -B tools/build_manifest.py [--inventory]` | Rewrite `SOURCE-MANIFEST.json` and print the three pins, or print the canonical inventory |
| `python -B tools/check_trace.py` | Check requirement trace and Markdown links; exit 1 on any problem |
| `python -B tools/gen_docs.py [--check]` | Regenerate (or check) the tool catalog |
| `python -B tools/gen_reports.py --label <label>` | Run the suites and write a test report and version description |

## Bridge exit status

| Exit | Meaning |
|---|---|
| 0 | stdin closed after complete frames |
| 2 | A frame over 65 536 bytes or without a final newline, a broken output pipe, or any command-line argument |

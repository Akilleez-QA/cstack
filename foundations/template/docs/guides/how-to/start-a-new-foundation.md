# Start a new Foundation from this template

This guide turns a copy of foundation-template into a new Foundation, for example `foundation-acoustics`, with a passing test suite and a complete, traced documentation set. The documentation here follows the Cstack family documentation standard (NASA-informed, self-assessed Class E analog); every control document in `docs/` is a filled-in instance that your copy edits rather than rewrites from scratch.

Throughout, replace `acoustics` with your domain, `FACOUSTICS` with your document code and `REQ-ACU` with your requirement prefix.

## 1. Copy and rename the code

```sh
git clone https://github.com/Akilleez-QA/foundation-template foundation-acoustics
cd foundation-acoustics
rm -rf .git && git init
git mv foundation_template foundation_acoustics 2>/dev/null || mv foundation_template foundation_acoustics
git mv foundation_template_bridge foundation_acoustics_bridge 2>/dev/null || mv foundation_template_bridge foundation_acoustics_bridge
grep -rlI --exclude-dir=.git -e foundation_template -e foundation-template . \
  | xargs sed -i -e 's/foundation_template/foundation_acoustics/g' -e 's/foundation-template/foundation-acoustics/g'
```

The `sed` renames the package imports, the protocol identifier (`foundation-acoustics-jsonrpc/1`), the bridge's `serverInfo.name`, the manifest schema name in `tools/build_manifest.py`, the tool definitions and every document. It also rewrites the `foundation-template` row of the family table in `README.md`; put that row back.

The remaining template names are the document code, the requirement and gap prefixes and the placeholder tool. List them; steps 2 and 3 replace them:

```sh
grep -rnI --exclude-dir=.git -e FTEMPLATE -e REQ-TPL -e GAP-TPL -e echo_observation -e PLACEHOLDER .
```

## 2. Replace the placeholder tool

1. In `foundation_acoustics/tools.py`, replace `echo_observation` with your tools. Keep `run()`, `input_sha256()`, `BOUNDARY` and the receipt shape. Raise `ToolInputError` for bad arguments.
2. In `foundation_acoustics_bridge/schemas.py`, replace the `TOOLS` entry with closed input and output schemas for each tool.
3. Keep `foundation_acoustics_bridge/server.py` unchanged unless your domain needs a different numeric profile. If it needs decimals, follow foundation-refrigeration's bounded decimal parser and add a requirement and tests for it.
4. Put any numeric reference data in JSON files with an envelope and a provenance record, never in Python source.
5. Replace the placeholder tests in `tests/test_bridge.py` with tests of your tools; keep the input-limit tests and the manifest test.

## 3. Update the documentation set

| File | What to change |
|---|---|
| `README.md` | Purpose, Status (version and classification summary), What is inside, Limitations |
| `docs/plan/software-management-plan.md` | Re-assess the classification in §1 for your domain. Engineering or safety-relevant data keeps the Class D-analog sentence. Update §8 components and §12 risks |
| `docs/plan/compliance-matrix.md` | Change only cells that differ for your repo (for example SWE-027 if you use offline generators, SWE-211 if you reuse code) |
| `docs/requirements/requirements.md` | Change the prefix to `REQ-ACU`. Keep the general requirements (manifest, boundary, Evidence, input hash, bounded execution, input limits, handshake, inventory, numeric profile, exit status). Replace REQ-TPL-001 and REQ-TPL-012 with one requirement per domain behaviour that a test checks. List untested behaviour as gaps |
| `docs/architecture/architecture.md` | Components table (each row lists its requirement IDs), decisions, quality attributes |
| `docs/icd/icd-cstack.md` | Protocol name, numeric profile, error table |
| `docs/data/data-dictionary.md` | Tool parameters with units and ranges; a provenance row (source, edition, units, transformation, validating test) for every embedded table |
| `docs/verification/verification-matrix.md` | One row per requirement naming `tests/file.py::Class.method` |
| `docs/verification/test-plan.md` | Test levels and fixtures for your domain |
| `docs/configuration/configuration-management.md` | Configuration items, generated outputs |
| `docs/guides/explanation/limitations.md` | What your outputs are and are not; data sources and editions; use in safety or engineering decisions. Required if your Foundation carries engineering or safety-relevant data |
| `docs/guides/tutorials/first-bridge-session.md` | A real session with your tool; run it and paste the output |
| `docs/assurance/assurance-record.md` | Replace the entry with your own first baseline entry |
| `CHANGELOG.md` | Start a fresh `Unreleased` section |

In every control document reset the metadata header: Document ID (`FACOUSTICS-SRS` and so on), Version `1.0`, Date, and Baseline commit (your first commit). Start each change history with one row.

Set the tool constants:

- `tools/check_trace.py`: `PREFIX = "REQ-ACU"`.
- `tools/gen_reports.py`: `REPO`, `CODE`, `GAP` (for example `GAP-ACU`) and `BRIDGE`, and the two import lines.
- `tools/gen_docs.py`: `PACKAGE`, `BRIDGE` and the import lines (the `sed` in step 1 does this).

## 4. Generate, check and commit

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
python -B tools/check_trace.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
git add -A && git commit -m "feat: initial foundation-acoustics"
python -B tools/gen_reports.py --label unreleased
python -B tools/build_manifest.py
git add -A && git commit -m "docs(reports): generate test report and version description"
```

The copy starts with the template's generated report files, so the trace check can find them; `gen_reports.py` overwrites them with your own results.

`check_trace.py` reports every requirement without a test, every test without a requirement, every requirement missing from the SDD and every dead link. Fix them until it prints `0 problem(s)`.

## 5. Connect it to a host

A Cstack adapter pins three values printed by `python -B tools/build_manifest.py`: `files`, `sha256` and `inventory_sha256`. The adapter lives in the Cstack repository; add it there and vendor a byte-pinned copy of your repository. Repin in the same change every time a covered file changes.

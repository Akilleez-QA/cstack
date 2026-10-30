# Independent v0.13 integration review

## Finding

No blocking defect was found in the reviewed additive hypothesis-scope integration.
This is syntactic contract and packaging review, not mathematical verification,
authenticity assurance, exhaustive equivalence, or security-sandbox certification.
The reviewer changed no implementation, baseline, or accepted lab source.

## Executable evidence

`review/v013_review.py` accepts an optional positional root or `--root ROOT`,
otherwise infers its selected delivery root. It prints deterministic JSON with
`status: PASS`, uses explicit exception guards rather than Python assertions,
and is designed to run identically normally and under `python -O`.

```sh
python -B review/v013_review.py
python -O -B review/v013_review.py
```

The focused review independently constructs canonical hashes, records, predicates,
expectations, old-tool calls and a deterministic ZIP. Its coverage includes:

- All 324 ordered pairs of the 18 predicate kinds and all 81 physical-label pairs.
- Nine map, object, catalog, torsion-role, constants, inclusion and path substitutions;
  stale rule/fact pins, missing facts and bindings, explicit withdrawal, precedence,
  rejected stale nested pins, context/endpoints, and 17 malformed documents.
- Equal summaries do not identify objects or maps. Consistent unsupported authored
  assertions can match, but all truth, geometry, proof and acceptance flags remain
  literal false. No new runtime domain is registered.
- Exactly one appended read-only tool, 15 byte-equal complete old tool contracts,
  and 92 independently constructed positive/malformed prior-tool calls replayed
  against an independently restored v0.12 process and the current process.
- Raw bridge input at 65,535/65,536/65,537 bytes; stdin CLI input at 262,144/262,145
  bytes, forbidden path/code/URL/limit arguments, duplicate keys, floats, invalid
  UTF-8, depth, no-work notifications, closed backend errors, and complete-output
  withholding on overflow. Ten CLI subprocess cases run in the caller's mode.
- Draft 2020-12 schema validity, every local reference resolved without fetching,
  embedded request-schema identity, closed input/output objects, pin bounds,
  status/assessment coupling, and rejection of true, zero and null evidence flags.
- Eleven executable source mutants killed, each preceded by its unmodified positive
  control: CLI argument check, raw-input overread, output cap, geometry and runtime
  flags, dispatch argument closure, bridge raw-input cap, assessment, schema false
  flags, schema object closure, and output exact-pin reference. Mutants execute in
  detached namespaces and never alter candidate files.
- Selected manifests and independent pre-freeze pins; 401 exact historical source
  files, all 388 unchanged donor files, precisely 13 declared changed baseline
  files, and independent reconstruction of the original 5,682,102-byte v0.12 ZIP.
  Production restoration is compared byte-for-byte with this independent result.
- Accepted standalone lab ZIP/manifest and all 19 copied lab files; all old vendor
  archives, the v0.11 snapshot, runtime/acceptance implementations, snapshot engine,
  budgets and serializer remain unchanged. The recipe binds only reused donors,
  not the next manifest, avoiding a hash cycle.
- AST review finds no new file, code-evaluation, process or network surface in the
  adapter, matcher and schema module. This is not a general sandbox proof.

The focused component checks passed normally and under optimization before final
freeze. The current release aggregate owns fresh full v0.12 and accepted-lab replay,
full current runtime and packaging suites, selected-only reproduction and final
normal/-O equality. These wider gates must pass on the final selected artifact;
focused review is not a substitute for those gates.

## Exact accepted inputs

- v0.12 manifest: `dcd1c48e50f3c384b96e7eea4a442286fc669ad71dd10e0704366632e75adf9d`
- v0.12 archive: `8aeadce5e8e343794f7716c7a1fb31e8eeb953191f7e4d52448d6459d2921814`
- Standalone lab manifest: `0d7cb6249f9c94eb073d330bd8c1ae59b0440e7ce703182cc4c2ee5856c079b9`
- Standalone lab archive: `d32bf32ddf6baa1a013425d9775a2e8ddf84a8a8ceedb11615679ff21875bd79`
- Compact v0.12 recipe: `3f33b16d89722d45e4c360fade0ae446cd6c58f454534c4b6d05d9a24afa3deb`

`review/V013-REVIEW-PINS.json` binds every reviewed selected file except the
selection, report and pins receipt itself; the final source manifest binds all
three review artifacts and selection without a self-hash cycle. The reviewer also
verified the actual unchanged sibling baseline and accepted lab against all 401
and 34 selected hashes respectively, but the executable review needs neither tree.

## Remaining limits

Authored facts, provenance hashes, context descriptions, physical labels and rule
adequacy are not authenticated or proved. There is no geometric computation,
inference, weakening, automatic ledger lookup, conclusion promotion or Lean proof.
The review does not install or invoke real Lean. Finite differential testing plus
byte preservation is not a formal proof of program equivalence. Packaging assumes
trusted single-writer POSIX operation and a compatible deterministic compression
profile; no concurrent hostile-filesystem or portable-zlib guarantee is claimed.

# Independent review: validation-receipt planning lab

## Result

No correctness defect was found in the reviewed planner's stated, bounded contract.
This is a test/review result, not a formal verification or a claim about real
validation outcomes. The review targets core SHA256
`9508bc57c57fa79bf31d538df48a08549b720f6a9e83935650f80371639c3305`
and clarified contract SHA256
`da459d29801efd2b8a51dd909f99369e6b31ab920e5cabf7c43e9d3a9ad82573`.

- Independent harness: **181/181 named cases passed in normal Python and 181/181
  under `-O`**, using Python 3.12.14. No author fixtures, author hashing helpers,
  author test helpers, external packages, or mutable sibling imports are used.
- One named case exhausts all **120 permutations** of the five-record registries;
  these are not counted as 120 separate named cases.
- Independently constructed, canonicalized and hashed records are compared with an
  independently assembled complete expected report, not a saved author-generated
  answer. Both normal and optimized runs check the CLI in both execution modes.
- **17/17 independent source-guard mutations were killed in each mode.** Every kill
  is a specific semantic assertion failure after the modified planner returned a
  report successfully. Exceptions, import failures and incidental crashes do not
  count. Temporary mutated copies never replace the author's source.
- The author's original **40 tests passed in each mode** when independently run.
  The complete lab aggregate was also independently rerun from the final archive
  in normal and optimized modes; both returned identical PASS receipts.

## Final sealed archive replay

The final lab archive is 326,451 bytes with 42 files (41 selected source files plus
its source manifest), SHA256
`5edf69aab764b000aca6b24c8503e277e85abe617cbc17b61b13d74796e575b0`.
Its source-manifest SHA256 is
`87e9ebc74819e201513887908b67e8e4b717bf90702e64cab413eb442b094515`.
The independent archive script checked exact member inventory, per-file hashes and
lengths, regular-file metadata and preserved reviewer-harness bytes, then extracted
into a temporary tree and removed PYTHONPATH from the subprocess environment.
The 181 cases, 17 semantic mutants and full lab aggregate each passed normally and
under `-O` from that extraction. Rebuilding the archive yielded identical bytes.
Both complete aggregate replay receipts have SHA256
`4f60483d7d38def34cab1d732a3e22a32be9c3ddf0cbb57ca22b1dceaedb15f0`.
See `archive-portability.json` and the six `selected-only-*.json` receipts.

## What was checked

1. Exact task identities bind revision, literal argv and argument order (including
   empty positional arguments), cwd, stdin, complete declared file manifests,
   file paths/sizes/hashes, runner, environment and its description.
2. Unknown closure fields, unknown stdin/file/environment pins, prior failed or
   unknown outcomes, nonzero/unknown exit codes, unknown output hashes and withdrawn
   evidence produce their specific fresh blockers even when coherently resealed.
3. Mandatory current-runtime, new-adapter and explicit archival-full-replay roles
   remain fresh with matching evidence. Identical argv does not turn a separately
   declared full replay into a historical evidence reference. Freshness propagates.
4. Selected task and receipt pins, receipt-to-task identity, exact dependency task
   and receipt pins, and the upstream explicit selection all matter. New output
   evidence does not silently rebind dependents. Complete explicit rebinding can
   match, which still does not mean any execution occurred.
5. Diamond invalidation gives exact direct fresh dependencies and transitive fresh
   ancestor sets; an unrelated component remains unaffected. Every supplied task
   appears in the report. No selection triggers no search for a newer substitute.
6. Stable-ID task and receipt cycles, including stale edges, self-cycles and unused
   cycles, reject atomically. Dangling dependencies, dangling selection task IDs,
   unused malformed receipts, duplicate IDs/selections, and malformed exact shapes
   reject with specific errors rather than partial classifications.
7. Ordinary JSON types, booleans in semantic integer positions, floats/nonfinite
   numbers, subclasses, tuples, duplicate/escaped-duplicate JSON keys, invalid UTF-8,
   unpaired surrogates, Python input cycles, path/array order and bounds are checked.
   Literal shell metacharacters remain data. Unicode is not silently normalized.
8. Real encoded-input limits and aggregate task/receipt/file/edge limits are checked.
   Positive boundary controls include 32 tasks, 64 receipts, 512 file entries,
   128 task and 128 receipt edges, raw input bytes and raw depth. The output-size
   guard is exercised by a temporarily reduced threshold only; this is not a claim
   that a natural maximum-size report was constructed.
9. Input nonmutation, detached output pins, exact canonical encoding, registry
   permutation invariance and all eight literal-false non-claims are checked.
   Static inspection and tests agree with the core's restricted import/I/O surface.

## Finding and resolution

One documentation precision issue was found: the initial contract said paths
reject “control characters,” but the implementation rejects ASCII U+0000–U+001F
and U+007F, not Unicode C1 controls. The author clarified the ASCII scope in the
contract. The independent suite now includes a positive C1-path boundary control.
No core change was needed or made for this finding. The reviewer corrected two
initial test expectations involving a blank executable after argv reversal and
an empty nested-array depth boundary before freezing the harness.

## Immutable baseline and provenance

The v0.13 baseline was only read. Its full 460-file byte inventory is identical
before and after the review; the 454 entries in its own source manifest all match.
No files were added, removed or changed. The baseline source manifest SHA256 is
`e2d034b8703bd1c98c847962627fbfd2f86c695ecc19dab83c596873f2de7de8`.
The original v0.13 archive remains 5,979,419 bytes with SHA256
`2d3098ecc24fc34c9e0e9df740a7fae4a2e10d83f16086b8ab89c1b553113bda`.
All ten provenance entries matched the referenced source bytes and lengths; copied
references also matched their sources exactly. Detailed inventories and checks are
in `baseline-v013-before.json` and `baseline-v013-verification.json`.

No actual v0.13 historical delivery gate, current-runtime check, new-adapter check,
model, network service, installation, repository publication or proof checker was
run or changed. Lab test execution is not a fresh run of any task described in a
planner input document.

## Exact trust boundaries and non-certification

A coherently fabricated closed world can produce
`PRIOR_PINNED_EVIDENCE_MATCHES`; a positive test deliberately confirms this.
A caller can mislabel the role of an arbitrary command, or omit an actual required
task; another positive test confirms that the planner does not infer role from argv.
Reporting every supplied task is not discovery or certification of the real task set.

The review does not certify honest role assignment, complete input/dependency closure,
authenticity or existence of prior executions, environment fingerprint coverage,
real artifact bytes, whether tests were skipped, freshness, mathematical correctness,
proof acceptance, absence of later revisions, external workflow completeness,
filesystem races, or resistance to hostile Python code in the same process. Hashes
are integrity comparisons, not signatures. Observed traces do not establish closure.
No automatic latest lookup, refetch, actual gate adapter, cache, execution, skip,
promotion, release or acceptance pathway is implemented by the core. No speedup was
measured. Any real workflow adoption remains a separately authorized engineering and
validation decision, preserving explicit full archival replay and mandatory fresh
runtime/adapter checks.

## Portable reproduction

From this review directory, use an explicit standalone lab root:

```sh
python -B verify.py /path/to/lab --output normal.json
python -B -O verify.py /path/to/lab --output optimized.json
python -B mutations.py /path/to/lab --output mutations-normal.json
python -B -O mutations.py /path/to/lab --output mutations-optimized.json
python -B check_archive.py /path/to/lab.zip /path/to/review-output-directory
```

`verify.py` is standalone. `mutations.py` additionally needs the adjacent,
byte-pinned reviewer `verify.py`. Neither imports the author test suite. Reports
and inventories are external evidence to avoid recursive source-manifest hashes.
`PINS.json` binds the final review files except itself; it is not an authenticity
signature or endorsement of a real validation result.

# Independent v0.12 packaging integration review

Status: PASS for the reviewed packaging-only integration inputs. This report and
its source-pin receipt are prepared before the final release freeze. The final
selection, manifest, complete aggregate, and selected-only delivery gate must bind
and rerun the included review harness. This is not publication authorization,
origin authentication, mathematical proof, runtime promotion, or a long-chain
storage-growth claim.

## Reviewed boundary and identities

The integration retains all 380 selected v0.11 source paths. Exactly README.md and
RELEASE-FILES.json change; all other 378 inherited files, including every runtime,
mathematical, ledger, acceptance, dispatch, schema, test and historical builder
source, remain byte-identical. All fifteen complete bridge tool definitions match.
All seven historical vendor archives remain present and unchanged.

- Historical manifest: `438bc999e2a3577a4c8525a5b990a7346bd4d0dd9f1b400d596661d7a465e6a4`.
- Historical ZIP: `530d9794c083801d6d0acb6273980bdf1d4d7d59aeeb500945d0d5a11a31f741`, 5,524,169 bytes.
- Accepted corrected lab manifest: `55991f10d519cdcc1e10389f60d178bc12fa82174615a390f059047a34350a1b`.
- Accepted corrected lab ZIP: `afe15b921ac5049604d9e6255e4acf4e3f2a76eac1d30a4b694be1e078737d4b`.
- Integration recipe: `0d8a5780fbad9df5811021c3b658f57a2aa696779d4a1d256612cb821bf22ef6`.

The snapshot engine, original regression suite and original contract are exact
accepted-lab copies. All fixed limits, including the 65,536-byte receipt reserve,
remain unchanged. The recipe has no current/next manifest dependency. The current
manifest binds the recipe, donor projection, four snapshot files and integration
sources in the opposite direction, avoiding a hash cycle.

V012-REVIEW-PINS.json binds the reviewed new implementation, tests, documentation,
README, snapshot inputs and this review's harness. It intentionally does not pin
itself, this report, RELEASE-FILES.json, or the current SOURCE-MANIFEST.json. The
final release manifest binds those files after inclusion. There is no self-pin or
precomputed final-manifest identity in this report.

## Independently executed controls

The portable review harness has 76 named controls in addition to direct inventory,
source, pin, filesystem, archive and contract checks. Normal and optimized Python
produce byte-identical JSON. The pre-freeze candidate run made 5,717 explicit
checks; that count can increase when the final review documents are selected.
The harness does not invoke the author's packaging test suite as its oracle.

- A separate replay process receives only the pinned snapshot engine, 378 named
  donor files and four snapshot files. It reconstructs all 380 historical sources
  plus the raw original manifest and exact original ZIP. The donor lacks a current
  manifest, changed README, selection file and new integration sources. The
  original v0.11 ZIP and sibling source trees are not inputs.
- Instrumentation observes exactly 382 input reads, checks their descriptor-rooted
  paths, and rejects external file-open and network/process events during replay.
  No forbidden event was attempted. This is dependency-audit evidence, not an OS
  sandbox or an assertion that an audit hook secures hostile Python.
- A separately implemented ZIP assembly and the unchanged restored historical
  builder both produce the exact original ZIP. A separate current serializer,
  repeated current builder and exact member/metadata checks agree byte-for-byte.
- Wrong expected pins, same-size donor/blob drift, missing inputs, alternate-source
  fallback attempts, extra snapshot files/directories, invalid recipe fields,
  projection drift, unsupported serializer profiles and wrong archive sizes fail.
  Handled failures leave no output or staging residue.
- Symlink files/parents, hardlinks and FIFOs fail closed. Existing files, symlinks
  and empty output directories are preserved. Injected write/serialization errors
  clean staging; an unexpected serializer hash fails without repinning.
- Current release source drift, attempted refreezing of changed baseline or
  accepted-lab source, changed recipe pins, duplicate selection keys, selected
  donor/snapshot omissions, unexpected snapshot payload, and output collisions
  are rejected. All tested changes occur only in disposable copies.
- The revised integration pre-copy uses one aggregate Budget for exactly 382
  reads, exact declared-size maxima for donors/blobs, immediate hash checks and
  exact accounting against shared replay eligibility. Oversized and same-size
  changed donors/blobs are rejected before core replay. Restoration also succeeds
  without the current manifest/selection or changed current README.
- Both accepted-lab corrections have independent controls. Nonfinite values,
  including exponent overflow 1e400 and -1e400 in historical metadata, are rejected.
  Real production-limit fixtures with 43 MiB of historical source bytes and 4,804
  restored inventory entries reject during build before serialization/publication;
  the shared restore-eligibility gate rejects them too. No limits are lowered or
  raised for these fixtures.

Four private integration guard-removal variants were also killed in both modes.
They remove the shared pre-copy budget/accounting, the immediate donor hash check,
the current-manifest source-drift guard, or inherited-source preservation during
freeze. Current/review content pins were deliberately rebound only in disposable
mutant copies, so these failures exercise behavioral controls rather than merely
the source-pin receipt. These private mutants are not shipped release inputs.

The author separately reports 591 unchanged runtime tests per mode, with one
explicit unavailable-Lean skip, and 85 packaging tests per mode after pre-copy
hardening. This review does not relabel those as its independent test results.
Fresh complete unchanged historical aggregation is owned by the current aggregate
and final delivery gate, rather than redundantly executed by this focused harness.

## Actual release measurements

The harness independently assembles four ZIPs from the current selected bytes:
common non-snapshot payload, actual snapshot release, counterfactual full-baseline
payload, and snapshot-only payload. All non-snapshot members remain identical,
including manifest, selection, implementation, tests, review and documentation.
The counterfactual adds the exactly regenerated original v0.11 ZIP. Common and
counterfactual assemblies are measurement-only, not alternative valid releases.

Independent archive hashes, sizes and incremental overheads must equal the release
measurement function's results. The actual assembly hash must equal the actual
current builder's archive hash. Generated JSON reports final measured bytes,
including total release growth over v0.11; this report deliberately does not embed
pre-freeze total sizes or a final archive hash that would become self-referential.
No synthetic-lab 50,885-byte result is reused as a release measurement. There is no
future linear-growth, timing, compression-ratio or cross-platform promise.

## Privacy, filesystem and serializer limits

A bounded independent marker scan covers selected textual documentation/data,
nested historical archives and the reconstructed old README/selection whose blobs
have hash-only filenames. No credential or private path markers were found in the
reviewed text. This is not universal secret detection. New source code was also
read; deliberate adversarial path/marker strings are not treated as leaked data.
No installs, network, model calls, repository changes, Library uploads or
publication are part of this review.

The supported contract remains Linux/POSIX in a trusted single-writer workspace.
The reviewer reproduced the excluded final check-to-rename race: a concurrently
introduced empty destination directory can be replaced. The implementation is
therefore not a kernel-level concurrent no-clobber primitive. There is no
power-loss durability claim; an abrupt kill may leave private staging.

Python 3.12.14 and zlib 1.3.2 produced the recorded matching archives. Other
serializer versions/platforms are not presumed byte-compatible; original-ZIP hash
mismatch rejects the restore. Expected-pin origins remain externally trusted.
Hashes establish relative byte integrity, not authenticity, theorem truth or proof.

## Reproduction and release condition

From a selected-only delivery, run:

    python -B review/v012_review.py
    python -O -B review/v012_review.py

The JSON outputs must be identical. The optional --root argument supports reviewing
a separate read-only candidate. The harness uses temporary working copies and
verifies that the reviewed selected source bytes remain unchanged.

The current aggregate and selected-only delivery gate must pass after these three
review files are selected and the current manifest is regenerated. The harness
recomputes all inventory counts and measurements from that final selection, so
review-file inclusion cannot silently reuse the smaller provisional package's
measurements. No supported-scope blocker remains in the reviewed implementation.

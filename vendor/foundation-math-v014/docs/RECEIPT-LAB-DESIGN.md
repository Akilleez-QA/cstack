# Design lineage and non-adoption boundary

## Existing evidence read, not rerun

The design reads the complete v0.13 delivery receipt, selected source manifest,
archival delivery and current aggregate source, claim-revision contract, hypothesis
scope contract, and timing summary. Exact source pointers and SHA256 hashes are in
`reference/PROVENANCE.json`. The copied reference contracts and receipts are read-only
design material, not executable imports or runtime dependencies.

The complete delivery receipt records the original archive SHA256
`2d3098ecc24fc34c9e0e9df740a7fae4a2e10d83f16086b8ab89c1b553113bda`, 5,979,419 bytes,
normal/optimized 607 current-runtime tests with one explicit unavailable Lean skip,
and 27 packaging tests per mode. Those are historical receipt claims, not tests
rerun for this lab. The timing summary records 1,590.072 observed wall seconds.
Its observer began 615.334 seconds after launch, some earlier logs were unavailable,
and file completion offsets are not individual command durations. Repeated/nested
suite entries must not be added as disjoint runtime. This lab claims no speedup.

Inspection of the delivery source shows normal and optimized aggregate entry
points from a selected-only extraction. Each aggregate runs a fresh reconstructed
historical v0.12 full aggregate, frozen accepted-lab checks, current tests and
independent review. This explains the design motivation; it does not grant
permission to suppress any of that work or prove the chosen manifest's closure.

## Small reuse of concepts, not a second claim ledger

The claim ledger established exact `{id, revision, revision_sha256}` pins, no
latest-version rebinding, explicit dependency graphs, and downstream invalidation.
The hypothesis-scope lab established a closed schema, caller-authored assertion
boundary, literal matching and immutable false non-claim fields. This lab uses
those concepts without importing mutable sibling code or copying either engine.

Its envelope hashing is the simpler scope-style SHA256 of `{id, revision, content}`.
It deliberately is **not** claim-ledger wire-compatible: there is no separate
`content_sha256`, claim kind, event replay, revision transition machinery, theorem,
refutation status or shortest-path explanation. Schema markers prevent accidental
cross-protocol use. All planner-specific state fits a task DAG, receipt DAG, and
explicit selection map. A future integration could use exact external ledger pins
as a separately reviewed adapter; no such adapter or seventeenth tool exists here.

## Why identity includes more than a command

Command/argv alone misses selected files, stdin, cwd, runner artifacts, environment,
closure assertions and dependency evidence. A manifest alone misses ambient process
inputs. An observed dependency trace cannot exclude branches that did not run.
A prior “passed” text cannot establish which input snapshot was tested. The task
revision hash binds the entire explicit definition. Its selected receipt hash binds
an authored result/output hash and the exact dependency task/receipt pins.

A leaf's changed task or changed selected receipt invalidates all dependent tasks;
an unrelated branch remains unaffected. Policy-fresh tasks also invalidate any task
that depends on their fresh result. Cycles/dangling graph references reject instead
of trying fixed points, optimistic reuse or implicit dependency restoration.

## What adoption would still require

This experiment intentionally stops before an executor or real-gate adapter:

1. Independently establish a closed input/environment boundary for each eligible
   historical-evidence task. Do not manufacture closure from file-access traces.
2. Define and authenticate trustworthy receipt production, artifact storage,
   exact output coverage, known environment fingerprinting, and accepted result
   semantics, including treatment of unavailable/skipped tests. None exists here.
3. Retain an explicit full archival replay mode and mandatory fresh current-runtime
   and new-adapter checks. Preserve task-set completeness and honest role assignment.
4. Separately authorize/review any gate-policy change; classify evidence honestly
   rather than counting it as a fresh pass. Measure actual end-to-end savings only
   after a real, authorized implementation and equivalent validation obligations.

No repository, network/model call, publication, Library write, HM research-instance
experiment, source-copy modification, frozen gate modification or proof-acceptance
change is part of this lab.

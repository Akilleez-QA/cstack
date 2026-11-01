# Independent v0.14 integration review

## Verdict and remaining release gate

The reviewed integration passes the independent bounded checks in normal and
optimized Python, including a clean selected-only replay. One real transport
boundary defect was found, corrected by the author, and independently reproduced
as a regression test. No unresolved integration defect was found within this
review's scope. This accepts the candidate for the separately required full fresh
release and delivery gates; it does not replace those gates or claim they have
already run on the final release.

The review changes only its own script, report and pin file. All 558 reviewed
source files outside the selection metadata and this report/pin pair are bound
by V014-REVIEW-PINS.json. The final source manifest binds the complete selected
inventory, including all three reviewer files. Hashes establish byte integrity,
not provenance authenticity. Generated review receipts remain outside selection.

The normal, optimized, selected-only normal and selected-only optimized harness
runs produce identical semantic JSON. The receipt contains 10,812 explicit
checks, five privacy rejection controls, and the precise finite coverage below.
Its SHA256 is
17f83495d5eb0df39a0a8a1bcd0b20cc335c19fecfb80d7ea51aa3c7bd9c93e9.
This count includes inventory/hash assertions and must not be mistaken for
10,812 distinct mathematical test cases. The reproducible harness is
review/v014_review.py; both invocation forms are supported:

    python -B review/v014_review.py
    python -B -O review/v014_review.py --root /path/to/selected-release

The existing preinstalled jsonschema package is used for schema validation.
No package or proof-assistant installation was performed.

## Found defect and verified resolution

The original producer round-trip reservation used U+FFFF repeated 128 times as
its supposedly maximally escaped legal JSON-RPC ID. A non-BMP scalar uses two
JSON Unicode escapes under ASCII serialization, taking twelve bytes per
character rather than six. The old reservation therefore did not establish the
advertised guarantee for every legal 128-character ID.

The reviewer independently found a natural, exact counterexample, not a mocked
certificate or reduced byte budget. Use twelve trivial-character line summands
with degrees -6 through 5, each with multiplicity one, and exterior orders
[1, 2, 3, 4, 5, 6, 7, 9, 10]. The complete verification frame occupies:

- 65,463 bytes with a 128-character U+FFFF ID;
- 66,231 bytes with a 128-character U+10FFFF ID.

Before correction, the producer accepted this request, but its whole genuine
certificate could not be checked with the legal astral ID at the unchanged
65,536-byte input limit. The author changed the reservation to U+10FFFF repeated
128 times. The fixed producer rejects the entire boundary result with -32002,
without truncation, partial evidence, changed lab arithmetic, or increased caps.
The larger standalone arithmetic contract continues to permit the certificate.

The independent script retains this exact regression, a natural node-count case
below the byte limit, and three semantic source mutants: reverting the astral
reservation, omitting the entire round-trip guard, and changing the planner's
outer skip-authority flag to true. All three are detected in both modes after
the mutated operation returns normally. Import failures and incidental crashes
are not counted. Pristine counterparts pass first.

## Historical preservation and exact compact reconstruction

The v0.13 source manifest is
 e2d034b8703bd1c98c847962627fbfd2f86c695ecc19dab83c596873f2de7de8.
The compact recipe is
 e67eaa66f4f6484ca81ab1fddb313613d170bc0664e51cb315b8a39c5efc5453.
The reviewer independently reconstructs all 454 selected old sources from 440
unchanged donor files and 14 exact old-byte blobs. An independently written
fixed-profile ZIP serializer yields the exact original 5,979,419-byte archive,
SHA256
2d3098ecc24fc34c9e0e9df740a7fae4a2e10d83f16086b8ab89c1b553113bda.
Production reconstruction is compared byte-for-byte with that independent tree
and ZIP. No original sibling checkout or original archive is used as input.

The only changed old files are the fourteen explicitly declared integration,
version, selection, README and test-registration files. Every inherited history
archive, earlier compact snapshot, old gate, old reviewer file and snapshot
implementation is byte-preserved. Sixty-one inherited mathematical/runtime files
are explicitly checked unchanged, including orchestrator, domains, ledger and
proof-adapter acceptance paths. No new accepted runtime domain is introduced.

The old CLI module has an identical AST after removing exactly the two appended
routing branches. Existing bridge parser, envelope, response encoder, sequential
server, notification behavior and dispatch functions are identical ASTs. All
sixteen old tool-routing branches and the common result-envelope handling are
unchanged. Exact normal/-O subprocess comparisons against the independently
restored v0.13 tree verify all sixteen full input/output tool contracts, unchanged
initialization apart from version, and 64 finite calls per mode, including one
positive case and three malformed/extra-field cases for every old tool. This is
finite differential evidence plus source preservation, not an exhaustive proof
of program equivalence.

## Accepted labs and new capability boundary

The exterior archive is byte-preserved at
 a6c32c393e7ebc61af34ec50d1793f6905b85c4d0043847152fc22a79c59eb67,
with source-manifest SHA256
89264e3f2d6dd2391f80bf5a1d07292a3748166bef9c60d9ab9f82c3c34d078e.
It has 55 selected source files plus its manifest; 41 copied runtime, example and
contract files are independently compared with exact accepted archive members.

The receipt archive is byte-preserved at
 5edf69aab764b000aca6b24c8503e277e85abe617cbc17b61b13d74796e575b0,
with source-manifest SHA256
87e9ebc74819e201513887908b67e8e4b717bf90702e64cab413eb442b094515.
It has 41 selected source files plus its manifest; 21 copied files are checked.
The supplied independent review documents were also compared byte-for-byte with
their integration copies. The accepted lab reviews provide the deeper standalone
mathematical/planner coverage; this review does not re-label those historical
results as freshly executed integrated release gates.

Exactly three read-only contracts are appended: calculate_formal_exterior,
check_formal_exterior_certificate and plan_validation_evidence. The independent
integration checks include:

- Six independently enumerated trivial-character line-sum families, using subset
  sums for exterior coefficients, binomial ranks and graded degree checks. Empty,
  repeated, positive and negative grades, order zero and above-rank zero appear.
- Complete compact certificate round trips with five ID shapes, including safe
  negative integers, maximum-length ASCII, BMP and astral IDs.
- Independent checker-only process imports without producer/fusion imports;
  certificate arithmetic, catalog, request-hash and scope mutation rejections.
- Physical W versus Wp distinction, determinant boundary, and the supplied finite
  illustration: ordinary comparison at twist 6 is equal, exterior order 2 gives
  D-P-1, while ordinary twist 1 already gives W+Wp-S4. No all-twist claim follows.
- Closed schemas and argument objects; proof/promotion and planner nonclaim flags;
  notification nonexecution and closed unexpected bridge failures.
- Eight CLI cases in each actual mode, including all three command routes,
  malformed/extra arguments, duplicate keys, and the real 262,144/262,145-byte
  stdin boundary. Two reduced-limit controls check whole-envelope withholding;
  these are not claims of naturally maximal standalone output construction.

The fixed catalog-to-group identification and supplied formal splitting remain
assumptions. Computations establish no actual geometric object, map, injection,
existence theorem, Lean result, or runtime acceptance.

## Planner purity and full-fresh fallback

Independently authored and hashed task/receipt records are checked against six
independently assembled complete expected reports. A coherent fabricated match
is deliberately accepted as a match, while still denying execution, fresh pass,
skip authority, closure verification, artifact-byte verification, authenticity,
mathematical truth and proof-acceptance changes. Current-runtime, new-adapter and
explicit full-archival roles remain mandatory fresh. Unknown environment pins,
unestablished closure and missing explicit receipt selection block matching.
Shell metacharacters in argv remain data; no process is executed.

The planner's imports/calls are checked against a small pure/data-only surface.
No current aggregate, archival launcher or delivery reproducer consults planner
classification or provides a caller skip/profile/command surface. The actual
archival orchestration is exercised with instrumented subprocess results: the
unchanged v0.13 builder and complete old aggregate are both required. This is an
orchestration test, not an execution of the long historical gate in this review.

The immutable prior v0.13 delivery receipt contains no exact runner identity,
complete environment fingerprint or closure declaration. Its timing observation
cannot supply these missing obligations. Therefore the integrated release makes
no historical reuse or speed-equivalence claim: full fresh archival replay is
required. The corrected current suites, both accepted labs, all old history and
independent integration checks must run afresh in the final gate. Real Lean
remains explicitly unavailable, not silently passing.

The new runner is independently tested under inherited PYTHONOPTIMIZE=2 and
invalid inherited Python path/home values. Its actual child modes remain 0 and 1.
Timing observations explicitly deny closure certification and reuse authority.
The final reproducer retains per-phase generated observations in unique,
non-selected evidence directories; this does not affect selection or skip work.

## Exact immutable provenance-path exception

The accepted receipt archive contains one reviewed design-provenance member:
 vendor/validation-receipt-lab.zip!reference/PROVENANCE.json
at SHA256
92a0c8b93142259e399f8600970744e19a19784f3c707e5acda443985a493e3a.
Its ten entries contain only technical source paths, byte lengths and hashes of
old source/contracts/receipts/timing references, plus a read-only scope statement.
The content was inspected and contains no credentials, personal records or
private instance data. It remains immutable rather than being silently edited.

An independent recursive scan covers 18 nested archives and 1,890 selected text
members, permitting only that exact qualified member, exact hash and count of
ten technical path markers. Detached negative controls reject altered member
bytes, a renamed member, another path prefix, a credential marker, and an extra
unreviewed member. The production scan also reports the exception explicitly.
There is no blanket path exemption, broad scan bypass or universal secret-
detection assurance.

## Final packaging and limits

The independent serializer matches the current selected release ZIP exactly,
including all 562 members and fixed metadata. A clean selected-only extraction
passes both review entry modes with the same semantic receipt as the original
tree. Source drift is rejected and all selected hashes are rechecked at the end.
Final archive and source-manifest hashes belong in external delivery evidence,
not inside the archive that they hash.

The exact compressed identity is established for the recorded Python/zlib
serializer profile, not assumed on arbitrary serializer versions. Filesystem
support remains trusted single-writer Linux/POSIX, not a concurrent hostile-
filesystem sandbox. The review performed no network/model/provider calls,
actual HM instance computations, repository creation, publication, Lean
installation, or modification of delivered v0.13. Full fresh aggregate/delivery
completion remains a separate release obligation.

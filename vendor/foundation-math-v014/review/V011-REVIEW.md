# Independent v0.11 integration review

## Outcome and scope

PASS for the implementation and reviewer-source pins in V011-REVIEW-PINS.json.
The independent integration suite was actually executed in normal and optimized
Python. Each mode passed 116,999 explicit checks, including all cases below, and
its report matched the other mode after removing the optimization-mode field.
No outstanding integration defect was observed within this scope.

This is evidence about local, bounded dependency-applicability software. It is not
a mathematical truth judgment, theorem validation, proof acceptance, evidence
acceptance, artifact authentication or formal proof of program correctness. A
successful replay and `no_recorded_dependency_blockers` do not discharge any
mathematical obligation. All inputs used here were synthetic.

The frozen release's selected-only aggregate and deterministic archive gate are
separate executable obligations, provided by the reviewed release tooling. This
report does not substitute for that gate's fresh result or claim a final archive
hash before the release is frozen.

## Reviewed foundation

The reviewer first read the accepted lab REPORT.md and CLEAN-REPLAY.json, checked
the lab archive SHA-256
`c3805e92aa2b3259e310c126fac751f4bf34646f17f3442cfd63b44386d93fa9`,
and independently checked each lab manifest member's length and digest. The
corrected pure core is unchanged at
`c6c1f2ef00a64d514a781f281c7318612d644dc6b872690f6de7f16577552294`.
All three public lab package files remain byte-identical.

Before judging the implementation, the reviewer independently captured the frozen
v0.10 source pins, all fourteen complete tool schemas, and fourteen representative
full successful tool responses. They are retained in V011-BASELINE.json. Their
baseline source manifest is
`7626cbaadd8b8bd70d1b8ebaea4c2e638c478c63bddbb6c7ade3a2e485b3695f`.
These are reviewer snapshots, not a claim that author assertions are independent
execution evidence.

The mathematical-software oracle is the separately pinned accepted lab review's
breadth-first model. It imports no candidate implementation, fixture or helper.
This integration review explicitly reuses that independent evidence rather than
misrepresenting the adapter's call to the unchanged pure replay as independent
verification. Complete reports are compared, including pins, hashes, event IDs,
current and historical lifecycle, exact causes, shortest/lexicographic witness
paths, affected lists and never-accepted proof/truth fields.

## Fresh checks in each Python mode

- 8,688 withdrawal states: all 543 labeled four-node DAGs and all 16 withdrawal
  subsets, compared through the new adapter with the independent BFS model.
- 2,172 revision states: every labeled four-node DAG and each revised node with
  the replacement withdrawn, checking stale-edge isolation.
- 240 seeded mixed-history and 25 focused full-report adapter comparisons.
  All 265 also passed through the new bridge tool. Focused cases include historical
  objections, authored-status neutrality, explicit repinning, independent causes,
  evidence lifecycle, citation-not-dependency semantics and Unicode preservation.
- 25 record-order and output-detachment cases; 54 adversarial invalid documents
  through both adapter and bridge.
- All fourteen prior complete tool definitions and representative full successful
  responses matched the frozen baseline. Fifty-six prior arithmetic/runtime and
  related schema source files were unchanged. Four ledger-like domain names were
  rejected by the unchanged runtime acceptance registry.
- Two executable-AST comparisons removed only the explicitly appended integration
  import, route, branch, tool name and help entry, then matched frozen v0.10's
  entire CLI and bridge server ASTs. Thus the old paths and transport implementation
  were not silently rewritten to make compatibility fixtures pass.
- Three raw escaped-surrogate key/value ledger rejections, six direct structured
  type rejections, seven malformed wire rejections and twelve closed-envelope
  rejections for unsupported arguments, including paths, commands and limits.
- Exact and one-over bridge input and output payload boundaries; oversized input
  closes without draining; notifications never invoke the new backend.
- A real synthetic ledger fits the 64 KiB bridge request limit but produces more
  than 1 MiB of report data. The bridge withholds the complete result, emits a
  resource error and continues to answer a later ping. No partial evidence leaks.
- Five full independent-oracle CLI comparisons, six malformed-input rejections,
  four argument/path/option rejections, and exact/one-over 256 KiB input boundaries.
- A Unicode-heavy report is below the pure core's 4 MiB UTF-8 report budget but
  exceeds 4 MiB after ASCII JSON escaping in the CLI envelope. The CLI correctly
  withholds that whole envelope. A guarded stream also verifies its single read
  requests exactly 262,145 bytes, not an unbounded read.
- Static import/call checks and opaque-text replay with guarded file/command
  interfaces found no new arbitrary file, command, network, model or credential
  path. The CLI's intentionally bounded stdin/stdout is distinct from the pure API.
- Nine new in-memory integration source mutations were killed by explicit guard
  or semantic comparisons, not crashes: formal-proof promotion, runtime-goal
  promotion, proof-accepted promotion, asserted truth, returning input as report,
  converting rejection to success, unbounded stdin read, accepting path arguments,
  and omitting the CLI envelope cap. The accepted lab's separate seventeen
  independent core mutations are not counted as new integration mutations here.

Frame byte boundaries follow the unchanged bridge's existing convention: the JSON
payload is bounded; the one terminating LF is framing. An LF is likewise written
after the bounded CLI JSON envelope.

## Unicode scope clarification, not an unresolved regression

The first inspection found that the inherited bridge decoder accepts escaped lone
surrogates in generic JSON strings, including ping IDs. The integration author
clarified that compatibility requires preserving that transport behavior, while
retaining the corrected lab's strict Unicode rejection for ledger keys and values.
The reviewer verified both the unchanged transport and typed new-tool rejection.
This is documented in CLAIM-REVISION-BRIDGE.md. No new-tool success, UnicodeEncodeError
escape or proof promotion was observed. The integration therefore does not claim
bridge-wide Unicode hardening beyond the ledger boundary.

## Packaging and reproducibility audit

The reviewer inspected and pinned the new build, aggregate, clean-reproduction,
frozen-input support and fourteen-tool differential scripts. The selected-source
builder checks an explicit sorted unique safe-path selection, rejects generated
evidence, verifies per-file hashes, and emits fixed ZIP metadata. Frozen v0.10 and
lab inputs are authenticated by fixed archive/manifest/source pins before replay;
executable lab-review source is checked against its pinned review archive. No
sibling-tree fallback was found. The current candidate has no symlinks.

The clean gate constructs its archive from that verified selection, checks exact
membership and metadata, extracts it into a fresh directory, reruns the complete
aggregate in both interpreter modes, compares aggregate outputs, rebuilds identical
ZIP bytes, and exercises source-corruption rejection. The aggregate freshly reruns
the historical accepted suites rather than treating stored result JSON as a pass.
The reviewed integration script requires its pin file and uses only selected files.
Generated review output JSON is deliberately not required for rerunning it.

Reproduce this reviewer evidence from the selected source root with:

```sh
python -B review/v011_review.py
python -B -O review/v011_review.py
```

The current-release aggregate regenerates these results in evidence/. The review
source, baseline snapshots, mandatory source pins and this report are the portable
review deliverable. No implementation file, frozen v0.10 input or accepted lab
input was edited by this reviewer.

## Remaining limits

Exhaustive four-node graphs are not exhaustive arbitrary graphs or histories.
The reused BFS oracle assumes valid histories; validation is tested separately.
Finite tests, source identity and AST preservation do not prove arbitrary program
correctness. Schema validation is structural, not hashing, chronology, applicability
or theorem verification. Fixed budgets may reject otherwise valid larger graphs.
The static audit is not an operating-system sandbox. Hashes identify bytes, not
authorship or trust. No actual HM data, external models, network use, Lean install,
repository creation, publication or live formal proof run was performed.

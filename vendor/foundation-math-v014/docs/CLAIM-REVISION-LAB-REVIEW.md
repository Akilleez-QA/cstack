# Independent review report

## Outcome

PASS against the corrected frozen candidate ZIP
`c3805e92aa2b3259e310c126fac751f4bf34646f17f3442cfd63b44386d93fa9`.
The original candidate had a reproducible strict-input rejection defect. Its author
corrected it, clarified one lifecycle restriction, refroze the release, and the reviewer
reran from a clean manifest-only extraction. No outstanding defect was observed.

This conclusion concerns a pure, bounded, all-required dependency applicability
ledger. It is not theorem validation, a mathematical truth judgment, evidence
acceptance, artifact authentication, or permission to integrate it into v0.10.

## Closed finding: unpaired surrogate object keys escaped typed rejection

Original ZIP: `1a2ebad3b9d5467ac790217ab5dabcdc3c9eba573d8edb9abb6c9cc75dc81e12`.
Original core: `e5b0a1b88f9333158830523ae34bf46f6d778ae101c6a92ea415515f167c136b`.

An escaped unpaired Unicode surrogate in an object key passed `loads`. Passing the
result into `replay` raised an uncaught UnicodeEncodeError during canonical encoding
rather than LedgerError; the CLI consequently did not follow its documented structured
exit-2 rejection path. A direct Python dictionary with such a key had the same issue.
The initial normal-mode reproducer was:

```python
loads('{"\\ud800":1}')  # returned {'\ud800': 1}
replay({'\ud800': 1})   # raised UnicodeEncodeError, not LedgerError
```

Root cause: the pre-serialization guard checked UTF-8 encodability of values but not
object keys. The author added the missing key check. Independent direct, nested,
escaped, CLI, normal, and optimized tests now reject these inputs correctly. This was
a rejection robustness defect, not observed false proof acceptance or arbitrary code
execution. Candidate tests also cover digest/sealing helpers and valid surrogate pairs.

## Clarified restriction

The original implementation rejected a second refutation report for the same exact
claim revision, while the contract explicitly documented only repeated withdrawal
rejection. The author confirmed this is intentional bounded behavior and documented
it: at most one report and one withdrawal may coexist per exact revision. A second
report is rejected even with a different event ID or evidence. This review does not
reinterpret the API as supporting a collection of multiple objections per revision.

## Independent method

`oracle.py` does not import candidate implementation, helpers, tests, or fixtures.
It independently constructs record hashes and replays valid histories, separates
intrinsic lifecycle/stale-edge causes from traversable current-pin edges, then uses
per-start-node breadth-first reachability and shortest/lexicographic path relaxation.
The candidate instead uses dependency-first dynamic propagation. The comparison is
of complete reports: exact causes and hashes, origin/current/expected/evidence pins,
event IDs, witness paths, history, applicability, affected lists, input digest, and
never-accepted truth/proof fields. It is not merely a blocked-record count comparison.

Fresh independent results in EACH of normal and optimized Python:

- 8,688 withdrawal states: all 543 labeled four-node DAGs times all 16 withdrawal
  subsets. This is broader than the 64 subgraphs of one fixed topological order.
- 2,172 revision states: all 543 labeled DAGs, each of four nodes revised once and
  its replacement withdrawn. These check stale-edge isolation throughout the graph.
- 240 seeded 12-record histories, each with up to 32 mixed revision, withdrawal, and
  report steps, including repinning and changing dependency arrays.
- 25 focused valid cases and 25 record-order metamorphic comparisons.
- 54 adversarial invalid documents with explicit expected rejection codes.
- 12 malformed raw JSON cases, 11 structured-type cases, 5 Python subclass cases,
  a cyclic Python input, exact/over raw byte boundaries, and depth overflow.
- 2 fresh CLI full-report comparisons with distinct hash seeds and 6 structured CLI
  rejection checks, including the discovered Unicode-key regression.
- 17 independent source mutations killed by explicit semantic/guard comparisons,
  never counted merely because of an import failure, crash, or timeout.

The 25 independently generated fixture pairs are in fixtures/. They include diamond
shortest/lexicographic ties; multiple separate causes; withdrawal then revision; stale
branches not inheriting replacement causes; latest revision event attribution; full
and partial explicit repinning; historical objections; withdrawn/revised evidence;
refutation-report citations that do not add graph edges; authored-status neutrality;
non-executed text; Unicode non-normalization; and exact record/event/edge budgets.

Adversarial cases cover complete hashes and pins, unknown fields/events, invalid
revision chronology, ID/kind changes, stale replacement dependencies, duplicate IDs,
edges and transitions, stable-ID cross-revision and self cycles, typed report targets
and evidence, blank/overlong text, and actual path-budget overflow. Source controls
add dropped propagation, silent repinning, replacement-cause leakage, historical
lifecycle leakage, wrong latest event, wrong shortest/lexicographic path choice,
withdrawal/refutation conflation, boolean revision acceptance, and proof promotion.

A static import/call audit of the pure core plus a guarded text replay checked that
it contains no arbitrary file/network/model/clock/credential/subprocess interface.
The CLI's bounded stdin/stdout is intentional and distinct from the pure core.

## Reproducibility and remaining limits

CLEAN-REPLAY.json was produced by actually extracting the pinned candidate archive
and rerunning both the complete author aggregate and this independent suite. It is
not copied author evidence. The candidate extraction contained exactly its manifest
and 39 named files, with byte sizes and SHA-256 digests checked independently.
Normal and optimized independent counts agree. The author aggregate passed its
37 tests per mode, fixture replay, and 14 author mutants per mode in that extraction.

The oracle assumes valid histories; invalid-input behavior is tested separately.
Four-node withdrawal graphs are exhaustive, but arbitrary larger graphs and all
possible lifecycle sequences are not. Generated tests, source inspection, and mutation
controls are evidence, not a formal proof of implementation correctness. The schemas
are structural aids, not substitutes for runtime hashing, chronology, exact types,
aggregate budgets, or proof checking. Fixed resource limits intentionally reject
some otherwise valid graphs. Hashes establish byte identity, not authenticity.

All inputs were synthetic. No actual HM instance data, external models, network,
credentials, repository publication, or mathematical proof run was used. No author
file or frozen v0.10 file was edited by the reviewer.

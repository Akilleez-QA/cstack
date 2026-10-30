# Contract and trust boundary

## Input and identifiers

The only input is an ordinary JSON document with exact keys `schema`, `records`,
`events`. The schema marker is `foundation-math-claim-revision/1`. Unknown keys,
floats (even 1.0), Python subclasses, nonfinite numbers, duplicate JSON object keys,
unpaired Unicode surrogates and unsupported types are rejected. Strings are not
Unicode-normalized. JSON structural validity is necessary, not sufficient.

Initial record IDs are unique. Event IDs are unique in their separate namespace.
A record has an ID, positive integer revision, kind, kind-specific content,
`content_sha256`, `revision_sha256`, and an explicit dependency list. An ID retains
its kind throughout this document. There is at most one edge per target ID.

Each edge is `{id, revision, revision_sha256}`. No name-only reference, latest-version
lookup, implicit hypothesis edge or inferred natural-language dependency exists.
Every listed dependency is required. There is no alternative-proof semantics.

Records distinguish:

- claim: exact authored statement, scope, assumptions, non-claims and authored status;
- obligation: exact authored requirement and authored status;
- evidence: description, declared evidence type, external artifact hash and authored status.

These authored fields are descriptive, not checked mathematics. In particular,
`claimed_established` and `claimed_refuted` never alter derived truth or acceptance.
Opaque artifact digests do not demonstrate that artifact bytes exist or were checked.

## Hashing

Canonical encoding is Python's JSON UTF-8 encoding with sorted object keys,
`ensure_ascii=False`, compact separators, and no nonfinite values. Arrays retain
order. No Unicode normalization is applied. Exact content includes its array order.

`content_sha256 = SHA256(canonical(content))`.
`revision_sha256 = SHA256(canonical(record without revision_sha256))`.
The latter binds ID, revision, kind, all content, content hash and ordered dependency
pins. Thus even an identical statement in a new revision is a different revision.
Changing only dependency pins also changes revision integrity identity.

Hash consistency is not authenticity, trust, mathematical validity or evidence
acceptance. An adversary can author new consistent hashes. External artifact hashes
are not compared with artifact bytes. `seal_record` is a construction convenience,
not a proof checking or approval API.

## State and events

Initial references must exactly match an initial record. Initial order is irrelevant.
Events are replayed in the supplied order, which is semantically meaningful. Every
event has a unique ID, exact current target pin and nonblank reason. Invalid input
rejects the whole pure replay; no state is persisted and no partial success returned.

1. `withdraw`: marks this exact revision as no longer usable. Repeating withdrawal
   of the same revision is rejected, even under a different event ID. This does not
   say the statement is false. Withdrawing evidence may block claims depending on it.
2. `revise`: supplies a completely sealed replacement with the same ID and kind and
   revision exactly one greater. Its dependencies must be exact current pins.
   Dependents retain their old pins and become stale; they are never auto-rebound.
   A withdrawn or objected-to revision may be replaced, but the new revision is still
   not proved. Prior lifecycle events remain attached to the historical revision.
3. `record_refutation_report`: only targets a claim and cites an exact current
   evidence record declared `counterexample_report`. It records an unverified
   authored objection, not a validated counterexample. It suspends applicability
   with `refutation_reported_unchecked`, never `truth=false`. The cited evidence
   need not be available or valid. At most one such report may be recorded per
   exact claim revision; another report event for that revision is rejected as
   `duplicate_transition`, even if its event ID or evidence differs. Both one
   report and one withdrawal may coexist on the same revision. If the cited
   evidence is later withdrawn or revised, the historical
   objection remains unresolved, not silently accepted or erased. The exact cited
   pin is retained for review. This event does not add a proof-dependency edge.

There is intentionally no direct mark-accepted, accept-proof, retract-report,
reactivate-revision, delete, add-new-ID or arbitrary patch API. To close an objection,
issue an explicit new revision after the external review process. A full system must
supply its own authorized review policy before accepting any mathematical result.

At every stage the current stable-ID graph must be acyclic, including edges whose
revision pins have become stale. This conservative rule rejects even historical
cross-version cycles that might be well-founded under richer semantics. Self-edges,
including to an earlier revision of the same ID, are rejected. Induction and fixed
points require a different explicitly verified device, not an exception here.

## Derived applicability

The report concerns current records, not all historical revisions. Intrinsic blockers
are an exact revision's withdrawal or explicit unchecked refutation report. A pin
that no longer matches its target's current revision contributes
`dependency_revision_not_current`, identifying both expected and current pins and
the latest revision event for that target. The stale edge itself is sufficient;
new blockers in the target's replacement are not falsely attributed to the old pin.

When an edge still matches the current target, every target cause propagates to its
dependent. Propagation is transitive in dependency-first order. Unrelated records
have no new cause. One canonical shortest witness path is retained per root cause;
ties use lexicographic canonical JSON path bytes. This is NOT enumeration of every
possible dependency path. Each actual cause remains represented separately. A stale
cause's final path step is the expected historical dependency pin, not its new pin.

Every reason contains its code, origin exact pin, originating event ID, stable
cause hash and witness path. Lifecycle reasons retain the authored reason text;
stale reasons retain expected/current pins. `affected_obligations` and
`affected_claims` enumerate all currently blocked records of those kinds, not just
newly changed records or a fabricated completion percentage. Directly blocked
and transitively blocked evidence appears in the full record list too.

Both input record order and map iteration are normalized for deterministic reports.
Dependency array order remains part of revision identity. Event order is retained.
The input digest uses records sorted by ID, preserving all other input array order.

## Boundaries and budgets

Hard limits, not caller-controlled overrides:

- 256 KiB encoded input; JSON depth 16, 65,536 visited values;
- 64 initial records, 64 events, 256 current edges at every revision;
- 32 fields per JSON object; 4,096 entries per raw list; 8,192 characters per raw string;
- at most 2,048 characters for nonblank authored text and 32 assumption/non-claim entries;
- IDs: ASCII letter then at most 63 letters/digits/underscore/dot/hyphen;
- revisions 1..1,000,000; raw integers at most 32 bits; lowercase 64-digit hashes;
- 4,096 emitted cause entries, 32,768 path pins, 4 MiB final encoded report.

A graph inside the size limits can still exceed the output explanation budget;
that returns `budget_exceeded`, never a partial graph or a mathematical conclusion.
All runtime guards use explicit exceptions and remain active under `python -O`.
Schemas describe structural shape; hashing, exact Python/JSON types, nonblank text,
chronology, edge uniqueness, cycles, reference equality and aggregate budgets are
implemented by the authoritative pure core.

## Public API and I/O

`loads(text_or_utf8_bytes)` strictly decodes bounded input.
`replay(document)` validates, detaches and replays structured input, returning a
JSON-serializable report or raising `LedgerError(code, path, message)`.
`seal_record(body)`, `pin(record)`, `digest(value)` and `canonical_bytes(value)` are
construction/encoding helpers, not independent verification. The pure replay has
no filesystem, subprocess, network, clock, model, credentials or global state I/O.
The CLI reads one bounded stdin document and emits either a report (exit 0) or a
structured rejection (exit 2). No text is evaluated as commands or code.

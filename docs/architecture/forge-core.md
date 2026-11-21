# Forge Core

Packet F3 implements the envelope and batch ledger layer on the b0761b1 baseline.
S1 adds the launch descriptor and optional host stream scheduler on F2/F3. S2 adds host kill gates and a staged commit outbox. S3 adds the optional host profiler and mission-board ledger projection.

## GPU mapping

| GPU concept | Forge Core |
|---|---|
| Host CPU | Craig, who supplies authority and policy |
| Kernel launch | An envelope on ApprovalPort |
| Reductions and batching | LedgerPort append_batch and Merkle roots |
| Nsight | S3 profiler operating on ledger records and roots |

Future throughput of tokens at 1M/s per isolate is an assumption, not a measured
result. F3 builds the cheap-today structures: envelopes, batch roots and indexed
append/gate operations. It does not claim that throughput today.

## Envelope authority

The trusted host calls ApprovalWriter.record_envelope with an approval ID, goal
ID and revision, policy ID, explicit positive cap, nonempty scope and expiry.
Cap and item cost use integer USD minor units fixed by host policy (for example
USD micros); floats, unknown costs and absent caps cannot grant authority.
The private SQLite store uses WAL and synchronous FULL, as per-item approvals do.

ApprovalReader.consume_envelope atomically launches the envelope once, binding
it to the reader's consumer. It cannot launch again, including after a process
restart. ApprovalReader.meter requires the same goal revision, policy and scope,
a unique item ID and a known nonnegative cost. One SQLite transaction checks the
remaining cap, subtracts cost and records the item. Duplicate items roll back
both operations. An exact-cap debit exhausts the envelope; all subsequent meters,
including zero-cost ones, refuse. Oversized items refuse without spending the
remaining budget. Expiry is inclusive, matching consume's existing contract.

The original meter supports only effect=read. Money, outgoing messages and unknown
effects refuse on that method; the core's existing request-bound lookup/consume path remains
required for those actions. The trusted host supplies cost and effect metadata;
requests cannot choose their own classification. F3 exposes these primitives for
S1; it does not automatically replace any core ask with an envelope. Terminal
approvals refuse envelope operations. Old adapters remain usable by old callers.

## Batch ledger contract

append_batch accepts a nonempty sequence of (kind, data) pairs, including one pair,
and returns a lowercase SHA-256 Merkle root. Events retain their existing sequence
and hash-chain fields. Leaves hash byte 0x00 followed by canonical ASCII event JSON;
parents hash byte 0x01 followed by the two binary child hashes. An odd final child
is duplicated. Ordering matters. Memory, durable and witnessed ledgers implement
this contract. Malformed batches and retention failures acknowledge no batch.

DurableLedger writes a batch as one newline-terminated forge.batch/1 JSON frame,
containing events and root, with one file fsync for the whole batch. A newly created
file also requires a directory sync. Replay checks the root and expands the frame;
legacy individual event lines remain readable. A torn frame is quarantined whole,
so complete events inside its partial bytes are not adopted. The workcell evidence
reader also expands batch frames. This changes the durable storage format for new
batch writes; older versions cannot read those frames.

WitnessedLedger retains the signed ADR 004 node-entry format. It stages the batch
under the node lock, writes entries with one node-file sync, and uses a private
batch-pending offset journal plus directory syncs to recover an interrupted batch.
Recovery quarantines the entire uncommitted suffix. Ordinary Log clients refuse a
pending batch until recovery, preventing another writer from adopting a partial
batch. Batch acknowledgement follows durable removal of the journal. A process
killed before acknowledgement may leave a complete batch or no batch; callers must
reconcile after an ambiguous response, rather than blindly retry. This is replay
integrity, not an exactly-once transport protocol or power-loss qualification.

The new core bytes have their own poodo_core_forge_core_f3_0_4 source pin; historical
and vendor pins remain unchanged. EndoforgePort retains its four-method runtime protocol and pinned evidence schema.
Its existing conformance tests require that exact surface. Batch support belongs
on LedgerPort here; no EndoForge source, pin or product dependency changes.

## Index and verification boundary

Log maintains hash-to-entry, referenced-intent and used-intent indexes while loading
or extending verified entries. WitnessedLedger maintains stream sequence, tip and
retention totals. Warm local append and the intent gate do not traverse prior
log.entries; a missing required intent index entry refuses. File identity, size,
mtime and ctime guard reuse. A disk change by another writer causes verification
and index rebuild; startup, external changes and explicit history reads remain
linear. Checkpoint verification is separate from event indexing. No hostile
same-user filesystem or in-process mutation protection is claimed.

Acceptance lives in tests/test_forge_core.py and tests/test_witnessed_ledger.py:
100 over-cap refusals, process races, restart, independent root recomputation,
file sync count, subprocess SIGKILL during both batch formats, and traversal traps
at synthetic 10k and 100k verified-history lengths. Those traps prove index use,
not real 100k-entry disk throughput. See the [verification matrix](../verification/verification-matrix.md).

## F2 verifier-first evidence and ECC

F2 stacks on the F3 envelope and batch-ledger implementation. Every domain
interpretation now supplies verdict, evidence_hash and verify_cost explicitly.
The scoped verdict is passed for a completed, adapter-admitted observation,
failed for tool_error, and unverified for other execution statuses. This verifies
the observation contract; it does not independently establish predicate truth,
formal proof, engineering approval or goal acceptance. Forge candidate gates
remain the adapter's responsibility before it can report completed.

Evidence is exactly the outcome's raw_result, including null for absent evidence.
The hash is SHA-256 of the existing canonical JSON encoding: sorted keys, compact
separators, ASCII escapes and finite JSON numbers. Attempt IDs and timestamps
outside that payload do not affect replay; changes within the payload do.
verify_cost measures canonical evidence bytes processed, not USD or wall time.
The core recomputes both hash and cost and admits only the status-matched verdict.
This is the cstack evidence/cost contract for ECC; it adds no scheduler or pricing.

Legacy Interpretation construction remains possible with unverified, unknown hash
and unknown cost defaults. Such a result fails admission. Missing fields, invalid
types (including boolean costs), negative costs, mismatched hashes or costs, and
failed or unverified verdicts on completed results quarantine the original payload.
The core records protocol_error with null raw_result, an unverified verdict, the
hash of null and unknown verify_cost. It never silently prices failed verification
at zero. The terminal record keeps goal_closed and runtime_goal_acceptance false;
there is no result-merge or goal-acceptance operation in this packet.

The new poodo_core_forge_core_f2_0_5 entry in contracts/SOURCE-PINS.json records
the intentionally changed core bytes; historical pins and Foundation pins remain
unchanged. A source pin identifies bytes, not verification or approval.

Focused coverage is in tests/test_interpretation.py (CS-REQ-095). F3 envelopes,
batch roots and indexed-ledger behavior remain separate requirements.

## S1 launches and streams

Launch in `poodo_core/streams.py` binds a launch ID (also its F3 envelope ID),
mission ID, immutable GoalContract revision, variants-by-depth grid, integer
block/cost budget vector, policy and envelope scope, canonical hierarchical scope
locks, priority, positive mission weight, dependency event IDs and inclusive expiry.
A stream traverses variants first, then depth, with at most one outstanding block.

GoalContract acceptance criteria are now AcceptanceReference records containing
kind (test or oracle) and a bounded target ID. Free prose is refused, including
through JSON and MCP. Existing callers must migrate their criteria to explicit
references; old goal payloads and ledger contract replay containing prose require
host migration before reuse. Objective, assumptions and exclusions remain prose.
The optional StreamAdmission host API requires every reference to resolve to a
callable in its copied host registry before consuming the envelope. Unknown IDs,
noncallable entries and expired launches refuse without consuming launch authority.
Resolution establishes runnability; it does not run the tests or claim they pass.
The host owns test execution, verdict interpretation and any goal acceptance.

StreamAdmission implements the extended AdmissionPort; capacity delegates to the
existing host capacity provider. Legacy capacity-only providers still serve the
existing core admission path. Hosts explicitly construct the scheduler with a slot
limit, integer clock, callable registry, trusted block-cost function and ApprovalPort.
It is not automatically wired into CLI/MCP dispatch. Launches grant no authority
beyond their envelopes: each block is metered before it is issued, against the exact
goal revision, policy and envelope scope, with effect read. Budget cost uses the same
host integer minor units as F3, separately from F2 verification bytes. Unknown costs
refuse; over-budget blocks remain queued; no refunds are inferred after failure.

Scheduling selects the eligible mission with the least accumulated service divided
by weight, then higher priority, stream progress and launch ID to break ties. Service
is the trusted cost, with a minimum of one unit for zero-cost blocks. All streams in
a mission share this account and must use the same weight and priority. New missions
join at the minimum existing service. Under sustained contention with bounded block
costs this provides weighted service fairness; priority breaks ties without starving
lower priorities. Short runs, blocked missions and heterogeneous real runtimes carry
no wall-time fairness guarantee. Slots and leases are cooperative host contracts.

next_block issues an immutable identity-checked lease. A running block is never
revoked; the scheduler reconsiders at block boundaries. Exact, ancestor and descendant
scope paths conflict. Locks cover execution and the entire commit callback, including
when other threads call next_block. Disjoint scopes may occupy separate slots.
Dependencies require all named host events; signal or a successful commit with an
event publishes them. A failed callback stops its stream, releases its lease and
publishes no event. Commit replay and simultaneous duplicate commits refuse. Expiry
refuses new dispatch and entry to commit; a callback already entered may finish.

One scheduler must own the whole scope namespace in one process. Queues, dependency
events and fairness counters are in memory. F3 envelope consumption and debits remain
durable: restart cannot relaunch an envelope, and hosts must reconcile ambiguous
work before issuing replacement authority. Cross-process locking, restart recovery,
S2 extends these host boundaries below; profiler integration remains outside S1. No throughput claim is made.

Acceptance is in `tests/test_stream_scheduler.py` (CS-REQ-096 and CS-REQ-097).


## S2 kill hierarchy

The host owns KillHierarchy and supplies a capacity provider, integer monotonic
clock, ledger and latency bound in that clock's units. Paths are tuples ordered
mission, kernel/envelope, block, warp, isolate; the empty tuple is global. Killing
a prefix seals registration, dispatch and commit for its descendants and sets their
cancellation Events. S2 host wiring passes the same hierarchy to StreamAdmission,
CommitOutbox and optionally PoodoCore through kills=. Mission IDs must equal the
core's AOR IDs when sharing it. A core budget hard_stop seals that mission in the
shared hierarchy. Raising the core budget alone does not clear a kill.

The global brake overrides every queried mission's CapacityLimits.live_cap to zero,
including future missions, and freezes staged outbox work. Kill records replay into
a fresh hierarchy. There is no unkill API. Ledger failure leaves this process sealed;
the host must reconcile an unacknowledged kill before restarting authority.
Registrations and explicit kill prefixes are bounded at 10,000 each. Global kill
remains available at the prefix bound. Registry exhaustion refuses new work.

Latency is measured from entry through sealing and cancellation signalling, including
lock acquisition, before ledger I/O. A bound overrun raises after sealing, and the
receipt records the overrun. Deterministic tests measure one clock unit against a
two-unit bound at all six levels, plus an overrun. This establishes host gate and
signal behavior only. It does not establish OS process termination latency, ledger
fsync latency or a production wall-time bound. EndoForge must connect its F1 tree
workers to the registered cancellation tokens and qualify physical termination.
An effect admitted by its final dispatch kill gate may finish, including a handler
about to enter. Killing cannot retract an external operation already in flight. Host callbacks and kernels must obey this
boundary; in-process Python is not an adversarial isolation boundary.

## S2 staged world writes and blast radius

Before launch, the trusted ApprovalWriter attaches a single immutable commit policy
to the F3 envelope with record_commit_policy: explicit exact world-object IDs and
rolling sixty-second caps for money, messages and writes. Missing policy denies all
writes. Object IDs are exact identifiers, not hierarchical wildcard scopes. Launch
scope locks still cover execution through commit. Kernels propose JSON data only;
the host stages each item against an issued Block lease with an operation, objects,
payload, and either a compensation operation plus payload or irreversible=true.
A leaf execution_scope binds a warp/isolate item to its block's kill ancestry.
Compensation is recorded for host reconciliation; it is not automatically executed.

CommitOutbox snapshots canonical JSON at staging, bounds each item to 64 KiB and
the staged queue to 10,000 items, and refuses duplicate item IDs. Rollback discards
staged data without invoking a world handler or writing a world_commit event.
The host quote callback supplies (envelope cost, money, messages, writes) as bounded
integers. Cost must be positive; absent or malformed prices refuse. This means even
zero-money writes exhaust the finite envelope. Host handlers are the only world
writers and must restrict effects to the item's declared objects, including any
compensation. Workers receive neither handlers, approval writers nor world credentials.

ApprovalReader.meter_commit atomically checks goal revision, consumer, policy,
operation scope, expiry, remaining F3 cost, exact objects and all three rolling caps.
It reserves cost and resource usage with unique item identity in one SQLite
transaction. Concurrent processes cannot multiply the cap. Rate usage survives
reader restart; a clock reversal into retained usage refuses. F3 meter remains
read-only and does not gain a world-write fallback. Envelope cost is shared between
block scheduling and commits; it is not refunded for uncertain or failed execution.

Irreversible items additionally require ApprovalPort.lookup/consume for that item's
ID and canonical digest, exact goal revision, expected approver and inclusive expiry.
An envelope never substitutes for this approval. A refusal after consumption may
spend approval without dispatch; reconciliation requires fresh authority.

Before calling a world handler, the outbox reserves the durable gate, consumes the
item locally and acknowledges a world_commit ledger record containing its digest,
objects, compensation and resources. Ledger failure dispatches nothing. A durable
LedgerPort is required for crash-surviving evidence; MemoryLedger is a test fake.
A crash can leave a debit without a commit, or a commit without an effect/outcome.
Never blindly retry these cases. Commit IDs replay from the ledger, and durable
SQLite debits independently reject reuse. This is write-ahead authorization, not an
atomic transaction with an arbitrary external service or an exactly-once promise.

Hosts opt into S2 by supplying kills and outbox to StreamAdmission; commit then
accepts a staged item ID and refuses raw callbacks. The S1 callback API remains for
legacy hosts. CLI/MCP dispatch does not automatically adopt S2. A single host owns
scheduler leases and the outbox; SQLite gates coordinate consumers, not world locks.
The host must not expose direct outbox.commit access to workers or fabricate Block
leases. Staging is volatile, so worker death before commit loses proposals only.

Acceptance lives in tests/test_kill_outbox.py: all kill levels and leaf isolation,
restart and overrun, global freeze, 100 out-of-scope refusals, rollback, rolling caps,
parallel gate races, per-item approvals, failed ledger/handler behavior and subprocess
SIGKILL before commit and after a durable record precedes a synthetic world write.
These are local synthetic checks, not qualification of remote-world transports.


## S3 profiler, mission board and judgment export

The optional host API in `poodo_core/profiler.py` records aggregate kernel windows
with record_profile and reconstructs forge.board/1 through ForgeBoard.read.
It introduces no registered adapter, background collector, scheduler wiring or
second persistent store. LedgerPort.read supplies the snapshot. Same ledger bytes
produce the same board; no clock, randomness or external query enters projection.
Host callers must serialize aggregate writes, use globally unique kernel IDs and
supply nonoverlapping windows. Repeated windows add their counters, retaining the
latest dependency, lock, conflict and policy snapshot. Envelope identity/cap and
mission binding must remain constant for a kernel.

Each window is an F3 one-event batch. A following root receipt binds a prior aggregate
event's canonical leaf hash; projection rejects mismatches. A crash between these
two writes leaves a usable aggregate without an acknowledged root receipt. Roots
are evidence references, not goal acceptance. Existing F2 outcome hashes supply
verdicts; missing references refuse projection. Each distinct outcome counts once
per kernel, including unverified outcomes in the denominator. The projection
trusts admitted ledger verdicts and does not independently rerun domain verification.

Occupancy is busy slot-time divided by duration times slots. Divergence is divergent
branches divided by branches. Verify pass rate is passed verdicts divided by all
referenced verdicts. Cache hit rate is hits divided by lookups. Empty denominators
produce null. Burn sums trusted integer host costs in the F3 envelope's units;
burn_vs_envelope divides burn by its fixed cap. Critical path is the longest sum
of window durations through named kernel dependencies, including the current kernel.
Missing dependencies and cycles refuse projection; these durations measure recorded
work, not predicted wall time.

The Friday feed is strictly exceptions-only: each row contains mission, kernel,
and anomaly, with no source payloads or token text. Aggregate schemas reject extra
fields; unrelated ledger records are dropped. Version 1 thresholds are explicit:
burn_over_plan means accumulated burn exceeds accumulated planned burn;
verify_collapse means pass rate below 0.5; divergence_explosion means divergence
above 0.5. These are fixed level thresholds, not statistical change detection.
Scope_lock_deadlock means a cycle of host-recorded wait edges with held locks at
every participating kernel. Goal_conflict_no_policy requires a host conflict flag
and absent policy. The host owns cost quotes, timing and wait-edge accuracy.

Native start/revise goal records establish executable intent. Missing results have
confidence zero. ForgeBoard.run_acceptance resolves every AcceptanceReference in
a host-owned callable registry before running any test/oracle. Exactly True passes;
False, other values and exceptions fail. Results bind the full GoalContract revision
and ordered references. The latest revision wins. Confidence is the fraction of
acceptance references passing, a descriptive score without probabilistic calibration;
runtime_goal_acceptance remains false. Callables must themselves execute the named
acceptance checks; the board cannot establish the provenance of arbitrary host code.

The trusted host records Craig's approve, reject, edit_spec and resolve_conflict
judgments with record_decision, including mission, revision, bounded JSON context
and a nonempty reason. This API records judgments; it grants no approval authority
and must not be exposed as a worker impersonation channel. export_decisions returns
forge.honcho-decision/1 JSON-compatible rows with source event hashes, context and
reason, in ledger order. The host can serialize these rows for Honcho; no network
export or Honcho training service is invoked. Source ledger durability applies.

Focused synthetic acceptance is in `tests/test_forge_profiler.py` (CS-REQ-102).

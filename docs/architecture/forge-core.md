# Forge Core

Packet F3 implements the envelope and batch ledger layer on the b0761b1 baseline.
S1 (launch/scheduler) will stack on this branch later. S2 (kill/outbox) and S3
(profiler) are outside this packet.

## GPU mapping

| GPU concept | Forge Core |
|---|---|
| Host CPU | Craig, who supplies authority and policy |
| Kernel launch | An envelope on ApprovalPort |
| Reductions and batching | LedgerPort append_batch and Merkle roots |
| Nsight | A later profiler operating on ledger roots |

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

Only effect=read is supported by envelopes. Money, outgoing messages and unknown
effects refuse; the core's existing request-bound lookup/consume path remains
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

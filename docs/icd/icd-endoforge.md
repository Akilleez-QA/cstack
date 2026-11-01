# Cstack–Endoforge interface control document

Status: contract baseline 0.2; approval is through repository review. The protocol,
local file adapter and host-configured POODO/CLI evidence routing are **implemented**.
This document follows the repository's NASA-style interface-control structure;
it does not assert NASA compliance, qualification or independent verification.

## 1. Purpose, scope and references

This ICD controls witnessed evidence storage between POODO and an
Endoforge adapter. It specifies synchronous, in-process Python calls, not a wire
transport, agent runner, caching service or synthesis lifecycle.

Controlled sources: `poodo_core/ports.py`, `poodo_core/models.py` and
`tests/test_endoforge_port.py`, `adapters/endoforge_ledger.py` and
`tests/test_endoforge_ledger.py`, `tests/test_endoforge_routing.py`, `poodo_core/core.py`, `bootstrap.py` and `cli.py`. Related baselines are the
[requirements](../requirements/requirements.md),
[design](../architecture/architecture.md),
[verification matrix](../verification/verification-matrix.md) and
[source-pin ICD](icd-endoforge-pin.md).

## 2. Allocation and authority

POODO owns policy: goals, revisions, grants, approvals, decisions, precommitments,
execution admission and interpretation. Endoforge owns witnessed storage:
append ordering, durable receipts, chain integrity and retrieval. Storage
success neither authorizes execution nor proves a goal or domain claim.
Foundations retain domain meaning and acceptance. The trusted host selects the
ledger and session; request data cannot select storage roots or implementations.

`EndoforgePort` is separate from `LedgerPort`; this change replaces neither the
existing ledger nor its adapter. `cli.py` reports `endoforge_implemented: True`
when host configuration binds this port, otherwise `False`. The pinned lifecycle-core slice contains no
runtime wiring and establishes no compatibility with this new contract.

The current claim-gate CLI rejects `--atoms`, `--atom-refs` and `--consumer` requests with exit status 2 and a `cstack.claim-gate/0.1` JSON error on stderr stating that the approved-atoms Registry is unavailable. It emits no verdict on stdout. The pinned lifecycle slice does not provide that Registry; the dead optional import has been removed. Calls without atom options retain the ledger-only interface.

[PR #16](https://github.com/Akilleez-QA/cstack/pull/16) added a pinned lifecycle-core slice from Endoforge commit `cebd463ea9828dfd9bbf09181a631ee604eac8cf`. That slice contains data and lifecycle rules plus an import-boundary test. It has no agent runner, caching implementation or runtime wiring. Its source-pin ICD, [icd-endoforge-pin.md](icd-endoforge-pin.md), records the manifest hash. Vendoring source does not implement `EndoforgePort`.

## 3. Operations and sequencing

| Operation | Inputs | Return and obligation |
|---|---|---|
| `append_precommit` | `session_id: str`, `decision: DecisionRecord` | `str` record hash after durable witnessed append of the decision and its prospective precommitment |
| `append_outcome` | `session_id: str`, `outcome: CapabilityOutcome` | `str` record hash after durable witnessed append of the unchanged outcome |
| `verify_chain` | None; host-bound ledger | Exact `bool`: `True` only for a complete valid snapshot, including an empty ledger; `False` for detected corruption |
| `read_records` | Keyword-only `goal_id: str \| None = None`, `session_id: str \| None = None` | `tuple[Document, ...]`, detached records in append order |

A precommit must be witnessed before the associated action is dispatched. An
outcome must match an earlier precommit in the same session on request id,
decision id, goal id, revision, capability, operation and request hash. Outcome
attempt identity is preserved. Storage validates this binding without deciding
whether the action was authorized. Failed or uncertain execution is recorded
with its original certainty and evidence ceiling.

Configured cores append at decision creation and again after execution gates,
before dispatch. The second precommit includes the consumed ApprovalPort approval,
when required; a bound decline is also witnessed before refusal. These are distinct
policy snapshots, not retries. Outcomes retain their original schema and correlate
to approvals through session, decision and request identity. Pending approvals do
not dispatch. An append error latches the core against further witnessed work.

At least one read filter is required. Each supplied id is an exact match; two
filters mean intersection. Unknown ids return an empty tuple. Reads verify the
whole chain before filtering and return a consistent snapshot, never partial
results. Host calls must be serialized; the adapter must provide atomic
append and exclusive writer ownership across processes.

## 4. Data formats and identity

Session and goal identifiers follow `models.identifier`: 1–128 characters from
`[A-Za-z0-9_.:-]`. Core model versions and validation remain authoritative.
Precommit input uses `DecisionRecord`, including `CapabilityRequest` and
`Precommitment`; its `request_sha256` must equal `request.sha256`.
Outcome input uses `CapabilityOutcome` without rewriting assessment, provenance,
certainty, limitations, `formal_proof` or `runtime_goal_acceptance`.

Each returned `Document` contains exactly these JSON fields:

| Field | Format / meaning |
|---|---|
| `schema` | `poodo.endoforge-record/0.1`, or `poodo.endoforge-record/0.2` for approval-bearing precommits |
| `record_id` | 64 lowercase hexadecimal SHA-256 characters |
| `previous_id` | Previous record hash; `null` for the first record |
| `kind` | `precommit` or `outcome` |
| `session_id`, `goal_id` | Valid identifiers; goal derived from the request/outcome |
| `payload` | Object defined below |

Precommit payload has exactly `request` (`CapabilityRequest.to_dict()`),
`request_sha256`, `grant_id` (identifier), and `precommitment`
(`Precommitment.to_dict()`). Outcome payload is `CapabilityOutcome.to_dict()`.
`DecisionRecord.approval` is an optional captured Document. When present, schema
0.2 adds exactly `approval`: the complete ApprovalRecord fields (`approval_id`,
`decision_id`, `request_sha256`, `goal_id`, `goal_revision`, `approver`, `verdict`,
`not_after`). Storage validates its request binding; POODO validates authority.
Readers accept mixed 0.1/0.2 chains without rewriting old bytes or hashes. Old
readers reject 0.2; upgrade readers before enabling approval-bearing writes.
The record hash is `models.digest` of the envelope excluding `record_id`, using
bounded canonical ASCII JSON with sorted keys and finite numbers. The complete
record must satisfy `Document.capture` limits. Hashes provide content identity
and linkage, not signature authentication or proof of external execution.
Physical storage and external witnessing mechanisms remain adapter decisions;
a hash chain alone cannot detect deletion of an otherwise valid final suffix.

### Local file adapter

`EndoforgeLedger(path)` binds a trusted host-selected path in an existing directory.
It holds a nonblocking exclusive `flock` on the file until `close()` or context
manager exit; competing opens, including hard-link aliases, raise `OSError`.
The host serializes calls and must not replace, unlink or externally modify the
file while open. Deployment requires a local POSIX filesystem supporting flock,
atomic append positioning and fsync. Each canonical ASCII JSON record occupies
one newline-terminated line, submitted in one `O_APPEND` write. The file and its
parent directory are synced at open, and each append is synced before its hash
is returned. Local fsync acknowledgement is this adapter's durable witness;
there is no independent external witness or suffix-rollback protection.
Short writes and torn tails fail closed without truncation, repair or retry.
Power-loss qualification and recovery procedures remain deployment work.
The pinned vendor slice has no storage ledger or append-receipt primitive;
its qualification receipt concerns artifact evaluation, not storage acknowledgement.

## 5. Errors and fail-closed behavior

Malformed inputs, missing read filters and unmatched outcomes raise
`ContractError` before append. Unavailable storage or witnessing raises
`OSError`; corruption prevents reads/appends with `RuntimeError` and makes
`verify_chain` return `False`. No exception becomes an empty read, valid chain
or successful receipt. Verification I/O failure raises rather than returning
`True`. Append/read must validate chain integrity at the operation boundary.

An append failure may occur after persistence but before acknowledgement; callers
must retain uncertainty and reconcile by session/goal before any explicit retry.
There is no implicit retry, deduplication or exactly-once guarantee. Failed
precommit prevents dispatch; failed outcome persistence prevents treating the
operation as durably evidenced. The core enforces these integration obligations;
failed outcome persistence withholds normal completion and leaves the attempt consumed.
No success receipt precedes durable
witness acknowledgement.

## 6. Verification, configuration and open work

CS-REQ-020 through CS-REQ-023 allocate the port contract; CS-REQ-024 through
CS-REQ-026 allocate the local file adapter; CS-REQ-027 through CS-REQ-030
allocate configured routing. The in-memory fake exercises
method signatures, payload preservation, correlation, filters and tamper
rejection. Adapter tests reuse conformance assertions and exercise reopen,
cross-process exclusion, corruption, short writes and acknowledgement failures.
Runtime Protocol checks only detect member presence.

`tests/test_endoforge_routing.py` supplies runtime evidence for ordering, storage
failures, outcomes, approval verdicts, chain reopen and trusted CLI configuration.
Bootstrap reads repository-local `cstack.config.json`; the example's `endoforge.path`
resolves relative to that config file. The parent directory must already exist.
It creates a fresh host session id and closes storage at run exit, including errors.
Missing config/section preserves the unconfigured driver; malformed or inaccessible
configured storage never falls back. Request JSON cannot select the port, path or session.
Other hosts must explicitly inject the port and session; AOR composition is unchanged.

Change signatures, envelope version, requirements and matrix together through
repository review. Incompatible payload/hash changes require a new schema
version and migration rules; silently reinterpreting stored records is forbidden.
Independent witnessing, deployment durability qualification and recovery remain
open acceptance work. Evidence routing does not implement an Endoforge agent runner or cache.

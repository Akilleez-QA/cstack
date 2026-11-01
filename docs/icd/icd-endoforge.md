# Cstack–Endoforge interface control document

Status: contract baseline 0.1; approval is through repository review. The Python
protocol is specified; the adapter and runtime seam remain **unimplemented**.
This document follows the repository's NASA-style interface-control structure;
it does not assert NASA compliance, qualification or independent verification.

## 1. Purpose, scope and references

This ICD controls witnessed evidence storage between POODO and a future
Endoforge adapter. It specifies synchronous, in-process Python calls, not a wire
transport, agent runner, caching service or synthesis lifecycle.

Controlled sources: `poodo_core/ports.py`, `poodo_core/models.py` and
`tests/test_endoforge_port.py`. Related baselines are the
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
existing ledger nor its adapter. `cli.py` still reports
`endoforge_implemented: False`. The pinned lifecycle-core slice contains no
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

At least one read filter is required. Each supplied id is an exact match; two
filters mean intersection. Unknown ids return an empty tuple. Reads verify the
whole chain before filtering and return a consistent snapshot, never partial
results. Host calls must be serialized; the future adapter must provide atomic
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
| `schema` | Literal `poodo.endoforge-record/0.1` |
| `record_id` | 64 lowercase hexadecimal SHA-256 characters |
| `previous_id` | Previous record hash; `null` for the first record |
| `kind` | `precommit` or `outcome` |
| `session_id`, `goal_id` | Valid identifiers; goal derived from the request/outcome |
| `payload` | Object defined below |

Precommit payload has exactly `request` (`CapabilityRequest.to_dict()`),
`request_sha256`, `grant_id` (identifier), and `precommitment`
(`Precommitment.to_dict()`). Outcome payload is `CapabilityOutcome.to_dict()`.
The record hash is `models.digest` of the envelope excluding `record_id`, using
bounded canonical ASCII JSON with sorted keys and finite numbers. The complete
record must satisfy `Document.capture` limits. Hashes provide content identity
and linkage, not signature authentication or proof of external execution.
Physical storage and external witnessing mechanisms remain adapter decisions;
a hash chain alone cannot detect deletion of an otherwise valid final suffix.

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
operation as durably evidenced. These are future integration obligations,
not behavior supplied by the Protocol. No success receipt precedes durable
witness acknowledgement.

## 6. Verification, configuration and open work

CS-REQ-020 through CS-REQ-023 allocate this contract. The in-memory fake exercises
method signatures, payload preservation, correlation, filters and tamper
rejection. It supplies no persistence, external witness, concurrency or crash
recovery evidence. Runtime Protocol checks only detect member presence.

Change signatures, envelope version, requirements and matrix together through
repository review. Incompatible payload/hash changes require a new schema
version and migration rules; silently reinterpreting stored records is forbidden.
Adapter implementation, durable-witness qualification, storage failures,
concurrent access, recovery and POODO dispatch gating remain open acceptance
work for a later PR. The seam must remain reported as unimplemented until that
work supplies evidence.

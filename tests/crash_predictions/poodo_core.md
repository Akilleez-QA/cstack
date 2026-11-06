# Crash predictions: POODO core decide and execute

Written and committed before the test first ran. Test: `tests/test_core_crash.py`.
Method: a child runs a real `PoodoCore` subclass over a real `WitnessedLedger` and SIGKILLs itself inside the capability,
before or after the effect. A new process builds a new core on the same log, the way `bootstrap.make_core` does, and
drives the same request. A second variant uses a plain JSONL `LedgerPort`. A process kill keeps the page cache, so this
does not test power loss.

| Window | Prediction on unfixed code | Falsified by | A failure means |
|---|---|---|---|
| `action` recorded, killed before the effect | stranded: no outcome is ever written, and all core memory is gone | an `outcome` record after restart | an attempt stays open for good |
| effect done, killed before the `outcome` | stranded and silently retried: the same `decision_id` and `request_id` are accepted again, effects = 2, and `attempt-1` is reused | a refusal, or a new attempt id | the Infinity class, in the retry direction |
| same, with `enforce=True` | the ADR 004 gate does not stop it, because the new precommit makes a new intent, and `_intents` is lost so the outcome is a `note` with no `ref` | a gate denial, or a `result` entry on the old intent | the witnessed gate protects one intent, not one request |
| `outcome` recorded, killed before settlement | budget `spent` and grant uses return to zero after restart: fail open | restored counters | a restart clears spend limits |
| empty ledger | no event is appended and nothing changes | any event | the fix would break fresh cores |

The `runtime_watch.py` read model lists an attempt with no outcome as unsettled. That is a read-side report, so it is not
counted as recovery here.

Required behaviour after the fix: building a core on a ledger with an open `action` appends an `outcome` with
`execution_status=indeterminate` and `execution_certainty=unknown`, keeps the whole cost hold, and lists it in
`unresolved_attempts()`. Used request and decision ids stay used. Attempt numbers continue. Budget spend and grant uses are
restored. A ledger that cannot be read refuses construction. Goals are not restored: the host starts a new goal.

## Added after independent review

Test: `tests/test_core_recovery_accounting.py`. Each row was written as a failing test first.

| Window | Measured on the earlier fix | Required now |
|---|---|---|
| a new AOR session over a used ledger, `max_calls=1` | refused: the fixed grant id counted every earlier session's calls, so a bot stopped after 64 lifetime calls | an action counts against a grant only when its goal is in that grant's `goal_ids`; each session's pool is new, and a restart with the same goals keeps its count |
| `outcome` recorded, killed before `budget_settled`, normal path | `spent: 0` after restart: fail open | settled on the recorded outcome, exactly once |
| same, in the recovery path | `spent: 0` after restart: fail open | whole hold charged, exactly once |
| `budget_settled` recorded, stopped before `budget_paused` | not paused after restart | pause recorded on restart, exactly once |

## Added after the second independent review

Test: `tests/test_core_unresolved.py`. Written and committed before the fix.

Finding: `unresolved_attempts()` lists only what this boot recorded. The ledger still holds the unknown, so the list is
empty after a second restart or after a kill during recovery. Spend is unaffected and stays one settlement.

The fix reads the list from the ledger on every call, so it adds no write and no new state. The remaining kill points are
the ones recovery already has. Each one is tested below by a real SIGKILL, then three new cores.

| Kill point | Prediction on the unfixed code | Required |
|---|---|---|
| plain second restart | `()` | the attempt is still listed |
| during recovery, before the unknown `outcome` | listed on the next boot, `()` on the one after | listed on every boot |
| during recovery, after the unknown `outcome`, before settlement | `()` | listed, one outcome, one settlement, whole hold charged |
| during recovery, before `budget_settled` | `()` | same |
| during recovery, after `budget_settled` | `()` | same |
| two open attempts, killed after the first unknown | only the second listed | both listed, in ledger order, two settlements |
| unknown from an adapter failure, killed before settlement | `()`, and never listed in the core that recorded it | listed, one settlement |

A reset of the list needs a host resolve record, which does not exist yet. Until then an attempt stays listed for the life
of the ledger.

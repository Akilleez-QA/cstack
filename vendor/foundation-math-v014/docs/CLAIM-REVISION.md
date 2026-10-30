# Claim-revision integration contract

This layer adds dependency applicability accounting, not an arithmetic domain or
proof system. `claim_revision/` is copied byte-for-byte from the independently
reviewed corrected lab. The authoritative core contract is
CLAIM-REVISION-LAB-CONTRACT.md. The schema is
`schemas/claim-revision/ledger.schema.json`; the old `schemas/claim-ledger.schema.json`
and `tools/validate_claim_ledger.py` remain distinct, unchanged legacy interfaces.
No automatic conversion or compatibility claim is made between the two formats.

## Python and CLI

`foundation_math.claim_ledger.replay_claim_ledger(document)` wraps the pure replay
report in a receipt. Success carries `status: success`, `result`,
`scope: bounded_dependency_applicability`, `schema_version: 1`, and explicit
`formal_proof: false`, `runtime_goal_acceptance: false`, `proof_accepted: false`,
`truth_assessment: not_assessed`. Success is operation completion only.

On a `LedgerError`, the receipt carries `status: error` and
`error: {code, path, message}`, with the same negative acceptance flags and no
partial result. No state is persisted, caller input is not modified, and repeated
calls are detached. The inner report is exactly the accepted lab output.

`python -B -m foundation_math claim-ledger-replay` accepts one JSON document on
stdin, reads at most 262,145 bytes to enforce the 262,144-byte input cap, and emits
one JSON receipt. Exit 0 means replay completed; exit 2 means rejected or failed
I/O. Extra options and file arguments produce structured errors. The full ASCII
JSON CLI output, including receipt wrapper, is limited to 4 MiB; oversized results
are withheld, not truncated. Broken output pipes return exit 2. The unchanged
standalone `python -B -m claim_revision` remains available with its original direct
report contract. Neither CLI is an independent verifier of the replay algorithm.

## Semantics and limits

All edges are required. No hidden hypotheses, OR-proof alternatives, induction
cycles, automatic repair, implicit acceptance or automatic repinning exist. Pins
bind ID, positive strict-integer revision and complete revision digest. New
revisions must increment by exactly one and explicitly supply current dependency
pins. Dependents retaining a previous pin become stale. Stale edges do not inherit
blockers belonging only to replacement revisions.

Withdrawals block the exact revision without declaring its statement false.
Refutation reports are explicit, unverified authored objections that block
applicability; they do not prove a counterexample or false theorem. One report and
one withdrawal may coexist per exact revision; duplicate transitions are rejected.
Authored `claimed_established` and `claimed_refuted` statuses never alter truth or
proof acceptance. Evidence hashes are opaque identifiers; bytes are not fetched.

The core enforces 64 records, 64 events, 256 current edges, exact types and hashes,
acyclic stable-ID dependency graphs, fixed JSON budgets, 4,096 cause entries and
32,768 explanation path pins. Input record ordering is normalized; dependency and
event order retains meaning. Strings are not Unicode-normalized, and unpaired
surrogate keys or values receive typed rejections. Resource rejection is not a
negative mathematical verdict.

The runtime verifier registry, calculators, orchestration and prior backends remain
unchanged. A clean graph only reports `no_recorded_dependency_blockers`; it is not
a certificate of truth, a verified proof or accepted evidence.

# Offline work queue examples

Run from the repository root with Python 3.11 or newer:

```sh
python -m foundation_math demo
python -m foundation_math run examples/workflow/rational_addition.json
python -m foundation_math run examples/workflow/rejected_proposal.json
python -m foundation_math lean-status
```

The rejected proposal intentionally returns exit code 1. Invalid input returns 2.
A verified exact result returns 0 even when optional formalization is blocked;
check `goal_status`, `proof_status`, and individual task statuses separately.

To persist a new, never-overwritten report:

```sh
python -m foundation_math demo --output /tmp/foundation-math-run.json
python -m foundation_math check-receipts /tmp/foundation-math-run.json
```

The queue supports proposer, calculator, verifier, critic, and formalizer roles.
Dependencies must name earlier tasks. An exclusive, expiring lease identifies
an owner, token, and attempt; retries and total attempts are bounded. State is
in-memory and thread-safe, not persistent or distributed. Exported evidence is
append-only within the runtime, immutable per receipt, and hash-chained. A chain
checks accidental alteration, not authenticity: anyone can recompute hashes.

The example provider returns a structured candidate, not an authoritative answer.
The calculator dispatches bounded scalar Z/Q or formal Q-polynomial operations. The verifier
recomputes the structured goal and rejects mismatched expectations. It reuses the
calculator implementation, so this is not independent verification and does not
establish general theorems or prove the prose goal/assumptions. The critic records
these scope limits. Formalization remains explicitly `not_run`; no untrusted
Lean, Python, shell, or task commands are executed by the queue.

To add a model later, implement `ProposalProvider.propose(problem, task, evidence)`
and call `Runtime.from_dict(workflow).run(provider)`. Return only `request`,
`expected`, and optional text `rationale`. The request must equal `goal_request`.
Keep API keys outside workflow files. A provider is trusted Python integration
code and must enforce its own network timeouts; the seed neither invokes live
models nor provisions credentials. Do not trust unreviewed provider plugins.

## Explicit domain and evidence examples

[DOMAIN-RUNTIME.md](../../docs/DOMAIN-RUNTIME.md) explains the full contract.

| File | Exit | Meaning |
| --- | --- | --- |
| `polynomial_distributivity.json` | 0 | Exact identity accepted in Q[x,y] |
| `polynomial_false_identity.json` | 1 | Successful operation, false identity rejected |
| `polynomial_formal_requirement.json` | 1 | Exact identity passes; formal requirement blocks acceptance |
| `polynomial_rejected_cancellation.json` | 2 | Division/cancellation AST unsupported |
| `polynomial_rejected_quotient.json` | 2 | Quotient relations unsupported |
| `polynomial_tampered_ring.json` | 1 | Proposal ordered ring does not match goal |
| `scalar_formal_requirement.json` | 1 | Exact scalar result cannot satisfy formal proof |

Run each with `python -m foundation_math run examples/workflow/<filename>`.
The evidence requirement is explicit in these examples; omission defaults to
exact computation for backward compatibility. `proof_status` stays
`not_formally_verified`, and informal correspondence is not checked.

# Claim-ledger validator

This Python 3.10+ standard-library tool checks evidence bookkeeping for
mathematical research. It is **not a theorem prover, proof certificate, reviewer
authentication service, or proof-status upgrade mechanism**.

From the repository root:

```sh
python tools/validate_claim_ledger.py examples/toy-ledger.json
python examples/artifacts/check_triangular.py
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

The scripts and checks do not rely on Python `assert`; optimized mode does not
disable validation. No third-party packages, network calls, citations, model
credentials, or external proof assistants are needed for this toy example.
The repository's calculator and Lean adapter are separate tools, not silently
invoked by this validator.

## Data contract

`schemas/claim-ledger.schema.json` describes the JSON shape. The Python validator
also checks graph relationships, status/evidence requirements, and local artifact
bytes. JSON Schema by itself cannot enforce all those relationships. Unknown
fields are rejected to catch misspellings. Duplicate JSON keys are rejected by
the CLI rather than silently choosing one value.

Each claim records:

- A stable `id` and precise `statement`. IDs should remain stable as the claim is
  tracked; the tool cannot compare revision history or judge statement precision.
- An explicit `assumptions` array, including `[]` when none are declared.
- `dependencies`, an acyclic list of other claim IDs in the same ledger.
- A `status`, a separate `closure`, pinned `evidence`, and `verification`.
- `verification.scope`: what was checked and what was not.
- `verification.reviewers`: explicit reviewer identities/roles, or `[]` when no
  human review is asserted. Reviewed/refuted claims require at least one entry.
- `verification.trust`: declared trusted foundations, tools, axioms, or limits.
  Formally checked claims require at least one explicit entry, not an omission.

Status names describe different dispositions, **not an ordered truth scale**:

| Status | Bookkeeping requirement and meaning |
| --- | --- |
| `conjecture` | Open proposal; no proof is implied. Must remain open. |
| `proof_draft` | Argument awaiting adequate review/checking. Must remain open. |
| `reviewed_conditional` | Pinned proof artifact plus a named reviewer and scope; remains conditional on declared assumptions and review quality. Tests or source references alone do not qualify. |
| `formally_checked` | Pinned formal-check artifact plus checker name/version, encoded statement, explicit assumptions/trust, and recorded `pass`. Validates declarations, not the checker run or semantic correspondence. |
| `refuted` | Pinned counterexample or refutation proof and named reviewer/scope. A refuted claim cannot support a closed downstream conclusion. |

`closure: "closed"` is a **workflow/dependency assertion**, not unconditional
mathematical truth. It is allowed for reviewed, formally checked, or refuted
claims only. Every dependency of a closed claim must itself be closed and have
status `reviewed_conditional` or `formally_checked`. A refutation may be closed as
a settled disposition, but is not a supporting theorem. A formal or reviewed
claim can remain open while other obligations are unresolved.

Explicit assumptions do not disappear when a claim closes. The tool does not
prove that dependency assumptions have been propagated or discharged. Keep
unsettled premises visible; do not relabel conjectures as facts to make a ledger
pass. Cycles and missing dependencies are rejected even for open drafts.

## Evidence pins and formal-check records

Every evidence record has `kind`, `description`, and
`artifact: {"path": "artifacts/proof.txt", "sha256": "<64 lowercase hex digits>"}`.
Kinds are `proof`, `test`, `formal_check`, `counterexample`, and `source`.

Paths are relative to the **ledger file's directory**, not the working
directory. Use portable slash-separated paths; absolute paths, parent/dot
components, backslashes, colons, and symlink escapes are rejected. Files must be
inside the ledger directory. The validator reads bytes but never executes
artifacts or commands. A content hash pins a version; it is not a signature,
provenance guarantee, or protection against someone editing both file and ledger.

To compute a pin with the standard library:

```sh
python -c "import hashlib,pathlib; p=pathlib.Path('examples/artifacts/triangular-proof.md'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

A `formal_check` record additionally requires:

- `checker: {"name": "...", "version": "..."}`;
- `encoded_statement`: the checked proposition or its unambiguous identifier;
- `assumptions`: explicitly listed, even if empty, and matching the claim's list;
- `trust`: a nonempty list describing the trusted computing/logical base;
- `result: "pass"`.

Pin a durable checker receipt containing the checked source digest, environment,
checker output, and replay instructions, rather than merely an unversioned source
link. A receipt can itself reference additional pinned artifacts. This validator
does not recursively inspect receipt contents. A missing checker, timeout,
simulated test, failed run, or unchecked `sorry` is not formal verification.
Formal verification is only as meaningful as the statement encoded, assumptions,
axioms, checker, and trust boundary. No field implies unconditioned truth.

## Interface and results

```python
from pathlib import Path
from tools.validate_claim_ledger import validate_ledger

issues = validate_ledger(data, base_dir=Path("examples"))
for issue in issues:
    print(issue.code, issue.location, issue.message)
```

The API returns a list of `Issue` objects. Empty means the bookkeeping contract
passed; it never means the mathematical claims are proved. The CLI returns:

- `0`: bookkeeping passes;
- `1`: ledger/evidence validation issues;
- `2`: unreadable/invalid JSON input or invalid command-line usage.

`--structure-only` (API: `verify_artifacts=False`) skips reading and hashing
evidence bytes. Its success message explicitly marks this weaker result. Do not
use it as an evidence-integrity gate.

The toy ledger deliberately remains `proof_draft`: supplying an induction
argument and running finite tests does not manufacture independent review. Its
test uses exact integer arithmetic for 1001 cases. Files in `examples/invalid/`
deliberately demonstrate missing dependencies, cyclic dependencies, duplicate
IDs, unsupported closure, and absent formal-check evidence. They should fail.

## Limits

The validator cannot establish mathematical correctness, completeness of
assumptions, applicability of a citation, reviewer competence, checker honesty,
agreement between prose and formal statements, or integrity against an attacker
who can rewrite the ledger and artifacts together. It is designed for trusted
local research inputs, not hostile multi-user filesystem isolation. Freeze and
review the same files before using a validation result; concurrent changes are
outside this small tool's guarantee. It does not supply actual HM coefficients or certify a six-square construction.

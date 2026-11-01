# Closed planning contract and trust boundary

## Scope and caller obligations

This pure computation compares **caller-authored JSON**, not live files or actual
execution. The caller supplies the entire task set, honest task roles, complete
input boundaries, runner/environment fingerprints, prior execution claims, and
exact selections. Completeness and honesty are not proved. A coherently fabricated
closed world can match; a positive test explicitly demonstrates that limitation.

An observed file-access trace never proves closure. Missing unobserved inputs,
conditional imports, dynamically selected files, ambient environment variables,
locale, working directory state, interpreter or library changes, tools, OS/kernel,
hardware behavior, permissions, network, random state, and clocks can matter.
Hashes of these are opaque declarations, not measurements made by this planner.
The environment's actual coverage and how its fingerprint was produced must be
established externally. If closure or a required pin is unknown, use `unknown` or
`null`; matching is blocked. No fallback to a name, installed version, mutable path,
“latest” registry entry, or an observed trace is performed.

Task-set completeness and policy-role assignment are also external obligations.
The planner cannot discover an omitted required archival check or interpret arbitrary
argv semantics. Changing an explicit fresh-replay task into a differently named
historical-evidence task, or omitting it, does not discharge the original obligation.
The report is not a completeness certificate or workflow authorization. In particular,
no report changes v0.13's frozen historical, current-runtime, or new-adapter gates.

## Root and exact identities

Input has exactly `schema`, `tasks`, `receipts`, `selections`.
`schema` is `foundation-math-validation-receipt-plan/1`.
All fields are required; unknown fields reject. `null` is permitted only where
explicitly described below. No extension keys or arbitrary expression evaluator.

Tasks and receipts each have a separate ID namespace. Each record has exactly:

- `id`: ASCII letter followed by at most 63 ASCII letters, digits, `_`, `.`, `-`;
- `revision`: ordinary integer from 1 through 1,000,000;
- `content`: the closed kind-specific object below;
- `revision_sha256`: SHA256 of canonical `{id, revision, content}`.

A pin has exactly `{id, revision, revision_sha256}`. ID equality alone never suffices.
Each registry supplies one current snapshot per stable ID, not a global history.
A higher revision is not accepted in place of a selected lower revision. Global
latestness, historical continuity and the absence of a later revision are not
established. Two records with the same ID in one registry reject.

Canonical JSON uses Python JSON encoding: UTF-8, sorted object keys, compact
separators, `ensure_ascii=False`, no nonfinite values, no Unicode normalization.
Arrays retain order. This is a named encoding profile, not a claim to implement an
external canonicalization standard. Integrity hashes are not signatures or trust.

## Task content

A task's content has exactly:

1. `role`: `historical_component`, `archival_full_replay`, `current_runtime`, or
   `new_adapter`. All but the first are mandatory fresh, irrespective of receipts.
2. `invocation`: exactly `{argv, cwd, stdin_sha256}`. `argv` is a nonempty array of
   literal argument strings, never shell-evaluated. Argument order and even empty
   positional arguments are bound. The first argument must be nonblank. `cwd` is
   `.` or a normalized relative POSIX path in the caller-declared execution root.
   `stdin_sha256` is the exact stdin-byte digest, including an explicitly empty
   stdin, or `null` if unknown. The planner does not compute it from real stdin.
3. `inputs`: the **entire selected file manifest**, a lexically path-sorted array of
   unique `{path, bytes, sha256}` entries. Paths are normalized relative POSIX paths;
   absolute paths, empty components, dot/dot-dot components, backslashes and ASCII
   control characters (U+0000..001F and U+007F) reject. Sizes are nonnegative 32-bit integers. `sha256` is a digest
   or `null` if unknown. Empty manifest is an explicit declaration of no file inputs,
   not inferred absence. Adding/removing/renaming files or changing sizes is material.
   This is caller-described regular-file content, not filesystem traversal or
   symlink/race validation. No glob expansion or file reads occur.
4. `environment`: exactly `{runner_sha256, environment_sha256, description}`.
   Both hashes are explicit exact identities or `null`. Runner identifies the
   interpreter/tool artifact; environment identifies the full externally defined
   process/runtime environment, not just a Python version. Description is bounded,
   nonblank context and is itself bound. The root location, environment variables,
   imported libraries, platform and any relevant process state belong in that
   externally established environment definition. No automatic fingerprinting.
5. `closure`: exactly the following six fields. Eligibility requires every value
   shown; each also accepts `unknown`, which blocks matching:
   - `declaration`: `caller_declares_complete`;
   - `files`: `exact_selected_manifest`;
   - `process_state`: `pinned_environment_and_stdin`;
   - `external_state`, `randomness`, `clock`: `none`.
   These are authored assertions, not generated claims from observation. A task
   requiring live external state, randomness or time is outside this reuse model.
6. `dependencies`: lexically ID-sorted unique exact task pins. Every listed
   dependency is required. There are no alternatives, optional branches, inferred
   dependencies or implicit rebinding. Missing keys are malformed; unknown fields
   do not silently become safe defaults.

A task's revision hash transitively binds every one of those declared values.
There is no separate potentially inconsistent command cache key.

## Prior receipt content and explicit selection

Receipt content has exactly `{task, availability, result, dependency_receipts}`:

- `task`: exact pin of the task definition the prior execution claims to cover;
- `availability`: caller-authored `supplied` or `withdrawn`;
- `result`: exactly `{outcome, exit_code, output_sha256}`. `outcome` is
  `declared_pass`, `declared_fail`, or `unknown`. Exit code is an ordinary integer
  -255..255 or `null`; output hash is a lowercase digest or `null`. Matching requires
  `declared_pass`, zero exit code and a known hash. Output hash should identify the
  externally specified complete result/output artifact bytes. The artifact's
  existence, bytes, authenticity, actual run, freshness, timing and semantics are
  not checked. A digest does not prove a complete test pass or that no tests skipped.
- `dependency_receipts`: lexically task-ID-sorted unique `{task, receipt}` pairs,
  each containing exact pins. This binds the precise upstream task and evidence
  used by the claimed prior run, rather than just its current implementation.

`selections` contains at most one `{task, receipt}` pair per task. The selected task
must be present by ID; its pin may be stale and then matching is blocked. A selected
receipt may be absent, stale, withdrawn, or unsuccessful: matching is blocked.
No selection means `MUST_RUN_FRESH`, even if an apparently good receipt is present.
Unselected records are never searched for substitutes; they are still validated.

The selected receipt must refer to the exact current task. Its dependency task set
must equal that task's declared dependency set; all task pins must agree; each receipt
pin must equal its supplied registry entry and the explicit selection for that
upstream task; and that upstream receipt must itself name the right task. Every
upstream task must also receive `PRIOR_PINNED_EVIDENCE_MATCHES`. New evidence or a
changed output hash invalidates dependents until explicitly rebound and resealed.
A newly selected consistent prior receipt can match; that is not a new execution.

## Graph invalidation and deterministic reports

Task stable-ID graphs and receipt stable-ID graphs are both required to be acyclic,
including stale edges and unused records. Self-cycles and dangling dependency IDs
reject the whole document. Receipt task references must name supplied task IDs.
A missing top-level selected receipt is a blocker, not a graph dependency edge, so
it yields a fresh classification rather than a malformed-graph rejection.

Every task is processed in dependency-first order. A mismatched dependency task pin
blocks its dependent. A fresh dependency blocks its dependent transitively, including
policy-driven freshness. Reports provide direct `fresh_dependencies` and the complete
set of fresh ancestors on the supplied **current stable-ID graph**. This is not a
historical causal claim about old revisions or shortest-path reconstruction. Unlike
the claim ledger, this lab does not implement events, revision histories, refutations,
withdrawal transitions, shortest witness paths, or mathematical claim status.

Every direct reason is reported in a fixed phase/order with exactly
`{code, subject, expected, supplied}`. Expected and supplied are nullable exact pins.
Reason phases are policy, closure, input pins, environment pins, dependency task
mismatches, dependency freshness, selection/receipt checks, and receipt-dependency
checks. The report preserves selected and supplied receipt pins, never silently
replaces them. `selected_manifest_sha256` hashes the declared full manifest.

Task, receipt and selection registry order is normalized for `input_sha256`;
reports are task-ID-sorted. This gives byte-identical reports under registry
permutations. Manifest/dependency array order is required to be canonical, argv
order remains material. Input is detached and never mutated. Malformed input
returns no partial classifications.

All reports set these to literal false: `execution_performed`, `fresh_pass_claimed`,
`skip_authorized`, `closure_verified`, `artifact_bytes_verified`,
`authenticity_verified`, `mathematical_truth_checked`, `proof_acceptance_changed`.
There is no execute, skip, promote, release, or proof-accept API.

## Budgets and API

- Encoded input at most 262,144 bytes; encoded report at most 524,288 UTF-8 bytes.
- 1..32 tasks, 0..64 receipts, 0..32 selections.
- At most 128 task edges and 128 receipt edges; at most 32 outgoing edges per record.
- At most 256 files per task and 512 file entries across the complete task set.
- At most 32 argv entries; each at most 1,024 characters, no NUL.
- Paths at most 512 characters; nonblank environment description at most 1,024.
- Raw JSON depth at most 16 (root zero), at most 32,768 values, 16 object fields,
  512 array entries, 2,048 characters per string, 64 per key, signed 32-bit integers.
- Strict built-in JSON types only: no floats (including 1.0), duplicate JSON keys,
  nonfinite numbers, tuples, subclasses, cyclic Python input, unpaired surrogates.
  Semantic integers never accept booleans. Guards remain active under `python -O`.

`plan(document)` returns a JSON-compatible report or raises
`PlanError(code, path, message)`. `loads(text_or_utf8_bytes)` strictly decodes bounded
JSON. `seal(body)`, `pin(record)`, `digest(value)` and `canonical_bytes(value)` are
construction/encoding conveniences, not approvals or independent proof checkers.
`seal` validates the record envelope; full semantic validation belongs to `plan`.
The core imports only `hashlib`, `json`, `re`; it has no filesystem, subprocess,
network, clock, model, credential or persistent-state I/O. The stdin CLI returns 0
for a valid classification report (including fresh blockers), 2 for rejection;
exit 0 does **not** mean validations passed. It never runs argv from the input.

The JSON Schema is only structural documentation. Ordinary Python types, hash
integrity, normalized paths, nonblank text, sorted unique arrays, reference equality,
graphs, aggregate budgets and policy are enforced by the core. This is a bounded
pure operation, not a hardened sandbox against hostile Python code or concurrent
mutation by other threads in the same process.

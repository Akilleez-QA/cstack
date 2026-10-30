# Validation design and reproducibility

The authoritative aggregate is `python -B tools/validate.py`. Its JSON output is
fresh evidence for that exact source tree. It runs the complete unittest suite in
normal and optimized Python modes, reconstructs every fixture and golden byte for
byte, then actually executes each named source mutant in both modes. Tests use
`unittest` assertion methods, not optimization-removable language assertions.

Controls include exact current pins, content and complete revision hashes, stale
references, explicit downstream repair, duplicate IDs/keys/edges, strict integer
revisions (rejecting bool), UTF-8 checks for nested/escaped object keys and values, self-edges and revision-introduced cycles, typed
refutation reports, negative and positive budget boundaries, no input mutation,
CLI rejection, no authored-status proof promotion, event chronology, deterministic
cross-process/hash-seed replay, and preserved independent branches.

The generated-DAG oracle uses a separate reverse-edge reachability traversal over
100 seeded graphs plus all 1,024 combinations of four-node ordered DAGs and
withdrawal subsets in each mode. It independently predicts withdrawal impact sets,
then compares with the core's dependency-first reason propagation. This does not
validate any mathematical assumption or external evidence.

Eight synthetic document/golden pairs cover faulty-argument withdrawal, a changed
revision, explicit repair of every dependent pin, an unchecked refutation report,
an authored “established” status that confers no proof, diamond-path ties, historical
objection retention, and stale-edge isolation from new replacement blockers. An
additional rejection fixture introduces a cycle across a stale stable-ID edge. Goldens alone are not
independent tests: explicit assertions and the reachability oracle supply separate
expectations.

`tools/run_mutations.py` copies source/tests/fixtures to temporary directories and
changes one production source guard or behavior at a time. Each run must be killed
by an actual assertion failure in a named targeted test. Syntax errors, import
errors, timeouts and crashes do not count as successful mutation controls. The
mutants cover hashing, exact pins, cycles, duplicate IDs, withdrawal, propagation,
stale-pin rebinding, authored proof promotion, bool revisions, invented alternatives,
withdrawal/refutation conflation, Unicode key validation and record budgets.

`RELEASE-FILES.json` is the explicit source allowlist. `tools/freeze_manifest.py`
refreshes its hashes during development; validation never refreshes them.
`tools/package.py` verifies and packages only the manifest plus its named files,
with fixed timestamps and permissions and no compression nondeterminism.
`tools/reproduce.py` verifies exact ZIP membership, size bounds and hashes, extracts
safely to a fresh directory and reruns the aggregate. No sibling tree, stored test
report, installation, network or model call is required. Archive checks protect
integrity and bounded packaging, not authenticity or permission to execute untrusted
code. Only run a source archive you already trust to execute.

The root coordinator will arrange an independent review before any integration.
Passing these local controls does not substitute for that review.

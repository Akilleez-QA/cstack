# Foundation Math

*Math is hard. Make the work inspectable.*

Foundation Math is an executable workbench for an **agentic mathematician**: a system that breaks mathematical problems into explicit obligations, proposes attacks, uses domain-aware calculators, challenges its own reasoning, and submits proof artifacts to verifiers.

The aim is reusable problem-solving machinery, not a collection of confident answers. Foundation Engine provides the sibling design pattern: a small reusable core, optional domain capabilities, explicit application contracts, and evidence tied to a particular revision. Mathematical problems remain separate consumers of that machinery.

## The system

1. **Problem contract**: exact statement, domain, quantifiers, assumptions, definitions and success condition.
2. **Agent work queue**: owned, bounded tasks for proposing, calculating, criticizing, verifying and formalizing.
3. **Agentic calculator**: structured requests to domain-specific tools. Exact arithmetic stays exact; approximate and symbolic backends must declare their semantics.
4. **Claim and evidence ledger**: dependencies, proof obligations, counterexamples, review scope, immutable artifacts and corrections.
5. **Formal verifier interface**: Lean as a proof-checking backend, with its environment and trust assumptions recorded.
6. **Research memory**: reusable techniques and precise failed approaches, carried into subsequent problems without promoting assumptions into facts.

An agent proposes. A tool computes within a declared domain. A verifier checks a stated artifact. None of those steps silently substitutes for the others.

## v0.14 local development: formal exterior powers and pure evidence planning

Three appended read-only tools bring the bridge to nineteen, preserving all
sixteen complete old contracts and all runtime acceptance implementations.
Exact exterior calculations are independently checked; evidence planning only
classifies caller-authored pins and never executes or skips a validation.

```sh
python -B -m foundation_math exterior-calculate examples/exterior-power/stronger-exterior-test.request.json
python -B -m foundation_math exterior-check examples/exterior-power/irrep-W.request.json examples/exterior-power/irrep-W.certificate.json
python -B -m foundation_math validation-evidence-plan < examples/validation-evidence/mandatory-fresh-policy.input.json
python -B tools/run_exterior_evidence_validation.py
python -B tools/reproduce_exterior_evidence_release.py
python -B tools/build_exterior_evidence_release.py --output foundation-math-v014.zip
```

The aggregate freshly replays the full frozen historical gate. Prior receipts lack
established runner/environment/closure pins, so no historical check is skipped.
The explicit archival command is tools/run_full_archival_replay.py. No speedup or
reused-evidence release profile is claimed. Actual timings are kept separately.
The selected-only delivery gate runs normal/-O, rechecks independent integration
review and rebuilds the exact ZIP. History uses a compact exact v0.13 recipe, not
a full nested v0.13 archive. All historical gates remain available unchanged.

Comparison twists apply after wedge. The formal illustration improves over the
ordinary comparison at t=6, not all twists: ordinary t=1 already obstructs.
No actual geometry, maps, existence, all-twist theorem, Lean proof or acceptance
promotion is claimed. The fixed 64 KiB bridge rejects whole oversized certificates
unless a bounded producer-to-verifier round trip is possible; standalone CLI caps
remain separate. Nothing publishes, creates a repository or installs software.

Read [the capability contract](docs/EXTERIOR-EVIDENCE.md),
[transport boundaries](docs/EXTERIOR-EVIDENCE-BRIDGE.md), and
[freshness and validation](docs/EXTERIOR-EVIDENCE-VALIDATION.md).
The following version sections describe historical releases, not current entry points.

## v0.13 local development: exact authored hypothesis-scope matching

One new stdin CLI and one appended bridge tool compare a caller's explicit exact
current fact bindings with a rule's typed requirements, for sixteen tools total.
All fifteen prior tool contracts, arithmetic, ledger and acceptance domains remain
unchanged. The standalone accepted matcher is byte-preserved.

```sh
python -B -m foundation_math hypothesis-scope-check < examples/hypothesis-scope/exact-full-kernel.json
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_hypothesis_scope_validation.py
python -B tools/reproduce_hypothesis_scope_release.py
python -B tools/build_hypothesis_scope_release.py --output foundation-math-v013.zip
```

The first aggregate is the current full local gate. The delivery command reruns
it under normal and optimized Python in a clean selected-only extraction and
rebuilds the exact ZIP. Historical release commands below are not current entry
points. The compact pinned snapshot reconstructs exact v0.12 source and its
original ZIP without embedding another full baseline archive. All earlier
retained archives and the v0.11 snapshot remain unchanged.

A match is only structural equality of caller-authored assertions. It does not
establish their truth, provenance authenticity, rule adequacy, geometry, any
conclusion, Lean proof, or runtime goal acceptance. The checker will accept
consistent false assertions as matches. Generic equality is not coherent equality;
a selected subkernel is not a full kernel; an abstract splitting is not an
embedded one. There is no inference or weakening, even when mathematics might
justify one with further assumptions. The ledger is not automatically consulted.

The bridge tool is `match_hypothesis_scope` with exactly one `document` argument.
The complete bridge input remains capped at 65,536 bytes. The stdin-only CLI
retains the lab's 262,144-byte input cap and separately bounds its output envelope.
No paths, network, model/provider calls, new repository, Lean installation,
publication or actual research-instance computation is part of this release.

Read [the scope integration contract](docs/HYPOTHESIS-SCOPE.md),
[transport boundaries](docs/HYPOTHESIS-SCOPE-BRIDGE.md), and
[portable validation](docs/HYPOTHESIS-SCOPE-VALIDATION.md).

## v0.12 local development: compact exact baseline snapshots

This is a packaging-only release. All fifteen runtime tool contracts and all
mathematics, ledger, and runtime-acceptance implementations are byte-for-byte
unchanged from v0.11. No tool or accepted proof domain has been added.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_snapshot_validation.py
python -B tools/reproduce_snapshot_release.py
python -B tools/build_snapshot_release.py --output foundation-math-v012.zip
```

The first command is the single current aggregate. It reconstructs the exact
selected v0.11 sources and byte-identical original v0.11 ZIP, then runs the
unchanged historical full aggregate fresh, along with current normal/-O tests,
packaging regressions, and independent integration review. The second command
repeats the gate from a selected-only delivery copy and checks deterministic ZIP
rebuilding. No sibling checkout or original v0.11 ZIP is an input. Historical
commands below are documentation of older versions, not current entry points.

Instead of nesting another full baseline ZIP, a pinned recipe uses unchanged
current donor bytes plus old-byte blobs for changed or removed baseline files.
The recipe pins only the reused donor projection, avoiding a cycle with this
release's manifest. Earlier vendor archives required by v0.11 remain unchanged.

The supported scope is Linux/POSIX in a trusted single-writer workspace. This is
not a concurrent no-clobber primitive or security sandbox. Exact compressed bytes
are checked against the original archive pin and depend on the serializer profile;
other Python/zlib versions are not assumed compatible. Real Lean remains an
explicit unavailable skip. There are no installs, model calls, or network steps.

Read [the snapshot integration contract](docs/BASELINE-SNAPSHOT.md) and
[reproduction and measurements](docs/BASELINE-SNAPSHOT-VALIDATION.md).

## v0.11 local development: exact-revision dependency applicability

One new stdin CLI and one appended bridge tool now replay a bounded claim-revision
ledger, for fifteen bridge tools total. All fourteen prior tool contracts, arithmetic
implementations and runtime acceptance domains remain unchanged.

```sh
python -B -m foundation_math claim-ledger-replay < examples/claim-revision/boundary-withdrawal.ledger.json
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_claim_ledger_validation.py
python -B tools/reproduce_claim_ledger_release.py
```

The middle command is the single advertised aggregate for this release. The last
command verifies a selected-only, clean normal/-O aggregate and deterministic archive
rebuild. Both work without sibling checkouts, generated historical evidence, network,
installations or model calls. Frozen embedded source archives replay the accepted
v0.10 baseline and corrected claim-revision lab, including the lab's separately
implemented breadth-first review oracle. Historical version commands below are not
additional current-release aggregates.

The ledger binds every required dependency to an exact record revision and hash.
Withdrawing an argument blocks its explicit downstream users. Revising an argument
leaves old pins stale until dependents are explicitly revised; it never silently
repins them. Historical withdrawals and objections do not leak into a new revision.
Shortest deterministic witness paths explain blockers and leave unrelated branches
unchanged. The data is synthetic and no actual HM instance has been calculated.

A successful replay means only that this bounded dependency-accounting operation
completed. No recorded dependency blockers does not mean truth, proof, checked
artifacts or discharged hypotheses. Authored statuses and reported counterexamples
remain unverified. An unchecked refutation report is an unresolved objection, not a
false theorem. Replay is the same accepted implementation, not an independent
runtime verifier. No result enters the existing goal-acceptance registry.

The bridge tool is `replay_claim_applicability`, with exactly one structured `ledger`
argument. Its input frame remains capped at 65,536 bytes including the envelope,
even though the standalone ledger accepts 262,144 bytes. Neither interface executes
text or fetches evidence artifacts. The new CLI accepts stdin only, without paths,
options or caller-set budgets. Existing original ledger validation remains a distinct
legacy schema; it is not automatically migrated or promoted to the revision format.

Read [the integration contract](docs/CLAIM-REVISION.md),
[bridge boundaries](docs/CLAIM-REVISION-BRIDGE.md),
[portable validation](docs/CLAIM-REVISION-VALIDATION.md), and
[the accepted lab contract](docs/CLAIM-REVISION-LAB-CONTRACT.md).

## v0.10 local development: formal split-bundle cohomology

A supplied formal equivariant splitting on P¹ now has a checked calculator adapter,
two CLI commands and two appended bridge tools, for fourteen tools total. All twelve
prior tool contracts, existing arithmetic implementations and the runtime verification
registry remain unchanged.

```sh
python -B -m foundation_math split-bundle-calculate examples/split-bundle/negative_h1_critical.request.json
python -B -m foundation_math split-bundle-check examples/split-bundle/hom_not_map_rank.request.json examples/split-bundle/hom_not_map_rank.certificate.json
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_split_bundle_validation.py
```

The last command is this release's single advertised aggregate. It runs from only
SOURCE-MANIFEST.json and the files it names, without sibling checkouts, historical
generated evidence, network, installations or model calls. Authenticated embedded
archives replay the complete v0.9 aggregate and the accepted split-bundle lab's
independent mathematical and mutation controls. The reproducible packaging gate is
`python -B tools/reproduce_split_bundle_release.py`.

The new domain computes H⁰, H¹, signed equivariant Euler characters, rank and degree
at bounded twists, or an equivariant Hom-space dimension between two supplied
splittings. It does not infer a splitting, identify an actual bundle, realize a
representation geometrically, or determine the rank of a chosen map. The physical
catalog and supplied formal splitting are explicit assumptions. H⁰ and H¹ are
genuine characters; their Euler difference may be virtual. Equal Euler characters
at every twist do not determine the splitting or cohomology.

Certificates are bound to the separately supplied original request, including its
ordered presentation. Both calculation and checking independently reconstruct every
field before reporting arithmetic success. No result promotes a runtime goal or a
Lean theorem. Real Lean remains unavailable with an explicit test skip. This remains
local development, with no repository creation, publication or actual HM instance.

Read [the adapter contract](docs/SPLIT-BUNDLE.md),
[bridge boundaries](docs/SPLIT-BUNDLE-BRIDGE.md),
[validation and intentional changes](docs/SPLIT-BUNDLE-VALIDATION.md), and
[the accepted mathematical assumptions](docs/SPLIT-BUNDLE-LAB-MATHEMATICS.md).
All following version sections describe historical commands, not additional advertised aggregates.

## v0.9 local development: fixed physical character-ring arithmetic

The explicitly labeled fixed character table now has a checked calculator adapter,
two CLI commands and two appended bridge tools, for twelve tools total. The original
ten tool contracts and all runtime acceptance domains remain unchanged.

```sh
python -B -m foundation_math character-calculate examples/character-ring/physical_tensor.request.json
python -B -m foundation_math character-check examples/character-ring/physical_tensor.request.json examples/character-ring/physical_tensor.certificate.json
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_character_ring_validation.py
```

The last command is the single advertised aggregate for this release. It runs from
an extraction containing only SOURCE-MANIFEST.json and the files it names, without
sibling trees, historical generated evidence, network access, installs or model calls.
The frozen accepted lab ZIP is authenticated, then only source and executable review
scripts are extracted for fresh replay. An embedded manifest-only v0.8 archive supplies
an isolated baseline for all ten prior-tool differential checks.

The fixed table's identification with the physically marked group is a pinned
mathematical input, not proved by hashes, orthogonality or these tests. A is not V;
W is not Wp. Signed virtual characters are not genuine representations merely because
their dimension is positive. Genuine means nonnegative irreducible multiplicities,
not geometric realization. Symmetric powers mean only Sym^n(W), for 0 <= n <= 256.
Exact class values remain in Q(sqrt(5)); no floating-point fallback exists.

An unmet expectation is an error with no success certificate. It neither proves nor
refutes an arbitrary mathematical problem. Checked arithmetic is never silently
accepted as runtime-goal or formal-proof evidence. This remains a local derivative:
no repository, publication, actual HM instance calculation or general group engine.

Read [the adapter contract](docs/CHARACTER-RING.md),
[bridge boundaries](docs/CHARACTER-RING-BRIDGE.md),
[validation and intentional changes](docs/CHARACTER-RING-VALIDATION.md), and
[the accepted lab's mathematical assumptions](docs/CHARACTER-RING-LAB-MATHEMATICS.md).
Earlier version commands below are historical, not additional advertised aggregates.

## v0.8 local development: exact rational linear systems

One explicit A,b now yields either a checked particular solution plus complete
Q-nullspace basis, or an exact left-null inconsistency witness. The accepted
standalone engine is unchanged. Z restricts input tokens only, not solutions.

```sh
python -B -m foundation_math system-solve examples/linear-systems/consistent-system.json
python -B -m foundation_math system-check examples/linear-systems/consistent-system.json examples/linear-systems/consistent-certificate.json
PYTHONDONTWRITEBYTECODE=1 python -B tools/run_linear_systems_validation.py
```

The bridge appends `solve_rational_linear_system` and
`check_rational_linear_system_certificate`, making ten tools. All eight prior
definitions and existing runtime acceptance domains remain unchanged. No integer
lattice, generic/family statement, formal proof or runtime goal promotion follows.
This is a separate local derivative, not a repository or publication.

The single aggregate above runs from a manifest-only extraction with no historical
evidence or sibling trees. Read the [API and mathematical scope](docs/LINEAR-SYSTEMS.md),
[append-only bridge contract](docs/LINEAR-SYSTEMS-BRIDGE.md), and
[portable validation procedure](docs/LINEAR-SYSTEMS-VALIDATION.md).
Earlier sections describe historical version commands and capability boundaries.

## v0.7 local development: small integer polynomial witnesses

False unrestricted formal Q-polynomial identities now receive a concrete small
integer point and exact left/right mismatch, checked afresh against the original
expression trees. Sequential coefficient-preserving substitution needs at most
n plus the normalized difference’s total degree in trial substitutions, not a
Cartesian grid. Under current caps this is at most 40 trials, with the sharp
40-trial case tested. A normalized zero difference instead reports an exact coefficient identity;
the point checker does not prove that identity. Resource failures are inconclusive.

```sh
python -B -m foundation_math polynomial-witness examples/polynomial-witness/false-square.json
python -B -m foundation_math polynomial-witness-check examples/polynomial-witness/false-square.json examples/polynomial-witness/false-square-witness.json
python -B tools/run_polynomial_witness_validation.py
```

The bridge appends `construct_polynomial_witness` and `check_polynomial_witness`,
for eight tools total. All original six tool definitions remain pinned unchanged.
Only characteristic-zero formal polynomials over Q with algebraically independent
variables and no added constraints are supported. No quotient rings, finite fields,
rational functions, restricted loci, runtime goal acceptance or formal proof.
The frozen v0.6 source and standalone witness lab remain unchanged; this is a
separate local derivative, with no repository creation or publication.

See the [API and evidence distinction](docs/POLYNOMIAL-WITNESS.md),
[sharp total-degree bound](docs/POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md),
[append-only bridge contracts](docs/POLYNOMIAL-WITNESS-BRIDGE.md), and
[v0.7 validation](docs/POLYNOMIAL-WITNESS-VALIDATION.md). Earlier version sections
below describe their historical tool counts and capability boundaries.

## v0.6 local development: exact rational matrix certificates

One explicit bounded matrix can now produce an independently checked RREF,
rank, complete Q-nullspace basis, and square determinant certificate. The
verifier replays an invertible row-operation log and checks `U*A=R`, RREF
conditions, nullspace membership and free-coordinate completeness, and the
exact determinant relation. It does not run the producer's elimination.

```sh
python -B -m foundation_math matrix-certify examples/linear-algebra/rectangular-matrix.json
python -B -m foundation_math matrix-check examples/linear-algebra/rectangular-matrix.json examples/linear-algebra/rectangular-certificate.json
python -B -m foundation_math_bridge
```

The bridge now advertises six tools: the original four plus
`certify_rational_matrix` and `check_rational_matrix_certificate`.
Every matrix result explicitly says `computational_field: Q` and
`scope: one_explicit_matrix`. Z restricts input coefficients only: the basis
for `[[2,1]]` is `[-1/2,1]`, not an integral-lattice basis. There is no symbolic
or generic rank claim, no formal proof, and no runtime goal acceptance. All
matrix fixtures are original synthetic inputs, unrelated to the motivating
proof-repair project.

The standalone calculator's original runtime is retained byte-for-byte. The
existing scalar/polynomial/counterexample calculators and domain acceptance
registry are unchanged. The CLI and bridge are explicitly extended; frozen
v0.5 and the standalone lab remain unchanged. See the [matrix API and trust
boundary](docs/LINEAR-ALGEBRA.md), [bridge tools](docs/LINEAR-ALGEBRA-BRIDGE.md),
and [v0.6 validation](docs/LINEAR-ALGEBRA-VALIDATION.md).

## v0.5 local development: agent-facing math bridge

External coding/research agents can now launch a fixed stdio process and discover
four bounded exact tools: scalar arithmetic, Q-polynomial identity comparison,
finite-integer-box counterexample search, and fresh witness checking. No embedded
model, credentials, dependency installation or network server is needed.

```sh
python -B -m foundation_math_bridge
python -B examples/bridge/stdio_client.py
python -B tools/run_bridge_validation.py
```

This is the custom `foundation-math-jsonrpc/1` protocol, **not MCP** and not a
claim of compatibility with any external agent host. Its tested methods are
`initialize`, `ping`, `tools/list` and `tools/call`. The current stable MCP
revision checked is 2026-07-28 and uses a different modern lifecycle.

Strict bounded frames and allowlisted JSON data preserve mathematical scope:
false identities remain false, finite exhaustion is never a universal proof,
and no bridge call grants runtime goal acceptance or formal-proof status. The
v0.4 backend, work queue and domain registry are byte-identical. See the
[bridge contract and agent examples](docs/AGENT-BRIDGE.md) and
[validation evidence](docs/AGENT-BRIDGE-VALIDATION.md).

## v0.4 local development: bounded counterexamples

The new exact search tool checks Q-polynomial assertions only on an explicit finite
integer Cartesian box. It either returns an exact counterexample or reports
`no_counterexample_in_declared_finite_domain`. A separate witness checker re-parses
the original request and enforces the integer bounds and every constraint.

```sh
python -m foundation_math counterexample-search examples/counterexample/true-bounded-inequality.json
python -m foundation_math counterexample-search examples/counterexample/false-bounded-inequality.json
python -m foundation_math counterexample-check examples/counterexample/false-bounded-inequality.json examples/counterexample/valid-witness.json
```

Finite exhaustion is not a universal or formal proof. These tools are deliberately
not registered as accepted runtime goal domains; the v0.3 verifier and domain
registry remain unchanged. No live model or actual Lean check was added. See the
[contract and domain pitfall](docs/BOUNDED-COUNTEREXAMPLES.md) and
[validation evidence](docs/COUNTEREXAMPLE-VALIDATION.md).

## Initial implementation boundary

### v0.3 focused extension: domain-aware acceptance

The work queue now dispatches typed scalar Z/Q and exact Q-polynomial goals.
A successful calculation is not the same as an accepted identity: identity
acceptance requires `result.equal is True`, exact goal/ring/ordered-variable
binding, trusted replay, and the requested evidence level.

```sh
python -m foundation_math run examples/workflow/polynomial_distributivity.json
python -m foundation_math run examples/workflow/polynomial_false_identity.json
python -m foundation_math run examples/workflow/polynomial_formal_requirement.json
```

The first exits 0 with an exact result. The second exits 1 with a nonzero
coefficient witness. The third also exits 1: exact computation cannot satisfy
`required_evidence: formal_proof`. No real Lean proof or informal-statement
correspondence is claimed. See the [runtime API and acceptance gates](docs/DOMAIN-RUNTIME.md).

The v0.2 polynomial calculator remains separately callable; its [domain contract](docs/POLYNOMIAL-DOMAIN.md)
and [worked proof-repair counterexample](docs/EULER-SEQUENCE-PITFALL.md) retain
their narrow formal-ring scope. The restricted Lean adapter is unchanged and
separate. Earlier delivered source trees are not modified by this extension.

This repository starts with a small local Python prototype, not an autonomous research service. It includes a deterministic work-queue interface, exact integer/rational calculation, ledger validation and a Lean adapter. Live model-provider execution, broad CAS coverage, automated theorem discovery, a distributed scheduler and a proof-assistant-independent certificate system are development goals, not current capabilities.

The Lean adapter requires a separately installed, suitably isolated Lean environment. If Lean is unavailable, the result must be `unavailable`, never `passed`. Stub-backed adapter tests exercise plumbing only. A successful Lean process must not be described as proof of the intended informal problem without checking the formal statement, imports, axioms and correspondence.

## Run the seed

Requires Python 3.11 or newer. The deterministic core has no third-party Python dependencies and makes no model/API calls.

```sh
python -m foundation_math demo
python -m foundation_math run examples/workflow/rejected_proposal.json
python -m foundation_math lean-status
python -m tools.validate_claim_ledger examples/toy-ledger.json
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

Run from the repository root. The demo computes 1/2 + 1/3 exactly and records the result 5/6. It distinguishes `exact_result_verified` from `not_formally_verified`. The wrong-answer example is a negative test and should be rejected.

The offline proposal provider is a deterministic fixture. An external agent can submit structured proposals through the provider interface, but this seed does not claim to run a live language model or solve open problems autonomously.

## Repository map

- `foundation_math/`: executable orchestration and calculator/verifier adapters.
- `tools/`: claim-ledger validation.
- `schemas/`: machine-readable record contracts.
- `examples/`: small worked inputs and reproducible demonstrations.
- `tests/`: positive and negative regressions.
- `methods/`: methods extracted from actual proof-repair work.
- `templates/`: problem, experiment and proof-review briefs.
- `docs/`: architecture, trust boundary and development scope.

See the [calculator and Lean adapter contract](foundation_math/ADAPTERS.md), [architecture](docs/ARCHITECTURE.md), [the verification contract](docs/VERIFICATION.md), and [the roadmap](docs/ROADMAP.md). Command examples and final test evidence are recorded with the executable modules and examples.

## What “verified” means

Verification always names its object and scope. A schema-valid ledger is not a valid proof. A reproducible finite test is not an unrestricted theorem. A reviewed conditional proof retains its assumptions. A kernel-checked formal theorem retains its foundational axioms and proves the formal statement actually supplied.

Closed subcases and finite remaining inventories can measure a fixed classification. They do not supply a percentage of the time or difficulty remaining in an open research problem.

## Relationship to the proof-repair project

The motivating case study is [read-em-and-weep](https://github.com/Akilleez-QA/read-em-and-weep). Foundation Math extracts reusable mechanisms; it does not move that project's proof files, change its ownership, or announce that its original problem is solved. Historical proof counts belong in the case study, not the reusable engine's capability claims.

## Licensing

A project license has not yet been selected. Foundation Engine is a design reference; its code and license are not silently copied into this repository. Source material and third-party dependencies retain their own terms.

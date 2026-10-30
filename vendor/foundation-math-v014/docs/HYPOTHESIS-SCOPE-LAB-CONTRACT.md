# Closed typed-premise contract

## Authority and result boundary

This checker recognizes a finite language of caller-authored predicates and checks
literal matching. It does not prove supplied facts, authenticate their authors,
fetch provenance artifacts, validate the mathematical meaning of descriptions,
check completeness of a rule's hypotheses, or establish a claimed conclusion.
The word `fact` denotes a supplied assertion, **not verified knowledge**.

`all_requirements_matched` means exactly that every listed requirement has an
explicit exact current fact binding, that fact is marked `supplied` rather than
`withdrawn`, and its predicate is structurally equal to the requirement. It never
means “the theorem applies in reality.” There is no conclusion field or promotion
API. Every report sets `fact_truth_checked`, `rule_soundness_checked`,
`geometry_checked`, `runtime_acceptance`, and `lean_proof` to literal false.

Hashes provide integrity identity, not authenticity or mathematical validity.
An adversary can author false predicates, omit a mathematically necessary premise
from a rule, and compute consistent hashes. Such input can match. Trust in rules,
object descriptions, physical markings, and evidence is external to this lab.

## Root and records

The input has exactly `schema`, `objects`, `maps`, `facts`, `rule`, `application`.
The schema is `foundation-math-hypothesis-scope/1`. Every registry record and the
single rule has exactly:

- `id`: ASCII letter followed by at most 63 ASCII letters/digits/underscore/dot/hyphen;
- `revision`: ordinary integer 1..1,000,000, never a boolean;
- `content`: the closed content shape below;
- `revision_sha256`: SHA256 of canonical `{id, revision, content}`.

Record IDs are unique across objects, maps, facts and rule. Requirement IDs form
a separate namespace. A reference/pin has exactly `id`, `revision`,
`revision_sha256`. No latest-revision lookup or name-only reference exists.

An object has content `{object_type, context_sha256, description}`. Supported types
are `coherent_sheaf`, `vector_space`, `representation`, `formal_splitting`, `locus`.
`context_sha256` is the caller's digest identifying the intended mathematical
universe/context. Its preimage is neither fetched nor validated. The nonblank
bounded description should identify the intended object; different exact IDs are
never identified from equal descriptions or dimensions. There is no implicit base,
coefficient-field, equivariance, or scheme inference. Correct context assignment
is a caller obligation.

A map has content `{source, target, description}`. Source and target are exact
object pins. Both must have the same declared type, one of coherent sheaf, vector
space or representation, and the same context digest. This intentionally excludes
cross-type maps, maps between different declared contexts, and general category
machinery. The description and exact ID identify the chosen map. Nothing checks
that it exists, is nonzero, is injective, or is the claimed geometric map.

A fact has content `{predicate, availability, provenance}`. Availability is
`supplied` or `withdrawn`, both caller authored. Provenance has exactly
`artifact_sha256` (lowercase 64-digit digest) and nonblank `description`. It cannot
be omitted. Artifact bytes are not fetched or hashed by this checker; even an
all-zero digest is structurally legal. This records where the assertion claims to
come from, not that any evidence exists or is accepted.

A rule has content `{purpose, requirements}`. Purpose is descriptive, not parsed.
The nonempty ordered requirements list contains `{id, predicate}` entries with
unique IDs. All are required. There are no optional requirements or alternative
proof branches. Reordering requirements changes the rule hash.

Application has `{rule, bindings}`. `rule` is an exact expected rule pin. Each
binding is `{requirement_id, fact}`, naming one rule requirement and an exact fact
pin. At most one binding per requirement; binding order is immaterial. Missing
bindings are allowed but block the result. Unknown requirement IDs or duplicate
bindings reject the input. A fact can serve two identical requirements if explicitly
bound twice. Unused facts are validated but are not searched or interpreted.

## Predicate vocabulary

Each predicate has exactly `kind` and the listed fields. All object/map fields
below are exact pins into the respective current registry. Every predicate's
referenced objects and map endpoints must share one context digest.

| Kind | Exact additional fields | Shape checks only |
|---|---|---|
| `generic_sheaf_equality` | left, right, locus | Two coherent sheaves and a locus |
| `coherent_sheaf_equality` | left, right | Two coherent sheaves |
| `selected_subkernel` | kernel, inclusion, of_map | Inclusion source is kernel; target is of_map source |
| `full_kernel` | kernel, inclusion, of_map | Same endpoint shape, different predicate kind |
| `abstract_splitting` | object, splitting | Coherent sheaf and formal splitting |
| `embedded_splitting` | object, splitting, inclusion | Additionally inclusion source is exact object |
| `coherent_image` | image, inclusion, of_map | Inclusion source is image; target is of_map target |
| `saturated_image` | image, inclusion, of_map | Same endpoint shape, different predicate kind |
| `physical_representation` | object, catalog_sha256, label | Representation, hash, one of nine labels |
| `object_rank` | object, value | Coherent sheaf; integer 0..1,000,000 |
| `object_dimension` | object, value | Vector space or representation; same integer bounds |
| `map_rank` | map, value | Exact map; same integer bounds |
| `map_injective` | map | Exact map |
| `map_zero` | map | Exact map |
| `constant_vanishing` | constants, inclusion, path | Constants object; inclusion into first path source; composable ordered path |
| `torsion_identification` | role, torsion, of_map, identified_with, identification | Role original/induced; exact sheaf map; identification has the two specified sheaf endpoints |
| `object_identity` | left, right | Same declared object type |
| `map_identity` | left, right | Exact same source and target pins |

For generic equality the caller asserts equality after restriction to the exact
named locus. The checker does not establish that the locus is open or dense.
For coherent equality the caller asserts equality in the intended category over
the context, not merely on that locus. Neither is converted to the other, even in
the direction that might follow under additional mathematical conventions.

Kernel and image predicates assert the described construction with these exact
maps. The checker only checks the displayed endpoints. It does not compute kernels,
images, saturation or rank, nor verify inclusion or universal properties.
`embedded_splitting` is the authored assertion that this splitting describes the
actual object with this exact inclusion, not a calculation from an abstract type.
It does not imply injectivity in the matching engine: that is a separate premise
if a rule explicitly asks for it.

Physical labels are exactly `1,W,A,S4,D,T6,P,Wp,V`. A label is meaningful only with
the caller's catalog digest; there is no loaded catalog, arithmetic, character
verification, canonicalization or geometric realization. The fixtures use a
synthetic catalog marker, not a physical representation calculation.

`constant_vanishing` asserts that the ordered path composite vanishes on the
image of the specified constants inclusion. Maps are written in execution order:
`[f,g]` denotes first f then g. The constants object and its inclusion are explicit;
the checker does not establish that they are actually a space/sheaf of constants.
Changing the designated constants, inclusion, any path map, path length or order
changes the predicate. A one-step path naming a separate composite map does not
match a two-step path even if someone asserts their composites agree. The checker
does not calculate compositions. The name `inclusion` does not itself prove a monic.

`torsion_identification` asserts an original or induced torsion identification for
the exact specified sheaf map. No torsion is computed. Both role and map identity
are material: changing either prevents matching. The identification map must have
the named torsion and identified_with objects as its endpoints.

## Exactness, snapshot freshness, and errors

The matching relation is **only JSON structural equality of validated predicates**.
There is no weakening, symmetry, transitivity, alpha-renaming, logical closure,
substitution, generic-to-global promotion, or numeric-to-object inference. Arrays
retain order. JSON object key order is irrelevant. Strings are not normalized.

Objects/maps/facts are one caller-supplied current snapshot, not an event log.
All record hashes and nested references in maps, facts, and requirements must match
that snapshot. A stale nested object/map pin, unknown typed target, wrong endpoint,
invalid hash, unsupported shape, or duplicate ID rejects the whole input. A higher
revision is not accepted as a match for an older pin. Revision history, continuity
and global latestness are not established: omitting a later real-world revision
cannot be detected from this document alone.

Application pins are allowed to be stale or missing. The computed per-requirement
status uses this fixed precedence:

1. `rule_pin_not_current`: application's rule pin differs from supplied rule;
2. `missing_binding`: this requirement has no binding;
3. `fact_not_supplied`: bound fact ID absent from fact registry;
4. `fact_pin_not_current`: bound revision/hash differs from current supplied fact;
5. `fact_withdrawn`: exact bound fact is explicitly marked withdrawn;
6. `predicate_mismatch`: validated predicates differ;
7. `exact_match`.

A syntactically valid blocked report is not an invalid document. The report contains
the required predicate, bound fact pin, and supplied current fact pin, so it does
not hide stale references or quietly replace them. There is no persistence and no
partial success on malformed input. This lab does not replicate the ledger's
withdrawal propagation or shortest blocker paths.

## Canonical bytes and deterministic result

Canonical JSON is UTF-8, sorted object keys, compact separators, `ensure_ascii=False`,
no nonfinite values, and no Unicode normalization. This is an explicitly named
Python JSON encoding profile, not a claim to implement an external canonical JSON
standard. All record hashes bind exact array order. The input digest normalizes
objects/maps/facts by ID and bindings by requirement ID; requirements remain in
rule-authored order. Reports list requirements by ID. Registry/binding permutations
therefore produce byte-identical reports.

`check(document)` detaches ordinary JSON-compatible input, validates everything,
and returns the report or raises `ScopeError(code,path,message)`.
`loads(str_or_utf8_bytes)` strictly decodes JSON before checking.
`seal`, `pin`, `digest`, `canonical_bytes` are construction/encoding helpers, not
validators of mathematics. `seal` validates only the record envelope and JSON limits;
the complete content is validated by `check`.

## Hard budgets and ordinary JSON only

- Encoded input: 262,144 bytes; encoded output: 262,144 bytes.
- At most 64 objects, 64 maps, 64 facts; exactly one rule with 1..32 requirements.
- At most 32 bindings; constant-vanishing path length 1..4.
- Raw JSON depth at most 16 with root depth zero; at most 32,768 visited values.
- At most 16 fields per raw object, 256 entries per raw array, 2,048 characters
  per raw string and 64 characters per object key.
- Descriptions/purpose/provenance text: nonblank, at most 1,024 characters.
- Raw integers: signed 32-bit; semantic nonnegative values at most 1,000,000.
- Strict integers, not bool or float; no floating-point fallback.

Duplicate JSON keys, unpaired Unicode surrogates, unsupported Python subclasses,
cycles, tuples, unknown fields/kinds/labels, and nonfinite numbers reject. Guards use
explicit exceptions and remain active under `python -O`. JSON Schema documents
structural shape only; it cannot express all strict Python types, nonblank text,
reference equality, hash integrity, shared contexts, endpoints or aggregate budgets.

This is a bounded pure computation, not a hardened sandbox for hostile Python
processes, filesystem races, mutable modules, or concurrent caller mutation.

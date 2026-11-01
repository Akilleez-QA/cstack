# Exact authored hypothesis-scope matching

The accepted standalone hypothesis-scope core is copied byte-for-byte and its
original frozen source archive is retained. See HYPOTHESIS-SCOPE-LAB-CONTRACT.md
for all 18 typed predicates, exact identity/pin rules, freshness precedence and
bounds. Facts are authored assertions, never verified knowledge. Provenance is
an opaque claimed artifact digest; it is not fetched or authenticated.

`foundation_math.hypothesis_scope.check_hypothesis_scope(document)` returns a
receipt with status `success` when the bounded comparison completed, including
when requirements are unmatched. `result.all_requirements_matched` only means
that each explicitly listed requirement has a supplied exact current predicate
binding in this snapshot. It does not establish rule adequacy, actual latestness,
fact truth, geometry, a conclusion or formal proof. An invalid document returns
status `error`, a code/path/message and no partial result. All receipt/report
truth, geometry, formal-proof and runtime-acceptance flags are literal false.

No domain is registered in the runtime acceptance registry. Existing arithmetic,
ledger and Lean interfaces are unchanged. The adapter neither imports ledger
records nor performs automatic repinning, proof promotion, provenance retrieval,
mathematical weakening or inference. Both the supplied snapshot and the rule's
adequacy remain caller obligations. The tool is useful as a scope mismatch alarm,
not an authority deciding that a mathematical theorem applies.

The synthetic examples distinguish generic/coherent equality, selected/full
kernel, abstract/embedded splitting, coherent/saturated image, A/V, W/Wp,
one/two-step constants vanishing, original/induced torsion, exact chosen maps,
stale pins and withdrawal. They do not compute an actual mathematical instance.

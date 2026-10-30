# Selected-only v0.13 validation and compact history

The single current aggregate is `tools/run_hypothesis_scope_validation.py`.
It verifies the canonical selected manifest, fixed accepted-lab/archive pins,
unchanged old contracts and runtime/acceptance bytes, then reconstructs exact
v0.12 source and its byte-identical original ZIP from named current donors and
old-byte blobs. It runs that frozen historical full aggregate afresh, not a saved
receipt. The accepted lab aggregate independently replays author and reviewer
normal/-O tests, selected-only delivery and deterministic asset/archive rebuilds.
Current full runtime tests, new packaging tests, fifteen-tool differential,
new-tool guards/mutations and independent integration review run normal and -O.
Real Lean remains an explicit unavailable skip, never a claimed proof.

`tools/reproduce_hypothesis_scope_release.py` copies only selected files, repeats
the full aggregate with normal and optimized entry points, requires deterministic
result identity and exact archive rebuilding, and measures actual final packaging
against a full-v0.12-baseline counterfactual with all other bytes held fixed.
Measurements are storage-only, not timing or long-chain growth predictions.
Generated evidence is outside selection. No sibling checkout, original baseline
ZIP, network or model is required. Nothing installs optional backends.

The v0.12 snapshot uses the unchanged accepted snapshot implementation, its fixed
budgets and deterministic serializer. Its recipe pins the old manifest and archive
and only reused donor bytes, never the new manifest, so no hash cycle is created.
The original v0.11 snapshot and all earlier retained vendor archives are unchanged.
All baseline source files remain present; a small declared set of CLI/transport,
inventory-test and release-documentation files changes only in the new candidate.
The exact older bytes are included as deduplicated blobs for restoration.

Supported packaging scope remains trusted single-writer Linux/POSIX. Existing
outputs are not overwritten and symlink/hardlink inputs are rejected by inherited
safe readers. No concurrent race-hardening or sandbox claim is made. Exact ZIP
compression identity depends on the pinned serializer profile and compatible zlib;
it is checked, not assumed. Review pins describe byte integrity, not authenticity.

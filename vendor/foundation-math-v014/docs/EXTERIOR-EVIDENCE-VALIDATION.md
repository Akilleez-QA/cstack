# v0.14 validation, freshness and history

The release aggregate is `python -B tools/run_exterior_evidence_validation.py`.
The delivery gate is `python -B tools/reproduce_exterior_evidence_release.py`.
The explicit full archival replay command is
`python -B tools/run_full_archival_replay.py`.
All historical v0.13 and earlier gate/receipt code remains unchanged and selected.
Historical commands in older README sections are not current entry points.

## Deliberate freshness decision

This release uses FRESH FULL ARCHIVAL REPLAY, not a reused-evidence validation
profile. The prior v0.13 delivery receipt has exact source/archive/output pins
and a Python version, but not an exact prior runner artifact identity, complete
process/environment fingerprint and externally established closure declaration.
The recorded timing observer trace cannot supply those missing obligations.
Therefore no prior result is classified as safe to reuse for a real release gate,
and the original full v0.13 aggregate is run afresh from exact reconstructed
sources. No invented prior identity, timing, closure, or speedup is asserted.

The pure planner is integrated only as a read-only capability. Its classifications
have no control-flow path into this gate. There is no caller-provided execution
plan, arbitrary argv execution, automatic cache, command-based task-role inference,
renaming of required fresh work into historical references, or skip option.
A future separately reviewed current-and-pinned-evidence profile would need a
complete honest declared input/task closure and exact prior runner/environment
and output pins; that profile is NOT supplied or accepted here. Different
profiles would not establish speed-equivalent coverage.

The old observed full-delivery duration of 1590.072 seconds is retained only in
the immutable receipt lab's provenance references. It is an observation of that
old gate, not a prediction or a measurement of this gate. New subprocess timing
and output-hash observations are generated outside source selection. They record
actual requested/reported optimization and the measured current runner hash;
they explicitly do not certify environment closure or authorize historical reuse.

## Mandatory fresh work

The current aggregate verifies selected source/accepted lab pins, all sixteen old
complete contracts and unchanged runtime acceptance sources. It reconstructs exact
v0.13 source and its original ZIP using a compact recipe, unchanged donor bytes
and old-byte blobs, then confirms the unchanged old builder produces identical
ZIP bytes and executes the complete original aggregate fresh.

Both accepted lab aggregates execute fresh normally and optimized from their
pinned extracted archives. The exterior suite includes its eigenvalue oracle and
semantic source mutations. The planner includes author tests, independent cases,
independent semantic mutations and selected-only lab rebuilding. Current full
runtime tests, new packaging tests, sixteen-tool finite positive/negative
differential, schema/budget/scope controls and independent integration review run
normally and optimized. Real Lean remains unavailable with an explicit skip.
No test result is mathematical proof or an assertion about actual geometry.

The v0.14 launcher removes inherited PYTHONPATH/PYTHONHOME and sets
PYTHONOPTIMIZE=0, then uses isolated explicit normal/-O entry interpreters.
A pre-script guard verifies actual sys.flags.optimize and reports it. The test
runner additionally reports actual mode. Subprocess environment resets propagate
to immutable historical/lab scripts, so an inherited PYTHONOPTIMIZE=2 cannot turn
a nominal normal child into an optimized one. Negative tests cover this condition.

## Freeze and portable delivery

The delivery gate builds from SOURCE-MANIFEST.json and selected members only,
checks exact archive inventory/metadata, runs the release aggregate in both
entry modes from a clean extraction, and requires equal semantic receipts. It
rebuilds the ZIP independently from selected bytes and compares exact bytes.
Final source hashes are rechecked. Generated current evidence is not selected.
A distinct independent integration review audits the freshness and scope boundary
before the long final delivery gate is used for release acceptance.

The compact v0.13 snapshot adds no full nested v0.13 ZIP. Both older snapshots and
all older vendor archives are unchanged. Packaging support remains bounded,
trusted single-writer Linux/POSIX, not a concurrent hostile-filesystem sandbox.
Exact compressed identity is checked under the recorded serializer profile, not
assumed across arbitrary Python/zlib versions. Hashes prove integrity, not origin.
A measurement-only full-baseline counterfactual holds every non-snapshot member
fixed and reports actual archive byte counts, not a synthetic fixture or speedup.

## Explicit inherited provenance-path exception

The unchanged accepted receipt-lab archive contains one design-provenance member
with ten technical local source paths to old source, receipt and timing files.
It contains no credential or personal-data content. The new textual scan reports
this exact member/hash as a reviewed exception rather than modifying the frozen
lab or silently claiming a path-free archive. Any changed member, additional path
marker elsewhere or credential marker remains a failure. This is not a general
path exemption or universal secret-detection assurance. The independent review
audits this exception as part of release acceptance.

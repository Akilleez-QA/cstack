# Contract and remaining obligations

## Scope and trusted inputs

This Linux/POSIX prototype receives a trusted local workspace capability from the
host. The ordinary CLI fixes that root to its own `work` directory. Input/output
identifiers are single lowercase alphanumeric/hyphen components (maximum 64
characters); recipes contain only canonical relative ASCII source paths.
Untrusted data cannot select another root. The fixture/reproduction harnesses are
trusted developer tooling, not path-bearing runtime interfaces.

Externally supplied SHA-256 pins identify the expected recipe, historical source
manifest, and delivered archive. The prototype checks consistency with these pins;
it does not authenticate their origin. Replacing all expected pins is outside
this integrity claim. No recipe strings, source files, or ZIP members are executed
by `snapshot.py`. Only the explicit reproduction harness executes the pinned,
unchanged historical validator.

A source manifest is UTF-8 JSON with a nonempty sorted `files` object mapping
canonical relative paths to lowercase 64-character SHA-256 strings. Historical
metadata is preserved verbatim. Duplicate JSON keys at every depth, duplicate
recipe paths, self-pinning manifests, path-prefix file/directory collisions,
conflicting sizes for an identical content pin, nonfinite decoded JSON numbers, noncanonical
recipes and unknown recipe fields are rejected. A checked float parser rejects
valid numeric tokens such as `1e400` when decoding would overflow to infinity,
including inside otherwise unused manifest metadata. Repeated identical content at
separate legitimate paths is not an ambiguous duplicate; it is deduplicated.

## Explicit budgets

- 2,048 selected source files per source manifest/recipe.
- 8 MiB maximum individual source/blob file.
- 1 MiB maximum source manifest; 2 MiB maximum recipe.
- 8,192 input file reads and 64 MiB aggregate bytes read per operation.
- 32 MiB total snapshot payload.
- 4,096 output files/inventory entries and 64 MiB final output bytes.
- Paths: 240 ASCII bytes, at most 16 components.
- Archive writes are capped before crossing their remaining output-byte budget;
  restored sources, ZIP, and receipt together must fit the total cap.

Both build and restore use the same replay-eligibility preflight before
publication. It checks exact restored file/directory entries (including the
restored root, source manifest, ZIP, and receipt), the existing conservative
1 MiB manifest allowance, actual source/manifest/archive bytes plus the unchanged
65,536-byte receipt reserve, snapshot entries/payload, and planned restore input
bytes/read count. Build must reject an unreplayable snapshot, even if its own
inputs and compressed snapshot fit their separate budgets. Actual restored
lengths, input accounting, and final output are checked again before commit.

These fixed implementation limits cannot be raised by a recipe or CLI option.
Inputs are checked before bounded reads. Recipe declared sizes are not trusted:
each file is checked against actual length and its historical manifest hash.
Sources are retained in bounded memory and ZIP content is regenerated, not
extracted from an arbitrary compressed input. No network, installers, imports of
baseline code, subprocesses, or model calls occur in the snapshot library.

## Filesystem and atomicity

Reads traverse descriptor-relative directories using `O_NOFOLLOW`. Symlinks,
hardlinks, nonregular files (including FIFOs), unsafe names and noncanonical
paths are rejected. Snapshot membership and directories must match exactly; no
extra blobs or hidden payloads are accepted. Donor directories may contain other
next-version files, which are never consulted by restoration.

All verification and writing precedes one same-filesystem directory rename.
Handled errors remove staging data and leave no final destination. Existing
output files, symlinks, and even empty directories are rejected; nonempty user
destinations are never overwritten. Tests cover simulated write interruption and
a destination appearing before commit. This is exception-safe publication, not a
power-loss durability promise: there is no filesystem-wide fsync protocol. An
abruptly killed process may leave a private `.stage-*` directory, never a partially
published final destination. A hostile process concurrently mutating the trusted
workspace/output parent is outside this prototype's isolation model. It is not a
multi-user service or a filesystem sandbox.

## Reproducibility and compatibility

The supported profile reproduces v0.11's sorted file order, 2026-01-01 timestamp,
Unix creator system, mode `100644`, and Python DEFLATE level 9. Different Python/
zlib versions are not assumed byte-compatible. A mismatch with the supplied
historical ZIP pin is a closed failure, never an automatic repin or silent switch
to a stored archive. The lab records Python and zlib versions in replay evidence.

The reused donor projection avoids a circular dependency between snapshot recipe
and next release manifest. Any future integration must select and pin the recipe,
its historical manifest, its blobs, and its reused source paths as release inputs.
The final next-release manifest can pin this complete inventory without the
recipe pointing back to that manifest. A portable restore needs only the named
projection and snapshot, not the candidate's other changed/new files or manifest.

No frozen ancestor ZIP is rewritten. Restored v0.11 continues to run its unchanged
aggregate and frozen v0.10 replay, including the existing real-Lean-unavailable
skip. This prototype makes no change to runtime verification or claim acceptance.

## Integration not performed

No current release selection, aggregate, Library item, repository, CI pipeline,
license, or publication is changed. Independent review and an explicit next-release
integration decision remain necessary. Future profiles, long chains of snapshots,
manifest schema migrations, cross-platform behavior, concurrent hostile writers,
and malicious alternative expected pins are not established by this one fixture.

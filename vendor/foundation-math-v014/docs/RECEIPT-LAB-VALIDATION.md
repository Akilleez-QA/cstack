# Reproduction and measured validation scope

The lab's full local command is `python -B tools/validate.py`. It performs:

1. Exact selected-source manifest verification and deterministic regeneration of
   the structural schema and seven complete synthetic input/output example pairs.
2. Forty fresh author tests under normal and optimized Python.
3. Sixteen author semantic source mutations, each killed under normal and optimized
   Python. These run only on disposable copies and are not changes to source.
4. The independent review's 181 cases and 17 semantic mutants under both modes.
   Independent mutant kills require specific semantic failures after successful
   planner output, not crashes or incidental exceptions.
5. Two byte-identical deterministic ZIP builds; extraction containing exactly the
   selected files; normal/optimized author and independent review reruns there;
   exact archive rebuilding; and deliberate selected-source drift rejection.

All suites are this lab's tests. No actual historical/current Foundation Math check
is skipped, reused, run fresh, or relabeled by this experiment. The original v0.13
source manifest was checked read-only against all 454 selected source files and
remained unchanged; this is not a fresh replay of its validation gate.

The artifact uses ZIP_STORED with fixed timestamps, file modes and member order,
avoiding compressor-version variability. The selection and full source manifest
are shipped. `tools/package.py --output PATH` exclusively creates an artifact and
never silently overwrites an existing file. `--write-manifest` is an explicit
maintainer operation, not a validator escape hatch. Manifest self-consistency is
byte integrity only, not authentication or approval of a modified package.

The output validation receipt and independent review reports are kept outside source
selection to avoid self-referential hashes and fake shipped fresh results. They
bind the source-manifest and archive digests. A later adopter can reproduce all lab
checks without sibling checkouts, historical v0.13 source, network, model access,
optional packages, or generated evidence files.

Packaging supports a trusted, single-writer local workspace. Selected symlink and
hardlink files are rejected. No concurrent race-hardening, general archive sandbox,
universal secret scanning, actual workflow runtime saving, or release-approval
claim is made.

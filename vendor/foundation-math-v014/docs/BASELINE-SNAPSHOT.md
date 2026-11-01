# v0.12 baseline-snapshot integration

This is packaging-only integration of the accepted corrected snapshot lab. It
introduces no runtime tool, mathematical algorithm, ledger semantic change,
verification registry change, or proof-acceptance path. All fifteen complete
bridge tool contracts and every inherited source except README.md and
RELEASE-FILES.json remain byte-identical. SOURCE-MANIFEST.json is the new release
manifest, and is separately reconstructed from its original raw bytes for v0.11.
The seven historical vendor ZIPs remain unchanged and are named donors.

## Closed reconstruction

The snapshot contains the original historical manifest, a canonical recipe, and
content-addressed old-byte blobs for the changed README and selection file. All
other baseline files are explicitly pinned donor paths. Restoration verifies the
recipe pin, original manifest pin, exact source inventory, file sizes and hashes,
donor projection, snapshot inventory, and expected byte-identical original ZIP.
No original v0.11 ZIP is shipped or read as a restoration input. No sibling source
tree, donor manifest, changed current README, or new current source is needed.
There is no fallback, fetch, repin, or execution of recipe text.

The recipe names only the baseline donor projection, not the v0.12 manifest.
The current selection and manifest then bind every donor, blob, historical
manifest, recipe, accepted snapshot module, regression tests and packaging tools.
This direction of references avoids a next-manifest hash cycle. Pins establish
relative byte integrity; they do not authenticate the origin of their inputs.

## Accepted implementation and scope

baseline_snapshot/snapshot.py and packaging_tests/test_snapshot.py are exact
copies from the accepted corrected lab. The original fixed limits are unchanged.
Shared producer/consumer replay eligibility rejects snapshots exceeding restored
byte or directory-entry budgets before publication. Checked float decoding
rejects JSON exponent overflow such as 1e400. Both fixes retain regression tests
in normal and optimized Python. The full inherited mathematical and ledger tests
are unchanged and remain separately executable from the restored baseline.

This is a Linux/POSIX trusted single-writer workspace contract, not a filesystem
or process sandbox. Reads use no-follow descriptor traversal and reject symlinks,
hardlinks and nonregular files. Handled failures clean snapshot staging; an abrupt
kill may leave staging. There is no power-loss durability claim. A hostile writer
can race the final destination check and rename, including introducing an empty
directory during that final window. The implementation is not a kernel-level
concurrent no-clobber primitive. The complete unchanged lab contract is retained
as historical scope documentation; its integration-not-performed section describes
the lab, while this document describes the subsequent reviewed integration.

The ZIP profile fixes sorted names, timestamp 2026-01-01, Unix creator, mode
100644 and Python DEFLATE level 9. Python 3.12.14 and zlib 1.3.2 are the validated
serializer versions. Other serializer versions and platforms are not presumed
byte-compatible: the historical ZIP pin mismatch fails closed. Long snapshot
chains and future growth behavior are not established. Hash equality, passing
software tests and packaging review are not mathematical proof or runtime
acceptance. No actual HM data, installs, network or model calls are introduced.

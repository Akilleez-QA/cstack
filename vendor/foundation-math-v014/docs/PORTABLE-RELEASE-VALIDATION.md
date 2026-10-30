# Portable v0.7 validation repair

This is a packaging-only derivative of the frozen v0.7 source manifest
`93892d475dd1cad0e1e5637a6fe682ee65af0846bfa0015650d088e68e5e30f3`,
preserved in [the original source manifest](BASE-V07-SOURCE-MANIFEST.json).
The original v0.7 tree was not edited. All mathematical code, parsers,
producer/checker implementations, runtime boundaries, CLI code, eight tool
contracts, synthetic examples and the independent mathematical review are
byte-identical to that frozen v0.7 snapshot.

## Problem and bounded fix

A ZIP containing exactly the source manifest's files correctly excludes
historical generated evidence. However, the original advertised aggregate
command assumed that `evidence/bridge-transcript-validation.json` existed for
optional schema validation, and its preservation gate also attempted to hash all 27 historical evidence
records in its 169-entry v0.6 frozen inventory. That made
the advertised command fail in a clean source-only extraction.

The development aggregate now regenerates its bridge transcript from the
shipped synthetic requests with the existing fixed transcript generator. Its
preservation gate checks all 142 inherited source inventory entries, including
the intentionally regenerated source manifest, and explicitly lists the 27
unshipped historical evidence records as excluded rather than checked. Missing
or modified inherited source still fails closed.

Four focused regressions cover clean transcript generation, explicit exclusion
of historical evidence, missing source and changed source. The aggregate also
pins all 194 original v0.7 source files and permits changes only to its own
development script and the current validation documentation. The original
independent review remains historical evidence for the unchanged mathematical
and runtime code, not a claim that its reviewer inspected this packaging repair.

## Reproduce from the source-only ZIP

From its extracted project directory, run:

```sh
python -B tools/run_polynomial_witness_validation.py
```

No preparatory evidence copy, installation or network access is required.
The standard-library tests and audits run normally and with Python optimization.
Optional schemas use already installed `jsonschema`, or explicitly report it
unavailable. The complete suite has 470 tests: 469 pass and one real-Lean test
is skipped when Lean is unavailable. Newly generated evidence remains local
and is not itself included in the source manifest or source-only ZIP.

The tighter n+D result is still a trial-substitution bound for the existing
algorithm, not measured wall-clock acceleration, arithmetic complexity,
point-checker certification of a trace, or a full formal proof.

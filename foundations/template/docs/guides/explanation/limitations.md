# Limitations

This page is the template's own limitations page and the model for a copy's "Limitations and safety-relevant use" page. A Foundation with engineering or safety-relevant data must have one (foundation-refrigeration's is the worked example).

## What the outputs are

`echo_observation` returns the caller's own text, with a fixed boundary saying it is an observation and not a determination or a control action, Evidence with status CHECK, and the SHA-256 of the request. It carries no domain meaning.

## What the software does not do

- It does not judge, approve or certify anything.
- It does not read or write files, open network connections or command any device.
- It does not validate its own output against the output schema; the host does that.

## Data sources and their limits

None. The template embeds no reference data. A copy that does must state, for each table, its source and edition, units, valid range, interpolation and extrapolation behaviour, and known differences from authoritative sources, and link the data dictionary's provenance table.

## Use in safety, engineering or regulated decisions

Not applicable to the placeholder. A copy whose outputs could inform such decisions must say plainly that they are not to be used as the sole basis for them, name the authoritative sources to verify against, and state that such use moves the user's application to a Class D analog that the project does not provide.

## Misuse and security considerations

Requests are untrusted. The bridge bounds every frame, refuses unknown fields, non-integers, NaN and duplicate keys, and takes no paths or options ([ICD §6](../../icd/icd-cstack.md#6-security-and-input-bounds)). Report vulnerabilities as in [SECURITY.md](../../../SECURITY.md).

## Known limitations

| Limitation | Effect | Issue |
|---|---|---|
| Placeholder tool only | No domain use | — |
| Integer-only numeric profile | Decimal inputs are refused; a copy that needs them must widen the parser | — |
| Several bridge error paths have no test (GAP-TPL-001 to GAP-TPL-006) | Copies inherit those untested paths | — |

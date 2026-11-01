# Transport and resource boundaries

The bridge retains the original 65,536-byte input frame, 1,048,576-byte output
frame, 16,384-value/key node count, depth 80, string length 4,096, integer bit
limit 4,096 and all existing ID bounds. No existing limit is increased.
All new tool argument objects and schemas are closed. Notifications never run
work. Unexpected exceptions are closed errors without private tracebacks.

## Exterior certificate round-trip guarantee

A successful bridge producer result is withheld unless the ENTIRE compact,
ASCII-escaped verifier JSON-RPC frame can be decoded by the unchanged bridge
parser. That frame includes the separately supplied original request, the whole
certificate and a maximally escaped legal 128-character ID. Thus any legal ID
fits that compact serialization profile. The guard checks bytes, nodes, depth,
strings and exact JSON types, not just certificate length. The same guard runs
before bridge verification. Oversized envelopes fail completely with a protocol
budget error; no truncated certificate, partial answer or expanded cap is used.
Whitespace-heavy caller serializations may still exceed the fixed frame limit.
Output framing has its separate unchanged cap. Producer/checker lab bounds also
remain active. A valid standalone certificate can therefore be inadmissible on
this narrower bridge. The tests include a naturally oversized certificate, not
only a mocked reduced limit, and a separate node-limit control.

## Separate standalone command contracts

`python -B -m foundation_math exterior-calculate REQUEST.json`
`python -B -m foundation_math exterior-check REQUEST.json CERTIFICATE.json`

These read only the explicitly supplied local input files and emit a bounded
JSON receipt to stdout. Request cap: 65,536 bytes. Certificate input cap:
2,097,152 bytes. Whole adapter output envelope cap: 2,097,152 bytes, plus one
newline. A whole-envelope overflow is rejected, never truncated. The unchanged
standalone `python -m exterior_power` lab command retains its own documented
bare-certificate contract. Errors exit 2; unexpected implementation failure
exits 4. The bridge is narrower and does not accept paths.

`python -B -m foundation_math validation-evidence-plan < DOCUMENT.json`

This accepts stdin only, no paths/options or caller budgets. Input cap: 262,144
bytes; whole ASCII-escaped receipt envelope cap: 524,288 bytes, plus newline.
The core's separate UTF-8 report limit and all aggregate limits remain active.
The bridge still has its 65,536-byte whole input cap and existing node bounds.
The command never executes invocation data. Rejection returns no partial plan.

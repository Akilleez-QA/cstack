# Fixed physical character arithmetic adapter

The new foundation_math.character_ring module exposes calculate_character(request)
and check_character_certificate(expected_request, certificate). The former calls the
unchanged accepted producer and then the independently implemented verifier against
the original external request. The latter imports neither producer nor contract;
it calls only the verifier and fixed owned source hashing. The verifier shares the
fixed table assumption, Python and rational arithmetic with the producer; it is not
a diverse formal kernel. CLI ingestion still uses the unchanged lab contract parser.

Successful receipts contain status=success, operation=calculate or verify,
request_sha256, implementation source hashes, result.verification and, for calculate
only, result.certificate. The certificate is byte-for-byte the lab's canonical data
object, not the enclosing receipt. Supply that certificate, not the whole adapter
receipt, to character-check. The example certificate files demonstrate the format.
The verifier always receives the separately supplied expected request.

Every receipt declares scope=universal_representation_arithmetic_only,
computational_field=Q(sqrt(5)), formal_proof=false, runtime_goal_acceptance=false,
table_group_identification_assumed=true and geometric_realization=false. Hashes bind
bytes only and neither authenticate an external authority nor prove mathematical
truth. Fixed table identification with SL2(F5) in the physical marking is an assumed
mathematical input, not a consequence of orthogonality or fusion consistency.

The labels in order are 1,W,A,S4,D,T6,P,Wp,V. A/V and W/Wp are physically distinct,
not interchangeable dimension aliases. Arithmetic permits signed integral virtual
characters. Genuine means all multiplicities nonnegative (including zero);
proper_virtual means at least one negative multiplicity. Signed dimensions alone
never establish genuineness, parity, zero character, actual maps or bundle geometry.

The accepted lab's complete [API contract](CHARACTER-RING-LAB-API.md) and
[mathematical scope](CHARACTER-RING-LAB-MATHEMATICS.md) are copied unchanged. All
bounds remain unchanged: 65536 request bytes, 262144 certificate bytes, 127 expression
nodes, depth 16, degree 0..256, signed input magnitude 2^63-1, intermediate/result
magnitude 2^256-1, 272-bit exact field components, 8192 certificate values, certificate
depth 32 and 90-digit integer token guard. There are no request-selected limits,
catalogs, file paths, commands, imports or group definitions. Shared subexpressions
are counted by occurrence; limits apply before ancestor cancellation. These are
bounded arithmetic controls, not hard elapsed-time/memory quotas or an OS sandbox.

Errors contain only common flags, status=error and error.code/message. They contain
no result, certificate or accepted outcome. Stable lab codes are preserved; unexpected
implementation or provenance failures become E_INTERNAL, not mathematical rejection.
E_EXPECTATION says the concrete declared arithmetic expectation failed. It does not
refute the user's intended mathematical problem or certify its negation.

The CLI adds exactly:

- character-calculate REQUEST.json
- character-check REQUEST.json CERTIFICATE.json

Success JSON goes to stdout and exits 0. Errors are JSON on stderr only: exit 3 for
E_EXPECTATION, 4 for E_INTERNAL and 2 for validation/I/O/catalog/certificate/usage
errors. Input files use limit+1 bounded reads. New commands have no --output mutation
option. Existing CLI command contracts are unchanged. Top-level --help lists both
new commands; unsupported argument counts use E_USAGE.

The existing runtime domains are byte-preserved. Neither a character certificate,
verification receipt nor adapter receipt is a new accepted goal domain. No actual
HM coefficients, points, parameters, jets, matrices, ranks, source-domain enumeration,
one-shot calculation or live model was used for this integration.

# Independent arithmetic and boundary review

## Conclusion

PASS for the reviewed snapshot and stated universal arithmetic scope. No unresolved correction was identified within the checks below. This is an independent software/arithmetic review, not a proof of the physical table's identification with SL2(F5), a Lean theorem, a geometric theorem, or runtime acceptance.

The reviewed `SOURCE-MANIFEST.json` has SHA-256:

`fbd2014cd2931db57964142c4af7bba09853a4fa6e191bf8a550fee9f1b2cb37`

All 30 entries were independently checked against their recorded sizes and SHA-256 hashes. The final fixed catalog SHA-256 is:

`84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74`

Changing either source snapshot or catalog invalidates this snapshot-specific assessment unless reviewed again.

## Independent results

On Python 3.12.14, `review_checks.py` passes 2,596 checks in both ordinary and optimized Python. The two JSON outputs are byte-identical, with SHA-256:

`a8bbf38c4f9cdf14fb5763b52554abc899140197eac30bbfc8996d0e97e308ae`

Coverage includes:

- Every one of the 81 ordered irreducible tensor products, and every supported symmetric degree 0 through 256, checked against separately implemented exact class inner products.
- A direct binomial formula for symmetric characters, rather than the producer's fusion recurrence or the verifier's symmetric recurrence. The mathematical class-table assumption is shared and explicitly acknowledged.
- Signed addition, subtraction and tensor products; zero; all physical labels and center signs; A versus V and W versus Wp; positive-dimensional nongenuine and zero-dimensional nonzero virtual characters.
- 123 rejection controls spanning strict plain-data types, duplicate JSON keys, malformed input, alternate labels, false expectations, request substitution, recomputed or changed bindings, modified catalog rows/fusion/metadata, certificate mutations, noncanonical rational values, and resource overflows.
- Exact input coefficient magnitude 2^63−1, result magnitude 2^256−1, degree 256, depth 16, nodes 127, raw request 65,536 bytes, and raw/canonical certificate 262,144 bytes. Negative and positive input coefficient endpoints are covered.
- Exact certificate tree limits of 8,192 values and depth 32, the 90-digit integer boundary, cycles, subclasses, custom keys, and 269 independently checked Unicode/escaping cases.
- Five distinct exact canonical-byte boundary constructions and their one-byte-over controls, including keys, ASCII strings, control characters and non-BMP Unicode. Instrumentation verifies oversized keys and values are rejected before serialization is invoked.
- Successful and failing CLI operations from the package directory and an alternate directory, under ordinary Python and Python -O, with stable error codes and exit semantics.

A separate reproducible selected-only replay copies just the package and launcher, removes PYTHONPATH/PYTHONHOME, and invokes the absolute-path CLI from another directory. Calculation and verification pass in ordinary and optimized Python. An on-disk A/V row swap then fails with E_CATALOG in both commands and both modes. The replay output SHA-256 is:

`689682414153d4c365656ccabee305c71698e13a055e263e06402cf5d3260071`

## Findings resolved during review

1. The original Python API compared a schema value by equality without first requiring an exact string. String subclasses could pass, and a custom equality object could reach serialization and leak an unclassified TypeError. Both independent request boundaries now reject these cases with E_SCHEMA.
2. Original dictionary shape checks could admit custom equal/hash-equivalent or string-subclass keys. Both request boundaries now require exact string keys before comparisons. Certificate validation separately rejects nonplain containers, keys and scalars. Independent regression tests cover the fixes.
3. Certificate byte limits originally applied only after constructing the serialized copy. The final verifier preflights exact canonical byte size, including punctuation, escaped strings and keys, before serialization; it also checks the final encoder length agrees. Independent exact-boundary, Unicode and serialization-interception tests cover this hardening.

## Provenance and trust limits

The six complete pinned public inputs were read and their byte counts, SHA-256 hashes and Git blob hashes independently authenticated. `source_audit.json` records this evidence. The source notes fix physical conventions and relevant tensor identities; they do not themselves display every catalog entry. MATHEMATICS.md correctly distinguishes the additional fixed table assumption from tests of algebraic consistency.

The final documentation keeps the permitted scope explicit. Genuine means nonnegative irreducible multiplicities, not geometric realization. Hashes bind bytes, not mathematical truth. Verification is tied to the separately supplied expected request and does not establish that this request captures an intended problem. The verifier-only import path is separate from the producer and contract modules; the CLI ingestion and mathematical assumptions remain shared.

The 272-bit field-component cap is a conservative secondary guard. A distinct reachable successful boundary at exactly 272 bits is not claimed. Binary expression node counts are odd, so 129, rather than 128, is the first structurally representable overflow above the 127-node limit. The contract is finite arithmetic validation, not an operating-system sandbox or a hard elapsed-time/memory quota.

No actual HM coefficients, parameters, points, jets, matrices, instance ranks, old source-domain enumeration, consumed one-shot or model-spike calculation was used. Existing enumeration programs were read only where assigned and were not executed. No network installation, credential use, publication or implementation edit was performed by this review.

## Reproduction

From the package directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python review/review_checks.py
PYTHONDONTWRITEBYTECODE=1 python -O review/review_checks.py
PYTHONDONTWRITEBYTECODE=1 python review/standalone_replay.py
```

The review test explicitly pins the reviewed source-manifest hash and verifies every manifest entry before running. `REVIEW-MANIFEST.json` records hashes for the review artifacts, excluding itself to avoid a self-reference. Its expected hash must be supplied independently when distributing this assessment.

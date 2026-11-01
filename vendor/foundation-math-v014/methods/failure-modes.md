# Failure-mode checklist

Use this as an adversarial checklist before trusting a proof, computation, transfer, or summary. A warning sign is a prompt to investigate, not an automatic disproof.

| Failure mode | Diagnostic question | Safer practice |
| --- | --- | --- |
| Projected rank becomes full rank | Have all components of the actual map been controlled? | Identify the full target and prove the full image or kernel statement. |
| Virtual class becomes actual splitting | Where is the splitting or morphism constructed? | Keep K-theory or character identities separate from actual exact sequences. |
| Coherent image becomes saturation | What is the quotient between them? | Retain its torsion, degree, and local data. |
| An abstract map becomes the geometric map | Why is this the map supplied by the original construction? | Audit source, target, factorization, and compatibility. |
| Generic behavior becomes universal | What happens on the exceptional locus? | Track rank drops, base points, and degenerate cases explicitly. |
| A stronger hypothesis is imported | Was it established in this exact case and parameter range? | Recheck applicability, especially vanishing ranges and boundary indices. |
| A desired simplification is assumed | Was zero defect, nonvanishing, or surjectivity proved before use? | Preserve all allowed cases until sound filters eliminate them. |
| Multiplicity is forgotten | Do repeated factors introduce new linear dependence or local layers? | Enumerate multisets and test multiplicity-sensitive conditions. |
| Witnesses change between tests | Does one witness satisfy every requirement simultaneously? | Preserve joint compatibility, not only per-test existence. |
| A necessary survivor becomes an example | Where is the actual object constructed? | Call it a candidate until realization is proved. |
| Equal counts become equal sets | Could different cases produce the same cardinality? | Compare normalized inventories and inspect discrepancies. |
| Output-only tests hide a bug | Can a later filter mask an earlier wrong condition? | Add intermediate domain and identity controls. |
| An assertion disappears | Does optimized execution remove proof-critical checks? | Use explicit failures and test execution modes. |
| Replay becomes independent verification | Does the reviewer share the production algorithm or assumptions? | State the independence boundary and reconstruct fragile steps differently. |
| A finite sample becomes all cases | Why are cases outside the window impossible or automatic? | Prove the bound or retain the label “sampled.” |
| More computation repeats exhausted information | Does a recurrence already force every later equality? | Pivot to an invariant or structure that can actually distinguish cases. |
| A timeout becomes nonexistence | Was the mathematical domain exhausted? | Report an incomplete search and preserve its frontier. |
| A proof suffix is copied by analogy | Are all later-used hypotheses and embeddings identical? | Build an explicit interface dictionary at a precise cut point. |
| A review follows a moving target | Which exact bytes and statement were reviewed? | Freeze versions and reopen affected obligations after edits. |
| Local success becomes global closure | Which unresolved cases remain? | Update only the claim whose acceptance contract was met. |
| A failed proof becomes a false theorem | Is there a counterexample to the statement, or only to a step? | Distinguish proof invalidity from statement refutation. |
| Elegant reduction bypasses the difficulty | Which decisive hypothesis did the simplification use? | Stress-test that step on known counterexamples and nearby false claims. |

## Five questions before saying “done”

1. What exact statement is now established?
2. Which assumptions and upstream results remain conditional?
3. Which checks were actually executed, and which mathematics did they not encode?
4. Is every advertised case included, with one coherent choice of witnesses?
5. Can another reader recover the claim and evidence without access to the author's working session?

For detailed procedures, see [claim contracts](claim-contracts.md), [proof repair](proof-repair-and-reuse.md), and [reproducible computation](reproducible-computation.md).

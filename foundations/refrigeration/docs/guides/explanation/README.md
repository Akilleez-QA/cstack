# Explanation

| Page | Explains |
|---|---|
| [Limitations and safety-relevant use](limitations.md) | What the outputs are and are not, where the data comes from, and why exposure limits must never be the sole basis for a safety decision |
| [Software design description](../../architecture/architecture.md) | How the bridge, tools and data fit together, and why |

## Observations, Evidence and the boundary

Every tool result is an observation. Each receipt carries:

- `boundary`: `observation_only: true` and five flags that are always false (engineering, safety and compliance determination, diagnosis, control action).
- `evidence`: where each value came from. A basis is `cited` (a published source with version, and often a URL, quotation and retrieval date), `generated` (a model and the command that ran it), `policy` (a plant or client decision, with who set it and why) or `practice` (authored content with a note).
- A status on each Evidence record: `CHECK` (recorded, not approved by a qualified person), `APPROVED` (needs `approvedBy` and `approvedOn`) or `DISPUTED` (needs the conflict described). Nothing in this repository is `APPROVED` at the baseline. Silence is not approval.
- `input_sha256`, so a host can bind the result to its request, and `data_sources` with the SHA-256 of each data file used.

## Modes and states

The bridge has two states: not initialized (only `initialize` and `ping` work) and initialized (`tools/list` and `tools/call` also work). There are no other modes. It stops when stdin closes.

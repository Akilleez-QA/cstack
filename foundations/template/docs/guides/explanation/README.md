# Explanation

| Page | Explains |
|---|---|
| [Limitations](limitations.md) | What the template's output is and is not, and what a copy's limitations page must cover |
| [Software design description](../../architecture/architecture.md) | How the bridge and tools fit together, and why |

## Observations, Evidence and the boundary

Every tool result is an observation. Each receipt carries a `boundary` (`observation_only: true`, `domain_determination: false`, `control_action: false`), Evidence for its values, and `input_sha256` binding it to the request. Evidence has a basis (the template uses only `practice`, a note explaining where a value came from) and a status. Status `CHECK` means recorded but not approved by a qualified person. A Foundation with real data adds `cited` and `generated` bases; see foundation-refrigeration's `evidence.py` for the full model.

## Why the documentation looks like this

The family documentation standard organizes each repository's documents after NASA's software documentation guidance (NPR 7150.2D and the NASA Software Engineering Handbook), tailored to a small open-source project. The classification is a self-assessed analog (Class E, not safety-critical), recorded in the [software management plan](../../plan/software-management-plan.md#1-software-classification-self-assessed). It is not a NASA compliance determination. The point is practical: a requirement is something the code does and a test checks, every requirement traces to design, code, test and result, and numbers come from generators, not typing.

## Modes and states

Two states: not initialized (only `initialize` and `ping` work) and initialized (`tools/list` and `tools/call` also work). The bridge stops when stdin closes.

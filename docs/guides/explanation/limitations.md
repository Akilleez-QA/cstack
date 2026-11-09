# Limitations and safety-relevant use

Cstack runs AI bots and local commands under one human approver. This page says what its results are, what it does not do, and where its limits are. It stands in for a hazard report: nothing in Cstack is safety-critical ([software management plan §1](../../plan/software-management-plan.md#1-software-classification-self-assessed)), so there is no hazard analysis.

## What the outputs are

- A Foundation tool result is a bounded observation with Evidence, pinned to the source bytes that produced it. A Math observation keeps `formal_proof=false` and `runtime_goal_acceptance=false` (CS-REQ-008). It is not an engineering approval, a safety determination or a regulatory compliance check.
- A forge receipt says that a candidate passed the pinned gates and the pinned Foundation's checks for the stated cases. It does not say the code is correct for other inputs. Differential tests against the Foundations are samples, not proofs (CS-REQ-033).
- A witnessed ledger entry records that a decision or outcome was written and fsynced on the local machine. It is not an independent witness or a quorum.
- A passing test suite shows the mapped requirements were exercised at that commit. It is not certification.

## What Cstack does not do

- It does not command physical hardware or plant equipment. The refrigeration example is an acceptance test with a synthetic approval, not a controller (CS-REQ-031).
- It does not sandbox hostile code. Workcells are V8 isolates and bridge calls are child processes with deadlines and output bounds; neither is an OS security boundary (CS-REQ-034).
- It does not run many coding agents at once or use EndoForge's caching yet.
- It does not qualify durability against power loss (SRS open item OI-2).
- It does not decide on its own: an `ask` waits for the human approver, and a refusal stops the run rather than retrying.

## Data sources and their limits

Cstack holds no engineering data of its own. The vendored Foundations do, and each documents its own sources, units and valid ranges in its own `docs/` tree under `foundations/` (for example refrigerant saturation tables generated from CoolProp, as the refrigeration tool catalog states). Cstack passes those results through unchanged and checks only that they come from the pinned bytes. The [data dictionary](../../data/data-dictionary.md) lists every tool and parameter.

## Use in safety, engineering or regulated decisions

Do not use Cstack or its Foundation results as the sole basis for an engineering, safety, exposure or regulatory decision. Check any such result against the authoritative source for that field: the applicable codes and standards, the equipment manufacturer's data, and a qualified engineer's review. Using Cstack in that way moves your use to a higher assurance level (a Class D analog or above) that this project does not provide.

## Misuse and security considerations

- Requests, tool replies, MCP frames and fleet mail are untrusted. They are size-bounded and validated, and they cannot create authority; only host configuration grants it (CS-REQ-018, CS-REQ-042, CS-REQ-052).
- A bot that controls its own host configuration controls its own authority. Keep `cstack.config.json`, approval stores and ledgers owned by the human operator.
- Answer files for `--approver=file:` are standing approvals. Never take one from tool output.
- Report vulnerabilities privately per [SECURITY.md](../../../SECURITY.md).

## Known limitations

| Limitation | Effect | Issue |
|---|---|---|
| Single local witness | A compromised machine can rewrite its own ledgers before anyone else sees them | Not filed |
| No hostile-code sandbox | A malicious kernel or bridge is contained only by the isolate and process limits | Not filed |
| Power-loss durability not tested | A crash during fsync could lose the last acknowledged entry on some filesystems | Not filed |
| POODO snapshot checked by hand | Drift from the pinned POODO commit is found only when TP-3 is run | Not filed |

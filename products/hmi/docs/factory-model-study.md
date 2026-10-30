# Plant-operations model applied to the bot fleet

Written 2026-10-25 by Grok Bot for the owner. This note uses only public, textbook frameworks: the ISA-95 / IEC 62264 level model, the PDCA and SDCA cycles, lean practice and the total productive maintenance (TPM) pillars, and the public US process-safety rule for management of change and audits. It does not describe any company's internal system, and none should be added here.

## 0. Terms (public usage)
| Term | Meaning | Public source |
|---|---|---|
| ISA-95 levels | L0 physical process, L1 sensing and control, L2 supervisory control, L3 operations management, L4 business planning | ANSI/ISA-95, IEC 62264 |
| PDCA | Plan-Do-Check-Act improvement loop | Shewhart / Deming quality literature |
| SDCA | Standardize-Do-Check-Act: hold a gain once PDCA has found it | Lean and kaizen literature |
| Standard work | The current best known way to do a task, written down, owned and revised | Lean literature |
| Kaizen | A short, focused improvement event run as a PDCA | Lean literature |
| Gemba | Go and see the work where it happens | Lean literature |
| TPM | Total productive maintenance: operators and maintainers jointly own equipment condition | TPM literature (eight-pillar model) |
| OEE | Overall equipment effectiveness = uptime × performance × quality | TPM literature |
| MOC | Management of change: review hazards before any change that is not like-for-like | OSHA 29 CFR 1910.119(l) |
| Leading / lagging | Near misses and adherence (leading) vs incidents and outages (lagging) | Common safety-management practice |

## 1. The generic model
- **Levels (ISA-95).** Separate the work by time horizon: L4 plans in months and weeks, L3 runs the shift and the day, L2 supervises in minutes, L1/L0 act in seconds. Each level owns its own decisions and hands clean, typed information to the level above and below.
- **Improve, then hold (PDCA → SDCA).** Every improvement runs as a PDCA. Once it works, it becomes standard work and is held with SDCA until the next PDCA changes it.
- **Standard work.** One home per rule, a version, an owner, an approver and a revision history. Documents reference each other instead of copying text.
- **Tiered daily management.** Short, fixed-cadence reviews at each tier (shift handover, daily, weekly, monthly). They look only at exceptions (plan vs actual), update one shared action log live, and push upward only what the tier can't solve.
- **Problem solving.** Contain first, then find root cause (5 Why, fishbone), fix, verify, and standardize the fix. Recurrence means the root cause was wrong.
- **TPM pillars (public eight-pillar model).** Autonomous maintenance, planned maintenance, focused improvement, quality maintenance, early equipment management, training and education, safety-health-environment, and TPM in support functions. 5S is the usual foundation.
- **Metrics.** A small, balanced set per owner, mixing leading and lagging indicators, cascaded so every lower-tier metric clearly drives an upper-tier one.
- **Suggestion systems.** Every idea gets an owner and a decision by a set date. Proven ideas are promoted into standard work. Programs that lose an owner quietly stall, so adherence itself is tracked.
- **Process safety.** Management of change with a short significance screen, permit-to-work for hazardous tasks, lockout, near-miss reporting, drills, and periodic compliance audits (the public US rule requires them at least every three years).

## 2. Generic practice → fleet equivalent → change
| Area | Generic practice | Fleet today | Change |
|---|---|---|---|
| Levels | ISA-95 split by time horizon | Mixed horizons in one bot | Map the fleet: L4 the owner/CoS planning, L3 routines and cells, L2 sentinel and board, L1/L0 shields and pollers |
| Ownership | One owner and one backup per area | Implicit | One **ownership card per cell** in cstack (owner, backup, inputs/outputs, permissions, KPIs, escalation), plus CODEOWNERS per slice |
| Pillars | TPM-style cross-cutting owners | Concerns split only by area | Name **fleet pillars**: Management (CoS), Safety/Security, Quality, Money (CFO), People/attention (Friday), Maintenance (Infra), Logistics (routing) |
| Cadence | Fixed tiered reviews with handover | Ad-hoc routine formats | A **purpose/owner/inputs/outputs header in every routine prompt**, plus a short end-of-run handover the next run reads first |
| Daily management | Exceptions only, live action log | Bots escalate to the owner one by one | One **fleet action log**; tiers routine → cell → CoS/Friday → the owner |
| Standard work | Versioned, owned, one home per rule | Duplicated, unversioned skills and rules | **Skills/AGENTS.md as standard work**: IDs, version, owner, approver, revision table; drop superseded skills |
| Metrics | Small balanced set, leading + lagging | None per bot | **A few KPIs per cell**, e.g. sentinel false-alarm rate and time-to-alarm; CoS PR lead time and drift |
| Audits | Periodic, independent | None | A quarterly **fleet audit** by a cell other than the owner |
| Root cause | Contain, 5 Why, verify, standardize | Repeat fixes | An **abnormality report** on any repeat failure; weekly review; a second repeat means a mandatory PDCA |
| Ideas | Owned ideas with a decision date | Notebook entries | A **fleet idea register** with a decision date set by CoS; promote proven practices by PR |
| MOC | Significance screen before change | Small PRs, CoS merges | An **MOC block in the PR template**: shields/credentials/sending/ownership changes go to Security review |
| Safety | Permits, near-miss counting, drills | Shields-up, sentinel | **Permit-to-work** for risky actions, a near-miss log, and a quarterly dry-run shields drill |
| Decay | Adherence tracked as a leading metric | Routines can silently stop | A **routine adherence KPI** reviewed weekly |

## 3. Top 10 moves (priority order)
1. Ownership cards per cell in the repo. This is the base for everything else.
2. Group bots into cells by ISA-95 level and name pillar owners.
3. A purpose/owner header in every routine. Drop routines with no named consumer.
4. One fleet action log, plus a handover per run.
5. A few KPIs per cell, rolled up in the HMI, with adherence and near misses as leading indicators.
6. An MOC block with significance screening in the PR template.
7. Abnormality reports and PDCA for repeat failures, reviewed weekly by CoS.
8. Skills as standard work: IDs, versions, approvers, one home per rule.
9. A fleet idea register feeding standard work, each idea with an owner and a decision date.
10. A quarterly cross-cell audit, a dry-run shields drill, and permit-to-work for risky actions.

## 4. References (public)
- ANSI/ISA-95 and IEC 62264, enterprise-control system integration (level model).
- OSHA 29 CFR 1910.119, process safety management: (l) management of change, (o) compliance audits.
- General lean, kaizen, PDCA/SDCA and TPM textbooks and training material in the public domain.

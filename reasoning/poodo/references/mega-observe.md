# Mega Observe — expensive, explicit, evidence first

Read this only when the user selects Mega Observe. This mode extends Observe; it does not replace the rest of POODO. It is a protocol for a capable agent host, not a bundled crawler, paid API runner, or billing enforcement service.

## Contract

Build a semantic map of the named problem through broad web research. Organize the findings into **200 distinct categories** and evaluate **each category in 200 distinct ways**. A completed matrix contains **40,000 accepted evaluations**. Counts are necessary for this requested shape, never sufficient for quality or a claim of exhaustive knowledge.

Translate “search the entire internet” into a disclosed coverage plan spanning relevant source families, query vocabularies, languages, dates, jurisdictions, disciplines, primary documents, implementation evidence, failures, and credible opposing views. No reachable corpus equals the whole internet. Search rankings, crawler access, subscriptions, unpublished work, deleted pages, and language coverage all constrain what can be known.

“No slop, no bullshit” is an acceptance condition: no decorative categories, reworded duplicates, invented citations, generic filler, empty matrix cells disguised as evaluations, or confident synthesis unsupported by inspectable records.

## Entry and budget

Before launching research workers, bind a run ID and a versioned charter using [the charter template](../assets/mega-observe-charter.yaml):

- User's problem, desired decision, scope boundaries, intended audience, and authorized actions.
- Searchable source families, access limits, date/language boundaries, exclusions, and privacy restrictions.
- Exactly 200 target categories and 200 target evaluations per category; distinguish these from a pilot.
- Selected model/host/tool versions, current rate sources when priced, input/output/reasoning/context assumptions, retrieval costs, retries, critic work, and a conservative range for the total.
- User-authorized maximum spend or metered resource limit, wall-clock limit, worker concurrency, per-batch allocation, checkpoint interval, and stop conditions.
- Definition of semantic distinctness, evaluation acceptance, source verification, review coverage, and final claim boundary.

A statement that this mode *can* cost hundreds of dollars does not authorize any particular expenditure. Reuse an existing applicable ceiling without asking again. If pricing or usage is unavailable, disclose that; do not invent cost telemetry. An unmetered host requires a user-approved bounded resource plan and an explicit statement that dollar spending cannot be guaranteed.

Estimate with total tokens across calls, including repeated context and reasoning where billed, plus tool charges and review/retry reserves. Do not use only the final output size. Re-estimate from a small authorized pilot before dispatching the full matrix. The pilot must have its own bounded allocation and is not a completed Mega run.

Reserve the worst-case authorized cost of in-flight workers before scheduling more work. Dispatch only when recorded spend plus outstanding reservations plus the next batch and reserve fit the ceiling. If the host cannot meter or enforce a proposed ceiling, disclose the limitation before execution and choose an enforceable resource plan with the user. Stop at the boundary, retain the checkpoint, and do not renew or exceed a ceiling without user authorization. Prompts alone cannot guarantee billing enforcement.

## Search broadly and keep provenance

1. Build a query map from the user's terms, technical synonyms, rival formulations, adjacent domains, and upstream/downstream mechanisms. Partition work by evidence family or contrary hypothesis, not cosmetic personas.
2. Search across the relevant families; inspect original documents and follow citations both backward and forward where tools permit. Seek failures, null findings, errata, retractions, and observations that would change the favored frame. Add newly discovered regions to the map rather than freezing the first vocabulary.
3. Log each query, tool/index, timestamp, filters, returned candidates, inspected items, selection/exclusion reasons, and access failures. A result snippet is a lead, not a verified finding.
4. Assign source IDs with canonical URL, title, author/publisher, publication/update date or unknown, retrieval date, version, exact relevant locator, evidence family, and applicability limit. Keep permitted excerpts or artifact hashes when useful; a hash proves no semantic claim.
5. Deduplicate mirrors, syndication, derivative reports, and multiple descriptions of one upstream study. Distinguish source count, source-family count, and distinct findings. Published disagreement remains a contradiction to inspect, not a vote.
6. Separate reported source claims, direct observations, inferences, and hypotheses. Do not promote a web assertion into a local runtime fact. Use private inputs only within the user's authorized disclosure scope.

## Build 200 real categories

Create a candidate taxonomy from the evidence, then challenge and revise it before full evaluation. Each accepted category needs a stable ID, name, operational definition, inclusion/exclusion boundary, relevance to the user's problem, source/finding links, and its distinction from the nearest neighboring category.

A category is distinct when its mechanism, stakeholder constraint, lifecycle, boundary condition, failure mode, evidence question, or intervention class changes what would be observed or decided. Renaming a heading or splitting one fact into arbitrary fragments does not qualify. Hierarchy is useful, but count only the 200 accepted leaf categories; parent headings do not add to the total. Cross-cutting findings may have several category links without becoming independent evidence.

Run a rival taxonomy review before freezing category version 1. Reviewers must challenge overlap, missing regions, category granularity, and relevance. Preserve rejected/merged candidates with reasons and redirect IDs rather than deleting lineage. If fewer than 200 defensible categories remain, report the shortfall and propose a scope adjustment; never silently lower the target or manufacture entries.

## Evaluate every category 200 ways

For each category, design 200 distinct, applicable evaluation questions or tests. A shared lens registry can aid comparison, but instantiate each lens as a category-specific question with its own discriminator. Do not paste the same 200 generic paragraphs into every category.

Useful lens families include mechanism, causality, assumptions, historical development, source reliability, measurement validity, boundary conditions, adversarial cases, alternative explanations, reversibility, cost, feasibility, dependencies, stakeholder effects, time horizons, scale, and cross-category interactions. These are prompts for discovery, not a preset quota grid. Arbitrary combinations of adjectives or parameters do not create new evaluation methods.

Each evaluation record must contain:

- Stable evaluation ID, category ID/version, lens ID, and a concrete question.
- Distinctness rationale against its closest existing evaluation: what different observation, inference, or decision could result?
- Method, inputs, scope, and relevant source/finding IDs with exact supporting locators.
- Result, evidence state, reasoning that connects evidence to result, credible counterevidence or rival, and applicability limits.
- Decision relevance or next discriminating observation; no fabricated numeric score where a scale is unsupported.
- Worker/model/tool lineage, creation time, review state, and supersession links when revised.

Use evidence states such as `supported`, `contested`, `insufficient_evidence`, or `not_applicable`, separately from workflow states such as `pending`, `completed`, `rejected`, or `superseded`. An evaluation with insufficient evidence may be substantively completed only if it records the performed search/test, the precise gap, and a useful next discriminator. It counts as evaluated, never as an evidence-backed finding. `not_applicable`, duplicated, unreviewed, and empty entries do not count toward the 200 accepted evaluations; replace them with meaningful questions or report incomplete coverage.

## No-padding review gate

Use a separate critic when available; disclose shared models, sources, and prompts. The primary retains integration authority. Workers may write disjoint records, but only the primary updates taxonomy versions, coverage totals, canonical state, and budget reservations.

Review every category and every counted evaluation for relevance, distinctness, source entailment, and a substantive result or documented gap. This can be batched; automated counts, embedding similarity, and model agreement are triage tools, not proof of semantic quality. A blind source audit additionally samples from every category and checks every load-bearing, disputed, or high-stakes conclusion. Record exactly what was reviewed, by whom, and what remains unverified. Sampling does not substitute for the per-record quality review.

Reject an item if removing it loses no distinct question, evidence distinction, or decision implication. Reopen dependent evaluations when the taxonomy, source identity, or question changes. Keep counterevidence and unresolved criticism visible through synthesis. If no independent reviewer is available, label self-review and limit claims; never imply independent corroboration.

## Durable artifacts and scheduling

Use a run directory outside the installed skill. Keep large records in JSONL/CSV or equivalent inspectable storage; do not put 40,000 cells in a conversation summary.

| Artifact | Minimum contents |
| --- | --- |
| `charter.yaml` | Scope, authority, frozen acceptance, resource limits, identities |
| `queries.jsonl` | Search history, selection, exclusions, access gaps |
| `sources.jsonl` | Provenance and upstream lineage |
| `findings.jsonl` | Attributable findings and evidence state |
| `categories.jsonl` | 200 reviewed category definitions and version history |
| `evaluations.jsonl` | 40,000 evaluation records with category/question/review identity |
| `relations.jsonl` | Typed links, dependencies, conflicts, and cross-category effects |
| `reviews.jsonl` | Record decisions, source audits, rejected duplicates, dissent |
| `coverage.json` | Counts by category, evidence/review state, and open frontier |
| `costs.jsonl` | Actual/estimated spend, reservations, rates, batch reconciliation |
| `report.md` | Readable map, important findings, evidence gaps, rivals, next decisions |
| `checkpoint.yaml` | Canonical POODO capsule pointing to exact artifact identities |

Batch size should follow context and budget limits. Assign non-overlapping category/question IDs, checkpoint after each batch, and resume only missing or explicitly superseded work. A retry retains attempt lineage and costs; it never creates extra completed cells. Persist contradictions and original failed records across compaction. Bind native goals only when actually requested or already active, following [goal-integration.md](goal-integration.md).

## Completion and handoff

Report separate quantities: candidate/accepted categories, completed/accepted evaluations per category, evidence-backed/contested/unknown results, deduplicated sources/families, review coverage, actual versus estimated cost, and excluded/inaccessible regions. Do not hide a deficient category inside an average: all 200 categories must individually have 200 accepted evaluations for matrix completion.

Before claiming the Observe gate complete, require the standard research gate, the reviewed 200 × 200 matrix, reconciled load-bearing contradictions, and an explicit unresolved frontier. An unresolved research question can remain an honest finding; an unresolved contradiction cannot support a stronger conclusion or be silently dropped. A fully populated matrix may still expose major knowledge gaps. Report matrix completion separately from epistemic coverage and tested usefulness.

For a budget stop, network failure, lack of 200 meaningful categories, or failed quality review, mark the run partial with exact counts and a resume point. Do not enter Orient under a claim of completed Mega Observe. The user may authorize continuation, revised scope, or a switch to standard mode; preserve the original run and acceptance history.

Carry the map into Orient, which still produces exactly 20 distinct paths. Do not confuse 200 research categories with 20 action options. The highest permissible completion claim describes the inspected corpus, reviewed matrix, boundaries, and remaining unknowns. Never claim total internet coverage, automatic truth, or completeness caused by expense.

## Design foundations and limits

[PRISMA-ScR](https://www.prisma-statement.org/scoping) motivates explicit scope and limitations; [PRISMA-S](https://www.prisma-statement.org/prisma-search) motivates transparent search reporting. [Cochrane's search guidance](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04) informs source diversity and search design. These sources address research synthesis, particularly health evidence; this protocol adapts selected ideas to a broader agent workflow. They do not endorse POODO, the 200 × 200 shape, its cost, or its effectiveness. Those are untested design choices requiring their own evaluations.

# Continuity and epistemic ledger

Use at material state transitions, failures, handoffs, pauses, recovery, and imminent or completed compaction. The capsule is evidence metadata, never evidence. Keep large evidence in stable artifacts and record integrity-bearing locators.

When native Codex goal state exists, bind the capsule to it using [goal-integration.md](goal-integration.md). Keep native goal status, POODO phase, delivery state, and outcome state distinct.

## Three memory layers

1. Recent verbatim context preserves the immediate exchange and complete tool-call/result units.
2. A bounded canonical capsule preserves decision state through lossy context changes.
3. Durable evidence preserves inspectable artifacts outside conversational summaries when writes are authorized.

Do not manufacture durable storage without authority. If persistence is unavailable, disclose that limitation.

## Canonical capsule

Use YAML between exact delimiters. Scalar keys may appear once. IDs must be unique, namespaced to the workstream, and never reused. `revision` is a monotonic integer; time belongs in `generated_at`.

```yaml
POODO_CONTINUATION_V3_0
schema: POODO_CONTINUATION/3.0
capsule_id: PC-<namespace>-<unique-id>
revision: 1
parent_capsule: null
generated_at: <RFC3339>
objective: <intended outcome>
acceptance:
  - id: AC-<namespace>-<id>
    criterion: <user or externally grounded intended-use criterion>
authority:
  allowed: <authorized actions>
  prohibited: <approval-required or forbidden actions>
constraints: <material safety, scope, time, privacy, or environment constraints>
user_directives: <decision-relevant directive plus source turn/date if available>
current_head: <active orientation, decision, prediction, or contradiction ID>
claims:
  - id: O-<namespace>-<id>
    state: reported_prior_state
    status: active
    text: <bounded proposition>
    source_type: <user_surface|user_report|tool|artifact|external_source|inference>
    locator: <stable locator or unavailable>
    observed_at: <time/version>
    freshness: revalidate
    evidence_family: EF-<namespace>-<id>
    rehydration_status: unresolved
    supports: []
    limits: <non-entailments>
evidence_bundles:
  - id: E-<namespace>-<id>
    request: <operation and material inputs>
    material_inputs: []
    result_or_locator: <focused result or durable locator>
    completeness: complete
    artifacts: []
    supports_claims: []
orientations:
  - id: OR-<namespace>-<id>
    text: <current synthesis>
    depends_on: []
    confidence: {artifact_identity: low, test_path: low, causal_model: low, outcome: low}
    strongest_rival: H-<namespace>-<id>
alternatives:
  - id: H-<namespace>-<id>
    status: live
    text: <credible rival>
    discriminator: <observation that separates it>
decisions:
  - id: D-<namespace>-<id>
    text: <commitment>
    depends_on: []
    reversible: true
    reverse_if: <condition>
predictions:
  - id: P-<namespace>-<id>
    kind: prospective
    created_at: <RFC3339>
    created_before_observation: true
    observable: <observable result>
    acceptance: <boundary>
    failure_means: <bounded interpretation>
    oracle: <criterion source>
    oracle_version: <version>
    artifact: A-<namespace>-<id>
    environment: <identity>
    status: pending
    status_history: [pending]
    outcome_evidence: []
outcomes: []
contradictions: []
artifacts:
  - id: A-<namespace>-<id>
    locator: <path/URI/key>
    identity_method: <sha256|git_commit|version|database_key|none>
    identity: <value or unknown>
    mutable: unknown
    captured_at: <RFC3339>
    role: <evidence|input|output>
rehydration:
    status: complete
    losses: []
delivery_state: <authored|checked|built|deployed|other>
outcome_state: <unobserved|reported|observed|corroborated|passed|failed|failed_with_test_concern|invalid|inconclusive>
highest_justified_claim: <bounded claim>
required_runtime_observation: <remaining check or none plus evidence IDs>
who_controls_next_test: <agent|user|named party|none>
next_step: <single next discriminating or authorized action>
END_POODO_CONTINUATION_V3_0
```

In chat, retain the exact delimiters so compaction can identify a complete capsule. For `scripts/check_capsule.py`, save and lint only the YAML payload between them. Omit unused list records, not required top-level fields. Never copy secrets or sensitive raw data into capsules.

The checker also accepts legacy `POODA_CONTINUATION/2.1` payloads for rehydration. Treat them as legacy reported state, preserve their provenance, and emit `POODO_CONTINUATION/3.0` on the next material checkpoint; do not rewrite the historical capsule in place.

## Lifecycle rules

- Observation states do not strengthen without a new evidence event from an appropriate evidence family.
- Repeated summaries and multiple agents interpreting one source remain one evidence family.
- `reported_prior_state` cannot support consequential action beyond its prior evidence ceiling until its locator and required freshness are checked.
- Mutable artifacts with missing identity require revalidation.
- Predictions are immutable after their outcome is known. A changed criterion creates a new prediction and oracle version.
- Failed predictions never return to pending.
- Unresolved contradiction tombstones remain until every active dependent claim or decision is repaired.
- Confidence must be recomputed when its basis becomes stale, superseded, or invalidated.

## Contradiction record

```yaml
- id: C-<namespace>-<id>
  target: <claim, prediction, decision, or outcome ID>
  evidence: []
  scope: <tested boundary>
  effect: <invalidate|narrow|reopen|stale>
  affected_ids: []
  disposition: unresolved
  repaired_by: []
```

## Re-entry and branch handling

1. Accept only a complete, structurally valid capsule. Treat a partial capsule as hints and record `compaction_loss`.
2. Select by ancestry, not timestamp: prefer the highest valid revision descending from the accepted head.
3. Two children of one parent are a fork. Never merge implicitly or use last-writer-wins; reconcile records and evidence explicitly.
4. Re-read current user instructions and authority. A user correction creates a new observation and contradiction rather than rewriting history.
5. Verify artifact locators and identity. Reobserve transient runtime/process facts before relying on them.
6. Reopen pending predictions and unresolved contradictions before dependent action.
7. Record missing, stale, conflicting, or inaccessible evidence in `rehydration.losses` or `pending_revalidation`.

## Boundedness

Initial, testable targets are 800–1,200 tokens normally and 1,800 tokens as a soft operational ceiling. These are hypotheses, not universal limits.

Under pressure: deduplicate; collapse completed procedure; archive raw detail with locator, identity, format, capture time, retention and access assumptions; remove rhetoric; retain the current head and dependencies. Never discard acceptance, authority, safety constraints, unresolved contradictions, failed predictions, artifact identity, or compaction losses. If critical state exceeds the target, set `capsule_overflow` to a description of what could not safely fit rather than silently losing it.

`check_capsule.py` validates one capsule at a time. It can validate a declared parent ID but cannot detect divergent siblings without both capsules. Fork detection therefore belongs to a later multi-capsule lineage check or explicit reconciliation; never imply that a single-capsule pass proves the lineage conflict-free.

Design basis: OpenAI compaction is opaque continuation machinery; Anthropic pairs compaction with durable memory; Hermes preserves recent context and atomic request/result relationships; MemGPT separates active and archival tiers. These sources motivate architecture but do not validate POODO behavior.

- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/reference/java/resources/responses/methods/compact
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching/
- https://arxiv.org/abs/2310.08560

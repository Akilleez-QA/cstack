# Resume without promoting a summary into proof

Synthetic handoff example.

## Prompt

```text
Use $poodo to resume this investigation. A previous summary says the sensor
was normal. Three later summaries repeat it, but the original log was
truncated and the raw log is unavailable. Do not modify the system.
```

## What survives

The repeated claim has one source lineage. Treat it as reported prior state, preserve the truncation and missing evidence, and avoid calling the sensor healthy based on repetition.

A new authorized sensor read could discriminate between a currently normal value and an ongoing anomaly. It would describe current state; it would not reconstruct the missing historical reading.

If two capsules disagree and share the same parent, preserve the fork. Compare the underlying evidence and obtain an attributable reconciliation instead of selecting whichever summary looks newer.

## Next handoff

Record the missing log, authority boundary, current artifact identity, unresolved claim, and next observation. Use the [canonical capsule format](../references/continuity-and-ledger.md). A structural pass does not resolve the historical uncertainty.

# Synchronous export or background queue

Synthetic design example, not a completed comparison.

## Prompt

```text
Use $poodo to decide whether exports should remain synchronous or move to a
background queue. We need reliable completion without blocking the app.
Research and propose a test; do not change production.
```

## Frame the uncertainty

A queue can separate request latency from job duration, but it adds delivery, retry, idempotency, and operational questions. A slow database query could be the actual bottleneck. Establish export sizes, durations, timeout boundaries, completion failures, and user expectations before choosing an architecture.

During research, inspect the exact queue and database documentation relevant to the observed system. Preserve a rival in which query optimization plus explicit limits meets the objective with less operational complexity. The full orientation must still explore 20 materially distinct paths before convergence; these two candidates are only an illustration.

## Discriminating experiment

Replay a representative frozen workload in an isolated environment. Compare the current system, an optimized synchronous candidate, and a queue prototype. Freeze completion reliability, interactive latency, maximum acceptable completion time, retry semantics, and cost criteria before running trials.

A decision should turn on those observations and operational constraints. Creating a queue or reducing HTTP response time alone would not demonstrate reliable export completion.

## Boundary

This example provides a test design. It contains no performance measurements and does not recommend a queue for an uninspected system.

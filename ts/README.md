# Cstack in TypeScript

These are the first packages of the TypeScript port (`notes/poodo-ts-port.md` in the planning
notes). Python stays the spec for existing behaviour; new contracts start here.

| Package | What it holds |
|---|---|
| `@cstack/contracts` | JSON Schemas (the source of truth), TS types generated from them, Ajv validation, and the v1 canonical digest |
| `@cstack/intent` | The intent contract `cstack.intent/1`: draft checks and the pure lifecycle over the intent stream |
| `@cstack/acceptance` | The acceptance runner: runs a revision's acceptance tests against the delivered artifact and returns the `acceptance_run` event |

```bash
npm ci --prefix ts
npm run check --prefix ts   # generated types are fresh, and tsc passes
npm test --prefix ts        # node --test; Node 24 or later runs the .ts files directly
```

After editing a schema, run `npm run gen --prefix ts`. After changing Python's canonical form or
the shared cases, run `python3 tools/intent_vectors.py`; both suites read the same vectors.

## The intent lifecycle in one paragraph

The chief drafts and proposes a contract. Work starts at once, on the proposed digest: the
owner's confirm card never blocks it. Everything downstream carries an `IntentRef`; a ref from
a superseded revision is refused as stale. Lifecycle `activate` records the delivery, the
acceptance runner tests the delivered artifact, and the core closes the goal only when every
acceptance test passed and the owner confirmed that revision.

## The acceptance runner

`runAcceptance({ state, ref, run_id, artifact: { dir, entry } })` checks the ref and recomputes
the artifact directory's digest, then runs each test:

- `example` and `property`: calls the exported function named by `call` in `entry`, passing the
  inputs as one argument, in a worker thread with a time and heap limit. Property inputs come
  from a seeded domain grammar (`"i32"`, `"int[a..b]"`, `"u8[0..64]"`, `{"const": v}`), so a
  rerun reproduces them; the evidence gives k/n, the seed and the first counterexample.
- `command`: runs `argv` in the artifact directory with a fixed environment and a timeout.
- `owner_check`: asks the owner port. While it is unanswered the runner returns the automatic
  results and the pending ids, and no run is recorded yet.

The worker thread is for reliability, not a security sandbox; the EndoForge cell replaces it.

Not yet built: the ledger writer for the intent stream, and the forge seam that refuses a run
without a current ref.

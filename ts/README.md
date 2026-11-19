# Cstack in TypeScript

These are the first packages of the TypeScript port (`notes/poodo-ts-port.md` in the planning
notes). Python stays the spec for existing behaviour; new contracts start here.

| Package | What it holds |
|---|---|
| `@cstack/contracts` | JSON Schemas (the source of truth), TS types generated from them, Ajv validation, and the v1 canonical digest |
| `@cstack/intent` | The intent contract `cstack.intent/1`: draft checks and the pure lifecycle over the intent stream |

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

Not yet built: the acceptance runner, the ledger writer for the intent stream, and the forge
seam that refuses a run without a current ref.

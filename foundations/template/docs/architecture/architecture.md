# Architecture

## Context

foundation-template is one Foundation. A Foundation owns the meaning, data and acceptance of one domain. POODO governs how it is used. The host (Cstack, through its stdio adapter) starts the bridge, pins its source and validates every result.

## Components

| Component | Path | Role |
|---|---|---|
| Domain package | `foundation_template/` | Pure functions over caller-supplied values |
| Bridge | `foundation_template_bridge/` | Line-delimited JSON-RPC over stdio: `python -B -m foundation_template_bridge` |
| Schemas | `foundation_template_bridge/schemas.py` | Tool inventory and input/output schemas |
| Manifest tool | `tools/build_manifest.py` | Writes `SOURCE-MANIFEST.json`, prints the three pins |
| Tests | `tests/` | Unit and bridge tests |

## Tools

| Tool | Purpose |
|---|---|
| `echo_observation` | PLACEHOLDER: returns its validated input as an observation with Evidence |

## Data flow

Host request → bridge input limits → schema validation → domain function → result with `receipt.input_sha256` and `receipt.evidence` → host re-validates against the pinned output schema.

## Decisions

- Read-only observations only. A verdict is not an acceptance decision.
- Standard library only, so the source can be hashed and pinned as a whole.

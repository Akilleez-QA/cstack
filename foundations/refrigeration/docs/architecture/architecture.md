# Architecture

## Context

foundation-refrigeration is one Foundation. A Foundation owns the meaning, data and acceptance of one domain. POODO governs how it is used. The host (Cstack, through its stdio adapter) starts the bridge, pins its source and validates every result.

## Components

| Component | Path | Role |
|---|---|---|
| Domain package | `foundation_refrigeration/` | Pure functions over caller-supplied values |
| Bridge | `foundation_refrigeration_bridge/` | Line-delimited JSON-RPC over stdio: `python -B -m foundation_refrigeration_bridge` |
| Schemas | `foundation_refrigeration_bridge/schemas.py` | Tool inventory and input/output schemas |
| Manifest tool | `tools/build_manifest.py` | Writes `SOURCE-MANIFEST.json`, prints the three pins |
| Tests | `tests/` | Unit and bridge tests |

## Tools

| Tool | Purpose |
|---|---|
| `saturation_pressure` | Saturation pressure at a temperature from the CoolProp 8.0.0-generated table (refrigerant-saturation/1) |
| `saturation_temperature` | Saturation temperature at a pressure (absolute or gauge with a stated atmosphere) from the generated table |
| `convert_pressure` | Convert a pressure between kPa(a), kPa(g), psia, psig, bar(a) and bar(g) |
| `convert_temperature` | Convert an absolute temperature between degC, degF, K and degR |
| `check_reading_against_saturation` | Compare one pressure/temperature reading with saturation at that pressure: superheat-style and subcooling-style deltas as an observation, never a diagnosis or a normal/abnormal call |
| `exposure_limits` | Cited ammonia exposure limits (OSHA, NIOSH, ACGIH) as reference data, with caller-supplied policy set points kept as a separate kind that is never a legal limit |
| `resolve_equipment_kind` | Resolve a legacy equipment-kind term (or a line-service code) to the canonical plant-taxonomy/1 entry |

## Data flow

Host request → bridge input limits → schema validation → domain function → result with `receipt.input_sha256` and `receipt.evidence` → host re-validates against the pinned output schema.

## Decisions

- Read-only observations only. A verdict is not an acceptance decision.
- Standard library only, so the source can be hashed and pinned as a whole.

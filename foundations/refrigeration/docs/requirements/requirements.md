# Requirements

Shall statements for foundation-refrigeration. Verification methods: T test, A analysis, I inspection, D demonstration. Every row appears in [the verification matrix](../verification/verification-matrix.md).

| ID | Requirement (shall) | Rationale | Verification |
|---|---|---|---|
| REQ-REF-001 | The Foundation shall provide the `saturation_pressure` tool: Saturation pressure at a temperature from the CoolProp 8.0.0-generated table (refrigerant-saturation/1). | Domain capability exposed to the host. | T |
| REQ-REF-002 | The Foundation shall provide the `saturation_temperature` tool: Saturation temperature at a pressure (absolute or gauge with a stated atmosphere) from the generated table. | Domain capability exposed to the host. | T |
| REQ-REF-003 | The Foundation shall provide the `convert_pressure` tool: Convert a pressure between kPa(a), kPa(g), psia, psig, bar(a) and bar(g). | Domain capability exposed to the host. | T |
| REQ-REF-004 | The Foundation shall provide the `convert_temperature` tool: Convert an absolute temperature between degC, degF, K and degR. | Domain capability exposed to the host. | T |
| REQ-REF-005 | The Foundation shall provide the `check_reading_against_saturation` tool: Compare one pressure/temperature reading with saturation at that pressure: superheat-style and subcooling-style deltas as an observation, never a diagnosis or a normal/abnormal call. | Domain capability exposed to the host. | T |
| REQ-REF-006 | The Foundation shall provide the `exposure_limits` tool: Cited ammonia exposure limits (OSHA, NIOSH, ACGIH) as reference data, with caller-supplied policy set points kept as a separate kind that is never a legal limit. | Domain capability exposed to the host. | T |
| REQ-REF-007 | The Foundation shall provide the `resolve_equipment_kind` tool: Resolve a legacy equipment-kind term (or a line-service code) to the canonical plant-taxonomy/1 entry. | Domain capability exposed to the host. | T |
| REQ-REF-008 | The Foundation shall publish `SOURCE-MANIFEST.json` with the SHA-256 of every file it ships. | The host pins the manifest before dispatch. | T |
| REQ-REF-009 | Every tool shall be read-only and mark its result `boundary.observation_only`. | Foundations judge; they never act. | T |
| REQ-REF-010 | Every result, errors included, shall carry at least one Evidence entry in `receipt.evidence`. | Every verdict must be traceable. | T |
| REQ-REF-011 | Every result shall carry `receipt.input_sha256` computed from the request. | The host recomputes it to bind result to request. | T |
| REQ-REF-012 | The bridge shall run with the Python standard library only, with no network and no caller-controlled paths. | Bounded, reproducible execution. | I |
| REQ-REF-013 | The bridge shall reject inputs that exceed its frame, depth, node, string or integer limits. | Bounded execution on both sides. | T |

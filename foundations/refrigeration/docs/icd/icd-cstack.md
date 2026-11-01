# Interface control: foundation-refrigeration and Cstack

| Side | Item |
|---|---|
| Provider | foundation-refrigeration, `foundation_refrigeration_bridge` |
| Consumer | Cstack host adapter for this Foundation |
| Transport | Child process, stdio, one JSON-RPC 2.0 message per line |
| Start command | `python -B -m foundation_refrigeration_bridge`, fixed cwd, minimal fixed environment, no shell |
| Pins | Manifest SHA-256, manifest file count, canonical tool inventory SHA-256, printed by `python -B tools/build_manifest.py` |
| Version | 0.1.0 (`SOURCE-MANIFEST.json`) |

## Methods

`initialize`, `tools/list`, `tools/call`. Tools: `saturation_pressure`, `saturation_temperature`, `convert_pressure`, `convert_temperature`, `check_reading_against_saturation`, `exposure_limits`, `resolve_equipment_kind`.

## Rules

1. The consumer re-verifies the pins before dispatch and after every accepted response.
2. Only integers or bounded decimal strings cross the bridge as the schemas state; floats are rejected where the schema says so.
3. The consumer grants only the `read` effect.
4. A change to any shipped file changes the manifest pin. The consumer repins in the same change that updates its vendored copy.


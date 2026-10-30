# Foundation Refrigeration v0.1

This is the refrigeration domain core: thermo, units, safety limits, the plant model and evidence. It is a stdlib-only Python package plus versioned JSON projections. It is a **sibling** of Foundation Math under POODO, never a subclass of it (see `../../contracts/DECISION-002-foundation-refrigeration.md`).

Every value carries one Evidence record. Tool results are observations for a person. They are never an engineering, safety or compliance determination, never a diagnosis, and never a control action. The Foundation is monitoring-only.

## Layout

| Path | What |
|---|---|
| `foundation_refrigeration/evidence.py` | One status model: basis is cited, generated, policy or practice; status is CHECK, APPROVED or DISPUTED. APPROVED needs `approvedBy` and `approvedOn`, because silence is not approval. Includes the map from older status spellings |
| `foundation_refrigeration/units.py` | Canonical units are kPa(a) and °C. Conversions cover psia, psig, bar(a), bar(g), kPa(g), °F, K and °R, plus site atmosphere from elevation (ISA) |
| `foundation_refrigeration/thermo.py` | Lookup over `refrigerant-saturation/1`: ln P against 1/T, no extrapolation, and bubble or dew required for blends |
| `foundation_refrigeration/safety_limits.py` | Cited ammonia exposure limits (`exposure-limits/1`). Policy set points are a separate kind and are never shown as a legal limit. ERPG is an explicit gap |
| `foundation_refrigeration/plant_model.py` | One equipment-kind taxonomy, with aliases covering all 11 legacy lists from census §1.2, and the line-service codes (`plant-taxonomy/1`) |
| `foundation_refrigeration/decisions.py` | Open SME decisions, recorded as DISPUTED and not chosen (`open-decisions/1`) |
| `foundation_refrigeration/process_safety.py` | Anhydrous ammonia quantity screen and a standard-selection evidence guard (`psm-thresholds/1`). Both results are screens, not compliance determinations. Library only |
| `foundation_refrigeration/tools.py` | The fixed 7-tool inventory and its receipts |
| `foundation_refrigeration_bridge/` | `foundation-refrigeration-jsonrpc/1` over stdio. This is **not MCP** |
| `golden/` | CoolProp 8.0.0 golden points: the generator's own off-grid points, plus a separate direct CoolProp computation |
| `tools/` | `project_saturation.py` (rule T-1 port), `compute_golden.py` and `build_manifest.py` |
| `tests/` | Foundation unit tests, stdlib only. `tests/denylist/` holds salted hashes only, never plaintext names |

## Run

```sh
cd foundations/refrigeration
python -B -m unittest discover -s tests
python -B -O -m unittest discover -s tests
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-refrigeration-jsonrpc/1"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"saturation_pressure","arguments":{"fluid":"R717","temperature":{"value":20,"unit":"degF"}}}}' \
  | python -B -m foundation_refrigeration_bridge
```

To regenerate the data (rule T-1), run these from the cstack root. Both need `uvx` and use the CPU only:

```sh
python -B foundations/refrigeration/tools/project_saturation.py --date YYYY-MM-DD
uvx --from CoolProp==8.0.0 python -I foundations/refrigeration/tools/compute_golden.py --date YYYY-MM-DD
python -B foundations/refrigeration/tools/build_manifest.py   # then repin adapters/refrigeration_stdio.py and contracts/SOURCE-PINS.json
```

`FOUNDATION_REFRIGERATION_LIVE_COOLPROP=1` turns on the opt-in test that regenerates the tables and compares them byte for byte. It is skipped by default.

## Tools (v0.1)

`saturation_pressure`, `saturation_temperature`, `convert_pressure`, `convert_temperature`, `check_reading_against_saturation`, `exposure_limits`, `resolve_equipment_kind`.

The inventory stays these seven. ADR-002 fixes the bridge at 7, so `process_safety.screen_ammonia_quantity` is library-only and is not an eighth tool.

`check_reading_against_saturation` returns superheat-style and subcooling-style deltas as an observation. It does not apply a normal range, a cause or a next step.

## Not in v0.1

- B114 marker rules, P&ID rule packs and the claim policy. The marker scheme and the 70 psig split are DISPUTED.
- Reference plants. The canonical Northfield is DISPUTED.
- The name-policy store.
- Normal operating ranges. The only source range found is marked UNVERIFIED.
- ERPG values.
- Any fluid other than the nine above.

# foundation-refrigeration data dictionary

| Field | Value |
|---|---|
| Document ID | FREFRIG-DD |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Generated parts: the per-argument tool tables are in the [tool catalog](../guides/reference/tool-catalog.md) and the full per-file provenance tables are in [reference data provenance](reference-data.md). Both are produced by `python -B tools/gen_docs.py`; `tests/test_docs_trace.py` fails when either is stale. This document defines the terms those tables use and gives the summary a reader needs.

Not applicable: channelization, rate-group, raw or calibrated sensor, telemetry, data-recorder and partitioning data. The software has no hardware or telemetry interfaces.

## 1. Tools

| Name | Purpose | Parameters | Result | Restrictions | Source |
|---|---|---|---|---|---|
| `saturation_pressure` | Saturation pressure at a temperature | `fluid`, `temperature`; optional `side`, `atmosphere` | `fluid`, `side`, `temperature` (degC), `pressure` (kPa(a)), `pressure_views` (6), `atmosphere` | Inside table range; blends need `side` | `foundation_refrigeration/tools.py` |
| `saturation_temperature` | Saturation temperature at a pressure | `fluid`, `pressure`; optional `side`, `atmosphere` | `fluid`, `side`, `pressure_absolute` (kPa(a)), `temperature` (degC), `temperature_views` (4), `atmosphere`, `atmosphere_used` | Inside table range; blends need `side` | `foundation_refrigeration/tools.py` |
| `convert_pressure` | Pressure unit conversion | `pressure`, `to_unit`; optional `atmosphere` | `input`, `absolute` (kPa(a)), `output`, `atmosphere`, `atmosphere_used` | Absolute result must be positive | `foundation_refrigeration/tools.py` |
| `convert_temperature` | Absolute temperature conversion | `temperature`, `to_unit` | `input`, `canonical` (degC), `output` | Above absolute zero; not for differences | `foundation_refrigeration/tools.py` |
| `check_reading_against_saturation` | Reading versus saturation at the reading pressure | `fluid`, `pressure`, `temperature`; optional `atmosphere` | dew and bubble temperatures, `superheat_style_delta`, `subcooling_style_delta` (K and degF difference), `lookup_resolution_k`, `not_determined` | Pressure inside both bubble and dew ranges | `foundation_refrigeration/tools.py` |
| `exposure_limits` | Cited ammonia limits and caller policy set points | `substance`; optional `issuer`, `policy_set_points` (≤ 16) | `substance`, `published_limits`, `policy_set_points`, `gaps`, `scope`, `separation` | Ammonia only (`ammonia`, `nh3`, `r717`, `r-717`, case-insensitive) | `foundation_refrigeration/tools.py`, `foundation_refrigeration/safety_limits.py` |
| `resolve_equipment_kind` | Canonical equipment kind or line-service code | `term`; optional `vocabulary` (`equipment_kind` default, or `line_service`) | `resolved`, `kind` or `service`, `evidence`, `note`; line services add `open_decisions` | Term ≤ 128 characters; line-service codes ≤ 16 characters | `foundation_refrigeration/tools.py`, `foundation_refrigeration/plant_model.py` |

Library-only functions (not bridge tools): `invariants.evaluate`, `process_safety.screen_ammonia_quantity`, `process_safety.assess_standard_requirement_selection`, `safety_limits.find_mislabelled_ammonia_limits`. Their inputs are in §2.

## 2. Data elements

| Name | Type | Units | Range / limits | Default | Meaning | Defined in |
|---|---|---|---|---|---|---|
| Quantity | object `{value, unit}` | as `unit` | `value` finite int or float, not bool, \|value\| ≤ 1e9 | none | Every physical input; a bare number is refused | `foundation_refrigeration/units.py` `quantity` |
| Pressure unit | string | — | `kPa(a)`, `kPa(g)`, `psia`, `psig`, `bar(a)`, `bar(g)` | none | `(a)`/`a` absolute, `(g)`/`g` gauge | `units.PRESSURE_UNITS` |
| Temperature unit | string | — | `degC`, `degF`, `K`, `degR` | none | Absolute temperature scales | `units.TEMPERATURE_UNITS` |
| psi | constant | kPa | 0.45359237 × 9.80665 / 0.0254² / 1000 = 6.894757293168361 | — | Pound-force per square inch from the avoirdupois pound, standard gravity and the inch | `units.KPA_PER_PSI` |
| Standard atmosphere | constant | kPa(a) | 101.325 | — | Used when `atmosphere` is omitted (`assumed: true`) or `basis: standard` | `units.STANDARD_ATMOSPHERE_KPA` |
| `atmosphere` | object | — | `{basis: standard}`; `{basis: elevation, elevation: quantity m or ft}` with −500 to 6000 m; `{basis: measured, pressure: quantity kPa(a), psia or bar(a)}` with 40 to 110 kPa(a) | standard, assumed | Site atmosphere for gauge values | `units.read_atmosphere` |
| Elevation formula | formula | kPa(a) | 101.325 × (1 − 2.25577e-5 × h)^5.25588, h in m | — | ISO 2533 troposphere barometric formula | `units.atmosphere_at_elevation_kpa` |
| `fluid` | string | — | ≤ 64 characters; matched after removing case, spaces, `-`, `_`, `(`, `)` | none | NH3 (R717, ammonia), CO2 (R744, carbon dioxide), R134a (HFC134a), R290 (propane), R22 (HCFC22), R404A, R410A, R507A, R448A | `thermo.FLUID_ALIASES` |
| `side` | string or null | — | `bubble`, `dew` | `bubble` for pure fluids (bubble equals dew); required for blends | Which saturation curve of a zeotropic blend | `thermo._side` |
| Lookup error | number | K | per table, 0.001111 to 0.005333 | — | Interpolation error of a pressure lookup expressed as temperature, measured over a 0.5 degF probe grid | table `interpolation.error_k` |
| Lookup resolution | number | K | lookup error + 0.0001 | — | Band within which a reading delta is `within_lookup_resolution` | `tools.check_reading_against_saturation` |
| Superheat-style delta | number | K (and degF difference = K × 1.8) | any | — | Reading temperature minus dew temperature at the reading pressure | `tools.check_reading_against_saturation` |
| Subcooling-style delta | number | K (and degF difference) | any | — | Bubble temperature at the reading pressure minus reading temperature | `tools.check_reading_against_saturation` |
| Policy set point | object | ppm | `label` 1–120 characters with no issuer, limit-type or legal words; `concentration` ppm ≥ 0; `set_by` 1–120 (a role, never a person); `scope` `plant`, `client` or `expression`; `reason` 1–1024 | none | A caller's own setting, returned as `not_a_legal_limit` | `safety_limits.policy_set_point` |
| Evidence | object | — | `basis` (one of four kinds), `status` `CHECK`/`APPROVED`/`DISPUTED`, optional `approvedBy`, `approvedOn` (ISO date), `dispute`, `freshForDays` (1–36 500) | — | Where a value came from and whether a qualified person approved it | `foundation_refrigeration/evidence.py` |
| Basis `cited` | object | — | `source`, `version`, `clause` (or null); optional `url`, `quoted`, `retrievedOn` | — | A published source | `evidence.CitedBasis` |
| Basis `generated` | object | — | `model`, `generator`, `generatedOn` | — | Computed by a named model and command | `evidence.GeneratedBasis` |
| Basis `policy` | object | — | `setBy`, `scope`, `reason` | — | A plant or client decision | `evidence.PolicyBasis` |
| Basis `practice` | object | — | `note` | — | Common practice or authored content, explained | `evidence.PracticeBasis` |
| Boundary | object | — | `observation_only: true`; five determination flags `false` | fixed | What a result is not | `tools.BOUNDARY` |
| Inventory record (PSM screen) | object | lb | exactly 12 fields: `framework` (`osha-psm`, `epa-rmp`), `process_id`, `substance`, `maximum_quantity_lb` `{lower, upper}`, `quantity_basis`, `boundary_review`, `inventory_review`, `freshness`, `source_kind`, `source_ids`, `boundary_review_id`, `inventory_review_id` | none | Input to the federal quantity screen | `process_safety._QUANTITY_FIELDS` |
| Selection record | object | — | exactly 16 fields listed in `process_safety._SELECTION_FIELDS` | none | Input to the standard-selection guard | `process_safety._SELECTION_FIELDS` |
| Invariant claim | object | as quantities | see [ICD §9](../icd/icd-cstack.md#9-python-invariant-interface) | none | Input to `invariants.evaluate` | `foundation_refrigeration/invariants.py` |

## 3. Records and files

Receipt `foundation-refrigeration-receipt/1` (inside every `tools/call` result):

| Field | Success | Error |
|---|---|---|
| `schema` | `foundation-refrigeration-receipt/1` | same |
| `foundation_version` | `0.1.0` | same |
| `tool` | tool name | same |
| `input_sha256` | SHA-256 of the arguments (sorted keys, compact, ASCII) | same |
| `boundary` | fixed boundary object | same |
| `status` | `success` | `error` |
| `result` | tool-specific object (see [tool catalog](../guides/reference/tool-catalog.md)) | `null` |
| `error` | `null` | `{code, message}`; code matches `^[a-z_]{1,64}$` |
| `evidence` | 1–64 entries `{applies_to, evidence}` | empty list |
| `data_sources` | 0–8 entries `{projection, schema, sha256, generator_sha256?}` | empty list |
| `limitations` | the three common limitations plus tool-specific ones (3–16) | the three common limitations |

| Record / file | Format | Schema | Producer | Consumer | Retention |
|---|---|---|---|---|---|
| JSON-RPC request and response lines | UTF-8 / ASCII JSON, one per line | JSON-RPC 2.0, `foundation-refrigeration-jsonrpc/1` | Host / bridge | Bridge / host | Not stored |
| `SOURCE-MANIFEST.json` | JSON, sorted keys, indent 2 | `foundation-refrigeration-source-manifest/1`: `schema`, `version`, `files` (path → SHA-256) | `tools/build_manifest.py` | Host pin, `tests/test_names_and_manifest.py` | Committed |
| Data projection | JSON envelope | `schema`, `version` (SemVer), `owner`, `generatedBy`, `data` | Authors and offline generators | `foundation_refrigeration/projection.py` | Committed |
| Golden reference | JSON | `refrigerant-saturation-golden/1` | `tools/compute_golden.py` (CoolProp file); external generator (generator file) | `tests/test_thermo.py`, `tests/test_invariants.py` | Committed |
| Invariant result | Python dict | `check`, `passed`, `reason`, `library_version`, optional `measurements` | `invariants.evaluate` | Caller | Not stored |
| Screen result | Python dict | `result_kind: screen`, `label`, `compliance_determination: false`, `observation_only: true`, `display`, `status`, `gaps`, `claim_boundary`, plus inputs | `process_safety` | Caller | Not stored |

## 4. Reference data provenance

Every embedded table, with its source, edition and units. Digests, row counts and per-row details are in the generated [reference data provenance](reference-data.md).

| Table | Source (edition/date) | Units | Transformation | Validation test |
|---|---|---|---|---|
| `refrigerant-saturation.nh3.json` (NH3) | CoolProp 8.0.0, HEOS backend, DEF reference state; edition `CoolProp-8.0.0@2026-10-24` | rows: degC, kPa(a), kPa(a), J/kg, J/kg | Generated in degF and psia, converted with degC = (degF − 32) / 1.8 and kPa = psia × 6.894757293168361 | `tests/test_thermo.py` (provenance, monotonicity, golden) |
| `refrigerant-saturation.co2.json` (CO2, subcritical) | same | same | same | same |
| `refrigerant-saturation.r134a.json` | same | same | same | same |
| `refrigerant-saturation.r290.json` (propane) | same | same | same | same |
| `refrigerant-saturation.r22.json` | same | same | same | same |
| `refrigerant-saturation.r404a.json` (blend) | same, CoolProp predefined mixture `R404A.mix` | same | same | same |
| `refrigerant-saturation.r410a.json` (blend) | same, `R410A.mix` | same | same | same |
| `refrigerant-saturation.r507a.json` (blend) | same, `R507A.mix` | same | same | same |
| `refrigerant-saturation.r448a.json` (blend) | same, `R448A.mix` | same | same | same |
| `exposure-limits.json` | OSHA Annotated Table Z-1 (29 CFR 1910.1000); NIOSH Pocket Guide to Chemical Hazards, Ammonia (npgd0028); ACGIH Ammonia summary page. All web pages as retrieved 2026-10-06 | ppm, with mg/m3 where the source gives it | Values and quotations copied from the sources; no conversion | `tests/test_domain_data.py::SafetyLimitTests` |
| `psm-thresholds.json` | 29 CFR 1910.119 Appendix A and (a)(1)(i), eCFR title 29 issue 2026-10-14; 40 CFR 68.130 Table 1 and 68.115(a), eCFR title 40 issue 2026-10-22; retrieved 2026-10-25 | lb | None; the loader checks that each quotation contains the threshold | `tests/test_process_safety.py` |
| `plant-taxonomy.json` | Authored for v0.1 from an internal census of eleven legacy equipment lists (read 2026-10-24); not reviewed by a subject-matter expert | none | Normalised to lower case with hyphens | `tests/test_domain_data.py::PlantModelTests` |
| `open-decisions.json` | Authored from the same internal census (read 2026-10-24); names replaced by role descriptions | none | None | `tests/test_domain_data.py::OpenDecisionTests` |
| `golden/coolprop-8.0.0-points.json` | CoolProp 8.0.0 `PropsSI`, computed directly on 2026-10-24 by `tools/compute_golden.py` | degC, kPa(a), psia, psig | None | `tests/test_thermo.py::GoldenTests`, `tests/test_invariants.py` |
| `golden/generator-golden-points.json` | Off-grid points from the table generator's own CoolProp 8.0.0 run on 2026-10-24 | degF, psia, psig (atmosphere 14.696 psia) | None | `tests/test_thermo.py::GoldenTests.test_generator_off_grid_golden_points` |

Notes:
- All saturation tables have status CHECK: generated by an oracle and not signed off by a qualified person. The tables themselves say to use REFPROP for design work.
- All exposure limits and PSM thresholds have status CHECK: the pages were read, but no qualified person approved the values. Re-check against the current official source before any use (see [Limitations and safety-relevant use](../guides/explanation/limitations.md)).
- The table generators (`generate_pt_tables.py`, `project_saturation.py`) are not shipped here; their command line and the generator script SHA-256 are recorded in each table.
- `exposure-limits.json` `generatedBy` names `tests/test_domain_data.py`, which holds the safety-limit tests; `SafetyLimitTests.test_provenance_names_only_test_files_that_exist` keeps that reference valid. It named a nonexistent `tests/test_safety_limits.py` until finding F-3 in the [assurance record](../assurance/assurance-record.md) was closed.

## 5. Configuration keys

None. The bridge reads no configuration file, environment variable or command-line option. `foundation_refrigeration_bridge/__main__.py` sets `sys.dont_write_bytecode`; the documented commands also pass `-B`.

## 6. Operational limits

| Limit | Value | Enforced in | Test |
|---|---|---|---|
| Input frame | 65 536 bytes | `server.decode_frame`, `server.serve` | `tests/test_bridge.py::TransportTests.test_numeric_profile_and_duplicate_keys` |
| Output frame | 1 048 576 bytes | `server.encode_response` | none (GAP-REF-001) |
| JSON depth / nodes / string | 32 / 4096 / 1024 characters | `server.decode_frame` | `tests/test_bridge.py::TransportTests.test_numeric_profile_and_duplicate_keys` |
| Integer digits / number literal | 15 / 24 characters | `server._integer`, `server._decimal` | same |
| Request id | string ≤ 128 characters or integer with \|id\| ≤ 9 007 199 254 740 991 | `server.Bridge.dispatch` | none (GAP-REF-003) |
| Quantity magnitude | ≤ 1e9 | `units.finite_number` | `tests/test_evidence_units.py::UnitTests.test_quantities_need_explicit_units_and_finite_numbers` |
| Elevation | −500 to 6000 m | `units.atmosphere_at_elevation_kpa` | `tests/test_evidence_units.py::UnitTests.test_site_atmosphere_from_elevation` |
| Measured atmosphere | 40 to 110 kPa(a) | `units.read_atmosphere` | same |
| Saturation range | per table (see [reference data](reference-data.md#saturation-tables)) | `thermo.saturation_pressure_kpa`, `thermo.saturation_temperature_c` | `tests/test_thermo.py::RefusalTests.test_no_extrapolation` |
| Policy set points per call | 16 | `tools.exposure_limits` | none for the count; label and field checks tested in `tests/test_domain_data.py` |
| Evidence text fields | 2048 characters | `evidence._text` | none |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 62764c7 | Initial baseline | PR adding the NASA-standard documentation set |

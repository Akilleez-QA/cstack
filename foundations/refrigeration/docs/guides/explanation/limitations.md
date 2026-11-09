# Limitations and safety-relevant use

foundation-refrigeration returns refrigerant saturation data, unit conversions, a comparison of one reading with saturation, ammonia exposure limits and equipment names. Some of this is safety-relevant data: ammonia exposure limits are used in the real world to protect people's lives. **This software is not for life-safety decisions.** Read this page before relying on any number it returns.

This page replaces a hazard report. The software is not safety-critical (it controls nothing and is part of no safety system), so no hazard report applies; see the classification in the [software management plan](../../plan/software-management-plan.md#1-software-classification-self-assessed).

## What the outputs are

Each tool result is a bounded observation. It carries:

- the value, with explicit units;
- Evidence for each value: where it came from and whether a qualified person approved it;
- the SHA-256 of the request (`input_sha256`) and of each data file used;
- a fixed `boundary` saying it is not an engineering, safety or compliance determination, not a diagnosis and not a control action;
- limitations, starting with "A tool observation is not an engineering, safety or compliance determination."

Every Evidence record shipped in this repository has status **CHECK**: recorded, but not approved by a qualified person. No value has status APPROVED.

## What the software does not do

- It does not monitor exposure, detect leaks, raise alarms or decide whether an area is safe to enter.
- It does not select respirators or other protective equipment.
- It does not set, recommend or check alarm set points. Caller-supplied policy set points are echoed back as `not_a_legal_limit`, never as limits.
- It does not determine whether OSHA PSM or EPA RMP applies to a facility. The process-safety functions are screens with `compliance_determination: false`.
- It does not say whether a reading is normal, what causes it or what to do. `check_reading_against_saturation` reports arithmetic deltas and lists what it does not determine.
- It does not replace a licensed engineer's calculation, a manufacturer's data or REFPROP for design work.
- It does not command or write to any plant, controller or device.

## Data sources and their limits

The [data dictionary](../../data/data-dictionary.md#4-reference-data-provenance) lists every table with its source, edition and units. The [reference data provenance](../../data/reference-data.md) page gives the exact values, ranges and digests.

### Exposure limits (ammonia only)

| Limit | Value | Issuer | Legal status | Source and edition |
|---|---|---|---|---|
| PEL, 8-hour TWA | 50 ppm (35 mg/m3) | OSHA | Enforceable (federal OSHA) | OSHA Annotated Table Z-1, 29 CFR 1910.1000, web page retrieved 2026-10-06 |
| REL, TWA | 25 ppm (18 mg/m3) | NIOSH | Recommended | NIOSH Pocket Guide to Chemical Hazards, Ammonia, web page retrieved 2026-10-06 |
| REL, 15-minute STEL | 35 ppm (27 mg/m3) | NIOSH | Recommended | same |
| IDLH | 300 ppm | NIOSH | Guideline | same |
| TLV-TWA, 8-hour | 25 ppm (17 mg/m3) | ACGIH | Guideline | ACGIH Ammonia summary page, retrieved 2026-10-06 (full documentation not read) |
| TLV-STEL, 15-minute | 35 ppm (24 mg/m3) | ACGIH | Guideline | same |

- Units are parts per million by volume (ppm), with mg/m3 where the source gives it. No conversion is done.
- Only ammonia (NH3, R717) is covered. Any other substance is refused.
- ERPG-1, ERPG-2 and ERPG-3 are an explicit gap: no primary AIHA source was read, so no value is stored.
- State plans can be stricter than federal OSHA. The OSHA table row itself lists Cal/OSHA at 25 ppm with a 35 ppm short-term limit; that value is not stored as a limit.
- The values were copied from web pages on one date. Sources change. Check the current official source before any use.

### Process-safety thresholds

OSHA PSM (29 CFR 1910.119 Appendix A, at or above 10 000 lb) and EPA RMP (40 CFR 68.130, above 10 000 lb) for anhydrous ammonia, from eCFR versions current in October 2026 (retrieved 2026-10-25). Aqueous ammonia is not screened. Jurisdiction, exemptions, process grouping, program level and state or local rules are outside the screen.

### Saturation tables

Generated with CoolProp 8.0.0 (HEOS backend) on 2026-10-24 for NH3, CO2, R134a, R290, R22, R404A, R410A, R507A and R448A, stored in degC and kPa(a). Limits:

- Bounded ranges only (for example NH3 −51.1 to 60 degC; CO2 −51.1 to 29.4 degC, subcritical). No critical point, no supercritical data, no extrapolation: values outside the table are refused.
- Lookups interpolate between rows; the stated error (0.0011 to 0.0053 K, depending on the fluid) covers the lookup only, not the accuracy of CoolProp itself.
- Blend tables use CoolProp's default mixing parameters. The tables themselves say to use REFPROP for design work.
- Agreement with the golden points shows consistency with CoolProp 8.0.0. It is not experimental validation.

### Taxonomy and open decisions

The equipment taxonomy and line-service codes were authored from an internal census and have not been reviewed by a subject-matter expert. Four expert questions (for example the IIAR Bulletin 114 marker colours and the 70 psig pressure split) are recorded as DISPUTED with every position; none is chosen.

## Use in safety, engineering or regulated decisions

- **Do not use these outputs as the sole basis for any safety, engineering or regulatory decision**, including alarm set points, evacuation levels, respirator selection, ventilation design, relief sizing, PSM or RMP applicability, or entry into an ammonia area.
- Verify every value against the authoritative source: for exposure limits, 29 CFR 1910.1000 Table Z-1 (OSHA), the NIOSH Pocket Guide, the current ACGIH TLV documentation, and your state plan; for thresholds, the current text of 29 CFR 1910.119 and 40 CFR Part 68; for refrigerant properties, REFPROP or the refrigerant manufacturer's data; for ammonia refrigeration practice, IIAR standards and a qualified engineer.
- The software's classification (Class E analog) holds only because no real engineering decision depends on it. If you use it in such a decision, your use falls under the Class D analog: you need the verification, approval and configuration control that this project does not provide.

## Misuse and security considerations

- Requests are untrusted. The bridge bounds every frame, refuses unknown fields, exponents, NaN, Infinity and duplicate keys, takes no paths or options, and opens no network connection. See [ICD §6](../../icd/icd-cstack.md#6-security-and-input-bounds).
- The worst outcome of a defect is a wrong number returned as a success (severity S1). The design reduces this by refusing extrapolation and unguessed blend sides, using exact unit constants, and checking the data at import.
- A caller could put misleading text in a policy set point. Labels that name an issuer, a limit type or a legal status are refused, and the result always says `not_a_legal_limit`, but `reason` and `set_by` are free text echoed back.
- Report vulnerabilities privately as described in [SECURITY.md](../../../SECURITY.md).

## Known limitations

| Limitation | Effect | Issue |
|---|---|---|
| All data is status CHECK; no qualified person has approved any value | Values may be wrong without anyone having noticed | — |
| Exposure limits and thresholds are a snapshot from October 2026 | They go stale when the sources change (SMP risk R-1) | — |
| Ammonia is the only substance with exposure limits | Other refrigerants' limits are not available | — |
| No ERPG values | Emergency planning values must come from AIHA | — |
| Saturation tables are bounded and subcritical | Conditions outside the ranges are refused | — |
| Blend properties use CoolProp default mixing parameters | Can differ from REFPROP and from manufacturer data | — |
| Several bridge error paths have no test (GAP-REF-001 to GAP-REF-008) | A regression in those paths might not be caught | — |

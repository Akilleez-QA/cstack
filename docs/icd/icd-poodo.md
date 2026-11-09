# Cstack–POODO source interface

| Field | Value |
|---|---|
| Document ID | CSTACK-ICD-POODO |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

`reasoning/poodo/` mirrors the explicitly listed files at `contracts/SOURCE-PINS.json` → `poodo_skill.commit`; this partial snapshot exposes skill instructions, references and structural validators, rather than a runtime transport or callable capability. POODO 3.1 retains `POODO_CONTINUATION/3.0` capsules and explicit invocation metadata. Deferred files and archived software-engineering extensions provide no compatibility promise; `poodo_core/` has its own independent pin.

## Requirements addressed

CS-REQ-019 (reasoning snapshot provenance), verified by hand through test plan TP-3; CS-REQ-074 covers the separate `poodo_core/` byte pin. See the [verification matrix](../verification/verification-matrix.md) for the tests.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Earlier versions | See `git log -- docs/icd/icd-poodo.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard header and disclaimer; requirements-addressed section | docs/nasa-standard PR |

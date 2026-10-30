# Foundation Refrigeration: agent rules

1. **Rule T-1.** Never hand-type a thermo table or number. Saturation data comes only from `upstream/app/scripts/refrigerant-tables/generate_pt_tables.py` (CoolProp 8.0.0), through `tools/project_saturation.py`. Golden points come from CoolProp, through `tools/compute_golden.py`.
2. **Every value carries Evidence.** Never set APPROVED without `approvedBy` (a role, not a person's name) and `approvedOn`. VERIFIED is not approval.
3. **Keep the kinds apart.** A policy value (a plant's or client's set point) is never presented as a legal or published limit.
4. **Do not choose open SME decisions.** They stay DISPUTED until an SME decides. Record every position.
5. **No client, customer or maker names**, including in data and tests. `tests/test_names_and_manifest.py` scans against the hashed term store. Use a role description instead.
6. **Observation only.** No diagnosis, no normal or abnormal call, no engineering, safety or compliance determination, and no control path.
7. **Stdlib only.** No network, no CoolProp at run time, and no caller-controlled paths.
8. After any change, rebuild `SOURCE-MANIFEST.json` and repin `adapters/refrigeration_stdio.py` and `contracts/SOURCE-PINS.json`. Then run this suite and the cstack suite, each in normal and `-O` mode, one run at a time.

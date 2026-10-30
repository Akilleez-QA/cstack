"""Compute golden saturation points DIRECTLY with CoolProp 8.0.0 (not through the table generator).

These points check the projected tables and the ln(P)-vs-1/T lookup against the oracle at points
chosen in degC/kPa (mostly off the generator's 5 degF grid), plus the census anchor points.
Run from the cstack repository root, CPU only:
    uvx --from CoolProp==8.0.0 python -I foundations/refrigeration/tools/compute_golden.py --date YYYY-MM-DD
"""
import argparse
import json
from pathlib import Path

import CoolProp
import CoolProp.CoolProp as CP

OUT = Path(__file__).resolve().parents[1] / "golden" / "coolprop-8.0.0-points.json"
PSI_KPA = 0.45359237 * 9.80665 / 0.0254 ** 2 / 1000.0
FLUIDS = {"R717": "Ammonia", "CO2": "CarbonDioxide", "R134a": "R134a", "R290": "Propane", "R22": "R22",
          "R404A": "R404A.mix", "R410A": "R410A.mix", "R507A": "R507A.mix", "R448A": "R448A.mix"}
BY_TEMP_C = {
    "R717": [-50.0, -40.0, -30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 57.5],
    "CO2": [-50.0, -40.0, -20.0, 0.0, 20.0, 28.0],
    "R134a": [-38.0, -20.0, 0.0, 25.0, 50.0],
    "R290": [-45.0, 0.0, 40.0],
    "R22": [-45.0, 0.0, 40.0],
    "R404A": [-45.0, -30.0, 0.0, 30.0],
    "R410A": [-45.0, -30.0, 0.0, 30.0],
    "R507A": [-45.0, -30.0, 0.0, 30.0],
    "R448A": [-45.0, -30.0, 0.0, 30.0, 55.0],
}
CENSUS_R717_F = [0.0, 20.0, 95.0]
BY_PRESSURE_KPA = {"R717": [100.0, 300.0, 1200.0], "CO2": [1000.0, 3000.0], "R448A": [200.0, 1500.0]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    if CoolProp.__version__ != "8.0.0":
        raise SystemExit("CoolProp 8.0.0 required")
    by_temp, by_pressure, census = [], [], []
    for fid, fluid in FLUIDS.items():
        for t_c in BY_TEMP_C[fid]:
            t_k = t_c + 273.15
            by_temp.append({"fluid": fid, "temperature_c": t_c,
                            "bubble_kpa_a": round(CP.PropsSI("P", "T", t_k, "Q", 0, fluid) / 1000.0, 6),
                            "dew_kpa_a": round(CP.PropsSI("P", "T", t_k, "Q", 1, fluid) / 1000.0, 6)})
        for p in BY_PRESSURE_KPA.get(fid, []):
            by_pressure.append({"fluid": fid, "pressure_kpa_a": p,
                                "bubble_temperature_c": round(CP.PropsSI("T", "P", p * 1000.0, "Q", 0, fluid) - 273.15, 6),
                                "dew_temperature_c": round(CP.PropsSI("T", "P", p * 1000.0, "Q", 1, fluid) - 273.15, 6)})
    for t_f in CENSUS_R717_F:
        p_kpa = CP.PropsSI("P", "T", (t_f - 32.0) / 1.8 + 273.15, "Q", 0, "Ammonia") / 1000.0
        census.append({"fluid": "R717", "temperature_f": t_f, "pressure_psia": round(p_kpa / PSI_KPA, 6),
                       "pressure_psig_standard_atmosphere": round((p_kpa - 101.325) / PSI_KPA, 6)})
    document = {"schema": "refrigerant-saturation-golden/1", "version": "1.0.0",
                "generatedBy": "uvx --from CoolProp==8.0.0 python -I foundations/refrigeration/tools/compute_golden.py --date " + args.date,
                "oracle": "CoolProp " + CoolProp.__version__ + " PropsSI (HEOS; blends via predefined .mix)",
                "generated_on": args.date, "standard_atmosphere_kpa": 101.325,
                "note": "Computed directly by CoolProp, independent of the table generator's code path. "
                        "Agreement checks consistency with the oracle, not experimental accuracy.",
                "by_temperature": by_temp, "by_pressure": by_pressure, "census_r717_anchor_points": census}
    OUT.write_text(json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
    print(OUT, len(by_temp), len(by_pressure), len(census))


if __name__ == "__main__":
    main()

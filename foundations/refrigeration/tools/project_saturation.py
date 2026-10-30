"""Port the the reference app saturation generator's output to refrigerant-saturation/1 JSON (rule T-1).

The ONLY source of saturation numbers is the unchanged the reference app generator
upstream/app/scripts/refrigerant-tables/generate_pt_tables.py (CoolProp 8.0.0). This
tool runs it into a scratch directory (or reads a directory it already wrote), parses the
generated TypeScript strictly, checks every row against the tables committed in the reference app,
and writes one projection per fluid plus the generator's off-grid golden points. No number is typed.

Usage, from the cstack repository root:
    python -B foundations/refrigeration/tools/project_saturation.py --date YYYY-MM-DD
    python -B foundations/refrigeration/tools/project_saturation.py --date YYYY-MM-DD --from-dir DIR
The first form needs `uvx` with network or cache access to CoolProp==8.0.0 (CPU only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FOUNDATION = HERE.parent
REPO = FOUNDATION.parents[1]
sys.path.insert(0, str(FOUNDATION))
from foundation_refrigeration.units import KPA_PER_PSI, f_to_c  # noqa: E402

GENERATOR = Path("upstream/app/scripts/refrigerant-tables/generate_pt_tables.py")
COMMITTED = Path("upstream/app/packages/domain/src/calculators")
DATA = FOUNDATION / "foundation_refrigeration" / "data"
GOLDEN = FOUNDATION / "golden"
FLUID_FILES = ("r717", "co2", "r134a", "r290", "r22", "r404a", "r410a", "r507a", "r448a")
NUMBER = r"-?\d+(?:\.\d+)?"


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field(text, name, pattern):
    found = re.findall(r"^  " + name + r": (" + pattern + r"),$", text, re.M)
    if len(found) != 1:
        raise ValueError("Field %s not found exactly once" % name)
    return found[0]


def parse_table(text: str) -> dict:
    quoted = r"'[^'\n]*'"
    table = {name: field(text, name, quoted)[1:-1] for name in (
        "id", "name", "kind", "composition", "coolpropFluid", "referenceState", "propertyBackend",
        "source", "edition")}
    for name in ("minTempF", "maxTempF", "interpolationErrorF"):
        table[name] = float(field(text, name, NUMBER))
    for name in ("verifiedBy", "verifiedAt"):
        if field(text, name, r"null|'[^'\n]*'") != "null":
            raise ValueError("Generator output now records a verifier; port it explicitly")
        table[name] = None
    block = re.search(r"^  rows: \[\n(.*?)^  \],$", text, re.M | re.S)
    if block is None:
        raise ValueError("Rows block not found")
    row_re = re.compile(r"^    \[(" + NUMBER + r"(?:, " + NUMBER + r"){4})\],$")
    rows = []
    for line in block.group(1).splitlines():
        match = row_re.fullmatch(line)
        if match is None:
            raise ValueError("Unexpected row line: " + line)
        rows.append([float(token) for token in match.group(1).split(", ")])
    if not rows:
        raise ValueError("Empty table")
    return {**table, "rows": rows}


def parse_golden(text: str) -> dict:
    out = {}
    current = None
    temp_re = re.compile(r"^      \{ tempF: (" + NUMBER + r"), bubblePsia: (" + NUMBER + r"), dewPsia: (" + NUMBER + r") \},$")
    press_re = re.compile(r"^      \{ psig: (" + NUMBER + r"), bubbleTempF: (" + NUMBER + r"), dewTempF: (" + NUMBER + r") \},$")
    for line in text.splitlines():
        head = re.fullmatch(r"  ([A-Za-z0-9]+): \{", line)
        if head:
            current = out.setdefault(head.group(1), {"byTemp": [], "byPressure": []})
            continue
        if (m := temp_re.fullmatch(line)):
            current["byTemp"].append({"tempF": float(m[1]), "bubblePsia": float(m[2]), "dewPsia": float(m[3])})
        elif (m := press_re.fullmatch(line)):
            current["byPressure"].append({"psig": float(m[1]), "bubbleTempF": float(m[2]), "dewTempF": float(m[3])})
    if set(out) != {"R717", "CO2", "R134a", "R290", "R22", "R404A", "R410A", "R507A", "R448A"}:
        raise ValueError("Golden fluids mismatch")
    return out


def run_generator(out_dir: Path, date: str) -> None:
    argv = ["uvx", "--from", "CoolProp==8.0.0", "python", str(GENERATOR), "--date", date,
            "--skip-sim", "--out", str(out_dir)]
    subprocess.run(argv, cwd=REPO, check=True, timeout=900)


def projection(table: dict, source_file: Path, generator_sha: str, date: str, matches: bool) -> dict:
    command = ("uvx --from CoolProp==8.0.0 python " + str(GENERATOR) + " --date " + date
               + " --skip-sim --out <scratch>; python -B foundations/refrigeration/tools/project_saturation.py"
               + " --date " + date + " --from-dir <scratch>")
    canonical = [[f_to_c(t), pb * KPA_PER_PSI, pd * KPA_PER_PSI, hl, hv] for t, pb, pd, hl, hv in table["rows"]]
    return {
        "schema": "refrigerant-saturation/1",
        "version": "1.0.0",
        "owner": "foundation_refrigeration.thermo",
        "generatedBy": command,
        "data": {
            "id": table["id"], "name": table["name"], "kind": table["kind"],
            "composition": table["composition"], "coolpropFluid": table["coolpropFluid"],
            "referenceState": table["referenceState"], "propertyBackend": table["propertyBackend"],
            "source": table["source"], "edition": table["edition"],
            "verifiedBy": table["verifiedBy"], "verifiedAt": table["verifiedAt"],
            "generator": {"path": str(GENERATOR), "sha256": generator_sha, "output_file": source_file.name,
                          "output_sha256": sha256(source_file), "generated_on": date,
                          "rows_match_committed_refrigeration_ai_table": matches},
            "range": {"min_temp_f": table["minTempF"], "max_temp_f": table["maxTempF"],
                      "min_temp_c": f_to_c(table["minTempF"]), "max_temp_c": f_to_c(table["maxTempF"])},
            "interpolation": {
                "method": "linear in ln(P) against 1/T between adjacent rows; no extrapolation (ADR-167)",
                "error_f": table["interpolationErrorF"], "error_k": table["interpolationErrorF"] / 1.8,
                "error_scope": "pressure lookup only, as a temperature-equivalent over a 0.5 degF probe grid"},
            "columns": ["temperature", "pressure_bubble", "pressure_dew", "enthalpy_liquid", "enthalpy_vapour"],
            "units": ["degC", "kPa(a)", "kPa(a)", "J/kg", "J/kg"],
            "rows": canonical,
            "generated_units": ["degF", "psia", "psia", "J/kg", "J/kg"],
            "generated_rows": table["rows"],
            "conversion": "degC = (degF - 32) / 1.8; kPa(a) = psia * 6.894757293168361 (exact psi definition)",
            "evidence": {
                "basis": {"kind": "generated", "model": table["source"] + " " + table["propertyBackend"]
                          + (" (CoolProp predefined mixture)" if table["kind"] != "pure" else ""),
                          "generator": command, "generatedOn": date},
                "status": "CHECK"},
            "limitations": [
                "Bounded saturation samples, not a complete dome; no critical point or extrapolation.",
                "CoolProp mixture models use default mixing parameters; use REFPROP for design work.",
                "Enthalpies use each fluid's CoolProp DEF reference state; they are not comparable across fluids.",
                "Oracle-generated and not signed off by a qualified person (verifiedBy null), so CHECK."],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--from-dir")
    args = parser.parse_args()
    generator_sha = sha256(REPO / GENERATOR)
    with tempfile.TemporaryDirectory(prefix="rai-pt-") as scratch:
        source = Path(args.from_dir).resolve() if args.from_dir else Path(scratch)
        if not args.from_dir:
            run_generator(source, args.date)
        for fid in FLUID_FILES:
            generated = source / ("pt-tables." + fid + ".generated.ts")
            table = parse_table(generated.read_text())
            committed = parse_table((REPO / COMMITTED / generated.name).read_text())
            matches = committed["rows"] == table["rows"] and all(
                committed[k] == table[k] for k in table if k not in ("rows", "edition"))
            if not matches:
                raise SystemExit("Fresh generator output differs from the committed the reference app table "
                                 + generated.name + "; stop and reconcile before projecting.")
            out = DATA / ("refrigerant-saturation." + fid + ".json")
            out.write_text(stable_json(projection(table, generated, generator_sha, args.date, matches)))
            print(out.relative_to(REPO), len(table["rows"]), "rows")
        golden_file = source / "pt-golden.test-support.ts"
        golden = {"schema": "refrigerant-saturation-golden/1", "version": "1.0.0",
                  "generatedBy": "upstream/app generator pt-golden.test-support.ts, parsed by "
                                 "foundations/refrigeration/tools/project_saturation.py",
                  "generator_sha256": generator_sha, "output_sha256": sha256(golden_file),
                  "generated_on": args.date, "atmosphere_psia_used_for_psig": 14.696,
                  "note": "Every point computed directly by CoolProp 8.0.0 at an off-grid point, by the generator.",
                  "units": {"tempF": "degF", "bubblePsia": "psia", "dewPsia": "psia", "psig": "psig (14.696 psia)",
                            "bubbleTempF": "degF", "dewTempF": "degF"},
                  "fluids": parse_golden(golden_file.read_text())}
        (GOLDEN / "generator-golden-points.json").write_text(stable_json(golden))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

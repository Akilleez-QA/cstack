import re

from .measures import ToolInputError, array, check, div_round, exact, identifier, integer, measure, verdict

LABEL = re.compile(r"[\x20-\x7e]{1,96}\Z")
DEFAULT_CONTRACT = {"loudness_target": -16000, "loudness_tolerance": 1000, "true_peak_max": -1000,
                    "voice_over_bed_min": 12000, "voice_over_bed_max": 15000, "cut_hit_share_min": 800,
                    "required_heard": ["Speech", "Music"], "forbidden_heard": ["Sine wave"], "wer_max": 50}
LEVELS = ("loudness_target", "loudness_tolerance", "true_peak_max", "voice_over_bed_min", "voice_over_bed_max")
FIELDS = ("integrated_lufs", "true_peak_dbtp", "voice_over_bed_db", "cuts", "cuts_with_hit", "heard", "line_wer")
MAX_LABELS, MAX_LINES, MAX_CUTS = 128, 512, 100_000


def _labels(value, name):
    items = array(value, name, 0, MAX_LABELS)
    for i, label in enumerate(items):
        if type(label) is not str or LABEL.fullmatch(label) is None:
            raise ToolInputError(f"{name}[{i}] must be printable ASCII text of 1 to 96 characters")
    return list(items)


def _contract(value):
    contract = dict(DEFAULT_CONTRACT, required_heard=list(DEFAULT_CONTRACT["required_heard"]),
                    forbidden_heard=list(DEFAULT_CONTRACT["forbidden_heard"]))
    if value is None:
        return contract, []
    exact(value, "contract", (), tuple(DEFAULT_CONTRACT))
    for key, number in value.items():
        if key in LEVELS:
            contract[key] = measure(number, f"contract.{key}")
        elif key in ("cut_hit_share_min", "wer_max"):
            contract[key] = integer(number, f"contract.{key}", 0, 1000)
        else:
            contract[key] = _labels(number, f"contract.{key}")
    if contract["loudness_tolerance"] < 0 or contract["voice_over_bed_min"] > contract["voice_over_bed_max"]:
        raise ToolInputError("contract tolerance must be >= 0 and voice_over_bed_min <= voice_over_bed_max")
    return contract, sorted(value)


def _optional(arguments, key, parse):
    return None if arguments[key] is None else parse(arguments[key])


def audio_gate(arguments):
    exact(arguments, "arguments", FIELDS, ("contract",))
    contract, overrides = _contract(arguments.get("contract"))
    loud = _optional(arguments, "integrated_lufs", lambda v: measure(v, "integrated_lufs"))
    peak = _optional(arguments, "true_peak_dbtp", lambda v: measure(v, "true_peak_dbtp"))
    margin = _optional(arguments, "voice_over_bed_db", lambda v: measure(v, "voice_over_bed_db"))
    cuts = _optional(arguments, "cuts", lambda v: integer(v, "cuts", 0, MAX_CUTS))
    hits = _optional(arguments, "cuts_with_hit", lambda v: integer(v, "cuts_with_hit", 0, MAX_CUTS))
    if cuts is not None and hits is not None and hits > cuts:
        raise ToolInputError("cuts_with_hit cannot exceed cuts")
    share = div_round(1000 * hits, cuts) if cuts and hits is not None else None
    heard = _optional(arguments, "heard", lambda v: _labels(v, "heard"))
    lines = _optional(arguments, "line_wer", _line_wer)
    folded = None if heard is None else {label.casefold() for label in heard}
    missing = None if folded is None else [x for x in contract["required_heard"] if x.casefold() not in folded]
    present = None if folded is None else [x for x in contract["forbidden_heard"] if x.casefold() in folded]
    worst = None if lines is None else max(lines, key=lambda line: line["wer_permille"])
    checks = [check("integrated_loudness", loud, contract["loudness_target"] - contract["loudness_tolerance"],
                    contract["loudness_target"] + contract["loudness_tolerance"]),
              check("true_peak", peak, None, contract["true_peak_max"]),
              check("voice_over_bed", margin, contract["voice_over_bed_min"], contract["voice_over_bed_max"]),
              check("cut_hit_share", share, contract["cut_hit_share_min"], None),
              check("heard_required_missing", None if missing is None else len(missing), None, 0),
              check("heard_forbidden_present", None if present is None else len(present), None, 0),
              check("worst_line_wer", None if worst is None else worst["wer_permille"], None, contract["wer_max"])]
    result = {"verdict": verdict(checks), "checks": checks, "contract": contract, "contract_overrides": overrides,
              "heard": {"missing": missing, "forbidden_present": present},
              "wer": {"lines": 0 if lines is None else len(lines), "worst_line": None if worst is None else worst["line"],
                      "failing_lines": [] if lines is None else
                      [x["line"] for x in lines if x["wer_permille"] > contract["wer_max"]]},
              "failing": [c["check"] for c in checks if c["status"] != "pass"]}
    return result["verdict"], result


def _line_wer(value):
    lines, seen = [], set()
    for i, raw in enumerate(array(value, "line_wer", 1, MAX_LINES)):
        row = exact(raw, f"line_wer[{i}]", ("line", "wer_permille"))
        line = identifier(row["line"], f"line_wer[{i}].line")
        if line in seen:
            raise ToolInputError(f"line_wer repeats line {line}")
        seen.add(line)
        lines.append({"line": line, "wer_permille": integer(row["wer_permille"], "wer_permille", 0, 10_000)})
    return lines

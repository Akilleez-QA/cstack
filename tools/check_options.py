"""Check a POODO options record before a goal moves from Orient to Decide.

    python -B tools/check_options.py work/decisions/<goal>-options.json

The record is JSON: {"schema": "cstack.options/0.1", "goal": "...", "options": [{"id", "kind", "mechanism",
"summary"}, ...]}. It must hold exactly twenty options with distinct ids, every required kind at least once, no two
options with the same mechanism, and no two options whose words overlap at or above SIMILARITY. The core already
refuses Orient-to-Decide without twenty distinct option ids (poodo_core/core.py); this check looks at the content.
It catches repeats and near-verbatim rephrasings only; it cannot tell that two differently worded options share a
mechanism, so an independent reviewer still reads the record. Exit 0 when clean, 1 with one problem per line.
Standard library only. See agents/PRACTICE.md for why the count is twenty.
"""
import argparse
import itertools
import json
import re
import sys

SCHEMA = "cstack.options/0.1"
COUNT = 20
SIMILARITY = 0.6
REQUIRED_KINDS = ("unconventional", "diagnostic", "conservative", "reversible", "defer_stop", "escalation")
KINDS = ("conventional",) + REQUIRED_KINDS
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
WORD = re.compile(r"[a-z0-9]+")
STOP = frozenset("a an and are as at be by for from in into is it of on or so that the then this to with "
                 "we our you your use using".split())


def words(text):
    return frozenset(w for w in WORD.findall(text.lower()) if w not in STOP)


def overlap(left, right):
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def problems(record):
    if not isinstance(record, dict):
        return ["the record must be a JSON object"]
    found = []
    if record.get("schema") != SCHEMA:
        found.append(f"schema must be {SCHEMA!r}")
    if not isinstance(record.get("goal"), str) or not record["goal"].strip():
        found.append("goal must be a non-empty string")
    options = record.get("options")
    if not isinstance(options, list):
        return found + ["options must be a list"]
    if len(options) != COUNT:
        found.append(f"options: {len(options)} given; exactly {COUNT} materially distinct options are required")
    usable = []
    for index, option in enumerate(options, 1):
        label = f"option {index}"
        if not isinstance(option, dict):
            found.append(f"{label}: must be an object")
            continue
        missing = [k for k in ("id", "kind", "mechanism", "summary")
                   if not isinstance(option.get(k), str) or not option[k].strip()]
        if missing:
            found.append(f"{label}: missing {', '.join(missing)}")
            continue
        extra = sorted(set(option) - {"id", "kind", "mechanism", "summary", "evidence", "risk", "reversibility",
                                      "authority"})
        if extra:
            found.append(f"{label}: unknown field {', '.join(extra)}")
        if not IDENTIFIER.match(option["id"]):
            found.append(f"{label}: id {option['id']!r} is not an identifier")
        if option["kind"] not in KINDS:
            found.append(f"{label}: kind {option['kind']!r} is not one of {', '.join(KINDS)}")
        usable.append(option)
    ids = [o["id"] for o in usable]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        found.append(f"id {duplicate!r} is used more than once")
    kinds = {o["kind"] for o in usable}
    for kind in REQUIRED_KINDS:
        if kind not in kinds:
            found.append(f"no {kind} option; include at least one")
    for left, right in itertools.combinations(usable, 2):
        if words(left["mechanism"]) == words(right["mechanism"]):
            found.append(f"{left['id']} and {right['id']} share one mechanism; make one differ in how it works")
            continue
        score = overlap(words(left["mechanism"] + " " + left["summary"]),
                        words(right["mechanism"] + " " + right["summary"]))
        if score >= SIMILARITY:
            found.append(f"{left['id']} and {right['id']} are near-duplicates ({score:.2f} word overlap); "
                         "replace one with an option that differs in mechanism, evidence, risk, reversibility "
                         "or authority")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record")
    args = parser.parse_args(argv)
    try:
        with open(args.record, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        print(f"{args.record}: {error}")
        return 1
    found = problems(record)
    for line in found:
        print(f"{args.record}: {line}")
    if not found:
        print(f"{args.record}: {COUNT} materially distinct options")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

"""Claim-versus-evidence gate (staging target endoforge.qualify). Pure, stdlib only.

A bot's final report is a set of claims; the POODO ledger events are the evidence.
Each strong claim gets one verdict: SUPPORTED (with the event sequence numbers),
UNSUPPORTED, or REPORTED-ONLY (only proposal, inference, decision or action events
back it). Ported from parts-wall parts: oss-pai-claim-vs-transcript-verification-gate,
oss-pai-evidence-modality-and-class-sweep, oss-pstack-orchestrate-single-writer-store
(verdict ladder), oss-t3code-structured-task-handoff (reported vs observed) and
oss-rea-evidence-obligation-ledger (absence of evidence never closes a claim).

Rules applied (POODO invariants 1-3): implementation is not effect, so a deploy or
edit outcome supports "deployed" but never "live" or "verified"; a type-check or a
unit test is not a runtime observation; a hash, digest or summary is not
corroboration; a corrected or failed outcome supports nothing.
The detector is heuristic text classification. A SUPPORTED verdict means matching
ledger evidence exists, not that the claim is true.
"""
import argparse
import json
import re
import sys

SCHEMA = "cstack.claim-gate/0.1"
SUPPORTED, UNSUPPORTED, REPORTED_ONLY = "SUPPORTED", "UNSUPPORTED", "REPORTED-ONLY"

# Requirement -> event evidence classes that can satisfy it (the verdict ladder).
SATISFIES = {
    "static": {"static", "unit", "runtime"},
    "unit": {"unit", "runtime"},
    "delivery": {"implementation", "runtime"},
    "effect": {"runtime"},
    "numeric": {"static", "unit", "implementation", "runtime"},
}
LADDER = ("runtime", "unit", "static", "implementation", "digest")  # strongest first
REPORTED_KINDS = ("proposal", "inference", "decision", "action")
OBSERVED_KINDS = ("outcome", "observation")

EFFECT_WORDS = re.compile(r"\b(verified|validated|fixed|resolved|live|works?|working|confirmed|end[\s-]to[\s-]end|"
                          r"in\s+production)\b", re.I)
DELIVERY_WORDS = re.compile(r"\b(deployed|shipped|installed)\b", re.I)
UNIT_WORDS = re.compile(r"\b(tested|pass(es|ed|ing)?|green)\b", re.I)
STATIC_SUBJECT = re.compile(r"\b(type[\s-]?check(s|ed|ing)?|typecheck\w*|lint\w*|mypy|tsc|pyright|ruff|compil\w+)\b", re.I)
UNITS = (r"%|ms|s|sec|secs|seconds?|minutes?|min|hours?|h|tests?|files?|bytes?|[KMGT]i?B|events?|"
         r"°\s?[CF]|deg\s?[CF]|K|psig?|kPa|bar|rpm|kW|hp|tons?")
NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:" + UNITS + r")(?![\w])")
# A unit that asks, hedges, negates, plans or downgrades is not a claim.
NONCLAIM = re.compile(r"\b(not|no|never|isn'?t|aren'?t|wasn'?t|didn'?t|doesn'?t|don'?t|won'?t|can'?t|cannot|"
                      r"couldn'?t|unverified|untested|pending|should|would|could|will|may|might|if|once|"
                      r"unless|until|expect\w*|hope|need(s|ed)?\s+to|reported|claimed|deferred)\b", re.I)
LEADING_QUESTION = re.compile(r"^\s*(is|are|does|do|did|can|could|has|have|how|why|what|where|which)\b", re.I)
LEADING_IMPERATIVE = re.compile(r"^\s*(run|try|please|make\s+sure|ensure|remember\s+to|verify|test|check|deploy)\b", re.I)

EVENT_CLASSES = (  # first match wins; checked against operation and capability identifiers
    ("digest", re.compile(r"hash|sha\d*|digest|checksum|summar|manifest|report|receipt", re.I)),
    ("static", re.compile(r"type.?check|typecheck|tsc|mypy|pyright|lint|ruff|compile|build|format|syntax", re.I)),
    ("unit", re.compile(r"test|spec|jest", re.I)),
    ("implementation", re.compile(r"deploy|edit|write|patch|commit|push|apply|install|publish|upload", re.I)),
)
CLASS_SYNONYMS = {"static": {"type", "typecheck", "check", "lint"}, "unit": {"test", "unittest"}}
NEGATIVE_KEYS = {"exit_code", "returncode", "exit_status", "failures", "failed", "errors"}
FALSE_KEYS = {"ok", "passed", "success"}
IGNORED_KEYS = re.compile(r"sha|hash|digest|summary|checksum", re.I)
STOPWORDS = {"the", "and", "for", "with", "this", "that", "all", "now", "was", "were", "are", "has", "have",
             "been", "its", "into", "from", "after", "against"}


def stem(word):
    word = word.lower()
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def tokens(text):
    return {stem(w) for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", text) if w.lower() not in STOPWORDS and len(w) > 2}


def split_units(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^\s*>.*$", " ", text, flags=re.M).replace("`", "")
    # Split only where punctuation ends a phrase, so 3.5, 1,470,679 and URLs stay whole.
    parts = re.split(r"\n+|[.!?;,]+(?=\s|$)", text)
    return [p.strip(" \t-*#") for p in parts if p and p.strip(" \t-*#")]


def requirements(unit):
    if any(p.search(unit) for p in (NONCLAIM, LEADING_QUESTION, LEADING_IMPERATIVE)):
        return []
    found = []
    if EFFECT_WORDS.search(unit):
        found.append("effect")
    elif DELIVERY_WORDS.search(unit):
        found.append("delivery")
    elif UNIT_WORDS.search(unit):
        found.append("static" if STATIC_SUBJECT.search(unit) else "unit")
    if NUMBER.search(unit):
        found.append("numeric")
    return found


def extract_claims(report):
    return [{"text": u, "requires": r} for u in split_units(report) if (r := requirements(u))]


def _record(event):
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    return data["outcome"] if isinstance(data.get("outcome"), dict) else data


def event_class(event):
    record = _record(event)
    name = " ".join(str(record.get(k, "")) for k in ("operation", "capability_id"))
    for label, pattern in EVENT_CLASSES:
        if pattern.search(name):
            return label
    return "runtime"


def _leaves(value, key=""):
    if isinstance(value, dict):
        for k, v in value.items():
            if not IGNORED_KEYS.search(str(k)):
                yield from _leaves(v, str(k))
    elif isinstance(value, list):
        for v in value:
            yield from _leaves(v, key)
    else:
        yield key, value


def is_negative(raw):
    for key, value in _leaves(raw):
        k = key.lower()
        if k in NEGATIVE_KEYS and type(value) in (int, float) and value != 0:
            return True
        if k in FALSE_KEYS and value is False:
            return True
    return False


def contains_number(raw, number):
    want = number.replace(",", "")
    for _key, value in _leaves(raw):
        if type(value) in (int, float) and not isinstance(value, bool) and float(value) == float(want):
            return True
        if isinstance(value, str) and re.search(r"(?<![\w.])" + re.escape(want) + r"(?![\w]|\.\d)", value.replace(",", "")):
            return True
    return False


def _corrected(events):
    out = set()
    for e in events:
        if e.get("kind") == "correction" and isinstance(e.get("data"), dict):
            target = e["data"].get("corrects")
            out.update(target if isinstance(target, list) else [target])
    return out


def _observed(events):
    """Completed, uncorrected, non-negative outcome/observation events: (event, class, raw_result)."""
    retracted = _corrected(events)
    for e in events:
        record = _record(e)
        if (e.get("kind") in OBSERVED_KINDS and record.get("execution_status") == "completed"
                and e.get("sequence") not in retracted and isinstance(record.get("raw_result"), dict)
                and not is_negative(record["raw_result"])):
            yield e, event_class(e), record["raw_result"]


def _names(event, label):
    record = _record(event)
    found = set()
    for k in ("operation", "capability_id"):
        ident = str(record.get(k, ""))
        found |= tokens(ident.replace("_", " ").replace("-", " ").replace(".", " ")) | {stem(ident)}
    return found | CLASS_SYNONYMS.get(label, set())


def judge(claim, events):
    words = tokens(claim["text"])
    numbers = [m.group(1) for m in NUMBER.finditer(claim["text"])]
    observed = list(_observed(events))
    support, best = set(), set()
    for req in claim["requires"]:
        hits = set()
        for e, label, raw in observed:
            if req == "numeric":
                matched = all(contains_number(raw, n) for n in numbers)
            else:
                matched = bool(words & _names(e, label))
            if matched:
                best.add(label)
                if label in SATISFIES[req]:
                    hits.add(e["sequence"])
        if not hits:
            break
        support |= hits
    else:
        return {**claim, "verdict": SUPPORTED, "sequences": sorted(support),
                "reason": "Matching completed observation of the required class."}
    claimed = [e["sequence"] for e in events if e.get("kind") in REPORTED_KINDS and (
        words & tokens(" ".join(str(v) for _k, v in _leaves(e.get("data"))))
        or any(contains_number(e.get("data"), n) for n in numbers))]
    if best:
        reason = ("Observed evidence (" + ", ".join(sorted(best)) + ") is below the required class ("
                  + ", ".join(claim["requires"]) + ")"
                  + ("; a hash or summary is not corroboration" if "digest" in best else "")
                  + ("; implementation is not effect" if "implementation" in best else "") + ".")
        return {**claim, "verdict": UNSUPPORTED, "sequences": [], "reason": reason}
    if claimed:
        return {**claim, "verdict": REPORTED_ONLY, "sequences": claimed,
                "reason": "Only proposal, inference, decision or action events back it; implementation is not effect."}
    ladder = [x for x in LADDER if x in {label for _e, label, _r in observed}]
    return {**claim, "verdict": UNSUPPORTED, "sequences": [], "reason": "No matching ledger evidence"
            + ("; strongest unrelated observation is " + ladder[0] if ladder else "") + "."}


def gate(report, events, *, registry=None, atom_refs=None, consumer=None):
    if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
        raise ValueError("Ledger must be a list of event objects")
    verdicts = [judge(c, events) for c in extract_claims(report)]
    failing = [v for v in verdicts if v["verdict"] != SUPPORTED]
    result = {"schema": SCHEMA, "claims": verdicts, "claim_count": len(verdicts),
            "unsupported": sum(v["verdict"] == UNSUPPORTED for v in verdicts),
            "reported_only": sum(v["verdict"] == REPORTED_ONLY for v in verdicts),
            "passed": not failing,
            "limitations": ["Heuristic claim detector; SUPPORTED means matching evidence exists, not truth."]}
    if atom_refs is not None:
        try:
            if registry is None:
                raise ValueError("Atom references require a registry")
            result["approved_atoms"] = registry.resolve(atom_refs, consumer)
        except (ValueError, OSError) as exc:
            result.update(passed=False, atom_error=str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a report's strong claims against POODO ledger events.")
    parser.add_argument("--report", required=True, help="final report text file")
    parser.add_argument("--ledger", required=True, help="JSON list of ledger events, or an object with 'ledger'")
    parser.add_argument("--atoms", help="approved-atom JSONL store")
    parser.add_argument("--atom-refs", help="JSON list of {id, sha256} references")
    parser.add_argument("--consumer", help="stable project/artifact consumer identifier")
    args = parser.parse_args(argv)
    if any((args.atoms, args.atom_refs, args.consumer)) and not all((args.atoms, args.atom_refs, args.consumer)):
        parser.error("--atoms, --atom-refs and --consumer must be supplied together")
    with open(args.report, encoding="utf-8") as f:
        report = f.read()
    with open(args.ledger, encoding="utf-8") as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get("ledger")
    try:
        options = {}
        if args.atoms:
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from forge.endoforge.tools.approved_atoms import Registry
            with open(args.atom_refs, encoding="utf-8") as f:
                options = dict(registry=Registry(args.atoms), atom_refs=json.load(f), consumer=args.consumer)
            if options["atom_refs"] is None:
                raise ValueError("Atom references must be a list")
        result = gate(report, events, **options)
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

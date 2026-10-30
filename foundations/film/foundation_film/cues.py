"""cue_vocabulary_check: is the shared cue vocabulary closed before anything renders? (I18.)

Every id two lanes must agree on (voice markers, picture cues, sound-effect events, shot ids) is a contract. One lane
provides ids with times (the recorded voice's markers); other lanes reference ids (scene, overlay and mix lanes). An
alias table may map a referenced spelling onto a provided id. The check, run statically before any render:
  - every referenced id resolves, directly or through one alias whose target is provided (missing ids are listed);
  - every per-beat required sequence resolves and lands in strictly increasing time;
  - every minimum gap rule holds (the time from the end of one marker, or its start when no end is given, to the next).
On the reference run 52 ids were unresolved because each scene lane invented its own marker names while the voice lane
wrote word markers, and the timing rules surfaced one boot at a time.
"""
from .measures import ToolInputError, array, check, exact, identifier, identifiers, ms, verdict

MAX_PROVIDED, MAX_ALIASES, MAX_LANES, MAX_REFS, MAX_ORDERS, MAX_SEQUENCE, MAX_GAPS = 1024, 512, 64, 256, 64, 64, 64


def _provided(value):
    markers = {}
    for i, raw in enumerate(array(value, "provided", 1, MAX_PROVIDED)):
        row = exact(raw, f"provided[{i}]", ("id", "t_ms"), ("end_ms",))
        ident = identifier(row["id"], f"provided[{i}].id")
        if ident in markers:
            raise ToolInputError(f"provided repeats id {ident}")
        start = ms(row["t_ms"], f"provided[{i}].t_ms")
        end = ms(row["end_ms"], f"provided[{i}].end_ms") if "end_ms" in row else None
        if end is not None and end < start:
            raise ToolInputError(f"provided[{i}] ends before it starts")
        markers[ident] = {"t_ms": start, "end_ms": end}
    return markers


def _aliases(value, markers):
    if type(value) is not dict or len(value) > MAX_ALIASES:
        raise ToolInputError(f"aliases must be an object of at most {MAX_ALIASES} entries")
    for key, target in value.items():
        identifier(key, "aliases key")
        identifier(target, f"aliases.{key}")
        if key in markers:
            raise ToolInputError(f"alias {key} shadows a provided id")
    return dict(value)


def cue_vocabulary_check(arguments):
    exact(arguments, "arguments", ("provided", "lanes"), ("aliases", "orders", "min_gaps"))
    markers = _provided(arguments["provided"])
    aliases = _aliases(arguments.get("aliases", {}), markers)
    broken = sorted(key for key, target in aliases.items() if target not in markers)
    missing = set()

    def resolve(ident):
        if ident in markers:
            return ident
        if ident in aliases and aliases[ident] in markers:
            return aliases[ident]
        missing.add(ident)
        return None

    lanes, seen = [], set()
    for i, raw in enumerate(array(arguments["lanes"], "lanes", 1, MAX_LANES)):
        row = exact(raw, f"lanes[{i}]", ("lane", "references"))
        lane = identifier(row["lane"], f"lanes[{i}].lane")
        if lane in seen:
            raise ToolInputError(f"lanes repeats lane {lane}")
        seen.add(lane)
        refs = identifiers(row["references"], f"lanes[{i}].references", MAX_REFS)
        resolved = {ref: resolve(ref) for ref in refs}
        lanes.append({"lane": lane, "references": len(refs), "direct": sum(1 for r in refs if r in markers),
                      "by_alias": [{"id": r, "to": t} for r, t in resolved.items() if t is not None and t != r],
                      "missing": sorted(r for r, t in resolved.items() if t is None)})
    orders, checks = [], []
    for i, raw in enumerate(array(arguments.get("orders", []), "orders", 0, MAX_ORDERS)):
        row = exact(raw, f"orders[{i}]", ("beat", "sequence"))
        beat = identifier(row["beat"], f"orders[{i}].beat")
        sequence = identifiers(row["sequence"], f"orders[{i}].sequence", MAX_SEQUENCE, min_items=2)
        steps = [(k, ref, resolve(ref)) for k, ref in enumerate(sequence)]
        timed = [(k, ref, markers[t]["t_ms"]) for k, ref, t in steps if t is not None]
        violation = next(({"index": k, "id": ref, "t_ms": t, "previous_id": pref, "previous_t_ms": pt}
                          for (_, pref, pt), (k, ref, t) in zip(timed, timed[1:]) if t <= pt), None)
        order_check = check(f"order:{beat}", None if len(timed) < 2 else
                            sum(1 for (_, _, a), (_, _, b) in zip(timed, timed[1:]) if b <= a), None, 0)
        checks.append(order_check)
        orders.append({"beat": beat, "status": order_check["status"], "resolved": len(timed),
                       "unresolved": [ref for _, ref, t in steps if t is None], "first_violation": violation})
    gaps = []
    for i, raw in enumerate(array(arguments.get("min_gaps", []), "min_gaps", 0, MAX_GAPS)):
        row = exact(raw, f"min_gaps[{i}]", ("rule", "after", "next", "min_ms"))
        rule = identifier(row["rule"], f"min_gaps[{i}].rule")
        after, nxt = resolve(identifier(row["after"], "after")), resolve(identifier(row["next"], "next"))
        gap = None
        if after is not None and nxt is not None:
            end = markers[after]["end_ms"]
            gap = markers[nxt]["t_ms"] - (markers[after]["t_ms"] if end is None else end)
        gap_check = check(f"gap:{rule}", gap, ms(row["min_ms"], f"min_gaps[{i}].min_ms"), None)
        checks.append(gap_check)
        gaps.append({"rule": rule, "gap_ms": gap, "min_ms": gap_check["min"], "status": gap_check["status"]})
    checks = [check("missing_ids", len(missing), None, 0), check("broken_aliases", len(broken), None, 0)] + checks
    aliased = {r["id"] for lane in lanes for r in lane["by_alias"]}
    result = {"verdict": verdict(checks), "checks": checks, "missing_ids": sorted(missing),
              "broken_aliases": [{"id": k, "to": aliases[k]} for k in broken], "lanes": lanes, "orders": orders,
              "gaps": gaps, "provided": len(markers), "aliases_used": len(aliased)}
    return result["verdict"], result

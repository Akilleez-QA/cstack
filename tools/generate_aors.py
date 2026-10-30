"""Generate aors/fleet.json from the fleet's own records. Every entry starts as CHECK until the owner reviews it.

Inputs (read-only):
  --roles   ops/agent-roles directory (notebook-slugs.tsv + index.md routing table)
  --agents  cstack AGENTS.md (the "Fleet ownership" slice table)
  --devices tailnet device names, one per line: the first label of each node's DNSName from
            `tailscale status --json` (HostName is not unique), excluding Tailscale's funnel-ingress-node relays
The output is reviewed and committed by a person; this tool never grants or changes runtime authority.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.aor_registry import parse_fleet  # noqa: E402

DEFAULT = {"read": "allow", "write_slice": "deny", "execute": "allow", "config": "allow",
           "send": "ask", "payment": "ask", "post": "ask", "filing": "ask", "delete": "ask"}
GUEST = {**DEFAULT, "execute": "deny", "config": "deny"}
# Other names the role map uses for the same bot.
ALIASES = {"money hour": "5d59a807", "personal assistant": "a5e5dd69", "the keymaster": "9973714f",
           "business coach": "d5eab1c4"}
# Owners stated in the role map; every other device is left unowned for the owner to assign.
DEVICE_OWNER_HINTS = {r"^grok-box": "grok-vm-maintenance"}


def table_rows(text, header):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def generate(roles: Path, agents: Path, hostnames: list[str]) -> dict:
    bots = {}
    for line in (roles / "notebook-slugs.tsv").read_text().splitlines()[1:]:
        name, ident, slug, _ = line.split("\t")
        bots[ident] = {"id": ident, "name": name.removesuffix(" test"), "slug": slug, "reports_to": None,
                       "owns": [], "not": [], "slices": [], "effects": dict(DEFAULT), "status": "CHECK"}
    names = sorted([(b["name"].lower(), b["id"]) for b in bots.values()] + list(ALIASES.items()),
                   key=lambda pair: -len(pair[0]))

    def find(cell):
        ident = re.search(r"\b([0-9a-f]{8})\b", cell)
        if ident and ident.group(1) in bots:
            return bots[ident.group(1)]
        return next((bots[i] for name, i in names if name in cell.lower() and i in bots), None)

    for domain, owner, not_owned in table_rows((roles / "index.md").read_text(), "| Domain |"):
        bot = find(owner)
        if bot is None or domain.startswith("Moves "):
            continue
        bot["owns"].append(domain)
        if not_owned:
            bot["not"].append(not_owned)
        boss = re.search(r"reports to ([A-Z][\w &]+?)[),]", domain + " " + owner)
        if boss and (parent := find(boss.group(1))) and parent is not bot:
            bot["reports_to"] = parent["slug"]
    for name, ident, slice_cell, scope, out_of_scope in table_rows(agents.read_text(), "| Bot | Id |"):
        bot = bots[ident]
        bot["owns"].append("Repo slice: " + scope)
        bot["not"].append(out_of_scope)
        bot["slices"] = re.findall(r"`([^`]+)`", slice_cell.split(", and every path")[0]) or ["/"]
        if "every path not listed" in slice_cell:
            bot["slices"] = ["/"] + [s for s in bot["slices"] if s != "/"]
        bot["effects"]["write_slice"] = "allow"
    devices = []
    for host in sorted(set(hostnames)):
        owner = next((slug for pattern, slug in DEVICE_OWNER_HINTS.items() if re.match(pattern, host)), None)
        devices.append({"hostname": host, "owner": owner, "guest_effects": dict(GUEST), "status": "CHECK"})
    return {"schema": "cstack.fleet/0.1", "approver": "owner-via-approver",
            "source": {"generated_by": "tools/generate_aors.py",
                       "inputs": [str(roles / "notebook-slugs.tsv"), str(roles / "index.md"), str(agents)]},
            "bots": sorted(bots.values(), key=lambda b: b["slug"]), "devices": devices}


def render(document) -> str:
    """One bot or device per line, so each AOR is a single reviewable diff line."""
    line = lambda value: json.dumps(value, ensure_ascii=False)  # noqa: E731
    rows = lambda items: ",\n".join("    " + line(item) for item in items)  # noqa: E731
    head = ",\n".join(f"  {line(key)}: {line(document[key])}" for key in ("schema", "approver", "source"))
    return f'{{\n{head},\n  "bots": [\n{rows(document["bots"])}\n  ],\n  "devices": [\n{rows(document["devices"])}\n  ]\n}}\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--roles", type=Path, required=True)
    parser.add_argument("--agents", type=Path, required=True)
    parser.add_argument("--devices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    document = generate(args.roles, args.agents, [h.strip() for h in args.devices.read_text().split() if h.strip()])
    parse_fleet(document)  # the output must load before it is written
    args.output.write_text(render(document))
    print(f"{len(document['bots'])} bots, {len(document['devices'])} devices -> {args.output}")


if __name__ == "__main__":
    main()

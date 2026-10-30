"""Shared fixtures for the per-AOR session (ADR 003, PR 5): a two-bot fleet and an ADR 004 test roster.

Session and MCP tests need *a* domain, not a particular one, so they run the Template's placeholder tool (SAMPLE).
Refrigeration-specific checks use REFRIGERATION and skip when that Foundation is absent from the checkout.
"""
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
from typing import Callable

from bootstrap import DOMAINS

APPROVER = "owner-via-approver"
OPTIONS = [f"option-{i}" for i in range(20)]
R717_20F = {"fluid": "R717", "temperature": {"value": 20, "unit": "degF"}}
HAVE_REFRIGERATION = "foundation_refrigeration" in DOMAINS
NO_REFRIGERATION = "Foundation Refrigeration is not in this checkout (foundations/refrigeration is absent)"
GATED = ("send", "payment", "post", "filing", "delete")
HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
NO_CRYPTO = "WitnessedLedger needs 'cryptography' (ADR 004 open question 3): uv run --with cryptography ..."


def psig(outcome):
    views = outcome["raw_result"]["structuredContent"]["receipt"]["result"]["pressure_views"]
    return f"{next(v['value'] for v in views if v['unit'] == 'psig'):.2f}"


def echoed(outcome):
    return outcome["raw_result"]["structuredContent"]["receipt"]["result"]["observation"]


@dataclass(frozen=True)
class Sample:
    """One domain's fixture goal and call; reading(outcome) must equal value after it executes."""
    domain: str
    objective: str
    reference: str
    operation: str
    arguments: dict
    expected: str
    reading: Callable
    value: str


TEMPLATE = Sample("foundation_template", "Echo one fixture observation.", "foundations/template/README.md",
                  "echo_observation", {"observation": "fixture reading 7"},
                  "The template echoes 'fixture reading 7', CHECK", echoed, "fixture reading 7")
REFRIGERATION = Sample("foundation_refrigeration", "Read R717 saturation at 20 degF.",
                       "contracts/DECISION-002-foundation-refrigeration.md", "saturation_pressure", R717_20F,
                       "R717 at 20 degF reads 33.49 psig, CHECK", psig, "33.49")
SAMPLE = TEMPLATE
DOMAIN = SAMPLE.domain


def golden_tools(path):
    """A golden tools/list with its domain enum set to this checkout's registered domains."""
    from adapters.mcp_stdio_server import domain_tools
    tools = json.loads(Path(path).read_text())["tools"]
    return json.loads(json.dumps(domain_tools(DOMAINS, tools)))


def effects(read):
    return {"read": read, "write_slice": "deny", "execute": "ask", "config": "ask", **{g: "ask" for g in GATED}}


def bot(bot_id, slug, read="allow"):
    return {"id": bot_id, "name": slug.title(), "slug": slug, "reports_to": None, "owns": ["Fixture work"],
            "not": ["everything else"], "slices": [], "effects": effects(read), "status": "CHECK"}


def write_fleet(directory, *, alpha_read="allow", owner="alpha", guest_read="allow"):
    path = Path(directory) / "fleet.json"
    path.write_text(json.dumps({
        "schema": "cstack.fleet/0.1", "approver": APPROVER,
        "source": {"generated_by": "tests/aor_fixtures.py", "inputs": ["fixture"]},
        "bots": [bot("0000000a", "alpha", alpha_read), bot("0000000b", "beta")],
        "devices": [{"hostname": "testbox", "owner": owner, "guest_effects": effects(guest_read),
                     "status": "CHECK"}]}))
    return path


def write_witnessed_config(state, node="testbox", bots=("alpha",)):
    """ADR 004 test roster, keys and <state>/ledger.json, made with the prototype's own helpers."""
    from adapters.witnessed_ledger import ledger_lib
    L = ledger_lib()
    (state / "ledger").mkdir(parents=True, exist_ok=True)
    keys = {name: L.Ed25519PrivateKey.generate() for name in (*bots, "w1", "w2", "w3")}
    roster = {"quorum": 2, "witnesses": {w: L.pub_hex(keys[w]) for w in ("w1", "w2", "w3")},
              "writers": {b: {"pub": L.pub_hex(keys[b]), "node": node} for b in bots}}
    (state / "ledger/roster.json").write_text(json.dumps(roster))
    for b in bots:
        L.save_key(keys[b], str(state / f"ledger/{b}.key"))
    (state / "ledger.json").write_text(json.dumps({
        "node": node, "log": f"ledger/{node}.jsonl", "roster": "ledger/roster.json",
        "writers": {b: {"writer": b, "key": f"ledger/{b}.key"} for b in bots}}))
    return state / f"ledger/{node}.jsonl"

"""Host-owned fleet AOR registry (ADR 003). Loading it grants nothing; bootstrap derives authority from it.

The registry is host configuration: only bootstrap reads it, and no request, hook or tool text can select,
extend or replace it. Validation fails closed.
"""
from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from poodo_core.models import LANES, READ_ONLY_LANES, ContractError

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "aor.schema.json"
EFFECTS = ("read", "write_slice", "execute", "config", "send", "payment", "post", "filing", "delete")
# the owner's rule in every role file: sends, payments, posts, filings and deletions need his explicit yes.
GATED = ("send", "payment", "post", "filing", "delete")
MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class Effects:
    classes: tuple[tuple[str, str], ...]

    def of(self, effect: str) -> str:
        return dict(self.classes)[effect]


@dataclass(frozen=True)
class Bot:
    id: str
    name: str
    slug: str
    reports_to: str | None
    owns: tuple[str, ...]
    not_owned: tuple[str, ...]
    slices: tuple[str, ...]
    effects: Effects
    status: str
    personal_route: str | None = None
    company_route: tuple[str, ...] = ()
    # ADR 005: the port lane this bot's effect set acts in. Optional; absent until the owner assigns fleet lanes.
    lane: str | None = None


@dataclass(frozen=True)
class Device:
    hostname: str
    owner: str | None
    guest_effects: Effects
    status: str


@dataclass(frozen=True)
class Fleet:
    approver: str
    bots: tuple[Bot, ...]
    devices: tuple[Device, ...]

    def bot(self, slug: str) -> Bot:
        for bot in self.bots:
            if bot.slug == slug:
                return bot
        raise ContractError("Unknown AOR")

    def device(self, hostname: str) -> Device:
        for device in self.devices:
            if device.hostname == hostname:
                return device
        raise ContractError("Unknown fleet device")


def _effects(raw) -> Effects:
    return Effects(tuple((name, raw[name]) for name in EFFECTS))


def _route_target(slug, slugs, target, label):
    if target not in slugs or target == slug:
        raise ContractError(f"{slug}: {label} must name another bot")


def _bot(raw, slugs) -> Bot:
    personal, company = None, ()
    routes = raw.get("routes") or {}
    if routes.get("personal") is not None:
        personal = routes["personal"]
        _route_target(raw["slug"], slugs, personal, "personal route")
    if routes.get("company"):
        company = tuple(routes["company"])
        for target in company:
            _route_target(raw["slug"], slugs, target, "company route")
    return Bot(raw["id"], raw["name"], raw["slug"], raw["reports_to"], tuple(raw["owns"]), tuple(raw["not"]),
               tuple(raw["slices"]), _effects(raw["effects"]), raw["status"], personal, company, raw.get("lane"))


def _check_gated(where, effects: Effects):
    for name in GATED:
        if effects.of(name) == "allow":
            raise ContractError(f"{where}: '{name}' needs the owner's explicit yes and can never be allow")


def _slice_overlaps(a: str, b: str) -> bool:
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _check_lane(bot: Bot):
    if bot.lane is None:
        return
    if bot.lane not in LANES:
        raise ContractError(f"{bot.slug}: unknown lane")
    if bot.lane in READ_ONLY_LANES:
        allowed = [name for name in EFFECTS if name != "read" and bot.effects.of(name) != "deny"]
        if allowed:
            raise ContractError(f"{bot.slug}: a {bot.lane} effect set is read-only; deny {', '.join(allowed)}")


def parse_fleet(document: dict) -> Fleet:
    schema = json.loads(SCHEMA_PATH.read_text())
    if tuple(schema["$defs"]["lane"]["enum"]) != LANES:
        raise ContractError("The AOR schema's lanes differ from the core's")
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=str)
    if errors:
        raise ContractError("Invalid fleet registry: " + errors[0].message)
    slugs = {b["slug"] for b in document["bots"]}
    bots = tuple(_bot(b, slugs) for b in document["bots"])
    for field in ("id", "slug"):
        if len({getattr(b, field) for b in bots}) != len(bots):
            raise ContractError(f"Duplicate bot {field}")
    for bot in bots:
        if bot.reports_to is not None and (bot.reports_to not in slugs or bot.reports_to == bot.slug):
            raise ContractError(f"{bot.slug}: reports_to must name another bot")
        if bot.slices and bot.effects.of("write_slice") == "deny":
            raise ContractError(f"{bot.slug}: owns slices but cannot write them")
        _check_gated(bot.slug, bot.effects)
        _check_lane(bot)
    # The root slice "/" means "every path no other bot owns" (Coordinator), so it overlaps nothing.
    owned = [(b.slug, s) for b in bots for s in b.slices if s.strip("/")]
    for i, (slug_a, a) in enumerate(owned):
        for slug_b, b in owned[i + 1:]:
            if slug_a != slug_b and _slice_overlaps(a, b):
                raise ContractError(f"Slice '{a}' ({slug_a}) overlaps '{b}' ({slug_b}): one owner per path")
    devices = tuple(Device(d["hostname"], d["owner"], _effects(d["guest_effects"]), d["status"])
                    for d in document["devices"])
    if len({d.hostname for d in devices}) != len(devices):
        raise ContractError("Duplicate device hostname")
    for device in devices:
        if device.owner is not None and device.owner not in slugs:
            raise ContractError(f"{device.hostname}: owner is not a fleet bot")
        _check_gated(device.hostname, device.guest_effects)
    return Fleet(document["approver"], bots, devices)


def load_fleet(path: Path) -> Fleet:
    """Trusted HOST call only (bootstrap). The path is fixed by host configuration, never by a request."""
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ContractError("Fleet registry exceeds byte budget")
    return parse_fleet(json.loads(raw))

"""The ONLY production composition root selecting concrete implementations/paths.

ADR 005: every Foundation capability attaches on ToolFace, so every Foundation grant is a ToolFace grant. Before a
core is built, each grant is checked against the host adapter inventory (contracts/ADAPTERS.json).

Domains are pluggable. DOMAINS is the one registry of (domain_id -> Foundation, capability adapter, source root,
tool names, inventory adapter); every composition below derives from it. Math and the empty Template are always
registered. Refrigeration, Robotics and Film are registered only when foundations/refrigeration, foundations/robotics
and foundations/film are present, so a checkout without them (the public open-core export) imports and runs cleanly.
"""
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Lock
from typing import Callable
from weakref import WeakValueDictionary
from adapters.adapter_inventory import load_inventory
from adapters.math_stdio import MathStdioCapability
from adapters.memory_ledger import MemoryLedger
from adapters.template_stdio import TemplateStdioCapability
from extensions.foundation_math import FoundationMath, TOOL_NAMES
from extensions.foundation_template import FoundationTemplate, TEMPLATE_TOOL_NAMES
from poodo_core import AuthorityGrant, ContractError

_HERE = Path(__file__).resolve().parent
DEFAULT_MATH_ROOT = _HERE / "vendor/foundation-math-v014"
DEFAULT_TEMPLATE_ROOT = _HERE / "foundations/template"
DEFAULT_REFRIGERATION_ROOT = _HERE / "foundations/refrigeration"
DEFAULT_ROBOTICS_ROOT = _HERE / "foundations/robotics"
DEFAULT_FILM_ROOT = _HERE / "foundations/film"


@dataclass(frozen=True)
class Domain:
    """One registered Foundation. Host configuration only; no request can select or add one."""
    domain_id: str              # also its capability id
    foundation: type            # PoodoCore subclass binding the domain's DomainExtension
    capability: type            # CapabilityPort adapter, constructed with source_root
    source_root: Path
    tool_names: tuple
    adapter_id: str             # its contracts/ADAPTERS.json row
    grant_id: str
    decode: Callable | None = None  # the domain's own driver numeric profile; None means adapters/wire.decode


DOMAINS = {}


def register(domain):
    if domain.domain_id in DOMAINS:
        raise ContractError(f"Domain {domain.domain_id} is already registered")
    DOMAINS[domain.domain_id] = domain


register(Domain("foundation_math", FoundationMath, MathStdioCapability, DEFAULT_MATH_ROOT, TOOL_NAMES,
                "foundation-math-stdio", "local-synthetic-math"))
register(Domain("foundation_template", FoundationTemplate, TemplateStdioCapability, DEFAULT_TEMPLATE_ROOT,
                TEMPLATE_TOOL_NAMES, "foundation-template-stdio", "local-template-observation"))
if DEFAULT_REFRIGERATION_ROOT.is_dir():
    from adapters.refrigeration_stdio import RefrigerationStdioCapability, decode as _decode_refrigeration
    from extensions.foundation_refrigeration import FoundationRefrigeration, REFRIGERATION_TOOL_NAMES
    register(Domain("foundation_refrigeration", FoundationRefrigeration, RefrigerationStdioCapability,
                    DEFAULT_REFRIGERATION_ROOT, REFRIGERATION_TOOL_NAMES, "foundation-refrigeration-stdio",
                    "local-refrigeration-observation", decode=_decode_refrigeration))
if DEFAULT_ROBOTICS_ROOT.is_dir():
    from adapters.robotics_stdio import RoboticsStdioCapability
    from extensions.foundation_robotics import FoundationRobotics, ROBOTICS_TOOL_NAMES
    register(Domain("foundation_robotics", FoundationRobotics, RoboticsStdioCapability, DEFAULT_ROBOTICS_ROOT,
                    ROBOTICS_TOOL_NAMES, "foundation-robotics-stdio", "local-robotics-observation"))
if DEFAULT_FILM_ROOT.is_dir():
    from adapters.film_stdio import FilmStdioCapability
    from extensions.foundation_film import FoundationFilm, FILM_TOOL_NAMES
    register(Domain("foundation_film", FoundationFilm, FilmStdioCapability, DEFAULT_FILM_ROOT, FILM_TOOL_NAMES,
                    "foundation-film-stdio", "local-film-observation"))

# Host table: capability id -> the inventory adapter_id that provides it. Explicit, never inferred.
CAPABILITY_ADAPTERS = {d.domain_id: d.adapter_id for d in DOMAINS.values()}

_LEDGER_CORES = WeakValueDictionary()
_LEDGER_BUILDING = set()
_LEDGER_BIND_LOCK = Lock()


def build_core(ledger, factory, *, store_path=None):
    """Build one live core per ledger store in this process; factory(ledger) must retain the ledger.

    Path-backed hosts must supply the underlying log path even when using separate port objects.
    Paths are resolved to catch relative and symlink aliases. This is not a cross-process lock;
    a persistent host must separately ensure exclusive store ownership across processes.
    The binding lasts until the core is collected. Hosts must still serialise all core calls,
    including reads, from different threads.
    """
    keys = [("port", id(ledger))]
    if store_path is not None:
        keys.append(("path", Path(store_path).resolve()))
    with _LEDGER_BIND_LOCK:
        if any(key in _LEDGER_CORES or key in _LEDGER_BUILDING for key in keys):
            raise ContractError("Ledger store is already bound to a live core or core under construction")
        _LEDGER_BUILDING.update(keys)
    try:
        core = factory(ledger)
        with _LEDGER_BIND_LOCK:
            for key in keys:
                _LEDGER_CORES[key] = core
        return core
    finally:
        with _LEDGER_BIND_LOCK:
            _LEDGER_BUILDING.difference_update(keys)


def check_grants(grants, inventory=None):
    """ADR 005 item 1 x item 3. Fail closed: an unmapped capability, an adapter missing from the inventory, or a
    grant whose lane is not the providing adapter's inventory lane refuses to start."""
    inventory = load_inventory() if inventory is None else inventory
    for grant in grants:
        adapter_id = CAPABILITY_ADAPTERS.get(grant.capability_id)
        if adapter_id is None:
            raise ContractError(f"No inventory adapter is mapped for capability {grant.capability_id}")
        lanes = inventory.lanes_for(adapter_id)
        if grant.lane not in lanes:
            raise ContractError(f"Grant {grant.grant_id} is on {grant.lane}; {adapter_id} is on {', '.join(lanes)}")
        inventory.attachment(adapter_id, grant.lane)
    return grants


def registered(domain_id):
    """The registered Domain, or ContractError: an absent or unknown domain never falls back to another."""
    if domain_id not in DOMAINS:
        raise ContractError(f"Domain {domain_id} is not registered on this host")
    return DOMAINS[domain_id]


def build_domain(domain_id, goal_id, *, operations=None, max_calls=64, source_root=None, inventory=None):
    """Trusted HOST configuration only. No external JSON controls source_root/grants/inventory.

    Every registered Foundation is read-only observation: the grant names only its fixed tools.
    """
    d = registered(domain_id)
    operations = d.tool_names if operations is None else operations
    grant = AuthorityGrant(d.grant_id, d.domain_id, d.domain_id, tuple(operations), (goal_id,), max_calls,
                           lane="ToolFace")
    grants = check_grants((grant,), inventory)
    capability = d.capability(d.source_root if source_root is None else source_root)
    core = build_core(MemoryLedger(), lambda ledger: d.foundation(capability, grants, ledger))
    return core, capability


def build_math(goal_id, *, operations=TOOL_NAMES, max_calls=64, source_root=DEFAULT_MATH_ROOT, inventory=None):
    return build_domain("foundation_math", goal_id, operations=operations, max_calls=max_calls,
                        source_root=source_root, inventory=inventory)


def build_template(goal_id, *, operations=TEMPLATE_TOOL_NAMES, max_calls=64, source_root=DEFAULT_TEMPLATE_ROOT,
                   inventory=None):
    return build_domain("foundation_template", goal_id, operations=operations, max_calls=max_calls,
                        source_root=source_root, inventory=inventory)


def build_refrigeration(goal_id, *, operations=None, max_calls=64, source_root=DEFAULT_REFRIGERATION_ROOT,
                        inventory=None):
    """Read-only observation tools; no control or write grant exists. Refuses when Refrigeration is absent."""
    return build_domain("foundation_refrigeration", goal_id, operations=operations, max_calls=max_calls,
                        source_root=source_root, inventory=inventory)


def build_robotics(goal_id, *, operations=None, max_calls=64, source_root=DEFAULT_ROBOTICS_ROOT, inventory=None):
    """Read-only motion judgements; no rig, render, write or control grant exists. Refuses when Robotics is absent."""
    return build_domain("foundation_robotics", goal_id, operations=operations, max_calls=max_calls,
                    source_root=source_root, inventory=inventory)


def build_film(goal_id, *, operations=None, max_calls=64, source_root=DEFAULT_FILM_ROOT, inventory=None):
    """Read-only measured gates; no render, generation or write grant exists. Refuses when Film is absent."""
    return build_domain("foundation_film", goal_id, operations=operations, max_calls=max_calls,
                        source_root=source_root, inventory=inventory)


DEFAULT_FLEET = Path(__file__).resolve().parent / "aors/fleet.json"
MEMORY_LEDGER = "memory (not durable: no ADR 004 roster configured)"


def _witnessed_config(state_root, bot_slug, hostname):
    """<state_root>/ledger.json names the node log, roster, and each bot's writer and key (ADR 004).

    Relative paths resolve under state_root. A configured ledger with no writer for this bot fails closed.
    """
    import json
    from poodo_core import ContractError

    try:
        config = json.loads((state_root / "ledger.json").read_text())
        writer = config["writers"][bot_slug]
        node = config.get("node", hostname)
        paths = {name: state_root / config[name] for name in ("log", "roster")}
        paths["key"] = state_root / writer["key"]
        if type(writer["writer"]) is not str or type(node) is not str:
            raise TypeError("writer and node must be strings")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ContractError(f"ledger.json has no usable ADR 004 writer for {bot_slug}: {error!r}") from None
    return node, writer["writer"], paths


def build_aor_session(bot_slug, *, state_root, hostname, fleet_path=DEFAULT_FLEET, clock=None, enforce=None,
                      fleet_mail=None):
    """Trusted HOST configuration only (ADR 003): one bot's AOR on this device, for the MCP driving adapter.

    The bot slug comes from the host's launch command, never from a request. Foundations are pure
    computations, so every operation is the 'read' effect; the AOR, device and shields decide its class.
    The ledger is the ADR 004 WitnessedLedger when <state_root>/ledger.json exists, else MemoryLedger. Every core
    owns a separate file derived from the configured log, with stream "<bot>.<domain>", its own chain, budget
    and anchor. A lifetime store claim refuses a second live session for the same bot and domain.
    enforce defaults to the host's LEDGER_ENFORCE=1 (ADR 004: off unless the owner turns it on).
    fleet_mail is a host-owned FleetMailConfig; None (the default) disables mail.
    """
    import os
    import time
    from adapters.aor_registry import load_fleet
    from adapters.aor_session import AorSession, LedgerStoreClaim, SessionApprovalReader
    from adapters.approval_store import ApprovalReader

    state_root = Path(state_root)
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fleet = load_fleet(fleet_path)
    clock = clock or (lambda: int(time.time()))
    enforce = os.environ.get("LEDGER_ENFORCE") == "1" if enforce is None else enforce
    approvals = SessionApprovalReader(lambda: ApprovalReader(state_root / "approvals.db", clock=clock,
                                                             consumer=bot_slug))
    witnessed = (state_root / "ledger.json").exists()
    if witnessed:
        from adapters.witnessed_ledger import WitnessedLedger
        node, writer, paths = _witnessed_config(state_root, bot_slug, hostname)

        def make_ledger(domain, anchors, store_path):
            stream = f"{bot_slug}.{domain}"
            return WitnessedLedger(store_path, node, paths["roster"], writer, paths["key"], stream=stream,
                                   enforce=enforce, anchor=anchors.get(stream))
    else:
        def make_ledger(domain, anchors, store_path):
            return MemoryLedger()

    def make_core(domain, grants, anchors):
        d = DOMAINS[domain]
        store_path = (paths["log"].with_suffix("") / bot_slug / f"{domain}.jsonl") if witnessed else None
        claim = LedgerStoreClaim(store_path) if store_path is not None else None
        ledger = None
        try:
            ledger = make_ledger(domain, anchors, store_path)
            checked = check_grants(grants)
            core = build_core(ledger, lambda port: d.foundation(
                d.capability(d.source_root), checked, port, approvals=approvals, approver=fleet.approver,
                clock=clock), store_path=store_path)
        except BaseException:
            if ledger is not None and hasattr(ledger, "close"):
                ledger.close()
            if claim is not None:
                claim.close()
            raise
        return core, ledger, claim

    domains = {d.domain_id: (d.tool_names, "read") for d in DOMAINS.values()}
    session = AorSession(fleet=fleet, bot_slug=bot_slug, hostname=hostname, state_dir=state_root, domains=domains,
                         make_core=make_core, ledger_label="witnessed" if witnessed else MEMORY_LEDGER,
                         shields_file=state_root / "SHIELDS_UP")
    if fleet_mail is not None:
        ledger = None
        try:
            # Mail has its own signed stream; never borrow a Foundation core's chain.
            ledger = make_ledger("fleet_mail", {}, paths["log"] if witnessed else None)
            session.mail = _build_fleet_mail(fleet_mail, session, fleet, state_root,
                                             paths if witnessed else None, ledger, clock)
        except BaseException:
            if ledger is not None and hasattr(ledger, "close"):
                ledger.close()
            session.close()
            raise
    return session


def _build_fleet_mail(config, session, fleet, state_root, witnessed_paths, ledger, clock):
    """Fleet mail for this AOR: repo, gh path and labels are host-fixed here; the sender is the --aor slug.

    Writes take the bot's own execute class (internal, non-destructive) plus shields; see adapters/fleet_mail.py.
    """
    import shutil
    from adapters.fleet_mail import FleetMail, GitHubIssuesMail, roster_signers

    slugs = tuple(bot.slug for bot in fleet.bots)
    gh = config.gh or shutil.which("gh")
    if gh is None:
        from poodo_core import ContractError
        raise ContractError("Fleet mail needs the gh CLI on the host's PATH")
    signers = roster_signers(state_root, slugs) if witnessed_paths else {}
    return FleetMail(GitHubIssuesMail(config.repo, str(Path(gh).resolve())), me=session.bot.slug, fleet_slugs=slugs,
                     config=config, state_dir=state_root / session.bot.slug, shields_up=session.shields_up,
                     write_class=session.bot.effects.of("execute"), read_class=session.bot.effects.of("read"),
                     clock=clock, ledger=ledger, signers=signers,
                     key_path=witnessed_paths["key"] if witnessed_paths else None)


COMPOSITIONS = tuple(partial(build_domain, domain_id) for domain_id in DOMAINS)

"""Host-owned adapter inventory (ADR 005 decision 3). Loading it grants nothing.

One row per attachment of an outside tool to a port lane, keyed by (adapter_id, lane). Like the AOR registry,
this is host configuration: only trusted host code reads it, and no request, hook or tool text can select,
extend or replace it. Validation fails closed. The repository checks (every scanned file has a row, every path
exists) live in tests/test_adapter_inventory.py, because they describe this checkout, not the contract.
"""
from dataclasses import dataclass
import inspect
import json
from pathlib import Path
from typing import Protocol

from jsonschema import Draft202012Validator
from poodo_core import ports
from poodo_core.models import LANES, READ_ONLY_LANES, ContractError

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "contracts" / "adapters.schema.json"
INVENTORY_PATH = ROOT / "contracts" / "ADAPTERS.json"
# LANES and READ_ONLY_LANES come from the core (poodo_core.models), the one definition; re-exported here.
# ADR 005 decision 2: these protocols are core seams with no lane.
CORE_SEAMS = ("Cancellation", "DomainExtension", "EndoforgePort")
LANE_PORTS = tuple(sorted(name for name, obj in vars(ports).items()
                          if inspect.isclass(obj) and Protocol in obj.__mro__ and obj is not Protocol
                          and name not in CORE_SEAMS))
# ADR 005 decision 2 table: the one lane of each port protocol. CostPort is SupervisorFace, not TruthFace.
# MemoryPort landed after the ADR (#77); LearningFace is this inventory's placement and needs ADR confirmation.
# AdmissionPort (#92) is SupervisorFace per contracts/INTERFACES.md.
PORT_LANES = {"ApprovalPort": "TruthFace", "LedgerPort": "EvidenceFace", "CostPort": "SupervisorFace",
              "CapabilityPort": "ToolFace", "MemoryPort": "LearningFace", "AdmissionPort": "SupervisorFace"}
MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class Attachment:
    adapter_id: str
    lane: str
    port: str | None          # None means "none": no ports.py protocol (see port_reason)
    port_reason: str | None
    vendor: str
    kind: str
    path: str | None
    command: str | None
    fake: str | None
    fake_reason: str | None
    status: str
    strategic_dependency_adr: str | None
    notes: str


@dataclass(frozen=True)
class Inventory:
    attachments: tuple[Attachment, ...]
    not_an_adapter: tuple[tuple[str, str], ...]   # (path, role)

    def lanes_for(self, adapter_id: str) -> tuple[str, ...]:
        """Every lane this adapter attaches to, in LANES order. Unknown adapters fail closed."""
        lanes = {a.lane for a in self.attachments if a.adapter_id == adapter_id}
        if not lanes:
            raise ContractError("Unknown adapter")
        return tuple(lane for lane in LANES if lane in lanes)

    def attachment(self, adapter_id: str, lane: str) -> Attachment:
        """The one row for this attachment. A grant on another lane finds nothing and fails closed."""
        for a in self.attachments:
            if a.adapter_id == adapter_id and a.lane == lane:
                return a
        raise ContractError("Unknown adapter attachment")


def parse_inventory(document: dict) -> Inventory:
    errors = sorted(Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(document), key=str)
    if errors:
        raise ContractError("Invalid adapter inventory: " + errors[0].message)
    rows = tuple(Attachment(r["adapter_id"], r["lane"], None if r["port"] == "none" else r["port"],
                            r.get("port_reason"), r["vendor"], r["kind"], r.get("path"), r.get("command"),
                            r["fake"], r.get("fake_reason"), r["status"], r["strategic_dependency_adr"], r["notes"])
                 for r in document["attachments"])
    keys = [(a.adapter_id, a.lane) for a in rows]
    if len(set(keys)) != len(keys):
        raise ContractError("Duplicate adapter attachment (adapter_id, lane)")
    port_lane = {}
    for a in rows:
        if a.port is None:
            continue
        if a.port not in LANE_PORTS:
            raise ContractError(f"{a.adapter_id}: '{a.port}' is not a lane port in poodo_core/ports.py")
        # ADR 005 decision 2: each port protocol sits in at most one lane, the one its table names.
        if port_lane.setdefault(a.port, a.lane) != a.lane:
            raise ContractError(f"{a.port} is listed on two lanes")
        if PORT_LANES.get(a.port) != a.lane:
            raise ContractError(f"{a.adapter_id}: {a.port} belongs on {PORT_LANES.get(a.port)}, not {a.lane}")
    skipped = tuple((n["path"], n["role"]) for n in document["not_an_adapter"])
    if len({p for p, _ in skipped}) != len(skipped) or {p for p, _ in skipped} & {a.path for a in rows}:
        raise ContractError("A not_an_adapter path is duplicated or also has an attachment row")
    return Inventory(rows, skipped)


def load_inventory(path: Path = INVENTORY_PATH) -> Inventory:
    """Trusted HOST call only. The path is fixed by host configuration, never by a request."""
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ContractError("Adapter inventory exceeds byte budget")
    return parse_inventory(json.loads(raw))

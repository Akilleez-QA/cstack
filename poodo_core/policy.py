"""Host-supplied authority is never minted by requests, hooks, or tool text."""
from dataclasses import dataclass, field
from .models import LANES, READ_ONLY_LANES, ContractError, identifier, port_lane

_HEX = set("0123456789abcdef")


class ApprovalPending(ContractError):
    """The decision needs the host approver's yes. Nothing was dispatched."""


class ApprovalDeclined(ContractError):
    """The host approver said no. The decision is consumed; a decline is never tool output."""


class BudgetPaused(ContractError):
    """The AOR's committed spend reached its host budget. Nothing is decided or dispatched until the host lifts it."""


MAX_COST = 10**15
MAX_CAPACITY = 10**6


class CapacityRefused(ContractError):
    """ADR 005 item 5a: the AOR's host capacity refused the call. Nothing was started, held, spent or dispatched."""


@dataclass(frozen=True)
class CapacityLimits:
    """Host capacity for one AOR (SupervisorFace). live_cap is the host's current dial on live attempts, at most
    max_live_attempts; 0 pauses the AOR. other_* is usage the host sees outside this core, added to the core's own.
    soonest_reset_at (epoch seconds) is when the host expects capacity to free up, if it knows."""
    aor_id: str
    max_open_goals: int
    max_live_attempts: int
    max_pending_asks: int
    live_cap: int
    other_open_goals: int = 0
    other_live_attempts: int = 0
    other_pending_asks: int = 0
    soonest_reset_at: int | None = None

    def __post_init__(self):
        identifier(self.aor_id)
        counts = (self.max_open_goals, self.max_live_attempts, self.max_pending_asks, self.live_cap,
                  self.other_open_goals, self.other_live_attempts, self.other_pending_asks)
        if any(type(n) is not int or not 0 <= n <= MAX_CAPACITY for n in counts):
            raise ContractError("Capacity limits and usage are bounded non-negative integers")
        if self.live_cap > self.max_live_attempts:
            raise ContractError("The live cap cannot exceed the maximum live attempts")
        if self.soonest_reset_at is not None and (type(self.soonest_reset_at) is not int
                                                or not 1 <= self.soonest_reset_at <= MAX_COST):
            raise ContractError("A capacity reset time is bounded positive integer epoch seconds")


@dataclass(frozen=True)
class CostBudget:
    """Host-supplied spend limit for one AOR, in integer minor units of `unit` (for example usd_micros)."""
    aor_id: str
    limit: int
    unit: str

    def __post_init__(self):
        identifier(self.aor_id)
        identifier(self.unit)
        if type(self.limit) is not int or not 1 <= self.limit <= MAX_COST:
            raise ContractError("A budget limit is a positive integer of minor units")


@dataclass(frozen=True)
class AuthorityGrant:
    grant_id: str
    domain_id: str
    capability_id: str
    operations: tuple[str, ...]
    goal_ids: tuple[str, ...]
    max_calls: int
    # ADR 003: a deny in any grant wins; an ask is allowed only with a host-recorded approval.
    ask_operations: tuple[str, ...] = ()
    deny_operations: tuple[str, ...] = ()
    # PR 9: the AOR whose host CostBudget pays for calls under this grant.
    aor_id: str | None = None
    # ADR 005: the port lane this grant's attachment sits in. Required; the core refuses a mismatch.
    lane: str = field(kw_only=True)

    def __post_init__(self):
        for value in (self.grant_id, self.domain_id, self.capability_id):
            identifier(value)
        if port_lane(self.lane) in READ_ONLY_LANES:
            # Every grant operation is an operation for execute, and read-only lanes have no execute path.
            raise ContractError("A ReadModelFace or LearningFace grant can never name an operation for execute")
        if self.aor_id is not None:
            identifier(self.aor_id)
        scopes = (self.operations, self.goal_ids, self.ask_operations, self.deny_operations)
        if any(type(scope) is not tuple for scope in scopes):
            raise ContractError("Authority scopes must be immutable")
        for value in (*self.operations, *self.goal_ids, *self.ask_operations, *self.deny_operations):
            identifier(value)
        if not self.operations or not self.goal_ids or type(self.max_calls) is not int or not 1 <= self.max_calls <= 64:
            raise ContractError("Invalid authority budget")
        if not set(self.ask_operations) <= set(self.operations):
            raise ContractError("Ask operations must be operations this grant could otherwise allow")
        if set(self.deny_operations) & set(self.operations):
            raise ContractError("An operation cannot be both granted and denied by one grant")

    def permits(self, domain_id, request):
        return (self.domain_id == domain_id and self.capability_id == request.capability_id
                and request.operation in self.operations and request.goal_id in self.goal_ids)

    def denies(self, domain_id, request):
        return (self.domain_id == domain_id and self.capability_id == request.capability_id
                and request.operation in self.deny_operations)

    def asks(self, request):
        return request.operation in self.ask_operations


@dataclass(frozen=True)
class ApprovalRecord:
    """A host-recorded answer to one ask, bound to one decision, one exact request digest and one goal revision.

    Only the trusted host's ApprovalPort supplies these (ADR 003: the owner, through the approval channel). A request, hook, tool
    result or model text can never create one. An approval is single-use and expires at not_after (epoch seconds).
    """
    approval_id: str
    decision_id: str
    request_sha256: str
    goal_id: str
    goal_revision: int
    approver: str
    verdict: str
    not_after: int

    def __post_init__(self):
        for value in (self.approval_id, self.decision_id, self.goal_id, self.approver):
            identifier(value)
        if type(self.request_sha256) is not str or len(self.request_sha256) != 64 or set(self.request_sha256) - _HEX:
            raise ContractError("An approval must bind an exact request digest")
        if type(self.goal_revision) is not int or self.goal_revision < 1:
            raise ContractError("An approval must bind a goal revision")
        if type(self.verdict) is not str or self.verdict not in ("approved", "declined"):
            raise ContractError("An approval verdict is approved or declined")
        if type(self.not_after) is not int or self.not_after < 1:
            raise ContractError("An approval needs an expiry")

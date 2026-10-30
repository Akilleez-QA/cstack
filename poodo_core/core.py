"""The inherited control loop. Extensions propose data, never core state changes."""
from __future__ import annotations

from .models import (Admission, CapabilityDescriptor, CapabilityOutcome, CapabilityRequest, ContractError,
                     DecisionRecord, DomainDescriptor, EXTENSION_VERSION, GoalContract, GoalSnapshot,
                     Interpretation, LivenessRecord, Phase, PhaseCheckpoint, Precommitment, READ_ONLY_LANES,
                     canonical, digest, identifier, outcome_for, port_lane, prose)
from .policy import (MAX_COST, ApprovalDeclined, ApprovalPending, ApprovalRecord, AuthorityGrant, BudgetPaused,
                     CapacityLimits, CapacityRefused, CostBudget)
from .ports import AdmissionPort, ApprovalPort, CapabilityPort, CostPort, DomainExtension, LedgerPort


class ReentryRefused(ContractError):
    """A mutation re-entered the core, or construction was re-entered or rerun. The refused call changed nothing."""


def _state(core, name):
    """Use object attribute lookup; the MRO check forbids descriptors shadowing guard state and attribute hooks."""
    try:
        return object.__getattribute__(core, name)
    except AttributeError:
        return None


def _contain(core, error):
    """Hold non-Exception failures caught around cancellation, invocation, outcome admission or actual cost.
    Re-raise at guard exit; outcome recording and settlement still depend on successful ledger operations."""
    if not isinstance(error, Exception) and _state(core, "_interrupted") is None:
        object.__setattr__(core, "_interrupted", error)


def _guarded(method, exclusive):
    """Refuse same-call-stack re-entry using a one-token list. The core is single-caller:
    the host must serialise all calls, including reads, from different threads."""
    def guarded(self, *args, **kwargs):
        token = _state(self, "_guard")
        try:
            token.pop()
        except (AttributeError, IndexError):  # not constructed yet, or another operation holds the token
            if not exclusive:
                return method(self, *args, **kwargs)
            raise ReentryRefused("Re-entrant call to " + method.__name__ + " refused while "
                                 + str(_state(self, "_busy") or "another operation or construction")
                                 + " is in progress; nothing changed") from None
        try:
            object.__setattr__(self, "_interrupted", None)  # never inherit one an earlier interrupted exit left behind
            object.__setattr__(self, "_busy", method.__name__)
            return method(self, *args, **kwargs)
        finally:
            interrupted = None
            try:  # take and clear this operation's state while it still holds the token, then always release
                interrupted = _state(self, "_interrupted")
                object.__setattr__(self, "_interrupted", None)
                object.__setattr__(self, "_busy", None)
            finally:
                token.append(True)
            if interrupted is not None:
                raise interrupted
    guarded.__name__, guarded.__qualname__, guarded.__doc__ = method.__name__, method.__qualname__, method.__doc__
    guarded.__wrapped__ = method
    return guarded


def _exclusive(method):
    """Refuse nested mutations caused by host/port code on the current call stack; nested reads are allowed."""
    return _guarded(method, True)


def _query(method):
    """A read may run inside an operation (ports may inspect state). Started on its own, it holds the guard while it
    calls host code (clock, ledger read), so that code cannot start a mutation in the middle of the read."""
    return _guarded(method, False)


class PoodoCore:
    """Concrete base for trusted extensions. This is not a hostile-Python sandbox.

    Single-caller: the host must serialise all reads and mutations from different threads.
    The guard only refuses same-call-stack mutation re-entry by host/port code.
    A phase gate checks required records, not research adequacy or option quality.
    There is intentionally no complete_goal, proof-acceptance, or effect grant API.
    """
    MAX_GOALS = 32
    MAX_DECISIONS = 64
    _FINAL_METHODS = {"start_goal", "revise_goal", "advance", "decide", "execute", "snapshot",
                      "_admit_outcome", "_record_outcome", "_authorize", "_check_request", "_admission",
                      "_check_denied", "_check_approval", "_asks", "__init_subclass__", "ledger",
                      "record_liveness", "liveness", "goals_without_live_path", "budget", "lift_budget_pause",
                      "_check_budget", "_cost", "_settle", "_check_lane", "_capacity", "_check_capacity",
                      "_queued",
                      # Attribute hooks would let a subclass fake or clear the re-entrancy guard.
                      "__getattribute__", "__getattr__", "__setattr__", "__delattr__"}
    # Core state a subclass must not shadow with a class attribute or property (ADR 003 review, S5).
    _CORE_STATE = {"_approvals", "_approver", "_clock", "_needs_approval", "_used_approvals", "_pending_noted",
                   "_denials_noted", "_extension", "_descriptor", "_capabilities", "_declared", "_grants",
                   "_grant_uses", "_ledger", "_goals", "_decisions", "_used_requests", "_consumed",
                   "_attempt_number", "_busy", "_guard", "_interrupted", "_liveness", "_costs", "_budget_units", "_budget_limits",
                   "_spent", "_held", "_paused", "_budget_noted", "_lanes_noted", "MAX_NOTED",
                   "_capacity_port", "_capacity_noted", "_live"}
    MAX_NOTED = 256

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Check every base in the MRO, before or after PoodoCore, so a mixin cannot shadow the core either.
        # A base after PoodoCore cannot shadow what PoodoCore itself defines, so only the rest is checked there.
        protected = PoodoCore._FINAL_METHODS | PoodoCore._CORE_STATE
        mro, later = cls.__mro__, protected - set(PoodoCore.__dict__)
        cut = mro.index(PoodoCore)
        forbidden = set().union(*(protected.intersection(b.__dict__) for b in mro[:cut]),
                                *(later.intersection(b.__dict__) for b in mro[cut + 1:] if b is not object))
        if forbidden:
            raise TypeError("Extensions cannot override inherited control methods: " + ", ".join(sorted(forbidden)))

    def __init__(self, extension: DomainExtension, capabilities: dict[str, CapabilityPort],
                 grants: tuple[AuthorityGrant, ...], ledger: LedgerPort, *,
                 approvals: ApprovalPort | None = None, approver: str | None = None, clock=None,
                 budgets: tuple[CostBudget, ...] = (), costs: CostPort | None = None,
                 admission: AdmissionPort | None = None):
        if _state(self, "_guard") is not None:
            raise ReentryRefused("A core is constructed once; re-running __init__ is refused and changed nothing")
        object.__setattr__(self, "_guard", [])  # an empty token: every operation and nested __init__ is refused
        descriptor = extension.descriptor()
        if type(descriptor) is not DomainDescriptor or descriptor.extension_contract != EXTENSION_VERSION:
            raise ContractError("Unsupported domain extension contract")
        identifier(descriptor.domain_id)
        identifier(descriptor.version)
        prose(descriptor.numeric_semantics)
        if type(descriptor.capabilities) is not tuple or not descriptor.capabilities:
            raise ContractError("A domain must declare immutable capabilities")
        declared = {}
        for cap in descriptor.capabilities:
            if type(cap) is not CapabilityDescriptor or type(cap.operations) is not tuple or not cap.operations:
                raise ContractError("Invalid capability descriptor")
            identifier(cap.capability_id)
            identifier(cap.contract_version)
            if cap.capability_id in declared or len(set(cap.operations)) != len(cap.operations):
                raise ContractError("Duplicate capability or operation")
            for operation in cap.operations:
                identifier(operation)
            if cap.evidence_ceiling != "tool_observation":
                raise ContractError("Unsupported capability evidence ceiling")
            if port_lane(cap.lane) in READ_ONLY_LANES:
                raise ContractError("A ReadModelFace or LearningFace capability has no execute path to bind")
            declared[cap.capability_id] = cap
        if type(capabilities) is not dict or set(capabilities) != set(declared):
            raise ContractError("Only declared capabilities may be bound")
        for key, port in capabilities.items():
            described = port.describe()
            if type(described) is not CapabilityDescriptor or described != declared[key]:
                raise ContractError("Capability implementation contract mismatch")
        if type(grants) is not tuple or not grants or any(type(g) is not AuthorityGrant for g in grants):
            raise ContractError("Trusted host must supply immutable scoped authority")
        if len({g.grant_id for g in grants}) != len(grants):
            raise ContractError("Duplicate authority grant")
        for grant in grants:
            if (grant.domain_id != descriptor.domain_id or grant.capability_id not in declared
                    or not set(grant.operations) <= set(declared[grant.capability_id].operations)
                    or not set(grant.deny_operations) <= set(declared[grant.capability_id].operations)):
                raise ContractError("Grant exceeds or misnames declared domain capability")
            if port_lane(grant.lane) != declared[grant.capability_id].lane:
                raise ContractError("Grant lane does not match its capability's lane")
        if any(g.ask_operations for g in grants) and (approvals is None or approver is None or not callable(clock)):
            raise ContractError("Ask-class authority needs a host approval port, a named approver and a host clock")
        if approver is not None:
            identifier(approver)
        if type(budgets) is not tuple or any(type(b) is not CostBudget for b in budgets):
            raise ContractError("Budgets must be immutable host CostBudget records")
        aors = {b.aor_id for b in budgets}
        if len(aors) != len(budgets):
            raise ContractError("Duplicate AOR budget")
        if (budgets or any(g.aor_id for g in grants)) and (
                costs is None or any(g.aor_id not in aors for g in grants)):
            # Once spend is governed, every grant must be paid from a budget, so a plain grant cannot bypass it.
            raise ContractError("Budgeted authority needs a host cost port and a budget for every grant's AOR")
        self._costs = costs
        # ADR 005 item 5a: once admission is configured, every grant names an AOR and every AOR has host limits.
        self._capacity_port, self._capacity_noted, self._live = admission, set(), {}
        if admission is not None:
            if any(g.aor_id is None for g in grants):
                raise ContractError("Admission-governed authority needs an AOR on every grant")
            for aor in sorted(aors | {g.aor_id for g in grants}):
                if self._capacity(aor) is None:  # under the construction guard: re-entry is refused
                    raise ContractError("Admission needs valid host capacity limits for every AOR")
                self._live[aor] = 0
        self._budget_units = {b.aor_id: b.unit for b in budgets}
        self._budget_limits = {b.aor_id: b.limit for b in budgets}
        self._spent = {aor: 0 for aor in aors}
        self._held = {aor: 0 for aor in aors}
        self._paused: dict[str, str] = {}
        self._budget_noted: set[str] = set()
        self._approvals, self._approver, self._clock = approvals, approver, clock
        self._needs_approval: set[str] = set()
        self._used_approvals: set[str] = set()
        self._pending_noted: set[str] = set()
        self._denials_noted: set[str] = set()
        self._lanes_noted: set[str] = set()
        self._extension = extension
        self._descriptor = descriptor
        self._capabilities = dict(capabilities)
        self._declared = declared
        self._grants = grants
        self._grant_uses = {g.grant_id: 0 for g in grants}
        self._ledger = ledger
        self._goals: dict[str, GoalSnapshot] = {}
        self._decisions: dict[str, DecisionRecord] = {}
        self._used_requests: set[str] = set()
        self._consumed: set[str] = set()
        self._attempt_number = 0
        self._liveness: dict[str, LivenessRecord] = {}
        # Last: until construction finishes, there is no guard to take, so every operation is refused.
        self._busy: str | None = None
        self._interrupted: BaseException | None = None
        self._guard = [True]

    def descriptor(self):
        return self._descriptor

    @_query
    def ledger(self):
        return self._ledger.read()

    def _admission(self, admission):
        if type(admission) is not Admission or admission.admitted is not True:
            raise ContractError("Domain admission denied")
        prose(admission.reason)

    @_exclusive
    def start_goal(self, goal: GoalContract) -> GoalSnapshot:
        goal = GoalContract.from_dict(goal.to_dict())
        if goal.domain_id != self._descriptor.domain_id or goal.goal_id in self._goals:
            raise ContractError("Wrong domain or duplicate goal")
        if len(self._goals) >= self.MAX_GOALS:
            raise ContractError("Retained goal budget exhausted")
        self._admission(self._extension.admit_goal(goal))
        self._check_capacity("start_goal", {g.aor_id for g in self._grants if goal.goal_id in g.goal_ids},
                             {"goal_id": goal.goal_id, "goal_sha256": digest(goal.to_dict())})
        snapshot = GoalSnapshot(goal, Phase.PONTIFICATE)
        self._ledger.append("proposal", {"action": "start_goal", "snapshot": snapshot.to_dict()})
        self._goals[goal.goal_id] = snapshot
        return snapshot

    @_exclusive
    def revise_goal(self, goal: GoalContract) -> GoalSnapshot:
        goal = GoalContract.from_dict(goal.to_dict())
        old = self.snapshot(goal.goal_id)
        if goal.domain_id != self._descriptor.domain_id or goal.revision != old.contract.revision + 1:
            raise ContractError("Revision must advance exactly once in the same domain")
        self._admission(self._extension.admit_goal(goal))
        new = GoalSnapshot(goal, Phase.PONTIFICATE)
        self._ledger.append("correction", {"action": "revise_goal", "prior_revision": old.contract.revision,
                                           "snapshot": new.to_dict()})
        self._goals[goal.goal_id] = new
        return new

    def snapshot(self, goal_id: str) -> GoalSnapshot:
        identifier(goal_id)
        if goal_id not in self._goals:
            raise ContractError("Unknown goal")
        return self._goals[goal_id]

    @_exclusive
    def record_liveness(self, record: LivenessRecord) -> dict:
        """Trusted host only: name who owns the next action on an open goal. Requests and tool text never reach this.

        A change is recorded once; supplying the same record again appends nothing.
        """
        if type(record) is not LivenessRecord:
            raise ContractError("The host must supply a liveness record")
        record = LivenessRecord(**record.to_dict())
        goal = self.snapshot(record.goal_id)
        if goal.closed or record.goal_revision != goal.contract.revision:
            raise ContractError("Liveness must name the current revision of an open goal")
        if record.review_by is not None and not callable(self._clock):
            raise ContractError("A bounded wait needs a host clock")
        if self._liveness.get(record.goal_id) != record:
            self._ledger.append("decision", {"action": "liveness_set", "prior": (
                self._liveness[record.goal_id].to_dict() if record.goal_id in self._liveness else None),
                "liveness": record.to_dict()})
            self._liveness[record.goal_id] = record
        return self.liveness(record.goal_id)

    @_query
    def liveness(self, goal_id: str) -> dict:
        """Evaluate the recorded wait against core state now. A claimed wait the core cannot see is not live."""
        goal = self.snapshot(goal_id)
        record = self._liveness.get(goal_id)
        report = {"goal_id": goal_id, "goal_revision": goal.contract.revision, "owner": None, "waiting_on": None,
                  "live": False, "reason": None}
        if goal.closed:
            return {**report, "reason": "goal_closed"}
        if record is None:
            return {**report, "reason": "no_next_action_owner"}
        report.update(owner=record.owner, waiting_on=record.waiting_on)
        if record.goal_revision != goal.contract.revision:
            return {**report, "reason": "liveness_names_stale_revision"}
        if record.review_by is not None:
            now = self._clock()
            if type(now) is not int:
                raise ContractError("The host clock must return integer epoch seconds")
            if now > record.review_by:
                return {**report, "reason": "wait_expired"}
        if record.waiting_on == "approval":
            if record.owner != self._approver:
                return {**report, "reason": "approval_wait_names_wrong_owner"}
            pending = [d for d in self._needs_approval if d not in self._consumed
                       and self._decisions[d].request.goal_id == goal_id
                       and self._decisions[d].request.goal_revision == goal.contract.revision]
            if not pending:
                return {**report, "reason": "no_pending_approval"}
            if all(self._decisions[d].request_sha256 in self._lanes_noted for d in pending):
                # An approval cannot move a lane-refused call; conservatively not live until one executes.
                return {**report, "reason": "approval_blocked_by_lane"}
        return {**report, "live": True, "reason": "waiting_on_" + record.waiting_on}

    @_query
    def goals_without_live_path(self) -> tuple[dict, ...]:
        """Every open goal whose next action has no live owner, in goal-id order."""
        reports = (self.liveness(goal_id) for goal_id in sorted(self._goals))
        return tuple(r for r in reports if not r["live"] and r["reason"] != "goal_closed")

    @_exclusive
    def advance(self, goal_id: str, next_phase: Phase, checkpoint: PhaseCheckpoint) -> GoalSnapshot:
        if type(next_phase) is not Phase or type(checkpoint) is not PhaseCheckpoint:
            raise ContractError("Invalid phase transition request")
        old = self.snapshot(goal_id)
        allowed = {Phase.PONTIFICATE: Phase.OBSERVE, Phase.OBSERVE: Phase.ORIENT,
                   Phase.ORIENT: Phase.DECIDE, Phase.DECIDE: Phase.ORCHESTRATE,
                   Phase.ORCHESTRATE: Phase.OBSERVE}
        if allowed[old.phase] != next_phase:
            raise ContractError("Phase skipping is not supported")
        if old.phase == Phase.OBSERVE and not checkpoint.research_references:
            raise ContractError("Observe-to-Orient requires a recorded research boundary")
        if old.phase == Phase.ORIENT and (len(checkpoint.option_ids) != 20 or len(set(checkpoint.option_ids)) != 20):
            raise ContractError("Orient-to-Decide requires 20 distinct option identifiers")
        new = GoalSnapshot(old.contract, next_phase)
        self._ledger.append("decision", {"action": "phase_transition", "goal_id": goal_id,
            "goal_revision": old.contract.revision, "from": old.phase.value, "to": next_phase.value,
            "checkpoint_id": checkpoint.checkpoint_id, "rationale": checkpoint.rationale,
            "research_references": list(checkpoint.research_references), "option_ids": list(checkpoint.option_ids),
            "quality_judgment": "Host-authored checkpoint; structural check only"})
        self._goals[goal_id] = new
        return new

    def _check_denied(self, request):
        """Deny wins over every grant. The first refusal per exact request is recorded, bounded, so a
        repeating caller cannot drain the ledger."""
        if any(g.denies(self._descriptor.domain_id, request) for g in self._grants):
            if request.sha256 not in self._denials_noted and len(self._denials_noted) < PoodoCore.MAX_NOTED:
                self._ledger.append("decision", {"action": "denied", "request_sha256": request.sha256,
                    "decision_id": request.decision_id, "operation": request.operation, "reason": "host_policy_deny"})
                self._denials_noted.add(request.sha256)
            raise ContractError("Operation is denied by host policy")

    def _check_lane(self, grant, request):
        """ADR 005: refuse unless the grant's lane equals the capability's lane, as declared and as the bound port
        describes it now. Read-only lanes never pass. The first refusal per exact request is recorded, bounded."""
        def valid(value):
            try:
                return port_lane(value)
            except ContractError:
                return None
        cap = self._declared[request.capability_id]
        grant_lane, cap_lane = valid(grant.lane), valid(cap.lane)
        try:  # decide and execute hold the core-wide guard, so describe() cannot re-enter the core
            live = self._capabilities[request.capability_id].describe()
            live_lane = valid(live.lane) if type(live) is CapabilityDescriptor else None
            drifted = live_lane is None or live_lane != cap_lane or live != cap
        except Exception:
            live_lane, drifted = None, True
        read_only = any(x in READ_ONLY_LANES for x in (cap_lane, grant_lane, live_lane))
        reason = ("read_only_lane" if read_only else "descriptor_drift" if drifted or cap_lane is None
                  else "lane_mismatch" if grant_lane is None or grant_lane != cap_lane else None)
        if reason is None:
            return
        if request.sha256 not in self._lanes_noted and len(self._lanes_noted) < PoodoCore.MAX_NOTED:
            self._ledger.append("decision", {"action": "lane_refused", "request_sha256": request.sha256,
                "decision_id": request.decision_id, "operation": request.operation, "grant_id": grant.grant_id,
                "grant_lane": grant_lane, "capability_lane": cap_lane, "described_lane": live_lane,
                "reason": reason})
            self._lanes_noted.add(request.sha256)
        raise ContractError("The grant's lane does not match the capability's lane")

    def _asks(self, request):
        """Ask is global like deny: any grant for this capability that asks makes approval mandatory."""
        return any(g.asks(request) for g in self._grants
                   if g.domain_id == self._descriptor.domain_id and g.capability_id == request.capability_id)

    def _check_approval(self, decision_id, request, extra_events=0):
        """Return the approval that admits this exact request, or raise. No state changes until the ledger has
        room for every event this path writes, so a failure never burns an approval or loses a decline."""
        approval = self._approvals.lookup(decision_id)
        if approval is None:
            if decision_id not in self._pending_noted:
                self._ledger.append("observation", {"action": "approval_pending", "decision_id": decision_id,
                    "request_sha256": request.sha256, "approver": self._approver})
                self._pending_noted.add(decision_id)
            raise ApprovalPending("Waiting for the host approver; nothing was dispatched")
        if type(approval) is not ApprovalRecord:
            raise ContractError("Approval port returned an unsupported record")
        bound = (approval.decision_id == decision_id and approval.request_sha256 == request.sha256
                 and approval.goal_id == request.goal_id and approval.goal_revision == request.goal_revision)
        if not bound or approval.approver != self._approver:
            raise ContractError("Approval does not bind this exact request, revision and approver")
        event = {"action": approval.verdict, "approval_id": approval.approval_id, "decision_id": decision_id,
                 "request_sha256": request.sha256, "approver": approval.approver}
        if approval.verdict == "declined":
            # A bound "no" is honoured even if expired or seen before: declining always fails safe.
            self._ledger.reserve(1, 16_384)
            self._ledger.append("decision", event)
            self._consumed.add(decision_id)
            raise ApprovalDeclined("The host approver declined; the decision is consumed")
        now = self._clock()
        if type(now) is not int:
            raise ContractError("The host clock must return integer epoch seconds")
        if approval.approval_id in self._used_approvals or now > approval.not_after:
            raise ContractError("Approval is used or expired")
        # Room for the approval event, the action and the worst permitted outcome, before anything is spent.
        self._ledger.reserve(3 + extra_events, 2_220_000 + 16_384 * extra_events)
        # Single use must hold across processes and restarts, so the host port confirms it, not just memory.
        if self._approvals.consume(approval.approval_id) is not True:
            raise ContractError("The host refused to consume this approval; it may already be used")
        self._used_approvals.add(approval.approval_id)
        self._ledger.append("decision", event)
        return approval

    def budget(self, aor_id: str) -> dict:
        identifier(aor_id)
        if aor_id not in self._budget_limits:
            raise ContractError("Unknown AOR budget")
        return {"aor_id": aor_id, "unit": self._budget_units[aor_id], "limit": self._budget_limits[aor_id],
                "spent": self._spent[aor_id], "held": self._held[aor_id], "paused": aor_id in self._paused}

    @_exclusive
    def lift_budget_pause(self, aor_id: str, new_limit: int) -> dict:
        """Trusted host only: raise an AOR's limit above its committed spend, which lifts a hard-stop pause."""
        state = self.budget(aor_id)
        if type(new_limit) is not int or not state["limit"] < new_limit <= MAX_COST:
            raise ContractError("A lift must raise the limit")
        if new_limit <= state["spent"] + state["held"]:
            raise ContractError("The new limit must exceed committed spend")
        self._ledger.append("decision", {"action": "budget_pause_lifted", "aor_id": aor_id,
            "prior_limit": state["limit"], "limit": new_limit, "was_paused": state["paused"]})
        self._budget_limits[aor_id] = new_limit
        self._paused.pop(aor_id, None)
        return self.budget(aor_id)

    def _capacity(self, aor):
        """The host's capacity for one AOR now, or None. Anything but a valid record for exactly this AOR is unknown."""
        try:
            answer = self._capacity_port.capacity(aor)
            if type(answer) is not CapacityLimits:
                return None
            answer = CapacityLimits(**vars(answer))  # re-validate: a frozen record can still be patched in place
            return answer if answer.aor_id == aor else None
        except Exception:
            return None

    def _queued(self, decision_id, aor):
        """An ask still in this AOR's approval queue: unconsumed, for its goal's current revision, and still
        executable under a grant with calls left. Like liveness, a stale or exhausted ask no longer counts."""
        decision = self._decisions[decision_id]
        grant = next(g for g in self._grants if g.grant_id == decision.grant_id)
        return (decision_id not in self._consumed and grant.aor_id == aor
                and decision.request.goal_revision == self._goals[decision.request.goal_id].contract.revision
                and self._grant_uses[grant.grant_id] < grant.max_calls)

    def _check_capacity(self, gate, aors, subject):
        """ADR 005 item 5a: refuse unless every AOR's host capacity admits this gate now. Runs after deny and lane
        and before budget and approval, so a refusal holds no spend and spends no approval. The first refusal per
        exact request and gate is recorded (capacity_refused), bounded."""
        if _state(self, "_capacity_port") is None:
            return
        for aor in sorted(aors) or [None]:  # a goal no grant's AOR covers has no capacity: refused
            limits = None if aor is None else self._capacity(aor)
            if limits is None:
                reason, limit, in_use = ("unknown_capacity" if aor else "no_aor"), None, None
            elif gate == "decide":
                reason, limit = "approval_queue", limits.max_pending_asks
                in_use = limits.other_pending_asks + sum(1 for d in self._needs_approval if self._queued(d, aor))
            elif limits.live_cap == 0:
                reason, limit, in_use = "paused", 0, None
            elif gate == "start_goal":
                reason, limit = "open_goals", limits.max_open_goals
                in_use = limits.other_open_goals + sum(1 for goal_id, snap in self._goals.items() if not snap.closed
                    and any(g.aor_id == aor and goal_id in g.goal_ids for g in self._grants))
            else:
                reason, limit, in_use = "live_attempts", limits.live_cap, limits.other_live_attempts + self._live[aor]
            if limit is not None and in_use is not None and in_use < limit:
                continue
            key = gate + ":" + subject.get("request_sha256", subject.get("goal_sha256"))
            reset = limits.soonest_reset_at if limits is not None else None
            if key not in self._capacity_noted and len(self._capacity_noted) < PoodoCore.MAX_NOTED:
                self._ledger.append("decision", {"action": "capacity_refused", "gate": gate, "aor_id": aor,
                    **subject, "reason": reason, "limit": limit, "in_use": in_use,
                    **({"soonest_reset_at": reset} if reset is not None else {})})
                self._capacity_noted.add(key)
            error = CapacityRefused("Host capacity refused this call (" + reason + "); nothing was started or spent")
            error.soonest_reset_at = reset
            raise error

    def _cost(self, method, *args):
        """A host price, or None. Anything but a bounded non-negative int is unknown, and unknown is not free."""
        try:
            value = method(*args)
        except Exception:
            return None
        return value if type(value) is int and 0 <= value <= MAX_COST else None

    def _check_budget(self, grant, request):
        """Return (aor, estimate) for a budgeted grant, or (None, 0). Refuses a paused AOR or an unaffordable call."""
        aor = grant.aor_id
        if aor is None:
            return None, 0
        if aor in self._paused:
            raise BudgetPaused("This AOR is paused at its budget limit until the host lifts it")
        estimate = self._cost(self._costs.estimate, request)
        if estimate is None or self._spent[aor] + self._held[aor] + estimate > self._budget_limits[aor]:
            if request.sha256 not in self._budget_noted and len(self._budget_noted) < PoodoCore.MAX_NOTED:
                self._ledger.append("decision", {"action": "budget_refused", "aor_id": aor, "estimate": estimate,
                    "request_sha256": request.sha256, "reason": "unknown_cost" if estimate is None else "over_limit"})
                self._budget_noted.add(request.sha256)
            raise ContractError("The call's cost is unknown or does not fit the AOR budget")
        return aor, estimate

    def _settle(self, aor, estimate, request, attempt_id, outcome):
        """Release a hold that never dispatched; otherwise charge the host's actual price, or keep the whole hold."""
        if outcome.to_dict()["execution_certainty"] == "not_dispatched":
            charge, priced = 0, True
        else:
            try:  # contain actual-cost callback failures; ledger failures below still propagate
                actual = self._cost(self._costs.actual, request, attempt_id, outcome)
            except BaseException as error:
                _contain(self, error)
                actual = None
            charge, priced = (estimate, False) if actual is None else (actual, True)
        self._held[aor] -= estimate
        self._spent[aor] += charge
        self._ledger.append("observation", {"action": "budget_settled", "aor_id": aor, "attempt_id": attempt_id,
            "reserved": estimate, "charged": charge, "priced": priced, "spent": self._spent[aor]})
        if self._spent[aor] >= self._budget_limits[aor] and aor not in self._paused:
            self._paused[aor] = "hard_stop"
            self._ledger.append("decision", {"action": "budget_paused", "aor_id": aor, "reason": "hard_stop",
                "spent": self._spent[aor], "limit": self._budget_limits[aor]})

    def _authorize(self, request):
        for grant in self._grants:
            if grant.permits(self._descriptor.domain_id, request) and self._grant_uses[grant.grant_id] < grant.max_calls:
                return grant
        raise ContractError("No remaining scoped authority for this call")

    def _check_request(self, request):
        request = CapabilityRequest.from_dict(request.to_dict())
        goal = self.snapshot(request.goal_id)
        if request.goal_revision != goal.contract.revision:
            raise ContractError("Stale goal revision")
        cap = self._declared.get(request.capability_id)
        if cap is None or request.operation not in cap.operations:
            raise ContractError("Undeclared capability or operation")
        if request.required_evidence != cap.evidence_ceiling:
            raise ContractError("Required evidence is unavailable from this capability")
        self._admission(self._extension.validate_call(goal, request))
        return request, goal

    @_exclusive
    def decide(self, request: CapabilityRequest, precommitment: Precommitment) -> DecisionRecord:
        if type(precommitment) is not Precommitment:
            raise ContractError("A prospective precommitment is required")
        request, goal = self._check_request(request)
        if goal.phase != Phase.DECIDE:
            raise ContractError("Decisions require the Decide phase")
        if request.decision_id in self._decisions or request.request_id in self._used_requests:
            raise ContractError("Decision and request identities must be new")
        if len(self._decisions) >= self.MAX_DECISIONS:
            raise ContractError("Retained decision budget exhausted")
        self._check_denied(request)
        grant = self._authorize(request)
        self._check_lane(grant, request)
        needs_approval = self._asks(request)
        if needs_approval:  # this call would join the approval queue
            self._check_capacity("decide", {grant.aor_id}, {"decision_id": request.decision_id,
                                                            "request_sha256": request.sha256})
        self._check_budget(grant, request)
        record = DecisionRecord(request, request.sha256, grant.grant_id, precommitment)
        self._ledger.append("decision", {"action": "precommit", "request": request.to_dict(),
            "request_sha256": record.request_sha256, "grant_id": grant.grant_id,
            "precommitment": precommitment.to_dict(), "approval_required": needs_approval})
        self._decisions[request.decision_id] = record
        if needs_approval:
            self._needs_approval.add(request.decision_id)
        self._used_requests.add(request.request_id)
        return record

    def _admit_outcome(self, request, attempt_id, candidate):
        if type(candidate) is not CapabilityOutcome:
            raise ContractError("Adapter returned an unsupported outcome")
        result = CapabilityOutcome.from_dict(candidate.to_dict())
        data = result.to_dict()
        # Leave a guaranteed envelope margin for interpretation + ledger identity.
        if len(canonical(data)) > 1_572_864:
            raise ContractError("Outcome exceeds terminal-accounting budget")
        for key in ("request_id", "goal_id", "goal_revision", "decision_id", "capability_id", "operation"):
            if type(data[key]) is not type(request.to_dict()[key]) or data[key] != request.to_dict()[key]:
                raise ContractError("Outcome binding mismatch")
        if data["attempt_id"] != attempt_id or data["request_sha256"] != request.sha256:
            raise ContractError("Outcome attempt or request identity mismatch")
        return result

    def _record_outcome(self, request, attempt_id, candidate):
        try:
            result = self._admit_outcome(request, attempt_id, candidate)
            interpretation = self._extension.interpret(self.snapshot(request.goal_id), request, result)
            expected_kind = "tool_observation" if result.to_dict()["execution_status"] == "completed" else "unassessed"
            if (type(interpretation) is not Interpretation or interpretation.evidence_kind != expected_kind
                    or interpretation.formal_proof is not False or interpretation.runtime_goal_acceptance is not False
                    or type(interpretation.limitations) is not tuple or len(interpretation.limitations) > 32):
                raise ContractError("Extension attempted evidence escalation")
            prose(interpretation.covered_scope)
            for limitation in interpretation.limitations:
                prose(limitation)
            terminal = {"outcome": result.to_dict(), "interpretation": {
                "evidence_kind": interpretation.evidence_kind, "covered_scope": interpretation.covered_scope,
                "limitations": list(interpretation.limitations), "formal_proof": False,
                "runtime_goal_acceptance": False}, "goal_closed": False}
            # Validate the WHOLE eventual event, not character-count estimates.
            # Placeholder IDs reserve more bytes than the bounded memory ledger uses.
            framed = {"sequence": 999999999, "kind": "outcome", "data": terminal,
                      "prior_event_sha256": "0"*64, "event_sha256": "0"*64}
            if len(canonical(framed)) > 2_000_000:
                raise ContractError("Terminal event exceeds retained-envelope budget")
        except BaseException as error:
            _contain(self, error)
            result = outcome_for(request, attempt_id, "protocol_error", "core_evidence_admission_failed",
                certainty="unknown", limitations=("Response quarantined; no mathematical evidence admitted.",))
            interpretation = Interpretation("unassessed", "No accepted result", ("No proof or goal acceptance.",))
            terminal = {"outcome": result.to_dict(), "interpretation": {
                "evidence_kind": interpretation.evidence_kind, "covered_scope": interpretation.covered_scope,
                "limitations": list(interpretation.limitations), "formal_proof": False,
                "runtime_goal_acceptance": False}, "goal_closed": False}
        self._ledger.append("outcome", terminal)
        return result

    @_exclusive
    def execute(self, decision_id: str, cancellation=None) -> CapabilityOutcome:
        identifier(decision_id)
        if decision_id not in self._decisions or decision_id in self._consumed:
            raise ContractError("Unknown or consumed decision")
        decision = self._decisions[decision_id]
        request, goal = self._check_request(decision.request)
        if goal.phase != Phase.ORCHESTRATE or request.sha256 != decision.request_sha256:
            raise ContractError("Execution requires Orchestrate and the unchanged precommitment")
        grant = next(g for g in self._grants if g.grant_id == decision.grant_id)
        if not grant.permits(self._descriptor.domain_id, request) or self._grant_uses[grant.grant_id] >= grant.max_calls:
            raise ContractError("Bound authority is exhausted or no longer applicable")
        self._check_denied(request)
        # Lane before budget and approval, so a mismatched call never holds spend or spends an approval.
        self._check_lane(grant, request)
        # Capacity, then budget, before approval, so a refused call never holds spend or spends an approval.
        self._check_capacity("execute", {grant.aor_id}, {"decision_id": decision_id, "request_sha256": request.sha256})
        aor, estimate = self._check_budget(grant, request)
        extra = 2 if aor else 0  # settlement and a possible pause must always be recordable
        needs_approval = decision_id in self._needs_approval or self._asks(request)
        approval = self._check_approval(decision_id, request, extra) if needs_approval else None
        # Reserve space for the action and worst permitted outcome BEFORE dispatch.
        self._ledger.reserve(2 + extra, 2_200_000 + 16_384 * extra)
        self._attempt_number += 1
        attempt_id = "attempt-" + str(self._attempt_number)
        self._ledger.append("action", {"attempt_id": attempt_id, "decision_id": decision_id,
            "request_sha256": request.sha256, "grant_id": grant.grant_id,
            "goal_id": request.goal_id, "goal_revision": request.goal_revision,
            "approval_id": approval.approval_id if approval else None,
            **({"aor_id": aor, "cost_reserved": estimate} if aor else {})})
        if aor:
            self._held[aor] += estimate
        live = grant.aor_id if self._capacity_port is not None else None
        if live:  # dispatched and not yet settled; an outcome that fails to record stays live (fail closed)
            self._live[live] += 1
        self._consumed.add(decision_id)
        self._grant_uses[grant.grant_id] += 1
        try:  # a cancellation object that fails is treated as set: nothing is dispatched
            cancelled = cancellation is not None and bool(cancellation.is_set())
        except BaseException as error:
            _contain(self, error)
            cancelled = True
        if cancelled:
            candidate = outcome_for(request, attempt_id, "cancelled", "cancelled_before_dispatch")
        else:
            try:
                candidate = self._capabilities[request.capability_id].invoke(request, attempt_id, cancellation)
            except BaseException as error:
                _contain(self, error)
                candidate = outcome_for(request, attempt_id, "indeterminate", "adapter_failed_without_accepted_result",
                    certainty="unknown", limitations=("No automatic retry; execution may have occurred.",))
        outcome = self._record_outcome(request, attempt_id, candidate)
        if aor:
            self._settle(aor, estimate, request, attempt_id, outcome)
        if live:
            self._live[live] -= 1
        return outcome

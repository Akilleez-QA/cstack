"""One bot's AOR on one device, as POODO cores (ADR 003). Built only by bootstrap; driven by the MCP adapter.

The bot identity, device, registry and state paths are host configuration fixed at process start. Every id
(goal, request, decision, checkpoint) is assigned here, never by the bot. Effects resolve strictest-first:
the bot's own class, then the device's guest rules when the bot does not own the device, then shields-up.
"""
import fcntl
from functools import wraps
import json
import os
import secrets
from pathlib import Path
import stat
from threading import Lock
import weakref

from poodo_core import (ApprovalDeclined, ApprovalPending, AuthorityGrant, CapabilityRequest, ContractError,
                        GoalContract, Phase, PhaseCheckpoint, Precommitment, REQUEST_VERSION)

STRICTNESS = ("allow", "ask", "deny")
LEDGER_TAIL_MAX = 50


# Claims cover a whole file, regardless of writer or stream, including resolved path aliases.
_STORE_LOCK = Lock()
_STORES = weakref.WeakValueDictionary()


class LedgerStoreClaim:
    """Lifetime store ownership, separate from the witnessed adapter's per-operation append lock."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _STORE_LOCK:
            if self.path in _STORES:
                raise ContractError(f"Ledger store {self.path} already has a live owner")
            fd = os.open(str(self.path) + ".owner.lock",
                         os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise ContractError("Ledger owner lock must be a private regular file")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ContractError(f"Ledger store {self.path} already has a live owner") from None
            except BaseException:
                os.close(fd)
                raise
            self._release = weakref.finalize(self, os.close, fd)
            _STORES[self.path] = self

    def close(self):
        with _STORE_LOCK:
            self._release()
            if _STORES.get(self.path) is self:
                del _STORES[self.path]


def _drop_inherited_store_claims():
    # A child must not keep its parent's locks alive, or inherit its process-local registry.
    global _STORE_LOCK
    _STORE_LOCK = Lock()
    for claim in list(_STORES.values()):
        claim._release()  # close only the child's fd; the parent retains its flock
    _STORES.clear()


os.register_at_fork(after_in_child=_drop_inherited_store_claims)


class SessionApprovalReader:
    """Open each SQLite reader on the calling thread; the session lock serializes its use."""
    def __init__(self, factory):
        self._factory = factory

    def lookup(self, decision_id):
        reader = self._factory()
        try:
            return reader.lookup(decision_id)
        finally:
            reader.close()

    def consume(self, approval_id):
        reader = self._factory()
        try:
            return reader.consume(approval_id)
        finally:
            reader.close()


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            if self._closed and method.__name__ != "close":
                raise ContractError("AOR session is closed")
            return method(self, *args, **kwargs)
    return call


def effective_class(bot, device, effect, shields_up):
    rank = STRICTNESS.index(bot.effects.of(effect))
    if device.owner != bot.slug:
        rank = max(rank, STRICTNESS.index(device.guest_effects.of(effect)))
    if shields_up and effect != "read":
        rank = STRICTNESS.index("deny")
    return STRICTNESS[rank]


class AorSession:
    mail = None  # Host-configured fleet-mail port, enabled only by --fleet-mail.

    def __init__(self, *, fleet, bot_slug, hostname, state_dir, domains, make_core, ledger_label, shields_file):
        """domains: {domain_id: (operations, effect)}; make_core(domain, grants, anchors) -> (core, ledger, store_claim).

        A ledger with a stream and head() (ADR 004 WitnessedLedger) is anchored in anchors.json under its stream
        name, {stream: head}; make_core picks its own. MemoryLedger has no anchor.
        """
        self._lock, self._closed = Lock(), False
        self._claims = []
        self.bot, self.device = fleet.bot(bot_slug), fleet.device(hostname)
        self.approver, self._shields_file, self.ledger_label = fleet.approver, Path(shields_file), ledger_label
        self._state = Path(state_dir) / self.bot.slug
        self._state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._anchors_path = self._state / "anchors.json"
        anchors = json.loads(self._anchors_path.read_text()) if self._anchors_path.exists() else {}
        if type(anchors) is not dict or any(not k.startswith(self.bot.slug + ".") for k in anchors):
            raise ContractError("anchors.json is not keyed by this bot's ledger streams (it predates streams?)")
        self._anchors = anchors  # kept whole, so a stream not opened this session (a denied domain) keeps its anchor
        self._session = secrets.token_hex(8)
        self._counter = 0
        shields = self._shields_up()
        self.classes, self._cores, self._ledgers, self._goal_pool = {}, {}, {}, {}
        try:
            for domain, (operations, effect) in domains.items():
                klass = effective_class(self.bot, self.device, effect, shields)
                self.classes[domain] = klass
                if klass == "deny":
                    continue
                pool = tuple(f"{self.bot.slug}.{self._session}.g{i}" for i in range(1, 33))
                grant = AuthorityGrant(f"{self.bot.slug}.{domain}", domain, domain, tuple(operations), pool, 64,
                                       lane="ToolFace", ask_operations=tuple(operations) if klass == "ask" else ())
                core, ledger, claim = make_core(domain, (grant,), anchors)
                self._cores[domain], self._ledgers[domain] = core, ledger
                if claim is not None:
                    self._claims.append(claim)
                self._goal_pool[domain] = list(pool)
        except BaseException:
            self.close()  # release the stream claims already taken
            raise

    def _shields_up(self):
        return self._shields_file.exists()

    @_serialized
    def shields_up(self):
        return self._shields_up()

    def _next(self, kind):
        self._counter += 1
        return f"{self.bot.slug}.{self._session}.{kind}{self._counter}"

    def _core(self, domain):
        if domain not in self._cores:
            raise ContractError(f"Domain '{domain}' is not available to {self.bot.slug} on {self.device.hostname}")
        return self._cores[domain]

    def _save_anchors(self):
        anchors = {ledger.stream: list(ledger.head()) for ledger in self._ledgers.values() if hasattr(ledger, "head")}
        if not anchors:
            return
        anchors = self._anchors = {**self._anchors, **anchors}
        tmp = self._anchors_path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(anchors, handle)
        os.replace(tmp, self._anchors_path)

    @_serialized
    def aor(self):
        return {"bot": {"id": self.bot.id, "name": self.bot.name, "slug": self.bot.slug},
                "device": self.device.hostname, "device_owner": self.device.owner, "approver": self.approver,
                "owns": list(self.bot.owns), "not": list(self.bot.not_owned), "registry_status": self.bot.status,
                "shields_up": self._shields_up(), "domains": self.classes, "ledger": self.ledger_label}

    @_serialized
    def start_goal(self, domain, objective, acceptance_criteria, assumptions=(), exclusions=()):
        core = self._core(domain)
        if not self._goal_pool[domain]:
            raise ContractError("This session's goal budget is exhausted")
        goal = GoalContract(self._goal_pool[domain][0], 1, domain, objective, tuple(assumptions), tuple(exclusions),
                            "1", tuple(acceptance_criteria))
        snapshot = core.start_goal(goal)
        self._goal_pool[domain].pop(0)
        self._save_anchors()
        return snapshot.to_dict()

    @_serialized
    def advance(self, domain, goal_id, next_phase, rationale, research_references=(), option_ids=()):
        checkpoint = PhaseCheckpoint(self._next("cp"), rationale, tuple(research_references), tuple(option_ids))
        snapshot = self._core(domain).advance(goal_id, Phase(next_phase), checkpoint)
        self._save_anchors()
        return snapshot.to_dict()

    @_serialized
    def decide(self, domain, goal_id, operation, arguments, expected_observation, success_boundary, failure_meaning):
        core = self._core(domain)
        if self._shields_up():
            raise ContractError("Shields are up: no new decisions until the host lowers them")
        decision_id = self._next("d")
        request = CapabilityRequest.from_dict({
            "schema": REQUEST_VERSION, "request_id": self._next("r"), "goal_id": goal_id,
            "goal_revision": core.snapshot(goal_id).contract.revision, "decision_id": decision_id,
            "capability_id": domain, "operation": operation, "arguments": arguments,
            "required_evidence": "tool_observation"})
        record = core.decide(request, Precommitment(expected_observation, success_boundary, failure_meaning,
                                                     f"{domain}.tool", "1"))
        self._save_anchors()
        return {"decision_id": decision_id, "request_sha256": record.request_sha256,
                "approval_required": self.classes[domain] == "ask"}

    @_serialized
    def execute(self, domain, decision_id):
        core = self._core(domain)
        if self._shields_up():
            raise ContractError("Shields are up: nothing executes until the host lowers them")
        try:
            result = {"status": "executed", "outcome": core.execute(decision_id).to_dict()}
        except ApprovalPending:
            result = {"status": "approval_pending", "dispatched": False, "approver": self.approver}
        except ApprovalDeclined:
            result = {"status": "declined_by_approver", "dispatched": False}
        except BaseException:
            self._save_anchors_after_execute()
            raise
        warning = self._save_anchors_after_execute()
        return {**result, "anchor_warning": warning} if warning else result

    def _save_anchors_after_execute(self):
        """An anchor that cannot be saved never hides what execute already did; the ledger holds the record."""
        try:
            self._save_anchors()
        except OSError as error:
            return f"ledger anchor not saved: {type(error).__name__}"
        return None

    @_serialized
    def ledger(self, domain=None, last=20):
        """One domain's stream, or with no domain every available domain's stream, labelled by domain."""
        if type(last) is not int or not 1 <= last <= LEDGER_TAIL_MAX:
            raise ContractError(f"last must be 1..{LEDGER_TAIL_MAX}")
        if domain is None:
            return {"streams": {d: self._stream_tail(d, last) for d in self._cores}}
        self._core(domain)
        return self._stream_tail(domain, last)

    def _stream_tail(self, domain, last):
        ledger = self._ledgers[domain]
        return {"domain": domain, "stream": getattr(ledger, "stream", None),
                "head": list(ledger.head()) if hasattr(ledger, "head") else None,
                "events": self._core(domain).ledger()[-last:]}

    @_serialized
    def close(self):
        if self._closed:
            return
        self._closed = True
        self._cores.clear()
        for ledger in self._ledgers.values():
            if hasattr(ledger, "close"):
                ledger.close()
        self._ledgers.clear()
        if self.mail is not None and hasattr(self.mail._ledger, "close"):
            self.mail._ledger.close()
        for claim in self._claims:
            claim.close()
        self._claims.clear()

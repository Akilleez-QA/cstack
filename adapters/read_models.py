"""ReadModelFace (ADR 005 items 8a, 8b): pure host projections over POODO ledger events. They never write.

Reading the ledger is already a host capability (`LedgerPort.read()`), so this needs no new core port. A projection
takes only a zero-argument read callable, such as `ledger.read` or a file reader, and never a ledger object. This
module imports nothing but the standard library and calls no append, reserve or other write method; a test checks
both.

Every Projection cites its source (the ledger identity and the event range read), as_of (the host clock at read time)
and a confidence: complete, partial or stale, with a reason. Event kinds or actions this module does not know are
counted in the confidence and otherwise skipped, never fatal (the t3code client-state reducer pattern). So are
malformed events, replayed sequences and gaps.
"""
from dataclasses import dataclass, field
import json

# Every (kind, action) the core writes today. Outcome and action events carry no "action" field.
KNOWN = frozenset({("proposal", "start_goal"), ("correction", "revise_goal"), ("action", None), ("outcome", None),
                   ("observation", "approval_pending"), ("observation", "budget_settled")} | {
                  ("decision", a) for a in ("precommit", "phase_transition", "liveness_set", "denied", "approved",
                                            "declined", "budget_refused", "budget_paused", "budget_pause_lifted")})

# Founder manual repairs: conservative, explicit, and only what the ledger itself shows as a host intervention.
FOUNDER_REPAIRS = {
    "budget_pause_lifted": "the host raised an AOR limit to lift a hard-stop pause (lift_budget_pause)",
    "approved_after_decline": "an approval for a goal, capability and operation the approver had already declined",
    "correction": "a correction event other than revise_goal, which references and amends a historical event",
}
NOT_COUNTED = {
    "revise_goal": "a goal revision is the normal way to change scope, not by itself a repair",
    "liveness_set": "naming a next-action owner is routine host bookkeeping",
    "approved": "a first approval is the normal ask path",
    "declined": "a decline is a decision, not a repair",
}
CLOSURE_DEFINITION = ("A goal is evidence-backed when its current revision has at least one completed, responded "
                      "tool_observation outcome. This is not closure: the core never closes a goal, and the ledger "
                      "does not bind an outcome to a single acceptance criterion, so criteria are counted, not matched.")
NAMES = ("goals_without_live_path", "evidence_backed_closure_rate", "founder_manual_repairs")


@dataclass(frozen=True)
class Confidence:
    level: str  # complete | partial | stale
    reason: str
    counts: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Projection:
    name: str
    source: dict
    as_of: int
    confidence: Confidence
    rows: tuple
    summary: dict

    def to_dict(self):
        return {"name": self.name, "source": dict(self.source), "as_of": self.as_of,
                "confidence": {"level": self.confidence.level, "reason": self.confidence.reason,
                               "counts": dict(self.confidence.counts)},
                "rows": [dict(r) for r in self.rows], "summary": dict(self.summary)}


class _Fold:
    """The reducer state: one pass over the events, sequence-gated and unknown-tolerant."""

    def __init__(self):
        self.goals, self.liveness, self.decisions = {}, {}, {}
        self.consumed, self.declined, self.outcomes = set(), set(), {}
        self.repairs = []
        self.counts = {"events": 0, "unknown": 0, "malformed": 0, "replayed": 0, "gaps": 0}
        self.first = self.last = self.head = None

    def feed(self, event):
        try:
            sequence, kind, data = event["sequence"], event["kind"], event["data"]
            if type(sequence) is not int or type(kind) is not str or type(data) is not dict:
                raise TypeError
        except (KeyError, TypeError):
            self.counts["malformed"] += 1
            return
        if self.last is not None and sequence <= self.last:
            self.counts["replayed"] += 1
            return
        if self.last is not None and sequence != self.last + 1:
            self.counts["gaps"] += 1
        self.first = sequence if self.first is None else self.first
        self.last, self.head = sequence, event.get("event_sha256")
        self.counts["events"] += 1
        try:
            self._apply(sequence, kind, data, data.get("action"))
        except (KeyError, TypeError, AttributeError):
            self.counts["malformed"] += 1

    def _repair(self, sequence, kind, detail):
        self.repairs += [{"sequence": sequence, "repair": kind, "detail": detail}]

    def _apply(self, sequence, kind, data, action):
        if (kind, action) in (("proposal", "start_goal"), ("correction", "revise_goal")):
            contract = data["snapshot"]["contract"]
            self.goals[contract["goal_id"]] = {"revision": contract["revision"],
                                               "closed": data["snapshot"]["closed"] is True,
                                               "criteria": len(contract["acceptance_criteria"])}
        elif kind == "correction":
            self._repair(sequence, "correction", str(action))
        elif (kind, action) == ("decision", "liveness_set"):
            self.liveness[data["liveness"]["goal_id"]] = dict(data["liveness"])
        elif (kind, action) == ("decision", "precommit"):
            r = data["request"]
            self.decisions[r["decision_id"]] = ((r["goal_id"], r["capability_id"], r["operation"]),
                                                r["goal_revision"], data["approval_required"] is True)
        elif kind == "action":
            self.consumed.add(data["decision_id"])
        elif (kind, action) == ("decision", "declined"):
            self.consumed.add(data["decision_id"])
            if data["decision_id"] in self.decisions:
                self.declined.add(self.decisions[data["decision_id"]][0])
        elif (kind, action) == ("decision", "approved"):
            scope = self.decisions.get(data["decision_id"], (None,))[0]
            if scope in self.declined:
                self._repair(sequence, "approved_after_decline", data["decision_id"])
        elif (kind, action) == ("decision", "budget_pause_lifted"):
            self._repair(sequence, "budget_pause_lifted", data["aor_id"])
        elif kind == "outcome":
            o, kind_seen = data["outcome"], data["interpretation"]["evidence_kind"]
            key = (o["goal_id"], o["goal_revision"])
            backed = (o["execution_status"], o["execution_certainty"], kind_seen) == (
                "completed", "responded", "tool_observation")
            self.outcomes[key] = self.outcomes.get(key, 0) + (1 if backed else 0)
        elif (kind, action) not in KNOWN:
            self.counts["unknown"] += 1

    def liveness_report(self, goal_id, now, approver):
        """Mirrors PoodoCore.liveness(), derived from events instead of core state."""
        goal, rec = self.goals[goal_id], self.liveness.get(goal_id)
        report = {"goal_id": goal_id, "goal_revision": goal["revision"], "owner": None, "waiting_on": None,
                  "live": False, "reason": None}
        if goal["closed"]:
            return {**report, "reason": "goal_closed"}
        if rec is None:
            return {**report, "reason": "no_next_action_owner"}
        report.update(owner=rec["owner"], waiting_on=rec["waiting_on"])
        if rec["goal_revision"] != goal["revision"]:
            return {**report, "reason": "liveness_names_stale_revision"}
        if rec.get("review_by") is not None and now > rec["review_by"]:
            return {**report, "reason": "wait_expired"}
        if rec["waiting_on"] == "approval":
            if rec["owner"] != approver:
                return {**report, "reason": "approval_wait_names_wrong_owner"}
            if not any(d not in self.consumed and needs and scope[0] == goal_id and revision == goal["revision"]
                       for d, (scope, revision, needs) in self.decisions.items()):
                return {**report, "reason": "no_pending_approval"}
        return {**report, "live": True, "reason": "waiting_on_" + rec["waiting_on"]}


def _confidence(fold, as_of, written_at, max_age):
    reasons = [f"{fold.counts[k]} {k} events" for k in ("unknown", "malformed", "replayed") if fold.counts[k]]
    if fold.counts["gaps"]:
        reasons += [f"{fold.counts['gaps']} sequence gaps"]
    if fold.first not in (None, 1):
        reasons += [f"window starts at sequence {fold.first}, not 1"]
    level = "partial" if reasons else "complete"
    if max_age is not None:
        if written_at is None:
            level, reasons = "stale", ["source write time unknown"] + reasons
        elif as_of - written_at > max_age:
            level, reasons = "stale", [f"source last written {as_of - written_at}s before as_of (limit {max_age}s)"] + reasons
    return Confidence(level, "; ".join(reasons) or "every event in the range was interpreted", dict(fold.counts))


def project(read, *, source_id, clock, approver=None, written_at=None, max_age=None):
    """Read once and return the three projections by name. `read` is a zero-argument callable, never a ledger."""
    if not callable(read) or any(hasattr(read, name) for name in ("append", "reserve")):
        raise TypeError("A projection takes only a read callable, never a ledger object")
    if type(source_id) is not str or not source_id:
        raise ValueError("A projection must name its source ledger")
    events = read()
    as_of = clock()
    if type(as_of) is not int:
        raise ValueError("The host clock must return integer epoch seconds")
    if type(events) is not list:
        raise ValueError("A ledger read returns a list of events")
    fold = _Fold()
    for event in json.loads(json.dumps(events)):  # detached copies; the source is never touched again
        fold.feed(event)
    confidence = _confidence(fold, as_of, written_at, max_age)
    source = {"ledger": source_id, "first_sequence": fold.first, "last_sequence": fold.last,
              "event_count": fold.counts["events"], "head_event_sha256": fold.head}

    reports = tuple(fold.liveness_report(g, as_of, approver) for g in sorted(fold.goals))
    stuck = tuple(r for r in reports if not r["live"] and r["reason"] != "goal_closed")
    open_goals = sum(1 for r in reports if r["reason"] != "goal_closed")
    evidence = tuple({"goal_id": g, "goal_revision": v["revision"], "acceptance_criteria": v["criteria"],
                      "backing_outcomes": fold.outcomes.get((g, v["revision"]), 0),
                      "evidence_backed": fold.outcomes.get((g, v["revision"]), 0) > 0}
                     for g, v in sorted(fold.goals.items()))
    backed = sum(1 for r in evidence if r["evidence_backed"])
    by_kind = {k: sum(1 for r in fold.repairs if r["repair"] == k) for k in FOUNDER_REPAIRS}

    def build(name, rows, summary):
        return Projection(name, source, as_of, confidence, rows, summary)
    return {
        "goals_without_live_path": build("goals_without_live_path", stuck,
            {"open_goals": open_goals, "without_live_path": len(stuck), "approver": approver}),
        "evidence_backed_closure_rate": build("evidence_backed_closure_rate", evidence,
            {"goals": len(evidence), "evidence_backed": backed,
             "rate": round(backed / len(evidence), 4) if evidence else None, "definition": CLOSURE_DEFINITION}),
        "founder_manual_repairs": build("founder_manual_repairs", tuple(fold.repairs),
            {"total": len(fold.repairs), "by_kind": by_kind, "counted": dict(FOUNDER_REPAIRS),
             "not_counted": dict(NOT_COUNTED)}),
    }

import hashlib
import json
from threading import RLock

from .models import ContractError, canonical, identifier
from .policy import ApprovalRecord
from .streams import Block


class CommitOutbox:
    def __init__(self, *, approvals, ledger, kills, clock, approver, quote, handlers):
        identifier(approver)
        self.approvals, self.ledger, self.kills = approvals, ledger, kills
        self.clock, self.approver, self.quote, self.handlers = clock, approver, quote, dict(handlers)
        self._lock, self._staged, self._used = RLock(), {}, set()
        for event in ledger.read():
            if event['data'].get('action') == 'world_commit':
                self._used.add(event['data']['item_id'])

    def stage(self, block, *, item_id, operation, objects, payload, compensation=None, irreversible=False, execution_scope=None):
        if type(block) is not Block:
            raise ContractError('A block lease is required')
        for value in (item_id, operation):
            identifier(value)
        if (type(objects) is not tuple or not objects or len(objects) > 32
                or len(set(objects)) != len(objects) or type(irreversible) is not bool
                or (irreversible and compensation is not None) or (not irreversible and compensation is None)):
            raise ContractError('Explicit objects and compensation or irreversible required')
        for value in objects:
            identifier(value)
        if compensation is not None:
            if type(compensation) is not dict or set(compensation) != {'operation', 'payload'}:
                raise ContractError('Compensation is an operation and payload')
            identifier(compensation['operation'])
        spec = block.launch
        prefix = (spec.mission_id, spec.launch_id, f'block-{block.index}')
        path = prefix if execution_scope is None else self.kills.path(execution_scope)
        if path[:3] != prefix:
            raise ContractError('Execution scope does not belong to block')
        self.kills.register(path)
        if not self.approvals.commit_scope(spec.launch_id, objects):
            raise ContractError('Commit outside envelope blast radius')
        item = dict(item_id=item_id, operation=operation, objects=list(objects), payload=payload,
                    compensation=compensation, irreversible=irreversible, execution_scope=list(path), envelope=spec.launch_id,
                    mission=spec.mission_id, block=block.index, goal_id=spec.goal.goal_id,
                    goal_revision=spec.goal.revision, policy=spec.policy, scope=spec.scope)
        raw = canonical(item)
        if len(raw) > 65536 or not callable(self.handlers.get(operation)):
            raise ContractError('Invalid commit operation or size')
        with self._lock:
            if item_id in self._staged or item_id in self._used or len(self._staged) >= 10000:
                raise ContractError('Duplicate or excessive staged item')
            self._staged[item_id] = (block, raw)
        return item_id

    def digest(self, item_id):
        with self._lock:
            return hashlib.sha256(self._staged[item_id][1].encode('ascii')).hexdigest()

    def rollback(self, item_id):
        with self._lock:
            self._staged.pop(item_id, None)

    def commit(self, block, item_id):
        with self._lock:
            staged = self._staged.get(item_id)
            if staged is None or staged[0] is not block:
                raise ContractError('Unknown commit or mismatched block lease')
            item = json.loads(staged[1])
            spec = block.launch
            path = tuple(item['execution_scope'])
            self.kills.check(path)
            if self.clock() > spec.expires_at:
                raise ContractError('Expired commit')
            resources = self.quote(json.loads(staged[1]))
            if (type(resources) is not tuple or len(resources) != 4
                    or any(type(v) is not int or not 0 <= v <= 10**15 for v in resources) or resources[0] == 0):
                raise ContractError('Unknown commit cost or resource usage')
            digest = self.digest(item_id)
            if item['irreversible']:
                approval = self.approvals.lookup(item_id)
                if (type(approval) is not ApprovalRecord or approval.decision_id != item_id
                        or approval.request_sha256 != digest or approval.goal_id != spec.goal.goal_id
                        or approval.goal_revision != spec.goal.revision or approval.approver != self.approver
                        or approval.verdict != 'approved' or approval.not_after < self.clock()
                        or not self.approvals.consume(approval.approval_id)):
                    raise ContractError('Per-item approval required')
            if not self.approvals.meter_commit(spec.launch_id, item_id='commit-' + hashlib.sha256(item_id.encode('ascii')).hexdigest(),
                    goal_id=spec.goal.goal_id, goal_revision=spec.goal.revision, policy=spec.policy,
                    scope=spec.scope, objects=tuple(item['objects']), resources=resources):
                raise ContractError('Envelope commit gate refused')
            del self._staged[item_id]
            self._used.add(item_id)
            self.ledger.append('action', {'action': 'world_commit', **item, 'sha256': digest,
                                          'resources': list(resources)})
            self.kills.check(path)
            return self.handlers[item['operation']](item)

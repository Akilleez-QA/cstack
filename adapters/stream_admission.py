from fractions import Fraction
from threading import RLock

from poodo_core.models import ContractError, identifier
from poodo_core.streams import Block, Launch, positive


class StreamAdmission:
    def __init__(self, *, capacity, approvals, acceptance, cost, clock, slots=1):
        positive(slots)
        self._capacity = capacity
        self.approvals, self.acceptance = approvals, dict(acceptance)
        self.cost, self.clock, self.slots = cost, clock, slots
        self._lock = RLock()
        self._streams, self._missions, self._active = {}, {}, {}
        self._committing, self._events = set(), set()

    def capacity(self, aor_id):
        return self._capacity(aor_id)

    def launch(self, launch):
        with self._lock:
            if type(launch) is not Launch or launch.launch_id in self._streams or len(self._streams) >= 10000:
                raise ContractError('Invalid, duplicate or excessive launch')
            if self.clock() > launch.expires_at:
                raise ContractError('Expired launch')
            if any(not callable(self.acceptance.get(ref)) for ref in launch.goal.acceptance_criteria):
                raise ContractError('No runnable acceptance test or oracle')
            mission = self._missions.get(launch.mission_id)
            if mission and mission[:2] != (launch.weight, launch.priority):
                raise ContractError('A mission has one weight and priority')
            if not self.approvals.consume_envelope(launch.launch_id):
                raise ContractError('Envelope launch refused')
            if mission is None:
                floor = min((m[2] for m in self._missions.values()), default=Fraction(0))
                self._missions[launch.mission_id] = (launch.weight, launch.priority, floor)
            self._streams[launch.launch_id] = [launch, 0, 0, False]

    def signal(self, event):
        identifier(event)
        with self._lock:
            self._events.add(event)

    @staticmethod
    def _overlap(left, right):
        return any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for a in left for b in right)

    def next_block(self):
        with self._lock:
            if len(self._active) >= self.slots:
                return None
            ready = []
            for state in self._streams.values():
                spec, index, spent, stopped = state
                if (stopped or index >= min(spec.grid[0] * spec.grid[1], spec.budget.blocks)
                        or self.clock() > spec.expires_at or not set(spec.depends_on) <= self._events
                        or spec.launch_id in self._active
                        or any(self._overlap(spec.scope_locks, b.launch.scope_locks) for b in self._active.values())):
                    continue
                weight, priority, service = self._missions[spec.mission_id]
                ready.append((service, -priority, index, spec.launch_id, state))
            for _, _, _, _, state in sorted(ready):
                spec, index, spent, _ = state
                cost = self.cost(spec, index)
                if type(cost) is not int or not 0 <= cost <= 10**15:
                    raise ContractError('Unknown or invalid block cost')
                if spent + cost > spec.budget.cost:
                    continue
                if not self.approvals.meter(spec.launch_id, item_id=f'block-{index}', goal_id=spec.goal.goal_id,
                        goal_revision=spec.goal.revision, policy=spec.policy, scope=spec.scope, cost=cost):
                    raise ContractError('Envelope meter refused')
                block = Block(spec, index, cost)
                state[1], state[2] = index + 1, spent + cost
                weight, priority, service = self._missions[spec.mission_id]
                self._missions[spec.mission_id] = (weight, priority, service + Fraction(max(1, cost), weight))
                self._active[spec.launch_id] = block
                return block
            return None

    def commit(self, block, action, *, event=None):
        if event is not None:
            identifier(event)
        with self._lock:
            key = block.launch.launch_id
            if self._active.get(key) is not block or key in self._committing:
                raise ContractError('Unknown or already committing block')
            self._committing.add(key)
        succeeded = False
        try:
            if self.clock() > block.launch.expires_at:
                raise ContractError('Expired block')
            result = action()
            succeeded = True
            return result
        finally:
            with self._lock:
                if succeeded and event is not None:
                    self._events.add(event)
                if not succeeded:
                    self._streams[key][3] = True
                self._committing.remove(key)
                del self._active[key]

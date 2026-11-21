from dataclasses import replace
from threading import Event, RLock

from .models import ContractError, identifier
from .policy import CapacityLimits


class KillHierarchy:
    def __init__(self, *, capacity, clock, ledger, latency_bound):
        if type(latency_bound) is not int or latency_bound < 0:
            raise ContractError('A kill latency bound is required')
        if not all(callable(value) for value in (capacity, clock)):
            raise ContractError('Host capacity and clock required')
        self._capacity, self.clock, self.ledger = capacity, clock, ledger
        self.latency_bound = latency_bound
        self._lock = RLock()
        self._stopped, self._tokens = set(), {}
        for event in ledger.read():
            if event['data'].get('action') == 'kill':
                self._stopped.add(self.path(tuple(event['data']['scope'])))

    @staticmethod
    def path(path):
        if type(path) is not tuple or len(path) > 5:
            raise ContractError('Kill path is mission/kernel/block/warp/isolate')
        for part in path:
            identifier(part)
        return path

    def capacity(self, mission):
        limits = self._capacity(mission)
        if type(limits) is not CapacityLimits or limits.aor_id != mission:
            raise ContractError('Unknown mission capacity')
        limits = CapacityLimits(**vars(limits))
        with self._lock:
            return replace(limits, live_cap=0) if () in self._stopped or (mission,) in self._stopped else limits

    def check(self, path):
        self.path(path)
        if not path or self.capacity(path[0]).live_cap == 0:
            raise ContractError('Mission paused')
        with self._lock:
            if any(path[:n] in self._stopped for n in range(len(path) + 1)):
                raise ContractError('Execution scope killed')

    def register(self, path):
        self.path(path)
        self.check(path)
        with self._lock:
            if any(path[:n] in self._stopped for n in range(len(path) + 1)):
                raise ContractError('Execution scope killed')
            if path not in self._tokens:
                if len(self._tokens) >= 10000:
                    raise ContractError('Kill registry full')
                self._tokens[path] = Event()
            return self._tokens[path]

    def kill(self, path):
        self.path(path)
        try:
            started = self.clock()
        except Exception:
            started = None
        with self._lock:
            if len(self._stopped) >= 10000 and path not in self._stopped and path:
                raise ContractError('Kill registry full; use global brake')
            self._stopped.add(path)
            for scope, token in self._tokens.items():
                if scope[:len(path)] == path:
                    token.set()
        ended = self.clock()
        if type(started) is not int or type(ended) is not int:
            raise ContractError('Kill sealed but clock unavailable')
        latency = ended - started
        receipt = {'action': 'kill', 'scope': list(path), 'latency': latency,
                   'bound': self.latency_bound, 'within_bound': 0 <= latency <= self.latency_bound}
        self.ledger.append('decision', receipt)
        if not receipt['within_bound']:
            raise ContractError('Kill sealed but latency bound exceeded')
        return receipt

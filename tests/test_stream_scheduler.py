from collections import Counter
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from adapters.stream_admission import StreamAdmission
from poodo_core.models import AcceptanceReference, ContractError, GoalContract
from poodo_core.streams import BudgetVector, Launch
from tests.helpers import goal
from tests import test_forge_core as envelopes


class StreamTests(unittest.TestCase):
    envelope = envelopes.EnvelopeTests.envelope

    def setUp(self):
        envelopes.EnvelopeTests.setUp(self)
        self.now = 100
        self.ref = AcceptanceReference('test', 'tests.test_stream_scheduler.StreamTests.test_reference_roundtrip')
        self.scheduler = StreamAdmission(capacity=lambda aor: None, approvals=self.reader,
            acceptance={self.ref: lambda: True}, cost=lambda launch, index: 1, clock=lambda: self.now, slots=4)

    def launch(self, name='a', **changes):
        g = replace(goal(), acceptance_criteria=(self.ref,))
        spec = Launch(name, name, g, (1, 10000), BudgetVector(10000, 10000),
                      'read-only', 'calculate', ('calculate',), 0, 1, (), 200)
        spec = replace(spec, **changes)
        self.envelope(approval_id=name, cap=100000, scope=[spec.scope])
        self.scheduler.launch(spec)
        return spec

    def test_reference_roundtrip(self):
        g = replace(goal(), acceptance_criteria=(self.ref,))
        self.assertEqual(GoalContract.from_dict(g.to_dict()), g)
        for criteria in ((), ('It works',), ({'kind': 'test', 'target': 'x'},)):
            with self.assertRaises(ContractError):
                replace(g, acceptance_criteria=criteria)

    def test_no_runnable_test_no_launch(self):
        g = replace(goal(), acceptance_criteria=(AcceptanceReference('oracle', 'missing'),))
        with self.assertRaises(ContractError):
            self.launch(goal=g)
        self.assertTrue(self.reader.consume_envelope('a'))
        self.assertIsNone(self.scheduler.next_block())

    def test_weighted_capacity_with_variable_cost(self):
        self.scheduler.cost = lambda launch, index: (index % 7) + 1
        for name, weight in [('a', 1), ('b', 3), ('c', 6)]:
            self.launch(name, weight=weight, scope_locks=(name,))
        used = Counter()
        for _ in range(2000):
            block = self.scheduler.next_block()
            used[block.launch.mission_id] += block.cost
            self.scheduler.commit(block, lambda: None)
        for name, weight in [('a', 1), ('b', 3), ('c', 6)]:
            self.assertLessEqual(abs(used[name] / sum(used.values()) - weight / 10), .05)

    def test_dependency_expiry_grid_and_budget(self):
        self.launch(depends_on=('ready',), grid=(2, 2), budget=BudgetVector(4, 4))
        self.assertIsNone(self.scheduler.next_block())
        self.scheduler.signal('ready')
        coordinates = []
        for _ in range(4):
            block = self.scheduler.next_block()
            coordinates.append((block.variant, block.depth))
            self.scheduler.commit(block, lambda: None)
        self.assertEqual(coordinates, [(0, 0), (1, 0), (0, 1), (1, 1)])
        self.assertIsNone(self.scheduler.next_block())
        self.launch('expired')
        self.now = 201
        self.assertIsNone(self.scheduler.next_block())

    def test_preemption_only_at_boundary_and_scope_serialization(self):
        self.launch('a', scope_locks=('tree',))
        first = self.scheduler.next_block()
        self.launch('b', scope_locks=('tree/child',), priority=10)
        self.assertIsNone(self.scheduler.next_block())
        entered, release = threading.Event(), threading.Event()
        def action():
            entered.set()
            self.assertTrue(release.wait(5))
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(self.scheduler.commit, first, action)
            self.assertTrue(entered.wait(5))
            self.assertIsNone(self.scheduler.next_block())
            release.set()
            pending.result()
        second = self.scheduler.next_block()
        self.assertEqual(second.launch.launch_id, 'b')
        self.scheduler.commit(second, lambda: None)
        with self.assertRaises(ContractError):
            self.scheduler.commit(first, lambda: self.fail('replayed commit'))

    def test_failed_commit_releases_scope_without_event(self):
        self.launch('a')
        self.launch('b', depends_on=('done',))
        block = self.scheduler.next_block()
        with self.assertRaises(RuntimeError):
            self.scheduler.commit(block, lambda: (_ for _ in ()).throw(RuntimeError()), event='done')
        self.assertIsNone(self.scheduler.next_block())
        self.scheduler.signal('done')
        self.assertEqual(self.scheduler.next_block().launch.launch_id, 'b')

    def test_unknown_cost_and_budget_refuse_dispatch(self):
        self.launch(budget=BudgetVector(1, 1))
        self.scheduler.cost = lambda launch, index: None
        with self.assertRaises(ContractError):
            self.scheduler.next_block()
        self.scheduler.cost = lambda launch, index: 2
        self.assertIsNone(self.scheduler.next_block())

    def test_multiple_streams_do_not_multiply_mission_share(self):
        self.launch('a', mission_id='shared', scope_locks=('a',))
        self.launch('b', mission_id='shared', scope_locks=('b',))
        self.launch('c', scope_locks=('c',))
        used = Counter()
        for _ in range(400):
            block = self.scheduler.next_block()
            used[block.launch.mission_id] += 1
            self.scheduler.commit(block, lambda: None)
        self.assertEqual(used, {'shared': 200, 'c': 200})

    def test_disjoint_scopes_run_and_duplicate_commit_is_refused(self):
        self.launch('a', scope_locks=('a',))
        self.launch('b', scope_locks=('b',))
        a, b = self.scheduler.next_block(), self.scheduler.next_block()
        self.assertIsNotNone(b)
        def action():
            with self.assertRaises(ContractError):
                self.scheduler.commit(a, lambda: self.fail('nested commit'))
        self.scheduler.commit(a, action, event='done')
        self.scheduler.commit(b, lambda: None)

    def test_expired_commit_never_calls_action(self):
        self.launch()
        block = self.scheduler.next_block()
        self.now = 201
        with self.assertRaises(ContractError):
            self.scheduler.commit(block, lambda: self.fail('expired commit'))

    def test_launch_descriptor_refuses_mutable_or_invalid_fields(self):
        spec = self.launch()
        for changes in ({'grid': (0, 1)}, {'weight': True}, {'scope_locks': ('x/../y',)},
                        {'scope_locks': ()}, {'depends_on': ['event']}, {'expires_at': -1}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                replace(spec, **changes)

    def test_noncallable_acceptance_refuses_before_envelope_consumption(self):
        self.scheduler.acceptance[self.ref] = None
        with self.assertRaises(ContractError):
            self.launch()
        self.assertTrue(self.reader.consume_envelope('a'))

    def test_block_budget_stops_a_larger_grid(self):
        self.launch(budget=BudgetVector(1, 10))
        block = self.scheduler.next_block()
        self.scheduler.commit(block, lambda: None)
        self.assertIsNone(self.scheduler.next_block())

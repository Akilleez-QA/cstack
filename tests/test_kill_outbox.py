from dataclasses import replace
from pathlib import Path
import signal
import subprocess
import sys
import unittest

from adapters.durable_ledger import DurableLedger
from adapters.memory_ledger import MemoryLedger
from poodo_core.models import ContractError
from poodo_core.policy import ApprovalRecord, CapacityLimits
from poodo_core.kill import KillHierarchy
from poodo_core.outbox import CommitOutbox
from tests import test_stream_scheduler as streams


class KillOutboxTests(unittest.TestCase):
    def envelope(self, **fields):
        streams.StreamTests.envelope(self, **fields)
        self.writer.record_commit_policy(fields['approval_id'], objects=('object',), per_minute=(3, 2, 2))
    def setUp(self):
        streams.StreamTests.setUp(self)
        self.reader._clock = lambda: self.now
        self.limits = CapacityLimits('a', 10, 4, 10, 4)
        self.ticks = 0
        def clock():
            self.ticks += 1
            return self.ticks
        self.ledger = MemoryLedger()
        self.kills = KillHierarchy(capacity=lambda mission: replace(self.limits, aor_id=mission),
                                   clock=clock, ledger=self.ledger, latency_bound=2)
        self.world = []
        self.outbox = CommitOutbox(approvals=self.reader, ledger=self.ledger, kills=self.kills,
            clock=lambda: self.now, approver='owner', quote=lambda item: (1, 0, 0, 1),
            handlers={'write': lambda item: self.world.append(item['payload'])})
        self.scheduler.kills = self.kills
        self.scheduler.outbox = self.outbox

    def launch(self, name='a', **changes):
        return streams.StreamTests.launch(self, name, **changes)

    def stage(self, block, name='item', **changes):
        return self.outbox.stage(block, item_id=name, operation='write', objects=('object',),
                                 payload={'value': 1}, compensation={'operation': 'restore', 'payload': {}}, **changes)

    def test_kill_each_level_measures_and_cancels_descendants(self):
        for depth in range(6):
            with self.subTest(depth=depth):
                path = ('a', 'kernel', 'block', 'warp', 'isolate')
                kills = KillHierarchy(capacity=lambda _: self.limits, clock=iter((100, 101)).__next__,
                                      ledger=MemoryLedger(), latency_bound=2)
                token = kills.register(path)
                receipt = kills.kill(path[:depth])
                self.assertEqual(receipt['latency'], 1)
                self.assertLessEqual(receipt['latency'], 2)
                self.assertTrue(token.is_set())
                with self.assertRaises(ContractError):
                    kills.check(path)
                if depth == 0:
                    self.assertEqual(kills.capacity('a').live_cap, 0)
                    with self.assertRaises(ContractError):
                        kills.register(('future', 'kernel'))

    def test_rollback_and_scope_refusal_have_no_world_trace(self):
        self.launch()
        block = self.scheduler.next_block()
        for index in range(100):
            with self.assertRaises(ContractError):
                self.outbox.stage(block, item_id=f'bad-{index}', operation='write', objects=('other',),
                                  payload={}, compensation={'operation': 'restore', 'payload': {}})
        self.stage(block)
        self.outbox.rollback('item')
        with self.assertRaises(ContractError):
            self.scheduler.commit(block, 'item')
        self.assertEqual(self.world, [])
        self.assertFalse(any(e['data'].get('action') == 'world_commit' for e in self.ledger.read()))

    def test_commit_record_precedes_effect_and_replay_refuses(self):
        self.launch()
        block = self.scheduler.next_block()
        self.outbox.handlers['write'] = lambda item: self.assertEqual(
            self.ledger.read()[-1]['data']['action'], 'world_commit')
        self.stage(block)
        self.scheduler.commit(block, 'item')
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'item')

    def test_global_brake_freezes_staged_and_raw_callbacks(self):
        self.launch()
        block = self.scheduler.next_block()
        self.stage(block)
        self.kills.kill(())
        self.assertEqual(self.scheduler.capacity('a').live_cap, 0)
        self.assertIsNone(self.scheduler.next_block())
        with self.assertRaises(ContractError):
            self.scheduler.commit(block, 'item')
        self.assertEqual(self.world, [])

    def test_raw_callback_cannot_bypass_outbox(self):
        self.launch()
        block = self.scheduler.next_block()
        with self.assertRaises(ContractError):
            self.scheduler.commit(block, lambda: self.world.append('escaped'))
        self.assertEqual(self.world, [])

    def test_irreversible_requires_exact_single_item_approval(self):
        spec = self.launch()
        block = self.scheduler.next_block()
        item = self.outbox.stage(block, item_id='irreversible', operation='write', objects=('object',),
                                 payload={}, irreversible=True)
        with self.assertRaises(ContractError):
            self.outbox.commit(block, item)
        digest = self.outbox.digest(item)
        self.writer.record(ApprovalRecord('yes', item, digest, spec.goal.goal_id,
                                         spec.goal.revision, 'owner', 'approved', 200))
        self.scheduler.commit(block, item)
        self.assertEqual(self.world, [{}])
        self.assertFalse(self.reader.consume('yes'))

    def test_rolling_rate_caps_survive_reader_restart(self):
        self.launch()
        for index in range(2):
            block = self.scheduler.next_block()
            self.stage(block, str(index))
            self.scheduler.commit(block, str(index))
        block = self.scheduler.next_block()
        self.stage(block, 'limited')
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'limited')
        self.assertEqual(len(self.world), 2)
        from adapters.approval_store import ApprovalReader
        restarted = ApprovalReader(self.path, clock=lambda: self.now, consumer='worker')
        self.addCleanup(restarted.close)
        self.outbox.approvals = restarted
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'limited')
        self.now = 160
        self.scheduler.commit(block, 'limited')
        self.assertEqual(len(self.world), 3)

    def test_failed_ledger_never_dispatches(self):
        self.launch()
        block = self.scheduler.next_block()
        self.stage(block)
        self.outbox.ledger.append = lambda *a: (_ for _ in ()).throw(OSError('disk'))
        with self.assertRaises(OSError):
            self.outbox.commit(block, 'item')
        self.assertEqual(self.world, [])

    def test_sigkill_staging_and_dispatch_have_durable_evidence(self):
        for dispatch in (False, True):
            root = Path(self.tmp.name) / str(dispatch)
            root.mkdir()
            code = """
from pathlib import Path
from tests.test_kill_outbox import KillOutboxTests
from adapters.durable_ledger import DurableLedger
import os, signal, sys
root, dispatch = Path(sys.argv[1]), sys.argv[2] == 'True'
case = KillOutboxTests()
case.setUp()
case.ledger = DurableLedger(root / 'ledger')
case.outbox.ledger = case.ledger
case.launch()
block = case.scheduler.next_block()
case.stage(block)
def write(item):
    (root / 'world').write_text('effect')
    os.kill(os.getpid(), signal.SIGKILL)
case.outbox.handlers['write'] = write
if dispatch:
    case.scheduler.commit(block, 'item')
print('staged', flush=True)
signal.pause()
"""
            process = subprocess.Popen([sys.executable, '-B', '-c', code, str(root), str(dispatch)],
                                       stdout=subprocess.PIPE, text=True)
            self.addCleanup(lambda p=process: p.poll() is None and p.kill())
            if not dispatch:
                import select
                self.assertTrue(select.select([process.stdout], [], [], 5)[0])
                self.assertEqual(process.stdout.readline().strip(), 'staged')
                process.kill()
            self.assertEqual(process.wait(timeout=5), -signal.SIGKILL)
            process.stdout.close()
            events = DurableLedger(root / 'ledger').read()
            commits = [e for e in events if e['data'].get('action') == 'world_commit']
            self.assertEqual(len(commits), int(dispatch))
            self.assertEqual((root / 'world').exists(), dispatch)

    def test_leaf_kill_blocks_its_commit_and_preserves_sibling(self):
        self.launch()
        block = self.scheduler.next_block()
        prefix = ('a', 'a', 'block-0', 'warp')
        self.stage(block, execution_scope=prefix + ('isolate',))
        sibling = self.kills.register(prefix + ('sibling',))
        self.kills.kill(prefix + ('isolate',))
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'item')
        self.assertFalse(sibling.is_set())
        self.assertEqual(self.world, [])

    def test_kill_replays_and_capacity_failures_refuse(self):
        self.kills.kill(())
        replay = KillHierarchy(capacity=lambda _: self.limits, clock=lambda: 0,
                               ledger=self.ledger, latency_bound=1)
        with self.assertRaises(ContractError):
            replay.check(('a',))
        self.assertEqual(replay.capacity('a').live_cap, 0)
        self.kills._capacity = lambda _: None
        with self.assertRaises(ContractError):
            self.kills.check(('a',))

    def test_all_resource_caps_and_scope_checked_at_commit(self):
        self.launch()
        block = self.scheduler.next_block()
        self.stage(block)
        for resources in ((1, 4, 0, 0), (1, 0, 3, 0), (1, 0, 0, 3), (None, 0, 0, 0)):
            self.outbox.quote = lambda item, r=resources: r
            with self.assertRaises(ContractError):
                self.outbox.commit(block, 'item')
        self.assertEqual(self.world, [])
        self.assertFalse(self.reader.meter_commit('a', item_id='bad', goal_id='g', goal_revision=1,
            policy='read-only', scope='calculate', objects=('other',), resources=(1, 0, 0, 1)))

    def test_wrong_irreversible_digest_refuses_without_consumption(self):
        spec = self.launch()
        block = self.scheduler.next_block()
        self.outbox.stage(block, item_id='i', operation='write', objects=('object',), payload={}, irreversible=True)
        self.writer.record(ApprovalRecord('yes', 'i', '0' * 64, spec.goal.goal_id, 1, 'owner', 'approved', 200))
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'i')
        self.assertTrue(self.reader.consume('yes'))
        self.assertEqual(self.world, [])

    def test_latency_overrun_stays_sealed(self):
        ticks = iter((0, 3))
        kills = KillHierarchy(capacity=lambda _: self.limits, clock=lambda: next(ticks),
                              ledger=MemoryLedger(), latency_bound=2)
        with self.assertRaises(ContractError):
            kills.kill(())
        with self.assertRaises(ContractError):
            kills.check(('a',))

    def test_core_budget_hard_stop_seals_shared_mission(self):
        from tests import test_budget_hard_stop as budgets
        from poodo_core import PoodoCore, CostBudget
        core = PoodoCore(budgets.Extension(), {'synthetic_sensor': budgets.Capability()},
                         (budgets.GRANT,), MemoryLedger(), approvals=budgets.Approvals(),
                         approver=budgets.APPROVER, clock=lambda: 1000,
                         budgets=(CostBudget('coordinator', 40, 'usd_micros'),),
                         costs=budgets.Costs(), kills=self.kills)
        budgets.run(core)
        self.assertEqual(self.kills.capacity('coordinator').live_cap, 0)
        with self.assertRaises(ContractError):
            self.kills.check(('coordinator', 'kernel'))

    def test_parallel_commit_gate_cannot_multiply_resource_cap(self):
        from tests.test_approval_store import in_parallel
        self.launch()
        code = ("from adapters.approval_store import ApprovalReader\nimport os\n"
                f"r=ApprovalReader({str(self.path)!r},clock=lambda:100,consumer='worker')\n"
                "print(r.meter_commit('a',item_id='parallel-'+str(os.getpid()),goal_id='g',goal_revision=1,"
                "policy='read-only',scope='calculate',objects=('object',),resources=(1,0,0,1)))")
        self.assertEqual(sorted(in_parallel(code, 8)), ['False'] * 6 + ['True'] * 2)

    def test_handler_failure_is_never_retried_after_restart(self):
        self.launch()
        block = self.scheduler.next_block()
        self.stage(block)
        self.outbox.handlers['write'] = lambda item: (_ for _ in ()).throw(RuntimeError('ambiguous'))
        with self.assertRaises(RuntimeError):
            self.outbox.commit(block, 'item')
        restarted = CommitOutbox(approvals=self.reader, ledger=self.ledger, kills=self.kills,
            clock=lambda: self.now, approver='owner', quote=self.outbox.quote, handlers=self.outbox.handlers)
        with self.assertRaises(ContractError):
            restarted.stage(block, item_id='item', operation='write', objects=('object',), payload={},
                            compensation={'operation': 'restore', 'payload': {}})

    def test_envelope_exhaustion_and_expiry_never_write(self):
        self.launch()
        block = self.scheduler.next_block()
        self.stage(block)
        self.outbox.quote = lambda _: (100001, 0, 0, 1)
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'item')
        self.now = 201
        self.outbox.quote = lambda _: (1, 0, 0, 1)
        with self.assertRaises(ContractError):
            self.outbox.commit(block, 'item')
        self.assertEqual(self.world, [])

    def test_killed_lease_does_not_block_unrelated_mission(self):
        self.scheduler.slots = 1
        self.launch('a')
        first = self.scheduler.next_block()
        self.launch('b', scope_locks=('other',))
        self.kills.kill(('a',))
        self.assertEqual(self.scheduler.next_block().launch.mission_id, 'b')
        with self.assertRaises(ContractError):
            self.scheduler.commit(first, lambda: self.fail('killed lease'))

    def test_staging_snapshots_payload_and_compensation(self):
        self.launch()
        block = self.scheduler.next_block()
        payload = {'value': 1}
        compensation = {'operation': 'restore', 'payload': {'value': 0}}
        self.outbox.stage(block, item_id='snapshot', operation='write', objects=('object',),
                          payload=payload, compensation=compensation)
        digest = self.outbox.digest('snapshot')
        payload['value'] = 2
        compensation['payload']['value'] = 3
        self.assertEqual(self.outbox.digest('snapshot'), digest)
        self.scheduler.commit(block, 'snapshot')
        self.assertEqual(self.world, [{'value': 1}])

    def test_terminal_approver_refuses_commit_authority(self):
        from adapters.terminal_approver import TerminalApprover
        port = TerminalApprover(state_root=self.tmp.name)
        self.assertFalse(port.commit_scope('a', ('object',)))
        self.assertFalse(port.meter_commit('a', item_id='i', goal_id='g', goal_revision=1,
            policy='read-only', scope='calculate', objects=('object',), resources=(1, 0, 0, 1)))

    def test_maximum_length_item_identifier_can_commit(self):
        self.launch()
        block = self.scheduler.next_block()
        name = 'i' * 128
        self.stage(block, name)
        self.scheduler.commit(block, name)
        self.assertEqual(self.world, [{'value': 1}])

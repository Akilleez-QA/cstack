import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from adapters.approval_store import ApprovalReader, ApprovalWriter
from adapters.durable_ledger import DurableLedger
from adapters.memory_ledger import MemoryLedger
from poodo_core.models import ContractError, canonical


def root(events):
    level = [hashlib.sha256(b'\x00' + canonical(e).encode('ascii')).digest() for e in events]
    while len(level) > 1:
        level = [hashlib.sha256(b'\x01' + level[i] + level[min(i + 1, len(level) - 1)]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'approvals.db'
        self.writer = ApprovalWriter(self.path, clock=lambda: 100)
        self.addCleanup(self.writer.close)
        self.reader = ApprovalReader(self.path, clock=lambda: 100, consumer='worker')
        self.addCleanup(self.reader.close)

    def envelope(self, **changes):
        fields = dict(approval_id='launch', goal_id='g', goal_revision=1, policy='read-only',
                      cap=10, scope=['calculate'], not_after=200)
        self.writer.record_envelope(**(fields | changes))

    def meter(self, item='i', cost=1, **changes):
        return self.reader.meter('launch', item_id=item, goal_id='g', goal_revision=1,
                                 policy='read-only', scope='calculate', cost=cost, **changes)

    def test_cap_exhaustion_and_launch_are_durable_and_single_use(self):
        self.envelope()
        self.assertFalse(self.meter())
        self.assertTrue(self.reader.consume_envelope('launch'))
        self.assertFalse(self.reader.consume_envelope('launch'))
        self.assertTrue(self.meter(cost=6))
        self.assertFalse(self.meter(cost=1))
        self.assertEqual([self.meter(str(i), 5) for i in range(100)], [False] * 100)
        self.assertTrue(self.meter('last', 4))
        self.assertFalse(self.meter('empty', 0))
        code = ("from adapters.approval_store import ApprovalReader\n"
                f"r=ApprovalReader({str(self.path)!r},clock=lambda:100,consumer='worker')\n"
                "print(r.consume_envelope('launch'))\n"
                "print(r.meter('launch',item_id='restart',goal_id='g',goal_revision=1,"
                "policy='read-only',scope='calculate',cost=1))")
        self.assertEqual(subprocess.check_output([sys.executable, '-B', '-c', code], text=True), 'False\nFalse\n')

    def test_restart_cannot_launch_again_with_budget_remaining(self):
        self.envelope()
        self.assertTrue(self.reader.consume_envelope('launch'))
        code = ("from adapters.approval_store import ApprovalReader\n"
                f"r=ApprovalReader({str(self.path)!r},clock=lambda:100,consumer='worker')\n"
                "print(r.consume_envelope('launch'))\n"
                "print(r.meter('launch',item_id='restart',goal_id='g',goal_revision=1,"
                "policy='read-only',scope='calculate',cost=1))")
        self.assertEqual(subprocess.check_output([sys.executable, '-B', '-c', code], text=True), 'False\nTrue\n')
        self.assertTrue(self.meter('remaining', 9))
        self.assertFalse(self.meter('spent', 1))

    def test_envelope_never_satisfies_a_core_message_ask(self):
        from poodo_core import ApprovalPending
        from tests.helpers import request
        from tests.test_approval_policy import Foundation, decided
        self.envelope(scope=['send_report'])
        self.assertTrue(self.reader.consume_envelope('launch'))
        core = Foundation(approvals=self.reader)
        req = decided(core, request('send_report'))
        with self.assertRaises(ApprovalPending):
            core.execute(req.decision_id)
        self.assertEqual(core.fake.calls, [])

    def test_parallel_launch_and_meter_refuse_replay_and_overspend(self):
        from tests.test_approval_store import in_parallel
        self.envelope(cap=3)
        prefix = ("from adapters.approval_store import ApprovalReader\n"
                  f"r=ApprovalReader({str(self.path)!r},clock=lambda:100,consumer='worker')\n")
        self.assertEqual(sorted(in_parallel(prefix + "print(r.consume_envelope('launch'))", 8)),
                         ['False'] * 7 + ['True'])
        metering = ("print(r.meter('launch',item_id='same',goal_id='g',goal_revision=1,"
                    "policy='read-only',scope='calculate',cost=2))")
        self.assertEqual(sorted(in_parallel(prefix + metering, 8)), ['False'] * 7 + ['True'])
        self.assertTrue(self.meter('remaining', 1))
        self.assertFalse(self.meter('spent', 1))

    def test_unknown_cost_scope_expiry_and_sensitive_effects_refuse(self):
        self.envelope()
        self.assertTrue(self.reader.consume_envelope('launch'))
        for cost in (None, -1, True, 1.5):
            self.assertFalse(self.meter(cost=cost))
        for effect in ('money', 'outgoing_message', 'unknown'):
            self.assertFalse(self.meter(effect=effect))
        for field, bad in (('scope', 'send'), ('goal_id', 'other'), ('goal_revision', 2), ('policy', 'other')):
            fields = dict(item_id='x', goal_id='g', goal_revision=1, policy='read-only', scope='calculate', cost=1)
            self.assertFalse(self.reader.meter('launch', **(fields | {field: bad})))
        self.reader._clock = lambda: 201
        self.assertFalse(self.meter())
        self.envelope(approval_id='expired', not_after=99)
        self.assertFalse(self.reader.consume_envelope('expired'))
        with self.assertRaises(ContractError):
            self.envelope(approval_id='no-cap', cap=None)


class BatchTests(unittest.TestCase):
    def test_batch_root_and_invalid_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ledger in (MemoryLedger(), DurableLedger(Path(tmp) / 'log')):
                for batch in ([], [('observation', {}) , ('bad', {})], [('observation', None)], 'bad'):
                    with self.assertRaises(ContractError):
                        ledger.append_batch(batch)
                    self.assertEqual(ledger.read(), [])
                for batch in ([('observation', {'i': 1})], [('decision', {}), ('learning', {}), ('outcome', {})]):
                    start = len(ledger.read())
                    self.assertEqual(ledger.append_batch(batch), root(ledger.read()[start:]))

    def test_retention_refusal_rolls_back_entire_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log'
            for ledger in (MemoryLedger(max_events=1), DurableLedger(path, max_events=1)):
                with self.assertRaises(ContractError):
                    ledger.append_batch([('observation', {}), ('observation', {})])
                self.assertEqual(ledger.read(), [])
                self.assertEqual(ledger._bytes, 0)
            self.assertEqual(DurableLedger(path).read(), [])

    def test_one_file_sync_per_batch_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log'
            ledger = DurableLedger(path)
            ledger.append('observation', {})
            with patch('adapters.durable_ledger.os.fsync', wraps=os.fsync) as sync:
                ledger.append_batch([('observation', {'i': i}) for i in range(10)])
                self.assertEqual(sync.call_count, 1)
            self.assertEqual(DurableLedger(path).read(), ledger.read())
            from adapters.endoforge_workcell import core_events
            self.assertEqual(core_events(path), ledger.read())

    def test_killed_mid_batch_quarantines_all_and_replays_accepted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log'
            DurableLedger(path).append('observation', {'accepted': True})
            code = ("import os,signal\nfrom adapters.durable_ledger import DurableLedger\n"
                    f"ledger=DurableLedger({str(path)!r})\n"
                    "def torn(fd,data):\n os.write(fd,bytes(data)[:len(data)//2]); os.kill(os.getpid(),signal.SIGKILL)\n"
                    "ledger._write_all=torn\n"
                    "ledger.append_batch([('observation',{'i':i}) for i in range(10)])")
            proc = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True)
            self.assertEqual(proc.returncode, -signal.SIGKILL, proc.stderr)
            reopened = DurableLedger(path)
            self.assertEqual(len(reopened.read()), 1)
            self.assertEqual(len(reopened.quarantined), 1)
            reopened.append_batch([('observation', {'i': i}) for i in range(10)])
            self.assertEqual(len(DurableLedger(path).read()), 11)

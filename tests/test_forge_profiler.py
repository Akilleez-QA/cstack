import unittest

from adapters.memory_ledger import MemoryLedger
from poodo_core.models import ContractError, canonical
from poodo_core.profiler import ForgeBoard, record_profile, record_decision, export_decisions


class ProfilerTests(unittest.TestCase):
    def sample(self, ledger, **changes):
        data = dict(mission='m', kernel='k', duration=10, busy=5, slots=1,
                    branches=10, divergent=1, cache_hits=2, cache_lookups=4,
                    burn=5, envelope=20, planned_burn=10, dependencies=[],
                    waiting_on=[], held_locks=[], conflict=False, policy='p', outcomes=[])
        return record_profile(ledger, **{**data, **changes})

    def test_counters_replay_and_roots(self):
        ledger = MemoryLedger()
        outcome = ledger.append('outcome', {'outcome': {'attempt_id': 'a'},
                                'interpretation': {'verdict': 'passed'}})
        root = self.sample(ledger, outcomes=[outcome['event_sha256']])
        board = ForgeBoard(ledger).read()
        kernel = board['kernels']['k']
        self.assertEqual((kernel['occupancy'], kernel['divergence_rate'],
                          kernel['verify_pass_rate'], kernel['cache_hit_rate']), (.5, .1, 1, .5))
        self.assertEqual((kernel['burn'], kernel['envelope'], kernel['critical_path']), (5, 20, 10))
        self.assertEqual(board['batch_roots'], [root])
        clone = MemoryLedger()
        for event in ledger.read():
            clone.append(event['kind'], event['data'])
        self.assertEqual(canonical(board), canonical(ForgeBoard(clone).read()))
        self.assertEqual(board['exceptions'], [])

    def test_all_exceptions_and_token_exclusion(self):
        ledger = MemoryLedger()
        bad = ledger.append('outcome', {'outcome': {}, 'interpretation': {'verdict': 'failed'}})
        self.sample(ledger, burn=11, divergent=6, outcomes=[bad['event_sha256']],
                    waiting_on=['other'], held_locks=['scope'], conflict=True, policy=None)
        self.sample(ledger, kernel='other', waiting_on=['k'], held_locks=['other-scope'])
        ledger.append('observation', {'action': 'token', 'text': 'PRIVATE_TOKEN'})
        feed = ForgeBoard(ledger).read()['exceptions']
        self.assertEqual({x['anomaly'] for x in feed}, {'burn_over_plan', 'verify_collapse',
                         'divergence_explosion', 'scope_lock_deadlock', 'goal_conflict_no_policy'})
        self.assertNotIn('PRIVATE_TOKEN', canonical(feed))
        self.assertTrue(all(set(x) == {'mission', 'kernel', 'anomaly'} for x in feed))
        with self.assertRaises((ContractError, TypeError)):
            self.sample(ledger, token='PRIVATE_TOKEN')

    def test_mission_diff_and_revision(self):
        ledger = MemoryLedger()
        from poodo_core.models import GoalContract, AcceptanceReference
        goal = GoalContract('m', 1, 'd', 'objective', (), (), 'v1',
                            (AcceptanceReference('test', 'yes'), AcceptanceReference('test', 'no')))
        board = ForgeBoard(ledger)
        board.run_acceptance(goal, {'yes': lambda: True, 'no': lambda: False})
        mission = board.read()['missions']['m']
        self.assertEqual(mission['confidence'], .5)
        self.assertEqual([x['result'] for x in mission['diff']], ['passed', 'failed'])
        self.assertFalse(mission['runtime_goal_acceptance'])
        revised = GoalContract('m', 2, 'd', 'objective', (), (), 'v2',
                               (AcceptanceReference('test', 'yes'),))
        ledger.append('correction', {'action': 'revise_goal', 'snapshot': {'contract': revised.to_dict()}})
        self.assertEqual(board.read()['missions']['m']['confidence'], 0)
        board.run_acceptance(revised, {'yes': lambda: True})
        board.run_acceptance(goal, {'yes': lambda: False, 'no': lambda: False})
        self.assertEqual(board.read()['missions']['m']['confidence'], 1)
        with self.assertRaises(ContractError):
            board.run_acceptance(goal, {'yes': lambda: True})

    def test_decision_export(self):
        ledger = MemoryLedger()
        for action in ('approve', 'reject', 'edit_spec', 'resolve_conflict'):
            record_decision(ledger, mission='m', revision=1, action=action,
                            context={'spec': 'synthetic'}, reason='host judgment')
        rows = export_decisions(ledger)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['context'], {'spec': 'synthetic'})
        self.assertEqual(rows[0]['schema'], 'forge.honcho-decision/1')
        with self.assertRaises(ContractError):
            record_decision(ledger, mission='m', revision=1, action='approve', context={}, reason='')

    def test_bad_evidence_and_dependencies_refuse(self):
        ledger = MemoryLedger()
        with self.assertRaises(ContractError):
            self.sample(ledger, busy=11)
        self.sample(ledger, outcomes=['0' * 64])
        with self.assertRaises(ContractError):
            ForgeBoard(ledger).read()

    def test_durable_bytes_reconstruct_and_critical_path(self):
        import tempfile
        from pathlib import Path
        from adapters.durable_ledger import DurableLedger
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.jsonl'
            ledger = DurableLedger(path)
            self.sample(ledger)
            self.sample(ledger, kernel='next', dependencies=['k'], duration=20)
            before = path.read_bytes()
            board = ForgeBoard(ledger).read()
            self.assertEqual(board['kernels']['next']['critical_path'], 30)
            self.assertEqual(board, ForgeBoard(DurableLedger(path)).read())
            self.assertEqual(before, path.read_bytes())
            self.assertIsNone(board['kernels']['k']['verify_pass_rate'])
            ledger.append('observation', {'schema': 'forge.profile-root/1', 'root': '0' * 64})
            with self.assertRaises(ContractError):
                ForgeBoard(ledger).read()

    def test_missing_acceptance_and_cycle(self):
        from poodo_core.models import GoalContract, AcceptanceReference
        ledger = MemoryLedger()
        goal = GoalContract('m', 1, 'd', 'objective', (), (), 'v1',
                            (AcceptanceReference('test', 'yes'),))
        ledger.append('proposal', {'action': 'start_goal', 'snapshot': {'contract': goal.to_dict()}})
        board = ForgeBoard(ledger)
        self.assertEqual(board.read()['missions']['m']['diff'][0]['result'], 'missing')
        self.sample(ledger, dependencies=['k'])
        with self.assertRaises(ContractError):
            board.read()

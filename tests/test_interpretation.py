import hashlib
import importlib
from dataclasses import replace
import unittest

from poodo_core import Interpretation, digest, canonical, outcome_for
from tests.helpers import FakeExtension, FakeFoundation, execute_one, goal, request


class InterpretationTests(unittest.TestCase):
    def test_every_extension_returns_verifier_metadata_and_replays_evidence(self):
        names = [('foundation_math', 'MathExtension'), ('foundation_refrigeration', 'RefrigerationExtension'),
                 ('foundation_robotics', 'RoboticsExtension'), ('foundation_film', 'FilmExtension'),
                 ('foundation_engine', 'EngineExtension'), ('foundation_template', 'TemplateExtension'),
                 ('cstack_forge', 'ForgeExtension')]
        req = request()
        for module, name in names:
            extension = getattr(importlib.import_module('extensions.' + module), name)()
            for status, verdict in [('completed', 'passed'), ('tool_error', 'failed'), ('unavailable', 'unverified')]:
                payload = {'b': [2, 1], 'a': 'evidence'} if status == 'completed' else None
                out = outcome_for(req, 'a1', status, 'fixture',
                                  certainty='responded' if status == 'completed' else 'not_dispatched', raw_result=payload)
                with self.subTest(extension=module, status=status):
                    first = extension.interpret(goal(), req, out)
                    self.assertEqual(first.verdict, verdict)
                    expected_bytes = b'{"a":"evidence","b":[2,1]}' if payload is not None else b'null'
                    self.assertEqual(first.evidence_hash, hashlib.sha256(expected_bytes).hexdigest())
                    self.assertEqual(first.verify_cost, len(canonical(payload).encode('ascii')))
                    replay = outcome_for(req, 'a2', status, 'fixture',
                                         certainty='responded' if status == 'completed' else 'not_dispatched', raw_result=payload)
                    self.assertEqual(extension.interpret(goal(), req, replay).evidence_hash, first.evidence_hash)
        self.assertEqual(digest({'a': 'evidence', 'b': [2, 1]}), digest({'b': [2, 1], 'a': 'evidence'}))

    def test_missing_malformed_or_failed_verification_is_quarantined(self):
        bad = [('verdict', x) for x in (None, '', True, 'failed', 'unverified', 'accepted', 'merged')]
        bad += [('evidence_hash', x) for x in (None, '', 'x' * 64, '0' * 64, True)]
        bad += [('verify_cost', x) for x in (None, -1, 0, True, 1.5, float('nan'), float('inf'), '0')]
        for field, value in bad:
            class Invalid(FakeExtension):
                def interpret(self, goal, request, outcome):
                    return replace(super().interpret(goal, request, outcome), **{field: value})
            with self.subTest(field=field, value=value):
                core = FakeFoundation(extension=Invalid())
                result = execute_one(core).to_dict()
                self.assertEqual(result['execution_status'], 'protocol_error')
                self.assertIsNone(result['raw_result'])
                terminal = core.ledger()[-1]['data']
                self.assertFalse(terminal['goal_closed'])
                self.assertFalse(terminal['interpretation']['runtime_goal_acceptance'])
                self.assertEqual(terminal['interpretation']['verdict'], 'unverified')
                self.assertIsNone(terminal['interpretation']['verify_cost'])

    def test_legacy_interpretation_fails_closed_and_success_is_scoped(self):
        class Legacy(FakeExtension):
            def interpret(self, goal, request, outcome):
                return Interpretation('tool_observation', 'Legacy observation', ())
        core = FakeFoundation(extension=Legacy())
        self.assertEqual(execute_one(core).to_dict()['execution_status'], 'protocol_error')
        core = FakeFoundation()
        self.assertEqual(execute_one(core).to_dict()['execution_status'], 'completed')
        terminal = core.ledger()[-1]['data']
        self.assertEqual(terminal['interpretation']['verdict'], 'passed')
        self.assertFalse(terminal['goal_closed'])
        self.assertFalse(terminal['interpretation']['runtime_goal_acceptance'])

    def test_noncompleted_verdicts_remain_unaccepted(self):
        from tests.helpers import FakeCapability

        for status, verdict in [('tool_error', 'failed'), ('unavailable', 'unverified')]:
            class Unsuccessful(FakeCapability):
                def invoke(self, request, attempt_id, cancellation=None):
                    return outcome_for(request, attempt_id, status, 'fixture')
            core = FakeFoundation(capability=Unsuccessful())
            self.assertEqual(execute_one(core).to_dict()['execution_status'], status)
            terminal = core.ledger()[-1]['data']
            self.assertEqual(terminal['interpretation']['verdict'], verdict)
            self.assertFalse(terminal['goal_closed'])
            self.assertFalse(terminal['interpretation']['runtime_goal_acceptance'])

    def test_evidence_changes_hash_and_missing_fields_fail_closed(self):
        req = request()
        left = outcome_for(req, 'a', 'completed', 'fixture', certainty='responded', raw_result={'x': 1})
        right = outcome_for(req, 'a', 'completed', 'fixture', certainty='responded', raw_result={'x': 2})
        extension = FakeExtension()
        self.assertNotEqual(extension.interpret(goal(), req, left).evidence_hash,
                            extension.interpret(goal(), req, right).evidence_hash)
        for field in ('verdict', 'evidence_hash', 'verify_cost'):
            class Missing(FakeExtension):
                def interpret(self, goal, request, outcome):
                    result = super().interpret(goal, request, outcome)
                    object.__delattr__(result, field)
                    return result
            core = FakeFoundation(extension=Missing())
            self.assertEqual(execute_one(core).to_dict()['execution_status'], 'protocol_error')

    def test_recovery_records_unknown_verification_without_acceptance(self):
        from adapters.memory_ledger import MemoryLedger

        core = FakeFoundation()
        execute_one(core)
        ledger = MemoryLedger()
        for event in core.ledger():
            if event['kind'] != 'outcome':
                ledger.append(event['kind'], event['data'])
        recovered = FakeFoundation(ledger=ledger)
        terminal = recovered.ledger()[-1]['data']
        self.assertEqual(terminal['outcome']['execution_status'], 'indeterminate')
        self.assertEqual(terminal['interpretation']['verdict'], 'unverified')
        self.assertEqual(terminal['interpretation']['evidence_hash'], hashlib.sha256(b'null').hexdigest())
        self.assertIsNone(terminal['interpretation']['verify_cost'])
        self.assertFalse(terminal['goal_closed'])

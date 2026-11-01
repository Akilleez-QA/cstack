"""M3 acceptance checks using local synthetic archives and private temporary DBs."""
import gzip
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from adapters.memory import MemoryStore
from adapters.memory.__main__ import main
from adapters.memory_ledger import MemoryLedger
from poodo_core.models import ContractError, canonical


class MemoryCliTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.root / 'test.memory.db'
        self.store = MemoryStore(self.path, clock=lambda: 123)
        self.addCleanup(self.store.close)

    def propose(self, **kwargs):
        return self.store.propose('Synthetic cooling inspection café complete.',
            archive_label='synthetic', thread_id='one', line_offset=0,
            chunk_index=0, role='assistant', **kwargs)[0]['fact_id']

    def run_cli(self, *argv, code=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main(['--db', str(self.path), *argv])
        self.assertEqual(result, code, err.getvalue())
        payload = err.getvalue() if code else out.getvalue()
        self.assertEqual(out.getvalue() if code else err.getvalue(), '')
        self.assertNotIn('Traceback', payload)
        self.assertNotIn(str(self.path), payload)
        value = json.loads(payload)
        self.assertEqual(payload, json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')
        return value

    def test_queries_and_reviews(self):
        fid = self.propose()
        self.assertEqual(self.run_cli('search', 'cooling')[0]['fact_id'], fid)
        self.assertEqual(self.run_cli('list', '--limit', '1')[0]['status'], 'proposed')
        self.assertEqual(self.run_cli('show', fid)['text'], 'Synthetic cooling inspection café complete.')
        self.assertEqual(self.run_cli('stats')['facts']['proposed'], 1)
        review = self.run_cli('confirm', fid, '--by', 'reviewer', '--ledger-ref', 'a' * 64)
        self.assertEqual((review['status'], review['ledger_ref']), ('confirmed', 'a' * 64))
        self.assertEqual(self.run_cli('search', 'cooling', '--status', 'confirmed')[0]['fact_id'], fid)
        other = self.store.propose_reference('Synthetic cooling manual.', source='catalog',
            path='manual', checksum='b' * 64, embedding=[0.25, -1.5])[0]['fact_id']
        self.assertEqual(self.run_cli('show', other)['embedding_dims'], 2)
        self.assertNotIn('embedding', self.run_cli('search', 'manual')[0])
        self.assertEqual(self.run_cli('reject', other, '--by', 'reviewer', '--note', 'Obsolete.')['status'],
                         'rejected')
        self.assertEqual(len(self.run_cli('list', '--status', 'rejected')), 1)
        self.assertEqual(self.run_cli('show', 'fact-' + '0' * 64), None)

    def test_errors_and_env_db(self):
        self.assertIn('error', self.run_cli('show', 'bad', code=2))
        self.assertIn('error', self.run_cli('list', '--limit', '0', code=2))
        self.assertIn('error', self.run_cli('ingest', str(self.root / 'missing'), code=2))
        self.assertIn('error', self.run_cli('--db', str(self.root / 'missing' / 'private.db'),
                                           'stats', code=2))
        with patch.dict(os.environ, {'CSTACK_MEMORY_DB': str(self.path)}):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['stats']), 0)
            self.assertIn('facts', json.loads(out.getvalue()))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(['reject', 'bad', '--by', 'reviewer'])
        self.assertEqual(error.exception.code, 2)

    def test_ingest(self):
        threads = self.root / 'threads'
        threads.mkdir()
        with gzip.open(threads / 'synthetic.jsonl.gz', 'wt') as out:
            out.write(json.dumps(dict(thread_id='one', msgs=[dict(role='user',
                text='We decided to inspect the synthetic cooling valve daily.')])) + '\n')
        receipt = self.run_cli('ingest', str(self.root), '--label', 'fixture')
        self.assertEqual((receipt['facts_added'], receipt['archive_label']), (1, 'fixture'))
        self.assertEqual(self.run_cli('stats')['ingest_runs'], 1)
        deny = self.root / 'deny.txt'
        deny.write_text('SyntheticCustomer', encoding='utf-8')
        with patch.dict(os.environ, {'CSTACK_MEMORY_DENYLIST': str(deny)}):
            self.assertIn('error', self.run_cli('ingest', str(self.root), '--label',
                                               'SyntheticCustomer', code=2))
        self.assertEqual(self.run_cli('stats')['ingest_runs'], 1)

    def test_ledger_reviews(self):
        ledger = MemoryLedger()
        self.store.close()
        self.store = MemoryStore(self.path, clock=lambda: 456, ledger=ledger)
        self.addCleanup(self.store.close)
        fid = self.propose()
        for kwargs in ({'by': ''}, {'by': 'reviewer', 'ledger_ref': 'a' * 64}):
            with self.assertRaises(ContractError):
                self.store.confirm(fid, **kwargs)
        self.assertRaises(ContractError, self.store.confirm, 'fact-' + '0' * 64, by='reviewer')
        self.assertRaises(ContractError, self.store.reject, fid, by='reviewer', note='')
        self.assertEqual(ledger.read(), [])
        with patch.object(ledger, 'reserve', wraps=ledger.reserve) as reserve:
            review = self.store.confirm(fid, by='reviewer', note='Private review note.')
        event = ledger.read()[0]
        self.assertEqual(review['ledger_ref'], event['event_sha256'])
        self.assertEqual(event['kind'], 'decision')
        self.assertEqual(event['data'], dict(action='memory_review', fact_id=fid,
                                             status='confirmed', by='reviewer'))
        self.assertEqual(reserve.call_args_list[0].args, (1, len(canonical(event['data']))))
        self.assertRaises(ContractError, self.store.reject, fid, by='reviewer', note='Again.')
        self.assertEqual(len(ledger.read()), 1)

    def test_hash_validation_capacity_and_write_ahead(self):
        ledger = MemoryLedger()
        self.store._ledger = ledger
        fid = self.propose()
        for event in ({}, {'hash': 'A' * 64}, {'event_sha256': 'bad'}, None):
            with patch.object(ledger, 'append', return_value=event):
                self.assertRaises(ContractError, self.store.confirm, fid, by='reviewer')
            self.assertEqual(self.store.get(fid)['status'], 'proposed')
        with patch.object(ledger, 'reserve', side_effect=ContractError('Full')):
            self.assertRaises(ContractError, self.store.confirm, fid, by='reviewer')
        self.assertEqual(ledger.read(), [])
        self.store._db.execute("""CREATE TRIGGER fail_review BEFORE UPDATE ON facts BEGIN
            SELECT RAISE(ABORT, 'Synthetic failure'); END""")
        self.assertRaises(ContractError, self.store.confirm, fid, by='reviewer')
        self.assertEqual((len(ledger.read()), self.store.get(fid)['status']), (1, 'proposed'))
        self.store._db.execute('DROP TRIGGER fail_review')
        with patch.object(ledger, 'append', return_value={'hash': 'b' * 64}):
            review = self.store.reject(fid, by='reviewer', note='Synthetic rejection.')
        self.assertEqual((review['status'], review['ledger_ref']), ('rejected', 'b' * 64))

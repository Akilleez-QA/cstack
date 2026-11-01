"""Synthetic, temporary-only acceptance checks for knowledge storage."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.memory import MemoryStore
from adapters.memory.store import FACT_KINDS, TRUST_TIERS
from adapters.memory_ledger import EVENT_KINDS
from poodo_core.models import ContractError, digest

class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'test.memory.db'
        self.store = self.open()

    def open(self, **kwargs):
        store = MemoryStore(self.path, clock=kwargs.get('clock', lambda: 123))
        self.addCleanup(store.close)
        return store

    def propose(self, text='Cooling inspection complete.', **kwargs):
        values = dict(archive_label='synthetic', thread_id='thread / one', line_offset=0,
                      chunk_index=0, role='assistant', trust='agent_written')
        return self.store.propose(text, **(values | kwargs))

    def test_persistence_paths_privacy_and_closed(self):
        fact, inserted = self.propose()
        self.assertEqual((inserted, self.path.stat().st_mode & 0o777), (True, 0o600))
        for pragma, expected in [('journal_mode', 'wal'), ('synchronous', 2)]:
            self.assertEqual(self.store._db.execute('PRAGMA ' + pragma).fetchone()[0], expected)
        self.store.close()
        self.assertEqual(self.open().get(fact['fact_id']), fact)
        with patch.dict(os.environ, {'CSTACK_MEMORY_DB': str(self.path)}):
            env = MemoryStore(clock=lambda: 123)
            self.addCleanup(env.close)
            self.assertEqual(env.get(fact['fact_id']), fact)
        with patch.dict(os.environ, {'CSTACK_MEMORY_DB': ''}):
            self.assertRaises(ContractError, MemoryStore, clock=lambda: 123)
        for call in (self.store.stats, self.store.list, lambda: self.store.get(fact['fact_id'])):
            self.assertRaises(ContractError, call)
        link = self.path.with_name('link.memory.db')
        link.symlink_to(self.path)
        self.assertRaises(ContractError, MemoryStore, link, clock=lambda: 123)

    def test_reviews_identity_labels_and_retention(self):
        self.assertEqual(FACT_KINDS, EVENT_KINDS + ('reference',))
        for i, kind in enumerate(EVENT_KINDS):
            fact, _ = self.propose(line_offset=i, kind=kind, trust=TRUST_TIERS[1 + i % 5])
            fid = fact['fact_id']
            identity = ['cstack.memory.fact/1', 'synthetic', 'thread / one', i, 0, 'assistant']
            self.assertEqual(fid, 'fact-' + digest(identity))
            self.assertEqual((fact['status'], fact['kind']), ('proposed', kind))
            fact['text'] = 'Detached read.'
            self.assertEqual(self.store.get(fid)['text'], 'Cooling inspection complete.')
            for ref in ('bad', 'A' * 64, True):
                self.assertRaises(ContractError, self.store.confirm, fid, by='reviewer', ledger_ref=ref)
            review = self.store.confirm if i % 2 else self.store.reject
            result = review(fid, by='reviewer', note='Synthetic review.', ledger_ref='a' * 64)
            self.assertEqual(result['trust_label'], 'trust:' + ('user_confirmed' if i % 2 else fact['source_trust']))
            self.assertEqual((result['decided_by'], result['decided_at'], result['ledger_ref']),
                             ('reviewer', 123, 'a' * 64))
            self.assertFalse(self.propose(line_offset=i, kind=kind, trust=fact['source_trust'])[1])
            for again in (self.store.confirm, self.store.reject):
                self.assertRaises(ContractError, again, fid, by='reviewer', note='Again.')
        self.assertEqual((len(self.store.search('cooling')), len(self.store.list(status='rejected'))), (8, 4))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store._db.execute('DELETE FROM facts')
        self.assertEqual(self.store.stats()['facts'], {'proposed': 0, 'confirmed': 4, 'rejected': 4})

    def test_validation_conflicts_and_search(self):
        fact, _ = self.propose()
        for kwargs in ({'trust': 'user_confirmed'}, {'kind': 'bad'}, {'line_offset': True},
                       {'chunk_index': -1}, {'role': ''}, {'kind': 'learning'}):
            self.assertRaises(ContractError, self.propose, **kwargs)
        for value in (True, 1.5, 2**63, -(2**63)-1):
            with patch.object(self.store, '_clock', lambda: value), self.assertRaises(ContractError):
                self.propose(line_offset=2)
        for query, expected in [('cooling', 1), ('cooling OR absent', 0), ('"* : ()', 0)]:
            self.assertEqual(len(self.store.search(query)), expected)
        self.propose('Cooling cooling inspection complete.', line_offset=1)
        ranked = self.store.search('cooling')
        self.assertLess(ranked[0]['score'], ranked[1]['score'])
        self.store.confirm(fact['fact_id'], by='reviewer')
        self.assertEqual(len(self.store.search('cooling', status='confirmed')), 1)
        for call in (lambda: self.store.list(limit=True), lambda: self.store.list(status='bad'),
                     lambda: self.store.get('bad'), lambda: self.store.reject(fact['fact_id'], by='reviewer', note='')):
            self.assertRaises(ContractError, call)
        self.store._db.execute('UPDATE schema_versions SET version=3 WHERE version=2')
        self.assertRaises(ContractError, self.open)
        self.store._db.execute('UPDATE schema_versions SET version=2 WHERE version=3')
        self.store._db.execute('DROP TRIGGER facts_no_delete')
        self.assertRaises(ContractError, self.open)

    def test_references_and_constraints(self):
        args = dict(source='catalog', path='synthetic / manual', checksum='a' * 64)
        def reference(**kwargs):
            return self.store.propose_reference('Synthetic cooling reference.', **(args | kwargs))
        fact, inserted = reference(embedding=[0.25, -1.5], ref_vec_id='vector:one')
        fid = fact['fact_id']
        self.assertEqual(fid, 'fact-' + digest(['cstack.memory.fact/1', 'catalog', args['path'], 0, 0,
                                               'reference', args['checksum']]))
        self.assertEqual((inserted, fact['embedding_dims'], self.store.embedding(fid)), (True, 2, [0.25, -1.5]))
        self.assertNotIn('embedding', fact)
        self.assertEqual(fact['ref_vec_id'], 'vector:one')
        self.assertEqual((self.open().get(fid), self.store.search('reference')[0]['embedding_dims']), (fact, 2))
        self.store.confirm(fid, by='reviewer')
        self.assertFalse(reference(embedding=(0.25, -1.5), ref_vec_id='vector:one')[1])
        changed, inserted = reference(checksum='b' * 64, ref_vec_id='vector:two')
        self.assertEqual((inserted, changed['embedding_dims'], self.store.embedding(changed['fact_id'])), (True, None, None))
        self.assertEqual(self.store.get(fid)['status'], 'confirmed')
        self.store.reject(changed['fact_id'], by='reviewer', note='Synthetic review.')
        for kwargs in ({'checksum': 'A' * 64}, {'checksum': 'bad'}, {'embedding': []},
                       {'embedding': [0.0] * 4097}, {'embedding': [True]}, {'embedding': [float('nan')]},
                       {'embedding': [float('inf')]}, {'embedding': [1e300]}, {'ref_vec_id': ''}):
            self.assertRaises(ContractError, reference, **kwargs)
        self.assertRaises(ContractError, self.propose, kind='reference')
        ordinary, _ = self.propose()
        values = {k: v for k, v in ordinary.items() if k not in ('trust_label', 'embedding_dims')}
        for extra in ({'ref_source': 'catalog'}, {'ref_path': 'manual'}, {'ref_sha256': 'a' * 64},
                      {'embedding': b'1234'}, {'ref_vec_id': 'vector:one'}, {'kind': 'reference'},
                      *({'kind': 'reference', 'ref_source': 'catalog', 'ref_path': 'manual',
                         'ref_sha256': checksum, 'embedding': blob}
                        for checksum, blob in [('bad', None), ('a' * 64, b'1'), ('a' * 64, b''),
                                               ('a' * 64, b'0' * 16388)])):
            row = values | dict(fact_id='fact-' + 'c' * 64, line_offset=99) | extra
            with self.assertRaises(sqlite3.IntegrityError):
                self.store._db.execute('INSERT INTO facts (' + ','.join(row) + ') VALUES (' +
                                       ','.join('?' for _ in row) + ')', tuple(row.values()))

"""Synthetic fixtures and fake secrets are assembled only in temporary storage."""
import gzip
import json
import os
import sqlite3
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adapters.memory import MemoryStore, redact as screening
from adapters.memory.ingest import ingest_archive
from adapters.memory.store import _SCHEMA
from adapters.memory.nrm_wall import Wall
from poodo_core.models import ContractError

CUE = 'We decided to inspect ' + 'the cooling valve daily.'
def msg(text, role='assistant', **kw):
    return dict(text=text, role=role, ts='2026-10-25T00:00:00Z', **kw)
def thread(tid, msgs, **kw):
    return dict(thread_id=tid, msgs=msgs, **kw)

class MemoryIngestTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root / 'threads').mkdir()
        self.store = MemoryStore(self.root / 'test.memory.db', clock=lambda: 123)
        self.addCleanup(self.store.close)

    def archive(self, name, records):
        with gzip.open(self.root / 'threads' / (name + '.jsonl.gz'), 'wb') as out:
            for record in records:
                out.write((record if isinstance(record, bytes) else json.dumps(record).encode()) + b'\n')

    def assert_absent(self, values):
        for path in self.root.glob('test.memory.db*'):
            for value in values:
                self.assertFalse(value.encode() in path.read_bytes(), value)

    def canary(self, records, forbidden):
        self.archive('alpha', records + [thread('control', [msg(CUE)])])
        receipt = ingest_archive(self.store, self.root)
        self.assertEqual((receipt['nrm_wall'], receipt['facts_added']), (len(records), 1))
        self.assert_absent(forbidden + [t['thread_id'] for t in records])

    def test_nrm_canary(self):
        terms = ['Partner'+'One', 'Partner'+'Two', 'Partner'+'Three', 'Partner '+'Four', 'Partner'+'Forge', 'Partner'+'Five']
        extra = 'Synthetic'+'Customer'
        deny = self.root / 'deny.txt'
        deny.write_text('# synthetic\n' + extra)
        records = [thread('drop'+str(i), [msg(CUE)], project=t) for i, t in enumerate(terms)]
        records += [thread('joined', [msg(CUE)], project=terms[0]+'_'+terms[2]),
                    thread('mixed', [msg(CUE)], path='/x/'+terms[3].replace(' ', '-_./')+'/'),
                    thread('nested', [msg(CUE), msg({'inner': [terms[2]]}, 'tool_result')]),
                    thread('extra', [msg(CUE+' '+extra)]), thread('lower', [msg(terms[4].lower())])]
        with patch.dict(os.environ, {'CSTACK_MEMORY_DENYLIST': str(deny)}):
            self.canary(records, terms+[extra, terms[4].lower()])
        for value in ('', str(deny)+'missing'):
            with patch.dict(os.environ, {'CSTACK_MEMORY_DENYLIST': value}):
                self.assertRaises(OSError, Wall.from_env)

    def test_private_search_canary(self):
        term = 'private'+'-'+'search'
        path = '/workspace/'+'private'+'-ops/'+term+'/'
        self.canary([thread('pathdrop', [msg(CUE)], source_root=path, path=path+'a'),
                     thread('textdrop', [msg(CUE+' '+path)])], [term, path])

    def test_planted_secret_canary(self):
        secrets = ['s'+'k-proj-'+'x'*35, 'gh'+'p_'+'x'*35, 'AK'+'IA'+'X'*16]
        self.archive('alpha', [thread('safe', [msg(CUE.rstrip('.')+' using '+v) for v in secrets]), thread(secrets[0], [msg(CUE)])])
        receipt = ingest_archive(self.store, self.root)
        self.assertEqual((receipt['redactions'], receipt['secret_residue'], receipt['facts_added']), (3, 1, 3))
        self.assertTrue(all('[REDACTED:' in f['text'] for f in self.store.list()))
        self.assert_absent(secrets)
        with patch.object(screening, '_SUBSTITUTIONS', ()):
            self.assertIsNone(screening.redact(secrets[0])[0])

    def test_standalone(self):
        for name in ('redact', 'nrm_wall'):
            tree = ast.parse(Path('adapters/memory', name+'.py').read_text())
            imports = [n.module if isinstance(n, ast.ImportFrom) else n.names[0].name
                       for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            self.assertTrue(set(imports) <= {'re', 'os', 'pathlib', 'collections.abc'})
        for func in (screening.redact, screening.has_secret):
            self.assertRaises(TypeError, func, None)

    def test_archive(self):
        root, store = self.root, self.store
        self.archive('alpha', [thread('p1:agent-a1', [msg(CUE, 'user'), msg(CUE.upper()),
            msg('The compressor runs on a synthetic test controller.'),
            msg('We must discard this tool narrative entirely.', 'tool_call')]),
            thread('fenced', [msg('```python\n'+CUE+'\n```\n- '+CUE)]),
            b'bad', b'\xff', [], {'thread_id': 'missing'},
            thread('cap', [msg('\n'.join(f'We must inspect synthetic valve {i} daily.' for i in range(30)))])])
        self.archive('beta', [thread('ops', [msg('## The default is a synthetic operations profile.', 'USER'),
                                           msg('Remember to check the synthetic cooling gauge.')])])
        receipt = ingest_archive(store, root)
        self.assertEqual([receipt[k] for k in ('files', 'facts_added', 'unparseable')], [2, 30, 4])
        facts = store.list()
        self.assertEqual(sum(f['thread_id'] == 'cap' for f in facts), 25)
        sub = [f for f in facts if f['thread_id'] == 'p1:agent-a1']
        self.assertEqual({f['parent_thread_id'] for f in sub}, {'p1'})
        self.assertEqual({f['source_ts'] for f in sub}, {'2026-10-25T00:00:00Z'})
        self.assertEqual({f['trust'] for f in sub}, {'unknown', 'agent_written'})
        self.assertEqual({f['status'] for f in facts}, {'proposed'})
        self.assertEqual(store.search('narrative'), [])
        fid = facts[0]['fact_id']
        store.confirm(fid, by='reviewer')
        retry = ingest_archive(store, root)
        self.assertEqual((retry['facts_added'], retry['duplicates'], store.get(fid)['status']), (0, 30, 'confirmed'))
        before = store.stats()
        self.archive('aaa', [thread('new', [msg(CUE)])])
        (root / 'threads' / 'zzz.jsonl.gz').write_bytes(b'corrupt')
        self.assertRaises(ContractError, ingest_archive, store, root)
        self.assertEqual(store.stats(), before)
        store.close()
        dbpath = root / 'test.memory.db'
        dbpath.unlink()
        with sqlite3.connect(dbpath) as db:
            db.executescript(_SCHEMA.replace('VALUES (1, ?)', 'VALUES (1, 123)'))
        db.close()
        dbpath.chmod(0o600)
        for _ in range(2):
            upgraded = MemoryStore(dbpath, clock=lambda: 456)
            self.assertEqual([r[0] for r in upgraded._db.execute('SELECT version FROM schema_versions')], [1, 2])
            upgraded.close()

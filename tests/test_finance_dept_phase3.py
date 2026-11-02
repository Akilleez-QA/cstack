"""Phase 3 tests: invented data only; no network or financial actions."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from products.finance_dept.__main__ import main
from products.finance_dept.core import SCHEMAS, json_text
from products.finance_dept.phase3 import collections, monthly_close

FIXTURES = Path(__file__).parent / 'fixtures' / 'finance_dept_phase3'


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        shutil.copytree(FIXTURES, self.directory, dirs_exist_ok=True)

    def edit(self, name, change):
        path = self.directory / name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def close(self, month='2026-02'):
        return monthly_close(self.directory, month, self.directory / 'export')

    def test_interest_penalty_rank_and_drafts(self):
        result = collections(self.directory, date(2026, 2, 1))
        tax = result['items'][0]
        self.assertEqual(tax['interest_estimate'], D('6.20'))
        self.assertEqual(tax['penalty_estimate'], D('5.00'))
        self.assertEqual(tax['exposure'], D('1011.20'))
        self.assertEqual([r['id'] for r in result['items']], ['tax-example','invoice-example','sale-example'])
        self.assertEqual(result['items'][-1]['exposure'], D('0'))
        self.assertTrue(all(r['requires_approval'] and r['draft_next_step'] for r in result['items']))

    def test_month_boundaries_cap_future_missing_rate(self):
        for day, months in [(date(2026,1,1),0),(date(2026,1,2),1),(date(2026,2,1),1),(date(2026,2,2),2)]:
            tax = collections(self.directory, day)['items'][0]
            self.assertEqual(tax['penalty_months'], months)
        self.assertEqual(collections(self.directory, date(2031,1,1))['items'][0]['penalty_estimate'], D('250'))
        self.edit('collections.json', lambda rows: rows[0].pop('annual_rate'))
        tax = collections(self.directory, date(2025,12,1))['items'][0]
        self.assertEqual(tax['interest_estimate'], D('0'))
        self.assertEqual(tax['penalty_estimate'], D('0'))
        self.assertTrue(tax['missing_annual_rate'])

    def test_close_balances_categories_and_diff(self):
        report = self.close()
        self.assertEqual(report['accounts'][0]['opening'], D('1000'))
        self.assertEqual(report['accounts'][0]['closing'], D('1200'))
        self.assertEqual(report['accounts'][0]['reconciliation_diff'], D('0'))
        self.assertEqual(len(report['uncategorized']), 1)
        self.assertEqual(next(r for r in report['categories'] if r['category'] == 'Work')['income'], D('300'))
        self.edit('accounts.json', lambda rows: rows[0].update(balance='1201.00'))
        self.assertEqual(self.close()['accounts'][0]['reconciliation_diff'], D('-1'))
        self.edit('accounts.json', lambda rows: rows[0].update(as_of='2026-02-01'))
        self.assertIsNone(self.close()['accounts'][0]['reconciliation_diff'])

    def test_unknown_accounts_and_month_filter(self):
        self.edit('export/export.json', lambda v: v['transactions'].extend([
            dict(date='2026-02-10',amount='10',description='Synthetic unknown',account_id='unknown'),
            dict(date='2026-03-01',amount='900',description='Synthetic next month',account_id='cash')]))
        report = self.close()
        self.assertEqual(len(report['unmatched']),1)
        self.assertEqual(report['accounts'][0]['closing'],D('1200'))
        self.edit('export/export.json', lambda v: v['transactions'].clear())
        self.assertEqual(self.close()['accounts'][0]['closing'],D('1000'))

    def test_invalid_exports_and_privacy(self):
        original = (self.directory/'export/export.json').read_text()
        for changes in [dict(amount='0.001'), dict(amount='NaN'),dict(date='2026-02-30'),dict(description='1234567890123456'),dict(token='fake')]:
            (self.directory/'export/export.json').write_text(original)
            self.edit('export/export.json',lambda v: v['transactions'][0].update(changes))
            with self.assertRaises(ValueError): self.close()
        (self.directory/'export/export.json').write_text(original)
        self.edit('export/export.json', lambda v: v['accounts'][0].update(as_of='2026-01-31'))
        with self.assertRaises(ValueError): self.close()
        for month in ['2026-13','2026-2','bad']:
            with self.assertRaises(ValueError): self.close(month)

    def test_invalid_collections(self):
        original = (self.directory/'collections.json').read_text()
        for changes in [dict(principal='-1'),dict(principal='0.001'),dict(annual_rate='NaN'),dict(kind='other'),dict(start_date='bad')]:
            (self.directory/'collections.json').write_text(original)
            self.edit('collections.json', lambda rows: rows[0].update(changes))
            with self.assertRaises(ValueError): collections(self.directory,date(2026,2,1))

    def test_duplicates_and_leap_month(self):
        self.edit('collections.json', lambda rows: rows.append(dict(rows[0])))
        with self.assertRaises(ValueError): collections(self.directory, date(2026,2,1))
        self.edit('export/export.json', lambda v: v['transactions'].append(dict(v['transactions'][0])))
        with self.assertRaises(ValueError): self.close()
        self.edit('export/export.json', lambda v: (v['transactions'].clear(), v['accounts'][0].update(as_of='2024-02-01')))
        self.edit('accounts.json', lambda rows: rows[0].update(as_of='2024-02-29',balance='1000.00'))
        report = self.close('2024-02')
        self.assertEqual(report['accounts'][0]['reconciliation_diff'],D('0'))
        self.assertEqual(report['actions'],[])
        self.assertEqual(main(['close','--data-dir',str(self.directory),'--month','2024-02','--export',str(self.directory/'export')]),0)

    def test_output_contracts_cli_and_determinism(self):
        for name, value in [('collections_report', collections(self.directory,date(2026,2,1))),('monthly_close',self.close())]:
            validator = Draft202012Validator(json.loads((SCHEMAS/f'{name}.schema.json').read_text()),format_checker=FormatChecker())
            validator.validate(json.loads(json_text(value)))
        for cmd, extra, name in [('collections',[],'collections'),('close',['--month','2026-02','--export',str(self.directory/'export')],'close_2026-02')]:
            args=[cmd,'--data-dir',str(self.directory),'--today','2026-02-01',*extra]
            self.assertEqual(main(args),3)
            path=self.directory/'out'/f'{name}.json'
            before=path.read_bytes()
            self.assertEqual(main(args),3)
            self.assertEqual(path.read_bytes(),before)
            self.assertIn('Draft', (self.directory/'out'/f'{name}.md').read_text())
        self.assertEqual(main(['close','--data-dir',str(self.directory)]),2)

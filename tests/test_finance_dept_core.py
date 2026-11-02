"""Synthetic-only coverage for finance validation and projection."""
import copy
import json
import shutil
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from products.finance_dept.core import build_reports, load_inputs, reject_secrets, markdown

FIXTURES = Path(__file__).parent / 'fixtures' / 'finance_dept'


class FinanceCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        shutil.copytree(FIXTURES, self.directory, dirs_exist_ok=True)
        self.data = load_inputs(self.directory)

    def report(self, today='2026-02-01', weeks=6):
        return build_reports(self.data, date.fromisoformat(today), weeks)

    def test_rollover_and_autopay_shutoff(self):
        report = self.report()
        occurrence = report['bill_calendar']['occurrences'][0]
        self.assertEqual(occurrence['date'], '2026-02-28')
        self.assertEqual(occurrence['conflicts'], ['two_payment_paths', 'autopay_insufficient_funds', 'after_shutoff'])
        flags = report['cashflow']['days'][27]['accounts']['wallet']['flags']
        self.assertEqual(flags, ['below_floor', 'overdraft'])
        risk = next(r for r in report['cashflow']['risks'] if r['type'] == 'overdraft')
        self.assertEqual(risk['overdraft_fee'], Decimal('0.00'))
        self.assertTrue(all(a['requires_approval'] is True for a in report['daily']['actions']))

    def test_weekly_prior_evening(self):
        days = self.report(weeks=1)['cashflow']['days']
        self.assertEqual(days[2]['date'], '2026-02-03')
        self.assertEqual(days[2]['accounts']['checking']['income'], Decimal('100.00'))
        self.assertEqual(days[3]['accounts']['checking']['income'], Decimal('0.00'))

    def test_monthly_yearly_weekly_and_once(self):
        base = self.data['bills'][0]
        self.data['bills'] = [dict(base, id=cadence, cadence=cadence, due_date='2024-02-29') for cadence in ['yearly', 'once', 'weekly']]
        for bill in self.data['bills']:
            del bill['due_day']
        occurrences = self.report('2026-02-22', 2)['bill_calendar']['occurrences']
        self.assertIn(('yearly', '2026-02-28'), [(o['bill_id'], o['date']) for o in occurrences])
        self.assertEqual(sum(o['bill_id'] == 'weekly' for o in occurrences), 2)
        self.assertFalse(any(o['bill_id'] == 'once' for o in occurrences))

    def test_decimal_and_transfers(self):
        self.data['accounts'][0]['balance'] = Decimal('0.10')
        self.data['bills'] = []
        self.data['income'][0].update(amount=Decimal('0.20'), weekday=6, lands='same_day')
        self.data['transfers'] = [dict(date='2026-02-01', **{'from': 'checking', 'to': 'wallet'}, amount=Decimal('0.10'), status='planned')]
        row = self.report(weeks=1)['cashflow']['days'][0]['accounts']
        self.assertEqual(row['checking']['closing'], Decimal('0.20'))
        self.assertEqual(row['wallet']['closing'], Decimal('0.10'))
        self.data['transfers'][0]['status'] = 'done'
        self.assertEqual(self.report(weeks=1)['cashflow']['days'][0]['accounts']['wallet']['closing'], Decimal('0.00'))

    def test_biweekly_anchor(self):
        self.data['income'][0].update(cadence='biweekly', start_date='2026-02-04')
        days = self.report(weeks=4)['cashflow']['days']
        self.assertEqual([d['date'] for d in days if d['accounts']['checking']['income']], ['2026-02-03', '2026-02-17'])

    def test_ledger_debt_and_brokerage(self):
        self.data['accounts'] += [dict(id='loan', name='Example loan', kind='loan', last4='0003', balance=Decimal('200.00'), as_of='2026-02-01'), dict(id='invest', name='Example fund', kind='brokerage', last4='0004', balance=Decimal('300.00'), as_of='2026-02-01')]
        self.assertEqual(self.report()['ledger']['totals'], dict(cash=Decimal('100'), debt=Decimal('200'), net_worth=Decimal('200')))

    def test_credit_card_charges_increase_debt(self):
        self.data['accounts'][1].update(kind='credit_card', balance=Decimal('100.00'), credit_limit=Decimal('1000.00'))
        self.data['bills'][0].update(due_day=1)
        report = self.report(weeks=1)
        self.assertNotIn('autopay_insufficient_funds', report['bill_calendar']['occurrences'][0]['conflicts'])
        self.assertEqual(report['cashflow']['days'][0]['accounts']['wallet']['closing'], Decimal('300.00'))

    def test_floor_fee_and_month_boundary_income(self):
        self.data['bills'] = []
        self.data['income'][0].update(cadence='monthly', day=1, lands='prior_evening')
        self.data['accounts'][0]['balance'] = Decimal('-10.00')
        report = self.report('2026-01-31', 1)
        self.assertEqual(report['cashflow']['days'][0]['accounts']['checking']['income'], Decimal('100.00'))
        self.data['income'] = []
        report = self.report(weeks=1)
        self.assertEqual(report['cashflow']['days'][0]['accounts']['checking']['flags'], ['below_floor', 'overdraft'])
        risk = next(r for r in report['cashflow']['risks'] if r['type'] == 'overdraft')
        self.assertEqual(risk['overdraft_fee'], Decimal('20.00'))

    def test_per_debit_fees_and_cashflow_table(self):
        self.data['income'] = []
        self.data['accounts'][0].update(balance=Decimal('10'), overdraft_fee=Decimal('20'))
        self.data['bills'] = [dict(id='one', payee='Synthetic bill', amount=Decimal('5'), cadence='once', due_date='2026-02-01', pay_from='checking', autopay='off')]
        self.data['transfers'] = [dict(date='2026-02-01', **{'from': 'checking', 'to': 'wallet'}, amount=Decimal('15'), status='planned')]
        report = self.report(weeks=1)
        rows = report['cashflow']['days']
        self.assertEqual(rows[0]['accounts']['checking']['fees'], Decimal('40'))
        self.assertEqual(rows[0]['accounts']['checking']['closing'], Decimal('-50'))
        self.assertEqual(rows[1]['accounts']['checking']['fees'], Decimal('0'))
        self.assertEqual(rows[1]['accounts']['checking']['closing'], Decimal('-50'))
        self.assertEqual([f['debit_type'] for f in report['cashflow']['fee_lines']], ['transfer', 'bill'])
        table = markdown('cashflow', report['cashflow'])
        self.assertIn('| Date | Opening | In | Transfers | Bills | Fees | Closing | Flags |', table)
        self.assertIn('| 2026-02-01 | 10.00 | 0.00 | -15.00 | 5.00 | 40.00 | -50.00 |', table)
        self.assertNotIn('```json', table)

    def test_actions_rank_money_and_put_snapshot_notices_last(self):
        self.data['income'] = []
        self.data['accounts'][0].update(balance=Decimal('10'), as_of='2026-01-01')
        base = dict(payee='Synthetic bill', cadence='once', pay_from='checking', autopay='on')
        self.data['bills'] = [dict(base, id='small', amount=Decimal('5'), due_date='2026-02-01', autopay_source='wallet'), dict(base, id='large', amount=Decimal('300'), due_date='2026-02-02', shutoff_date='2026-02-01')]
        report = self.report(weeks=1)
        actions = report['daily']['actions']
        self.assertEqual(len(actions), 3)
        self.assertEqual([a['money_at_risk'] for a in actions], sorted([a['money_at_risk'] for a in actions], reverse=True))
        self.assertTrue(any('shutoff' in a['action'] for a in actions))
        self.assertTrue(all('snapshot_date' not in a['action'] for a in actions))
        self.assertEqual(report['daily']['risks'][-1]['type'], 'snapshot_date')
        self.data['bills'] = []
        self.assertIn('snapshot_date', self.report(weeks=1)['daily']['actions'][0]['action'])

    def test_secret_rejection(self):
        for value in [{'Password': 'example'}, {'nested': [{'cvv': '000'}]}, {'notes': '1234567890123456'}, {'notes': 'example', 'dob': '2000-01-01'}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                reject_secrets(value)

    def test_invalid_inputs(self):
        original = json.loads((FIXTURES / 'accounts.json').read_text())
        for change in [dict(balance='0.001'), dict(balance=0.001), dict(balance='NaN'), dict(last4='1234567890123456'), dict(password='example'), dict(as_of='2026-02-30')]:
            rows = copy.deepcopy(original)
            rows[0].update(change)
            (self.directory / 'accounts.json').write_text(json.dumps(rows))
            with self.subTest(change=change), self.assertRaises(ValueError):
                load_inputs(self.directory)

    def test_unknown_reference_and_duplicates(self):
        bills = json.loads((self.directory / 'bills.json').read_text())
        bills[0]['pay_from'] = 'missing'
        (self.directory / 'bills.json').write_text(json.dumps(bills))
        with self.assertRaises(ValueError):
            load_inputs(self.directory)
        shutil.copy(FIXTURES / 'bills.json', self.directory / 'bills.json')
        accounts = json.loads((self.directory / 'accounts.json').read_text())
        accounts.append(accounts[0])
        (self.directory / 'accounts.json').write_text(json.dumps(accounts))
        with self.assertRaises(ValueError):
            load_inputs(self.directory)

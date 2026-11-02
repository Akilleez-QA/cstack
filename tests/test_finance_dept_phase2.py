"""Phase 2 uses synthetic accounts and transactions only."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from products.finance_dept.core import SCHEMAS, build_reports, json_text, load_inputs
from products.finance_dept.phase2 import debt_plan, subscriptions

TODAY = date(2026, 2, 1)
FIXTURES = Path(__file__).parent / 'fixtures' / 'finance_dept'


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        shutil.copytree(FIXTURES, self.directory, dirs_exist_ok=True)
        self.data = load_inputs(self.directory)

    def test_avalanche_interest_payoff(self):
        self.data['accounts'] = [dict(id='low', kind='loan', balance=D('100'), apr=D('0'), min_payment=D('10')), dict(id='high', kind='credit_card', balance=D('100'), apr=D('12'), min_payment=D('10'))]
        report = debt_plan(self.data, TODAY, D('20'))
        self.assertEqual(report['avalanche_order'], ['high', 'low'])
        self.assertEqual(report['total_monthly_interest'], D('1.00'))
        self.assertEqual(report['months_at_minimum'], 11)
        self.assertEqual(report['months_with_extra'], 6)
        self.assertEqual(report['debts'][0]['months_with_extra'], 4)
        self.assertTrue(all(r['requires_approval'] for r in report['debts']))

    def test_non_amortizing_and_missing_terms(self):
        self.data['accounts'] = [dict(id='loan', kind='loan', balance=D('100'), apr=D('24'), min_payment=D('1'))]
        self.assertIsNone(debt_plan(self.data, TODAY, D('0'))['months_at_minimum'])
        self.assertIsNotNone(debt_plan(self.data, TODAY, D('10'))['months_with_extra'])
        self.data['accounts'][0].pop('min_payment')
        self.assertEqual(debt_plan(self.data, TODAY, D('0'))['debts'][0]['missing_terms'], ['min_payment'])
        self.data['accounts'] = []
        self.assertEqual(debt_plan(self.data, TODAY, D('0'))['months_at_minimum'], 0)

    def sub(self, **changes):
        return dict(dict(id='video', payee='Example Video', amount='10.00', cadence='monthly', next_renewal='2026-02-15', account='checking'), **changes)

    def test_subscriptions_boundaries_duplicates_and_keep(self):
        a = self.sub(); a['last_used'] = '2025-12-03'  # exactly 60 days
        b = self.sub(); b.update(id='second', payee=' EXAMPLE-video ', keep=True)
        c = self.sub(); c.update(id='old', payee='Example Music', last_used='2025-12-02', next_renewal='2026-02-16')
        d = self.sub(); d.update(id='missing', payee='Example Book', next_renewal='2026-01-31')
        self.data['subscriptions'] = [a, b, c, d]
        rows = subscriptions(self.data, TODAY)['recommendations']
        self.assertEqual([r['id'] for r in rows], ['video', 'old', 'missing'])
        self.assertEqual(rows[0]['flags'], ['duplicate', 'renewal_soon'])
        self.assertEqual(rows[1]['flags'], ['unused'])
        self.assertEqual(rows[2]['flags'], ['unused'])
        self.assertTrue(all(r['requires_approval'] for r in rows))

    def test_optional_transaction_files_and_validation(self):
        (self.directory / 'subscriptions.json').write_text(json.dumps([self.sub()]))
        folder = self.directory / 'transactions'; folder.mkdir()
        (folder / 'one.csv').write_text('date,payee,amount,account\n2026-01-30,EXAMPLE VIDEO,10.00,checking\n')
        (folder / 'two.json').write_text('[{"date":"2026-01-29","payee":"Example Video","amount":"10.00","account":"checking"}]')
        data = load_inputs(self.directory)
        row = subscriptions(data, TODAY)['recommendations'][0]
        self.assertEqual(len(row['matching_transactions']), 2)
        self.assertIn('unused', row['flags'])  # payment is not proof of usage
        for bad in ['[{"token":"fake"}]', '[{"date":"bad"}]']:
            (folder / 'two.json').write_text(bad)
            with self.assertRaises(ValueError):
                load_inputs(self.directory)

    def guard_data(self):
        self.data['accounts'][0].update(balance=D('50'), floor=D('20'), overdraft_fee=D('25'))
        self.data['bills'] = [dict(id='bill', payee='Example bill', amount=D('80'), due_date='2026-02-01', cadence='once', pay_from='checking', autopay='off', grace_days=2)]
        self.data['income'] = [dict(id='pay', source='Example payroll', amount=D('100'), cadence='weekly', weekday=1, deposit_to='checking', lands='same_day')]
        return self.data

    def test_guard_retiming_and_fee(self):
        report = build_reports(self.guard_data(), TODAY, 1)['overdraft_guard']
        self.assertEqual(len(report['risk_days']), 2)
        self.assertEqual(report['total_fee_saved'], D('25'))
        move = report['recommendations'][0]
        self.assertEqual(move['suggested_date'], '2026-02-03')
        self.assertTrue(move['requires_approval'])

    def test_guard_deadlines_shutoff_and_insufficient_income(self):
        data = self.guard_data()
        for change in [dict(grace_days=1), dict(shutoff_date='2026-02-04')]:
            original = dict(data['bills'][0]); data['bills'][0].update(change)
            self.assertEqual(build_reports(data, TODAY, 1)['overdraft_guard']['recommendations'], [])
            data['bills'][0] = original
        data['income'][0]['amount'] = D('10')
        self.assertEqual(build_reports(data, TODAY, 1)['overdraft_guard']['recommendations'], [])

    def test_guard_floor_only_and_combined_savings(self):
        data = self.guard_data()
        data['bills'][0]['amount'] = D('40')
        guard = build_reports(data, TODAY, 1)['overdraft_guard']
        self.assertEqual(len(guard['recommendations']), 1)
        self.assertEqual(guard['total_fee_saved'], D('0'))
        data['bills'][0]['amount'] = D('80')
        data['bills'].append(dict(data['bills'][0], id='bill2', amount=D('10')))
        guard = build_reports(data, TODAY, 1)['overdraft_guard']
        self.assertEqual(len(guard['recommendations']), 1)
        self.assertEqual(guard['total_fee_saved'], D('50'))

    def test_bad_transaction_csv(self):
        folder = self.directory / 'transactions'; folder.mkdir()
        for raw in ['date,payee,amount,account\n2026-01-30,Example,10.00,checking,extra\n',
                    'date,payee,amount,account\n2026-01-30,Example,0.001,checking\n',
                    'date,payee,amount,account\n2026-01-30,1234567890123456,10.00,checking\n']:
            (folder / 'bad.csv').write_text(raw)
            with self.assertRaises(ValueError):
                load_inputs(self.directory)

    def test_output_schemas_and_extra_validation(self):
        data = self.guard_data()
        data['subscriptions'] = [self.sub()]
        reports = build_reports(data, TODAY, 1)
        for name, schema_name in [('debt_plan', 'debt_plan'), ('subscriptions', 'subscriptions_report'), ('overdraft_guard', 'overdraft_guard')]:
            schema = json.loads((SCHEMAS / (schema_name + '.schema.json')).read_text())
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(json.loads(json_text(reports[name])))
        for extra in ['-1', 'NaN', '0.001']:
            with self.assertRaises(ValueError):
                build_reports(data, TODAY, 1, extra)

    def test_invalid_subscription_inputs(self):
        for changes in [dict(amount='0.001'), dict(account='unknown'), dict(keep='true'), dict(next_renewal='2026-02-30'), dict(password='fake')]:
            row = self.sub(); row.update(changes)
            (self.directory / 'subscriptions.json').write_text(json.dumps([row]))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                load_inputs(self.directory)

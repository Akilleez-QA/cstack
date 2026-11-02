"""Validation and deterministic, offline projection calculations."""
import calendar
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = Path(__file__).resolve().parents[2] / 'schemas' / 'finance_dept'
MONEY = {'balance', 'amount', 'apr', 'credit_limit', 'min_payment', 'floor', 'overdraft_fee', 'late_fee'}
ZERO = Decimal('0.00')


def reject_secrets(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if re.search(r'password|token|ssn|dob|cvv', key, re.I):
                raise ValueError('Forbidden secret field')
            reject_secrets(key)
            reject_secrets(child)
    elif isinstance(value, list):
        for child in value:
            reject_secrets(child)
    elif re.search(r'\d{13,19}', str(value)):
        raise ValueError('Forbidden long digit run')


def load_inputs(directory):
    result = {}
    for name in ('accounts', 'bills', 'income', 'transfers', 'collections'):
        path = Path(directory) / f'{name}.json'
        if not path.exists() and name in ('transfers', 'collections'):
            result[name] = []
            continue
        # Check raw text too, before parsing can erase numeric digit runs.
        raw = path.read_text()
        if re.search(r'\d{13,19}', raw):
            raise ValueError('Forbidden long digit run')
        data = json.loads(raw, parse_float=Decimal, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
        reject_secrets(data)
        schema = json.loads((SCHEMAS / f'{name}.schema.json').read_text())
        if next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), None):
            raise ValueError(f'Invalid {name} input')
        ids = set()
        for row in data:
            if 'id' in row:
                if row['id'] in ids:
                    raise ValueError(f'Duplicate {name} id')
                ids.add(row['id'])
            for key in MONEY & row.keys():
                try:
                    amount = Decimal(str(row[key]))
                    if not amount.is_finite() or amount != amount.quantize(Decimal('.01')):
                        raise ValueError('Money must be cents-exact')
                    if key != 'balance' and amount < 0:
                        raise ValueError('Negative amount')
                    row[key] = amount.quantize(Decimal('.01'))
                except InvalidOperation:
                    raise ValueError('Invalid money') from None
        result[name] = data
    accounts = {a['id'] for a in result['accounts']}
    for name, fields in [('bills', ('pay_from', 'autopay_source')), ('income', ('deposit_to',)), ('transfers', ('from', 'to'))]:
        for row in result[name]:
            if any(row[f] not in accounts for f in fields if f in row):
                raise ValueError('Unknown account reference')
    for row in result['income']:
        if row['cadence'] == 'biweekly' and date.fromisoformat(row['start_date']).weekday() != row['weekday']:
            raise ValueError('Biweekly anchor must match weekday')
    return result


def clamped(year, month, day):
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def bill_due(bill, day):
    anchor = date.fromisoformat(bill['due_date']) if 'due_date' in bill else None
    cadence = bill['cadence']
    if anchor and day < anchor:
        return False
    if cadence == 'once':
        return day == anchor
    if cadence == 'weekly':
        return anchor is not None and (day - anchor).days % 7 == 0
    if cadence == 'yearly':
        return anchor is not None and day == clamped(day.year, anchor.month, anchor.day)
    return day == clamped(day.year, day.month, bill.get('due_day', anchor.day if anchor else 1))


def income_due(row, day):
    nominal = day + timedelta(days=row['lands'] == 'prior_evening')
    if row['cadence'] == 'monthly':
        return nominal == clamped(nominal.year, nominal.month, row['day'])
    if nominal.weekday() != row['weekday']:
        return False
    if row['cadence'] == 'biweekly':
        delta = (nominal - date.fromisoformat(row['start_date'])).days
        return delta >= 0 and delta % 14 == 0
    return True


def build_reports(data, today, weeks=6):
    if weeks <= 0:
        raise ValueError('weeks must be positive')
    accounts = {a['id']: a for a in data['accounts']}
    balances = {key: row['balance'] for key, row in accounts.items()}
    debt_kinds = {'credit_card', 'loan'}
    cash = sum((a['balance'] for a in accounts.values() if a['kind'] in {'checking', 'wallet'}), ZERO)
    debt = sum((a['balance'] for a in accounts.values() if a['kind'] in debt_kinds), ZERO)
    assets = sum((a['balance'] for a in accounts.values() if a['kind'] not in debt_kinds), ZERO)
    warnings = [{'type': 'snapshot_date', 'account': a['id'], 'as_of': a['as_of']} for a in accounts.values() if a['as_of'] != today.isoformat()]
    ledger = dict(accounts=data['accounts'], totals=dict(cash=cash, debt=debt, net_worth=assets-debt), warnings=warnings)
    occurrences, days, risks = [], [], list(warnings)
    for offset in range(weeks * 7):
        day = today + timedelta(days=offset)
        stamp = day.isoformat()
        rows = {key: dict(opening=value, income=ZERO, transfers=ZERO, bills=ZERO) for key, value in balances.items()}
        for income in data['income']:
            if income_due(income, day):
                rows[income['deposit_to']]['income'] += income['amount']
        for transfer in data['transfers']:
            if transfer['date'] == stamp and transfer['status'] == 'planned':
                rows[transfer['from']]['transfers'] -= transfer['amount']
                rows[transfer['to']]['transfers'] += transfer['amount']
        for key, row in rows.items():
            direction = -1 if accounts[key]['kind'] in debt_kinds else 1
            balances[key] += direction * (row['income'] + row['transfers'])
        for bill in data['bills']:
            if not bill_due(bill, day):
                continue
            source = bill.get('autopay_source', bill['pay_from']) if bill['autopay'] == 'on' else bill['pay_from']
            conflicts = []
            if bill['autopay'] == 'on' and source != bill['pay_from']:
                conflicts.append('two_payment_paths')
            available = balances[source]
            if accounts[source]['kind'] in debt_kinds:
                available = accounts[source].get('credit_limit', ZERO) - balances[source]
            if bill['autopay'] == 'on' and available < bill['amount']:
                conflicts.append('autopay_insufficient_funds')
            if bill.get('shutoff_date', stamp) < stamp:
                conflicts.append('after_shutoff')
            occurrence = dict(date=stamp, bill_id=bill['id'], payee=bill['payee'], amount=bill['amount'], pay_from=source, autopay=bill['autopay'], conflicts=conflicts)
            occurrences.append(occurrence)
            for conflict in conflicts:
                risks.append(dict(type=conflict, date=stamp, bill_id=bill['id'], account=source))
            rows[source]['bills'] += bill['amount']
            balances[source] += bill['amount'] if accounts[source]['kind'] in debt_kinds else -bill['amount']
        for key, row in rows.items():
            row['closing'] = balances[key]
            row['flags'] = []
            if accounts[key]['kind'] not in debt_kinds:
                for flag, threshold in [('below_floor', accounts[key].get('floor', ZERO)), ('overdraft', ZERO)]:
                    if balances[key] < threshold:
                        row['flags'].append(flag)
                        risk = dict(type=flag, date=stamp, account=key)
                        if flag == 'overdraft':
                            risk['overdraft_fee'] = accounts[key].get('overdraft_fee', ZERO)
                        risks.append(risk)
        days.append(dict(date=stamp, accounts=rows))
    actions = []
    for risk in risks:
        action = dict(action=f"Review {risk['type']} for {risk.get('bill_id', risk.get('account', 'account'))}", requires_approval=True)
        if action not in actions and len(actions) < 3:
            actions.append(action)
    return dict(ledger=ledger, bill_calendar=dict(occurrences=occurrences), cashflow=dict(days=days, risks=risks), daily=dict(date=today.isoformat(), cash=cash, due_next_7_days=[o for o in occurrences if o['date'] < (today+timedelta(days=7)).isoformat()], risks=risks, actions=actions))


def json_text(value):
    return json.dumps(value, default=lambda v: format(v, '.2f') if isinstance(v, Decimal) else str(v), indent=2, sort_keys=True) + '\n'


def markdown(name, value):
    if name == 'daily_report':
        lines = [f"# Daily report: {value['date']}", '', f"Cash position today: {value['cash']:.2f}", '', '## Due next 7 days', '']
        lines += [f"- {o['date']}: {o['payee']} — {o['amount']:.2f} from {o['pay_from']} (autopay {o['autopay']})" for o in value['due_next_7_days']] or ['None.']
        lines += ['', '## Risks', '']
        lines += [f"- {r.get('date', value['date'])}: {r['type']} ({r.get('bill_id', r.get('account', 'account'))})" for r in value['risks']] or ['None.']
        lines += ['', '## Top 3 actions', '']
        lines += [f"- {a['action']} (requires_approval: true)" for a in value['actions']] or ['No actions recommended.']
        return '\n'.join(lines) + '\n'
    # JSON blocks preserve all amounts and flags in calendar/forecast Markdown.
    return f'# {name.replace("_", " ").title()}\n\n```json\n{json_text(value)}```\n'

"""Validation and deterministic, offline projection calculations."""
import calendar
import csv
import json
import io
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
            if not isinstance(key, str):
                raise ValueError('Invalid field name')
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
    for name in ('accounts', 'bills', 'income', 'transfers', 'collections', 'subscriptions'):
        path = Path(directory) / f'{name}.json'
        if not path.exists() and name in ('transfers', 'collections', 'subscriptions'):
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
    for name, fields in [('bills', ('pay_from', 'autopay_source')), ('income', ('deposit_to',)), ('transfers', ('from', 'to')), ('subscriptions', ('account',))]:
        for row in result[name]:
            if any(row[f] not in accounts for f in fields if f in row):
                raise ValueError('Unknown account reference')
    for row in result['income']:
        if row['cadence'] == 'biweekly' and date.fromisoformat(row['start_date']).weekday() != row['weekday']:
            raise ValueError('Biweekly anchor must match weekday')
    result['transactions'] = []
    for path in sorted((Path(directory) / 'transactions').glob('*')):
        if path.suffix.lower() not in {'.json', '.csv'}:
            continue
        raw = path.read_text()
        if re.search(r'\d{13,19}', raw):
            raise ValueError('Forbidden long digit run')
        if path.suffix.lower() == '.json':
            rows = json.loads(raw, parse_float=Decimal)
        else:
            try:
                rows = list(csv.DictReader(io.StringIO(raw), strict=True))
            except csv.Error:
                raise ValueError('Invalid transaction CSV') from None
        reject_secrets(rows)
        schema = json.loads((SCHEMAS / 'transactions.schema.json').read_text())
        if next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(rows), None):
            raise ValueError('Invalid transactions input')
        for row in rows:
            amount = Decimal(str(row['amount']))
            if not amount.is_finite() or amount != amount.quantize(Decimal('.01')):
                raise ValueError('Invalid transaction amount')
            row['amount'] = amount.quantize(Decimal('.01'))
            if row['account'] not in accounts:
                raise ValueError('Unknown transaction account')
        result['transactions'].extend(rows)
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


def build_reports(data, today, weeks=6, extra=ZERO, _include_guard=True):
    from .phase2 import debt_plan, subscriptions, overdraft_guard
    extra = Decimal(str(extra))
    if not extra.is_finite() or extra < 0 or extra != extra.quantize(Decimal(".01")):
        raise ValueError("Invalid extra monthly payment")
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
    fee_lines = []

    def charge_fee(key, amount, debit_type, debit_id, stamp, rows):
        if amount > ZERO and accounts[key]['kind'] not in debt_kinds and balances[key] < ZERO:
            fee = accounts[key].get('overdraft_fee', ZERO)
            balances[key] -= fee
            rows[key]['fees'] += fee
            fee_lines.append(dict(date=stamp, account=key, debit_type=debit_type, debit_id=debit_id, amount=fee))

    for offset in range(weeks * 7):
        day = today + timedelta(days=offset)
        stamp = day.isoformat()
        rows = {key: dict(opening=value, income=ZERO, transfers=ZERO, bills=ZERO, fees=ZERO) for key, value in balances.items()}
        for income in data['income']:
            if income_due(income, day):
                rows[income['deposit_to']]['income'] += income['amount']
        for key, row in rows.items():
            direction = -1 if accounts[key]['kind'] in debt_kinds else 1
            balances[key] += direction * row['income']
        for index, transfer in enumerate(data['transfers']):
            if transfer['date'] == stamp and transfer['status'] == 'planned':
                for key, sign in [(transfer['from'], -1), (transfer['to'], 1)]:
                    rows[key]['transfers'] += sign * transfer['amount']
                    direction = -1 if accounts[key]['kind'] in debt_kinds else 1
                    balances[key] += direction * sign * transfer['amount']
                    if sign == -1:
                        charge_fee(key, transfer['amount'], 'transfer', transfer.get('id', str(index)), stamp, rows)
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
                risks.append(dict(type=conflict, date=stamp, bill_id=bill['id'], account=source, money_at_risk=bill['amount']))
            occurrence['funded'] = available >= bill['amount']
            rows[source]['bills'] += bill['amount']
            balances[source] += bill['amount'] if accounts[source]['kind'] in debt_kinds else -bill['amount']
            charge_fee(source, bill['amount'], 'bill', bill['id'], stamp, rows)
        for bill in data['bills']:
            if bill.get('shutoff_date') != stamp:
                continue
            paid = [o for o in occurrences if o['bill_id'] == bill['id'] and o['date'] <= stamp]
            if not paid or not paid[-1]['funded']:
                risks.append(dict(type='shutoff', date=stamp, bill_id=bill['id'], account=bill['pay_from'], money_at_risk=bill['amount'] + bill.get('late_fee', ZERO)))
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
                            risk['fees'] = row['fees']
                            risk['money_at_risk'] = -balances[key]
                        risks.append(risk)
        days.append(dict(date=stamp, accounts=rows))
    # Keep the largest exposure for each actionable issue across the horizon.
    candidates = {}
    actionable = {'overdraft', 'shutoff', 'after_shutoff', 'two_payment_paths', 'autopay_insufficient_funds'}
    for risk in risks:
        if risk['type'] not in actionable:
            continue
        kind = 'shutoff' if risk['type'] == 'after_shutoff' else risk['type']
        key = (kind, risk.get('bill_id', risk.get('account')))
        if key not in candidates or risk.get('money_at_risk', ZERO) > candidates[key].get('money_at_risk', ZERO):
            candidates[key] = dict(risk, type=kind)
    ranked = sorted(candidates.values(), key=lambda r: (-r.get('money_at_risk', ZERO), r.get('date', ''), r['type'], r.get('bill_id', r.get('account', ''))))
    if not ranked:
        ranked = sorted(warnings, key=lambda r: r['account'])
    actions = [dict(action=f"Review {r['type']} for {r.get('bill_id', r.get('account', 'account'))}", money_at_risk=r.get('money_at_risk', ZERO), requires_approval=True) for r in ranked[:3]]
    risks.sort(key=lambda r: r['type'] == 'snapshot_date')
    phase2 = dict(debt_plan=debt_plan(data, today, extra), subscriptions=subscriptions(data, today), overdraft_guard=overdraft_guard(data, dict(days=days), dict(occurrences=occurrences)) if _include_guard else None)
    return dict(**phase2, ledger=ledger, bill_calendar=dict(occurrences=occurrences), cashflow=dict(days=days, risks=risks, fee_lines=fee_lines, cash_accounts=[key for key in accounts if accounts[key]['kind'] not in debt_kinds]), daily=dict(date=today.isoformat(), cash=cash, due_next_7_days=[o for o in occurrences if o['date'] < (today+timedelta(days=7)).isoformat()], risks=risks, actions=actions))


def json_text(value):
    return json.dumps(value, default=lambda v: format(v, '.2f') if isinstance(v, Decimal) else str(v), indent=2, sort_keys=True) + '\n'


def markdown(name, value):
    if name == 'daily_report':
        lines = [f"# Daily report: {value['date']}", '', f"Cash position today: {value['cash']:.2f}", '', '## Due next 7 days', '']
        lines += [f"- {o['date']}: {o['payee']} — {o['amount']:.2f} from {o['pay_from']} (autopay {o['autopay']})" for o in value['due_next_7_days']] or ['None.']
        lines += ['', '## Risks', '']
        lines += [f"- {r.get('date', value['date'])}: {r['type']} ({r.get('bill_id', r.get('account', 'account'))})" for r in value['risks']] or ['None.']
        lines += ['', '## Top 3 actions', '']
        lines += [f"- {a['action']} — money at risk: {a['money_at_risk']:.2f} (requires_approval: true)" for a in value['actions']] or ['No actions recommended.']
        return '\n'.join(lines) + '\n'
    if name == 'cashflow':
        def cell(text):
            return str(text).replace('|', '&#124;').replace('\n', ' ')
        lines = ['# Cashflow', '']
        for key in value['cash_accounts']:
            lines += [f'## {cell(key)}', '', '| Date | Opening | In | Transfers | Bills | Fees | Closing | Flags |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
            for day in value['days']:
                row = day['accounts'][key]
                amounts = ' | '.join(f"{row[field]:.2f}" for field in ('opening', 'income', 'transfers', 'bills', 'fees', 'closing'))
                lines.append(f"| {day['date']} | {amounts} | {cell(', '.join(row['flags']))} |")
            lines.append('')
        return '\n'.join(lines) + '\n'
    # JSON blocks preserve all amounts and flags in calendar/forecast Markdown.
    return f'# {name.replace("_", " ").title()}\n\n```json\n{json_text(value)}```\n'

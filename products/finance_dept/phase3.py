"""Deterministic collections drafts and monthly close; no financial actions."""
import calendar
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .core import SCHEMAS, ZERO, reject_secrets
from .phase2 import cents


def read_validated(path, schema_name):
    raw = Path(path).read_text()
    if re.search(r'\d{13,19}', raw):
        raise ValueError('Forbidden long digit run')
    value = json.loads(raw, parse_float=Decimal,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))
    reject_secrets(value)
    schema = json.loads((SCHEMAS / f'{schema_name}.schema.json').read_text())
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value):
        raise ValueError('Invalid input')
    return value


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != cents(amount):
        raise ValueError('Invalid money')
    return cents(amount)


def collections(directory, today):
    path = Path(directory) / 'collections.json'
    items = read_validated(path, 'collections') if path.exists() else []
    rows, ids = [], set()
    for item in items:
        if item['id'] in ids:
            raise ValueError('Duplicate collection id')
        ids.add(item['id'])
        principal = money(item['principal'])
        rate = Decimal(str(item.get('annual_rate', 0)))
        if principal < 0 or not rate.is_finite() or rate < 0:
            raise ValueError('Invalid principal or rate')
        start = date.fromisoformat(item['start_date'])
        days = max(0, (today - start).days)
        months = 0
        if days:
            months = (today.year-start.year)*12 + today.month-start.month
            anniversary = date(today.year, today.month, min(start.day, calendar.monthrange(today.year, today.month)[1]))
            months += today > anniversary
        interest = cents(principal * rate / 100 * Decimal(days) / 365) if item['kind'] == 'tax_debt' else ZERO
        penalty = cents(principal * min(Decimal('.005') * months, Decimal('.25'))) if item['kind'] == 'tax_debt' else ZERO
        inactive = item['status'].casefold() in {'paid', 'closed', 'resolved', 'cancelled', 'sold', 'collected'}
        exposure = ZERO if inactive else principal + interest + penalty
        draft = (f"Review closure evidence for {item['counterparty']}." if inactive else
                 f"Draft for human review — {item['counterparty']}: {item['next_action']}. "
                 f"Verify principal {principal:.2f} and evidence: {item['evidence']}.")
        rows.append(dict(item, principal=principal, interest_estimate=interest, penalty_estimate=penalty,
                         elapsed_days=days, penalty_months=months, exposure=exposure,
                         missing_annual_rate=item['kind'] == 'tax_debt' and 'annual_rate' not in item,
                         draft_next_step=draft, requires_approval=True))
    rows.sort(key=lambda r: (-r['exposure'], r['id']))
    return dict(date=today.isoformat(), items=rows, requires_approval=True,
                assumptions='Estimates only, not a tax assessment. Annual rate is a percent; missing rate means zero interest, flagged for review. Simple principal-only daily interest, actual days/365; 0.5% per started calendar month after start_date, anniversary clamped to month end, capped at 25%. Future starts accrue zero. Closed statuses have zero ranked exposure. Drafts only; nothing sent.')


def monthly_close(directory, month, export):
    if not re.fullmatch(r'\d{4}-\d{2}', month or ''):
        raise ValueError('Invalid month')
    first = date.fromisoformat(month + '-01')
    last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    source = read_validated(Path(export) / 'export.json', 'close_export')
    snapshots = read_validated(Path(directory) / 'accounts.json', 'accounts')
    def unique(rows):
        result = {}
        for row in rows:
            if row['id'] in result:
                raise ValueError('Duplicate account id')
            result[row['id']] = row
        return result
    accounts, snapshots = unique(source['accounts']), unique(snapshots)
    balances = {}
    for key, account in accounts.items():
        if account['as_of'] != first.isoformat():
            raise ValueError('Export opening snapshot must be first of month')
        balances[key] = money(account['opening_balance'])
    unmatched, uncategorized, categories, seen = [], [], {}, set()
    for tx in source['transactions']:
        amount = money(tx['amount'])
        if 'id' in tx:
            if tx['id'] in seen:
                raise ValueError('Duplicate transaction id')
            seen.add(tx['id'])
        if not first.isoformat() <= tx['date'] <= last.isoformat():
            continue
        tx = dict(tx, amount=amount)
        if tx['account_id'] not in accounts:
            unmatched.append(tx)
            continue
        balances[tx['account_id']] += amount
        category = tx.get('category', '').strip() or 'Uncategorized'
        if category == 'Uncategorized':
            uncategorized.append(tx)
        totals = categories.setdefault(category, dict(income=ZERO, spend=ZERO))
        totals['income' if amount >= 0 else 'spend'] += abs(amount)
    rows = []
    for key in sorted(accounts.keys() | snapshots.keys()):
        snapshot = snapshots.get(key)
        comparable = key in accounts and snapshot is not None and snapshot['as_of'] == last.isoformat()
        closing = balances.get(key)
        expected = money(snapshot['balance']) if snapshot else None
        rows.append(dict(id=key, opening=money(accounts[key]['opening_balance']) if key in accounts else None,
                         closing=closing, snapshot_balance=expected, snapshot_as_of=snapshot['as_of'] if snapshot else None,
                         reconciliation_diff=closing-expected if comparable else None,
                         reconciliation_status='comparable' if comparable else 'missing_account_or_month_end_snapshot'))
    issues = [r for r in rows if r['reconciliation_diff'] != ZERO]
    actions = [dict(draft_next_step=f"Review reconciliation for {r['id']} using month-end evidence.", requires_approval=True) for r in issues]
    if unmatched or uncategorized:
        actions.append(dict(draft_next_step='Review unmatched accounts and assign missing categories using transaction evidence.', requires_approval=True))
    return dict(month=month, accounts=rows, categories=[dict(category=k, **v) for k,v in sorted(categories.items())],
                unmatched=unmatched, uncategorized=uncategorized, actions=actions, requires_approval=True,
                assumptions='Export accounts are opening snapshots on day 1; transactions are signed balance deltas (positive income, negative spend), inclusive calendar month. Categories describe flows, not tax treatment; transfers need explicit categories and are not eliminated. Unknown-account transactions are excluded from balances and categories. Difference = calculated closing minus accounts.json month-end balance; other dates are noncomparable. Debt balances must use the same signed convention in both files. Drafts only.')

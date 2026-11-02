"""Offline recommendations. APR is a percentage; payoff uses monthly compounding."""
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def payoff(debts, extra):
    balances = [max(d['balance'], ZERO) for d in debts]
    finished = {d['id']: 0 for d, b in zip(debts, balances) if not b}
    for month in range(1, 12001):
        if not any(balances):
            return month - 1, finished
        previous = list(balances)
        for i, debt in enumerate(debts):
            balances[i] += cents(balances[i] * debt.get('apr', ZERO) / Decimal(1200))
        remaining = extra
        for i, debt in enumerate(debts):
            payment = min(balances[i], debt.get('min_payment', ZERO))
            balances[i] -= payment
        for i in range(len(debts)):
            payment = min(balances[i], remaining)
            balances[i] -= payment
            remaining -= payment
        for debt, balance in zip(debts, balances):
            if not balance and debt['id'] not in finished:
                finished[debt['id']] = month
        if not any(balances):
            return month, finished
        if all(b >= old for b, old in zip(balances, previous)):
            break
    return None, {d['id']: finished.get(d['id']) for d in debts}


def debt_plan(data, today, extra):
    debts = sorted((d for d in data['accounts'] if d['kind'] in {'loan', 'credit_card'} and d['balance'] > 0), key=lambda d: (-d.get('apr', ZERO), d['id']))
    minimum_months, minimum = payoff(debts, ZERO)
    extra_months, accelerated = payoff(debts, extra)
    rows = []
    for debt in debts:
        rows.append(dict(account=debt['id'], balance=debt['balance'], apr=debt.get('apr'), min_payment=debt.get('min_payment'), monthly_interest=cents(debt['balance'] * debt.get('apr', ZERO) / Decimal(1200)), months_at_minimum=minimum.get(debt['id']), months_with_extra=accelerated.get(debt['id']), missing_terms=[k for k in ('apr', 'min_payment') if k not in debt], requires_approval=True))
    return dict(date=today.isoformat(), extra_monthly=extra, avalanche_order=[d['id'] for d in debts], debts=rows, total_monthly_interest=sum((r['monthly_interest'] for r in rows), ZERO), months_at_minimum=minimum_months, months_with_extra=extra_months, assumptions='APR percent; missing APR/minimum treated as zero; fixed minimums; interest rounded half up monthly before payments; extra goes to highest APR; no minimum rollover; null months means no payoff within 12000 months or non-amortizing.', requires_approval=True)


def normalize(payee):
    return re.sub(r'[\W_]', '', payee.casefold())


def subscriptions(data, today):
    rows = data.get('subscriptions', [])
    counts = {}
    for row in rows:
        key = normalize(row['payee'])
        counts[key] = counts.get(key, 0) + 1
    recommendations = []
    for row in rows:
        if row.get('keep', False):
            continue
        reasons = []
        if not row.get('last_used') or (today - date.fromisoformat(row['last_used'])).days > 60:
            reasons.append('unused')
        if counts[normalize(row['payee'])] > 1:
            reasons.append('duplicate')
        if 0 <= (date.fromisoformat(row['next_renewal']) - today).days <= 14:
            reasons.append('renewal_soon')
        if reasons:
            matches = [t for t in data.get('transactions', []) if normalize(t['payee']) == normalize(row['payee']) and t['account'] == row['account']]
            recommendations.append(dict(row, flags=reasons, matching_transactions=matches, requires_approval=True))
    return dict(date=today.isoformat(), recommendations=recommendations)


def overdraft_guard(data, forecast, calendar):
    accounts = {a['id']: a for a in data['accounts'] if a['kind'] in {'checking', 'wallet'}}
    days = forecast['days']
    balances = {key: [day['accounts'][key]['closing'] for day in days] for key in accounts}
    risk_days = [dict(date=d['date'], account=key, closing=d['accounts'][key]['closing'], flags=d['accounts'][key]['flags']) for d in days for key in accounts if d['accounts'][key]['flags']]
    bills = {b['id']: b for b in data['bills']}
    recommendations = []
    for occurrence in calendar['occurrences']:
        key = occurrence['pay_from']
        if key not in accounts:
            continue
        start = (date.fromisoformat(occurrence['date']) - date.fromisoformat(days[0]['date'])).days
        floor = accounts[key].get('floor', ZERO)
        bill = bills[occurrence['bill_id']]
        # Shutoff bills require individual review and are never moved automatically.
        if 'shutoff_date' in bill:
            continue
        deadline = date.fromisoformat(occurrence['date']) + timedelta(days=bill.get('grace_days', 0))
        target = next((i for i in range(start + 1, len(days)) if days[i]['accounts'][key]['income'] > 0), None)
        if target is None or date.fromisoformat(days[target]['date']) > deadline:
            continue
        trial = list(balances[key])
        for i in range(start, target):
            trial[i] += occurrence['amount']
        threshold = max(floor, ZERO)
        before = sum(b < threshold for b in balances[key])
        after = sum(b < threshold for b in trial)
        if after >= before or trial[target] < threshold:
            continue
        avoided = sum(b < 0 for b in balances[key]) - sum(b < 0 for b in trial)
        recommendations.append(dict(bill_id=bill['id'], account=key, original_date=occurrence['date'], suggested_date=days[target]['date'], amount=occurrence['amount'], fee_saved=avoided * accounts[key].get('overdraft_fee', ZERO), requires_approval=True))
        balances[key] = trial
    return dict(risk_days=risk_days, recommendations=recommendations, total_fee_saved=sum((r['fee_saved'] for r in recommendations), ZERO), fee_assumption='Estimated fee per negative forecast day; actual bank fee policies may differ.')

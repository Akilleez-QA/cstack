# Finance Department, Phases 1–2

Run `python -B -m products.finance_dept all --data-dir /path/outside/repo
--today 2026-02-01 --weeks 6` (on one line). Commands are `validate`, `ledger`,
`calendar`, `forecast`, `daily`, `debts`, `subs`, `guard`, and `all`. The data directory defaults to
`FINANCE_DEPT_DATA`, then `~/.local/share/finance-dept`. Inputs follow the schemas
in `schemas/finance_dept/`; transfers, collections, subscriptions, and transactions may be omitted.

Reports are written to the data directory's `out/`. Exit codes are 0 for success,
2 for invalid inputs or filesystem errors, and 3 for reported risks. `validate`
only checks inputs and writes nothing. Amounts serialize as decimal strings.
The module makes no network calls and executes no financial actions.

Balances are opening snapshots on `--today`. A different `as_of` produces a
warning; the forecast does not reconstruct history. Debt balances are positive
amounts owed; cash includes checking and wallets, while net worth also includes
brokerage assets and subtracts debt. Each projected day applies income, planned
transfers, and then bills in input order. Completed transfers are already included
in snapshots. Bills are projected even when autopay is off or unknown, so future
obligations remain visible. When autopay is on, its source is the projected
payment account; a different `pay_from` is flagged as a possible second path.

Monthly dates clamp to the last day of short months. Weekly and yearly bills
use `due_date` as their first occurrence; yearly leap-day bills clamp too.
Income weekdays use Monday=0 through Sunday=6. Biweekly income additionally
requires `start_date` on its weekday to identify the first payday. Prior-evening
income lands one calendar day before the nominal payday, including across month
boundaries. No holiday or banking-day adjustments are assumed.

Floors, negative balances, autopay conflicts, snapshot dates and bills after a
shutoff date are reported as risks. Each bill or outgoing transfer that posts to a negative balance incurs the
configured overdraft fee once. Fee lines and daily fee totals reduce forecast
closing balances; negative days without a debit incur no new fee. The guard uses grace days as the latest permitted delay; late fees are retained
metadata because no payment history is available to determine late charges.
Daily actions rank overdraft shortfalls including fees, shutoff exposure, and
payment-path conflicts by money at risk. Snapshot notices appear last and are
actions only when there are no actionable risks. Cashflow Markdown contains one
daily table per cash account. Recommendations require human approval. Collections are validated but tracking
and transaction reconciliation belong to later phases.

Tests use synthetic fixtures copied to temporary directories. Private data and
reports must stay outside this public repository, even when ignored by Git.

`debts --extra 50.00` (alias `--extra-monthly`) writes `debt_plan.json` and
`debt_plan.md`. Debts sort by descending APR, then account ID. APR is a percent
(e.g. 12 means 12%); monthly interest rounds half up to cents before payments.
Minimums stay fixed; extra goes to the highest APR balance and spills to the next
when paid off. Paid-off minimums are not rolled forward. Missing APR/minimums are
listed and treated as zero; null payoff months means non-amortizing or beyond
12,000 months. Estimates exclude new borrowing and changing rates.

`subs` reads optional `subscriptions.json`, following its input schema, and writes
`out/subscriptions.json` (schema `subscriptions_report.schema.json`). Candidates
have missing usage or usage older than 60 days, a duplicate payee after case and
punctuation/space normalization, or renewal from today through 14 days ahead.
`keep: true` entries never appear as recommendations. Optional transaction exports
in `transactions/*.json` (arrays) or `*.csv` use `date,payee,amount,account` with
optional `id`. Matching payee/account charges provide evidence, not proof of use.
Exports undergo the same secret, date, account-reference and cents validation.

`guard` writes `overdraft_guard.json`: negative/below-floor forecast days and
proposed bill moves to the next income day in the same account. It skips bills
with a shutoff date, requires the move to fit within `grace_days` (default zero),
and only suggests moves reducing risk days with enough balance on the new date.
Moves are evaluated together to avoid double-counting savings. Fee savings assume
configured overdraft fees avoided by retiming debits; actual bank policies vary.
Balances remain end-of-day projections. All recommendations require approval;
nothing is rescheduled or paid. `all` includes every Phase 2 output. Subscription
flags, like forecast risks, produce exit code 3.

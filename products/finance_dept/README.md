# Finance Department, Phase 1

Run `python -B -m products.finance_dept all --data-dir /path/outside/repo
--today 2026-02-01 --weeks 6` (on one line). Commands are `validate`, `ledger`,
`calendar`, `forecast`, `daily`, and `all`. The data directory defaults to
`FINANCE_DEPT_DATA`, then `~/.local/share/finance-dept`. Inputs follow the schemas
in `schemas/finance_dept/`; transfers and collections may be omitted.

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
shutoff date are reported as risks. Overdraft fees are disclosed with negative
balance flags, not automatically charged. Grace days and late fees are retained
input metadata; this phase has no payment history to determine late charges.
Recommendations require human approval. Collections are validated but tracking
and transaction reconciliation belong to later phases.

Tests use synthetic fixtures copied to temporary directories. Private data and
reports must stay outside this public repository, even when ignored by Git.

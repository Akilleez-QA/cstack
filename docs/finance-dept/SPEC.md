# Finance Department module (`products/finance_dept`)

A personal finance and accounting "department" for one human approver. It reads
exported files, computes, and writes reports/JSON an assistant bot reads. It
**recommends and drafts only**: it never pays, transfers, sends, or logs in.

## Hard rules
- **Public repo: no real data ever committed.** Only code, schemas, and synthetic
  fixtures (fake names, round fake numbers) live here. Real inputs/outputs live in
  a data dir outside the repo (`--data-dir`, default `$FINANCE_DEPT_DATA` or
  `~/.local/share/finance-dept`). `.gitignore` covers `*.local.json`, `data/`, `out/`.
- No secrets in inputs or outputs: no passwords, full card/account numbers, tokens,
  SSN, DOB. Accounts are identified by nickname + last 4 only. Loader rejects any
  field matching 13–19 digit runs or keys like `password|token|ssn|dob|cvv`.
- No network, no third-party deps (stdlib + existing `jsonschema`). Python 3.11.
- Money is `decimal.Decimal`, cents-exact; dates are ISO `YYYY-MM-DD` local.
- Every recommendation carries `requires_approval: true`.

## Inputs (JSON in data dir; schemas in `schemas/finance_dept/`)
- `accounts.json`: `[{id, name, kind: checking|wallet|credit_card|loan|brokerage,
  last4, balance, as_of, apr?, credit_limit?, min_payment?, floor?, overdraft_fee?}]`
- `bills.json`: `[{id, payee, amount, due_day | due_date, cadence: monthly|weekly|
  yearly|once, pay_from, autopay: on|off|unknown, autopay_source?, shutoff_date?,
  late_fee?, grace_days?, notes?}]`
- `income.json`: `[{id, source, amount, cadence: weekly|biweekly|monthly,
  weekday | day, deposit_to, lands: "same_day"|"prior_evening"}]`
  (example shape: weekly Wed deposit to checking + a split to a wallet the prior evening).
- `transfers.json` (planned, human-executed): `[{date, from, to, amount, status:
  planned|done}]`
- `collections.json`: `[{id, kind: tax_debt|receivable|asset_sale, counterparty,
  principal, annual_rate?, start_date, status, next_action, evidence}]`. Tax debt
  is money at risk; receivables and asset sales are money recoverable.
- `transactions/*.csv|json` (phase 2): bank/aggregator exports for reconciliation.

## Outputs (data dir `out/`)
- `ledger.json`: normalized accounts, totals (cash, debt, net worth), warnings.
- `bill_calendar.json` + `.md`: occurrences in window, autopay state, conflicts
  (e.g. autopay on a source that can't cover it; two payment paths for one bill).
- `cashflow.json` + `.md`: day-by-day running balance per account for N weeks
  (default 6): opening, income, transfers, bills, closing; flags days below
  `floor`, below 0 (overdraft risk with fee), and bills due after shutoff_date.
- `daily_report.md`: cash position today, due next 7 days, risks, top 3 actions.
- Later phases: `debt_plan.json` (avalanche order, monthly interest),
  `subscriptions.json` (recurring charges, unused/duplicate candidates),
  `overdraft_guard.json`. Phase 3 writes `collections.json` + `.md` and
  `close_YYYY-MM.json` + `.md` (reconciliation).

## CLI
`python -m products.finance_dept <cmd> --data-dir D [--today YYYY-MM-DD] [--weeks N]`
cmds: `validate`, `ledger`, `calendar`, `forecast`, `daily`, `debts`, `subs`,
`guard`, `collections`, `close`, `all`. Close requires `--month YYYY-MM --export DIR`. Exit 0 ok,
2 invalid input, 3 risk flagged (still writes outputs).

## Phases
1. **Ledger + bill calendar + cash-flow forecast + daily report + tests** (this PR).
2. Debt avalanche & interest tracker; subscription/unused-charge detector;
   overdraft-fee guard (suggest bill re-timing to avoid negative days).
3. Collections tracker; monthly close/reconciliation from transaction exports;
   signed flows by category and month-end snapshot differences. Plan variance is
   deferred until an actual category budget input contract exists.

## Tests (`tests/test_finance_dept_*.py`, unittest)
Synthetic fixtures under `tests/fixtures/finance_dept/`. Cover: due-day rollover
(31st in short months), weekly/prior-evening income, autopay conflict detection,
floor/overdraft/shutoff flags, Decimal exactness, secret-field rejection,
deterministic output with `--today`.


## Phase 3 contracts

See [the module README](../../products/finance_dept/README.md) for exact schemas,
examples, sign conventions, status handling and CLI behavior. Phase 3 commands
are standalone; `all` preserves its Phase 1–2 outputs. Collections sort by dollar
exposure, then ID, and include approval-required next-step drafts. Tax amounts
are explicitly estimates: principal × annual percentage / 100 × elapsed days /
365 plus principal × min(0.005 × started calendar months, 0.25), each rounded
half up to cents. Missing annual rate is flagged and treated as zero; future
start dates accrue nothing. Calendar month anniversaries clamp to month end.
No authoritative tax-policy lookup or network access occurs.

The close export contract is a directory with `export.json`: an accounts list
(`id`, optional `name`, `opening_balance`, first-of-month `as_of`) and transactions
(`date`, signed `amount`, `description`, `account_id`, optional `category`/`id`).
Close includes per-account opening/closing, income/spend by category, unmatched
and uncategorized transactions, and differences against month-end `accounts.json`
balances. Noncomparable dates/missing accounts have null differences and require
review. No opening balances are inferred from closing balances. Unknown-account
transactions never affect calculated balances. Transfers are not eliminated.
All new input paths use secret rejection, date validation and Decimal arithmetic.
All recommendations require approval; reports never trigger financial actions.

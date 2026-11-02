"""CLI for local reports; never executes financial actions."""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

from .core import build_reports, json_text, load_inputs, markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=['validate', 'ledger', 'calendar', 'forecast', 'daily', 'all'])
    parser.add_argument('--data-dir', default=os.environ.get('FINANCE_DEPT_DATA', '~/.local/share/finance-dept'))
    parser.add_argument('--today', default=date.today().isoformat())
    parser.add_argument('--weeks', type=int, default=6)
    args = parser.parse_args(argv)
    try:
        directory = Path(args.data_dir).expanduser().resolve()
        repo = Path(__file__).resolve().parents[2]
        if directory.is_relative_to(repo):
            raise ValueError('Data directory must be outside the repository')
        today = date.fromisoformat(args.today)
        if today.isoformat() != args.today or args.weeks < 1:
            raise ValueError('Invalid date or weeks')
        data = load_inputs(directory)
        reports = build_reports(data, today, args.weeks)
        if args.cmd == 'validate':
            return 0
        names = {'ledger': ['ledger'], 'calendar': ['bill_calendar'], 'forecast': ['cashflow'], 'daily': ['daily'], 'all': ['ledger', 'bill_calendar', 'cashflow', 'daily']}[args.cmd]
        out = directory / 'out'
        # Resolve output too so a symlink cannot place private reports in the repo.
        if out.resolve().is_relative_to(repo):
            raise ValueError('Output directory must be outside the repository')
        out.mkdir(parents=True, exist_ok=True)
        for name in names:
            if name != 'daily':
                (out / f'{name}.json').write_text(json_text(reports[name]))
            if name != 'ledger':
                filename = 'daily_report' if name == 'daily' else name
                (out / f'{filename}.md').write_text(markdown(filename, reports[name]))
        return 3 if reports['cashflow']['risks'] else 0
    except (ValueError, OSError, ArithmeticError):
        # Never echo input fragments, filesystem paths, or secrets on failure.
        print('Invalid finance input or data directory.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

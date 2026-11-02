"""Exercise CLI output and exit codes using only synthetic temporary data."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures' / 'finance_dept'


class FinanceCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        shutil.copytree(FIXTURES, self.directory, dirs_exist_ok=True)

    def run_cli(self, command, *extra):
        return subprocess.run([sys.executable, '-B', '-m', 'products.finance_dept', command, '--data-dir', str(self.directory), '--today', '2026-02-01', *extra], capture_output=True, text=True)

    def test_all_deterministic(self):
        self.assertEqual(self.run_cli('all').returncode, 3)
        output = self.directory / 'out'
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        self.assertEqual(set(before), {'ledger.json', 'bill_calendar.json', 'bill_calendar.md', 'cashflow.json', 'cashflow.md', 'daily_report.md'})
        self.assertEqual(self.run_cli('all').returncode, 3)
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
        self.assertIn('requires_approval', before['daily_report.md'].decode())

    def test_validate_and_individual_commands(self):
        self.assertEqual(self.run_cli('validate').returncode, 0)
        self.assertFalse((self.directory / 'out').exists())
        for command in ['ledger', 'calendar', 'forecast', 'daily']:
            self.assertEqual(self.run_cli(command).returncode, 3)
        (self.directory / 'bills.json').write_text('[]')
        self.assertEqual(self.run_cli('all', '--weeks', '1').returncode, 0)

    def test_invalid_no_secret_echo_or_output(self):
        (self.directory / 'accounts.json').write_text('[{"token":"synthetic-secret"}]')
        result = self.run_cli('all')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('synthetic-secret', result.stderr)
        self.assertFalse((self.directory / 'out').exists())

    def test_invalid_options(self):
        self.assertEqual(self.run_cli('all', '--weeks', '0').returncode, 2)
        self.assertEqual(self.run_cli('all', '--today', 'bad').returncode, 2)
        self.assertEqual(self.run_cli('all', '--data-dir', str(FIXTURES)).returncode, 2)

    def test_env_data_dir(self):
        env = dict(os.environ, FINANCE_DEPT_DATA=str(self.directory))
        result = subprocess.run([sys.executable, '-B', '-m', 'products.finance_dept', 'validate', '--today', '2026-02-01'], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0)

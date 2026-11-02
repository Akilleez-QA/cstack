"""Offline finance reports. Amounts are exact Decimal values, serialized as strings.

Debt balances are positive amounts owed. Account snapshots are opening balances
on --today; completed transfers are already reflected in those snapshots.
Biweekly income requires start_date to establish the alternating week.
"""
from .core import load_inputs, build_reports

__all__ = ['load_inputs', 'build_reports']

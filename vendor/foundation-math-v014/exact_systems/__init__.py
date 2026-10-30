"""Exact one-RHS rational linear systems, separate from runtime proof acceptance.

Import producer, verifier or API explicitly. Importing the verifier does not load
any producer. The original Foundation Math six-tool bridge is not modified.
"""
from .contract import (
    Coefficient, ConsistentCertificate, InconsistentCertificate, Limits,
    MathError, SystemCertificate, SystemRequest, SystemSpec,
)

__all__ = ['Coefficient', 'ConsistentCertificate', 'InconsistentCertificate',
           'Limits', 'MathError', 'SystemCertificate', 'SystemRequest', 'SystemSpec']

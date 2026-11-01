"""Bounded exact linear algebra. Mathematical modules are imported explicitly.

Producer: ``exact_linalg.producer.produce``
Verifier: ``exact_linalg.verifier.verify`` (does not load producer)
Combined checked API: ``exact_linalg.api.handle_request``
"""
from .contract import Coefficient, Limits, MathError, MatrixCertificate, MatrixSpec

__all__ = ['Coefficient', 'Limits', 'MathError', 'MatrixCertificate', 'MatrixSpec']

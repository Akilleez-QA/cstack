"""Standalone exact authored-premise matching lab. No release/runtime integration."""
from .core import ScopeError, VERSION, canonical_bytes, check, digest, loads, pin, seal

__all__ = ["ScopeError", "VERSION", "canonical_bytes", "check", "digest", "loads", "pin", "seal"]

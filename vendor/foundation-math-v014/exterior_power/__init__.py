"""Standalone bounded formal-domain lab; no Foundation Math tool registration."""
__all__ = ['calculate','verify','DomainError','BUDGETS']
def __getattr__(name):
    if name=='calculate':
        from .producer import calculate
        return calculate
    if name=='verify':
        from .verifier import verify
        return verify
    if name in ('DomainError','BUDGETS'):
        from . import contract
        return getattr(contract,name)
    raise AttributeError(name)

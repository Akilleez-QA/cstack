"""Shared exclusion wall: counts only; never log/store blocked content or ids."""
import os
import re
from collections.abc import Mapping
from pathlib import Path

TERMS = ('PartnerOne', 'PartnerTwo', 'PartnerThree', 'Partner Four', 'PartnerForge', 'PartnerFive')
DENY_PATHS = ('private-ops/private-search',)

def _compact(s):
    return ''.join(c for c in s.casefold() if c.isalnum())

class Wall:
    def __init__(self, extra_terms=()):
        terms = (*TERMS, *extra_terms, 'private search')
        self._paths = tuple(_compact(t) for t in (*terms, *DENY_PATHS))
        patterns = []
        for term in (*terms, *DENY_PATHS):
            # Also permit separators in the built-in concatenated product name.
            words = ['Partner', 'Forge'] if term == 'PartnerForge' else re.split(r'[\s_./-]+', term)
            patterns.append(r'[\s_./-]*'.join(re.escape(w) for w in words))
        self._text = re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(patterns) + r')(?![A-Za-z0-9])', re.I)

    @classmethod
    def from_env(cls, var='CSTACK_MEMORY_DENYLIST'):
        if var not in os.environ:
            return cls()
        path = os.environ[var]
        if not path.strip():
            raise OSError('Denylist path required')
        return cls(line.strip() for line in Path(path).read_text().splitlines()
                   if line.strip() and not line.lstrip().startswith('#'))

    def text_blocked(self, s):
        return bool(self._text.search(s))

    def path_blocked(self, s):
        return any(term in _compact(s) for term in self._paths)

    def record_blocked(self, mapping):
        def walk(value):
            if isinstance(value, str):
                return self.text_blocked(value)
            if isinstance(value, Mapping):
                return any(not isinstance(k, str) or
                           (self.path_blocked(v) if k in fields and isinstance(v, str) else walk(v))
                           for k, v in value.items())
            if isinstance(value, list):
                return any(walk(v) for v in value)
            return value is not None and not isinstance(value, (bool, int, float))
        fields = {'project', 'path', 'source_root', 'account', 'thread_id', 'kind'}
        try:
            return not isinstance(mapping, Mapping) or walk(mapping)
        except (TypeError, ValueError, RecursionError):
            return True

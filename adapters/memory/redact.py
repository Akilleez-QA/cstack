"""Pure lexical screening; no source content is retained."""
import re

# Detect-only markers: forge/endoforge/tools/factory_portability/checkpoint.py.
_HEADER = r"^[ \t]*(?:%s)[ \t]*:[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*"
PATTERNS = (
    ('private_key', r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|\Z)'),
    ('authorization', _HEADER % r'(?:Proxy-)?Authorization'),
    ('cookie', _HEADER % r'Cookie|Set-Cookie'),
    ('assignment', r'''(?<!\w)["']?(?:password|passwd|secret|token|api_key|apikey|access_key|client_secret|auth)["']?(?!\w)\s*[=:]\s*(?:"(?:\\.|[^"\\])*(?:"|\\?\Z)|'(?:\\.|[^'\\])*(?:'|\\?\Z)|[^\s,;&}\]"']+)'''),
    ('url_credentials', r'\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:[^\s/@]*@'),
    ('api_key', r'(?<![A-Za-z0-9_])sk-(?:(?:ant|proj)-)?[A-Za-z0-9_-]+'),
    ('github_token', r'(?<![A-Za-z0-9_])(?:gh[pos]_|github_pat_)[A-Za-z0-9_]+'),
    ('aws_key', r'\bAKIA[A-Z0-9]{16}\b'),
    ('slack_token', r'(?<![A-Za-z0-9_])xox[abprs]-[A-Za-z0-9-]+'),
    ('google_key', r'(?<![A-Za-z0-9_])AIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])'),
    ('jwt', r'(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![A-Za-z0-9_-])'),
    ('age_key', r'\bAGE-SECRET-KEY-[A-Z0-9]+\b'),
)
_DETECTORS = tuple((kind, re.compile(pattern, re.I | re.M if kind in
                    ('authorization', 'cookie', 'assignment', 'age_key') else 0))
                   for kind, pattern in PATTERNS)
_SUBSTITUTIONS = _DETECTORS
_PRIVATE_HEADER = re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----')

def _string(text):
    if type(text) is not str:
        raise TypeError('Screening requires text')

def has_secret(text: str) -> bool:
    _string(text)
    return bool(_PRIVATE_HEADER.search(text) or any(p.search(text) for _, p in _DETECTORS))

def redact(text: str) -> tuple[str | None, dict[str, int]]:
    _string(text)
    count = 0
    for kind, pattern in _SUBSTITUTIONS:
        text, added = pattern.subn('[REDACTED:' + kind + ']', text)
        count += added
    residue = int(has_secret(text))
    return (None if residue else text), {'redactions': count, 'secret_residue': residue}

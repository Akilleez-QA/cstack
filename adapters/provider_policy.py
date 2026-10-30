"""Model-provider adapter policy (staging target adapter.provider). Pure, stdlib-only, no network.

Classifies raw provider failures into a closed set, computes capped jittered backoff that honours
retry-after, and chooses failover routes that never exceed a request's data-class ceiling. Clock and
random source are injected, so every decision is deterministic under test. No provider SDK, socket
or secret is touched here; a host transport adapter performs the call and reports the failure.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import Enum, IntEnum
import json
import re
from typing import Callable


class ProviderPolicyError(ValueError):
    """Invalid host route configuration or request; never a provider outcome."""


class FailureKind(str, Enum):
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMITED = "rate_limited"
    USAGE_LIMIT = "usage_limit"
    AUTH_FAILED = "auth_failed"
    TRANSIENT = "transient"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"


class DataClass(IntEnum):
    """Leak-consequence classes after PAI DataClassification (MIT, (c) 2025-2026 Daniel Miessler).
    Higher is more sensitive. Unclassified data is RESTRICTED (fail closed)."""
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3

    @classmethod
    def parse(cls, value):
        if value is None:
            return cls.RESTRICTED
        if isinstance(value, cls):
            return value
        try:
            return cls[str(value).upper()]
        except KeyError:
            raise ProviderPolicyError("Unknown data class: " + repr(value)) from None


# Context-overflow, payload and exclusion patterns ported from opencode packages/ai/src/provider-error.ts
# at sst/opencode@097a93e. MIT License, Copyright (c) 2025 opencode; full text in
# parts-wall/primitives/integrations/oss-opencode-provider-error-classifier/files/LICENSE.
_OVERFLOW = [re.compile(p, re.I) for p in (
    r"prompt is too long",
    r"input is too long for (?:the )?(?:requested|selected) model",
    r"too large for the model'?s configured input limit",
    r"exceeded this model context window limit",
    r"exceeds the context window",
    r"exceeds (?:the )?(?:model'?s )?maximum context length(?: of [\d,]+ tokens?|\s*\([\d,]+\))",
    r"input token count.*exceeds the maximum",
    r"number of input tokens exceeds maximum length",
    r"tokens in request more than max tokens allowed",
    r"maximum prompt length is \d+",
    r"reduce the length of the messages",
    r"requested input length \d+ exceeds maximum input length",
    r"maximum context length is \d+ tokens",
    r"exceeds (?:the )?maximum allowed input length of [\d,]+ tokens?",
    r"input(?: \(\d+ tokens\))? is longer than the model'?s context length",
    r"exceeds the limit of \d+",
    r"exceeds the available context size",
    r"greater than the context length",
    r"`inputs` tokens \+ `max_new_tokens` must be <= \d+",
    r"context window exceeds limit",
    r"exceeded model token limit",
    r"context[_ ]length[_ ]exceeded",
    r"context length is only \d+ tokens",
    r"input length.*exceeds.*context length",
    r"prompt (?:too long|exceeds max length|超长)",
    r"too large for model with \d+ maximum context length",
    r"prompt has [\d,]+ tokens?, but the configured context size is [\d,]+ tokens?",
    r"model_context_window_exceeded",
    r"range of input length should be",
    r"too many tokens",
    r"token limit exceeded",
    r"request_too_large",
)]
_OVERFLOW_NO_BODY = re.compile(r"^4(?:00|13)\s*(status code)?\s*\(no body\)", re.I)
_OVERFLOW_EXCLUSIONS = [re.compile(p, re.I) for p in (
    r"^(throttling error|service unavailable):", r"rate limit", r"too many requests",
    r"max[_ ]tokens must be less than", r"too many tokens(?: per day)?, please wait",
)]
_OVERFLOW_CODES = {"context_length_exceeded", "model_context_window_exceeded", "request_too_large"}
_QUOTA_CODES = {"insufficient_quota", "usage_not_included", "billing_error", "gousagelimiterror",
                "budgetlimiterror", "freeusagelimiterror", "creditlimitexceeded"}
_AUTH_CODES = {"authentication_error", "permission_error", "permission_denied", "api_key_invalid"}
_SERVER_CODES = {"api_error", "internal_error", "internalserverexception", "modelstreamerrorexception",
                 "overloaded_error", "server_error", "server_is_overloaded", "slow_down", "serviceunavailableexception"}
_AUTH_TEXT = re.compile(r"incorrect api key provided", re.I)
_RATE_TEXT = re.compile(r"rate increased too quickly|rate[-_\s]?limit|too[_\s]?many[_\s]?requests", re.I)
_QUOTA_TEXT = re.compile(r"insufficient[-_\s]?(?:quota|balance)|quota[-_\s]?exceeded|budget exceeded|usage limit|"
                         r"limit exhausted|package has expired|plan does not yet include", re.I)
_SERVER_TEXT = re.compile(r"\b(?:try again|(?:currently |temporarily )?at capacity|overloaded|temporarily unavailable|"
                          r"service[-_\s]?unavailable|(?:server|internal)[-_\s]?error|server (?:is )?busy)\b", re.I)
# End of opencode-derived patterns.

TRANSIENT_EXCEPTIONS = frozenset({"timeout", "connection_error", "connection_reset", "read_error", "dns_error"})


def is_context_overflow(text):
    return (not any(p.search(text) for p in _OVERFLOW_EXCLUSIONS)
            and (any(p.search(text) for p in _OVERFLOW) or bool(_OVERFLOW_NO_BODY.search(text))))


def _codes(body):
    try:
        data = json.loads(body) if body else None
    except ValueError:
        return set()
    if not isinstance(data, dict):
        return set()
    err = data.get("error") if isinstance(data.get("error"), dict) else {}
    raw = [data.get("code"), data.get("__type"), data.get("error_type"),
           err.get("code"), err.get("type"), err.get("status"), err.get("error_type")]
    return {re.sub(r"^[^#]*#", "", re.sub(r":.*", "", v, flags=re.S)).lower() for v in raw if isinstance(v, str)}


@dataclass(frozen=True)
class ProviderFailure:
    """What a transport adapter observed. exception_kind is one of TRANSIENT_EXCEPTIONS or None."""
    status: int | None = None
    body: str = ""
    message: str = ""
    exception_kind: str | None = None
    retry_after_s: float | None = None


def classify(failure):
    """Map a raw failure to a FailureKind. Order follows opencode: overflow before quota/auth/rate."""
    status, codes = failure.status, _codes(failure.body)
    text = "\n".join(x for x in (failure.message, failure.body) if x)
    client = status is None or 400 <= status < 500
    if client and (codes & _OVERFLOW_CODES or is_context_overflow(text)):
        return FailureKind.CONTEXT_OVERFLOW
    # A usage cap printed by a CLI carries no status ("You've hit your usage limit ... try again at Nov 2nd, 2026
    # 2:38 AM", Codex, 2026-10-27); its "try again" must not make it transient.
    if status == 402 or codes & _QUOTA_CODES or ((status == 429 or status is None) and _QUOTA_TEXT.search(text)):
        return FailureKind.USAGE_LIMIT
    if status in (401, 403) or codes & _AUTH_CODES or (status == 400 and _AUTH_TEXT.search(text)):
        return FailureKind.AUTH_FAILED
    if status == 429 or any("rate_limit" in c or c in ("too_many_requests", "throttlingexception") for c in codes) \
            or _RATE_TEXT.search(text):
        return FailureKind.RATE_LIMITED
    if failure.exception_kind in TRANSIENT_EXCEPTIONS or status in (408, 409) or (status is not None and status >= 500) \
            or ((status is None or status < 400) and (codes & _SERVER_CODES or _SERVER_TEXT.search(text))):
        return FailureKind.TRANSIENT
    if status is not None and 400 <= status < 500:
        return FailureKind.INVALID_REQUEST
    return FailureKind.UNKNOWN


def parse_retry_after(value, now):
    """Seconds from a Retry-After header (delta-seconds or HTTP-date) at epoch time now; None if unusable."""
    if value is None:
        return None
    text = str(value).strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(text).timestamp() - now
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    return max(0.0, seconds) if seconds == seconds and seconds != float("inf") else None


_MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
_UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1, "m": 60, "min": 60, "mins": 60, "minute": 60,
          "minutes": 60, "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600, "d": 86400, "day": 86400,
          "days": 86400}
_RESET_IN = re.compile(r"(?:try again|resets?|available again)\s+in\s+((?:\d+(?:\.\d+)?\s*[a-z]+[\s,]*(?:and\s+)?)+)", re.I)
_RESET_AT = re.compile(r"(?:try again|resets?|available again)\s+(?:at|on)\s+(?:(?P<mon>[a-z]{3})[a-z]*\.?\s+(?P<day>\d{1,2})"
                       r"(?:st|nd|rd|th)?,?\s+(?:(?P<year>\d{4}),?\s+)?)?(?P<h>\d{1,2}):(?P<min>\d{2})\s*(?P<ampm>[ap]\.?m\.?)?", re.I)


def parse_reset(text, now, tz=None):
    """Seconds from epoch time now until the reset a limit message names, or None. Relative ("try again in 2h 30m",
    "in 120 seconds") and absolute ("try again at Nov 2nd, 2026 2:38 AM", "resets at 14:05") forms; an absolute
    time without a zone is in tz (default: this host's), a missing year or date is the next such moment."""
    text = text or ""
    m = _RESET_IN.search(text)
    if m:
        total, found = 0.0, False
        for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]+)", m.group(1), re.I):
            if unit.lower() in _UNITS:
                total, found = total + float(n) * _UNITS[unit.lower()], True
        if found:
            return total
    m = _RESET_AT.search(text)
    if not m:
        return None
    # no zone: naive local time, so .timestamp() applies this host's own rules, daylight saving included (a fixed
    # offset taken today would put a reset after the clocks change an hour off)
    current = datetime.fromtimestamp(now, tz) if tz else datetime.fromtimestamp(now)
    hour, minute = int(m["h"]), int(m["min"])
    if m["ampm"]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if m["ampm"].lower().startswith("p") else 0)
    if hour > 23 or minute > 59:
        return None
    try:
        if m["mon"]:
            month = _MONTHS.get(m["mon"].lower())
            if month is None:
                return None
            when = datetime(int(m["year"] or current.year), month, int(m["day"]), hour, minute, tzinfo=tz)
            if not m["year"] and when < current - timedelta(days=1):
                when = when.replace(year=when.year + 1)
        else:
            when = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if when < current:
                when += timedelta(days=1)
    except ValueError:
        return None
    return max(0.0, when.timestamp() - now)


def limit_bucket(seconds):
    """How long a limit lasts, for the response it deserves: 'minutes' (<= 15 min, wait in place), 'hours'
    (<= 6 h), 'days' (longer: park the work and tell the operator once), or None when the reset is unknown."""
    if seconds is None:
        return None
    return "minutes" if seconds <= 900 else "hours" if seconds <= 6 * 3600 else "days"


def reset_after(failure, now, tz=None):
    """The failure's own retry-after, else the reset its message names (parse_reset), else None."""
    if failure.retry_after_s is not None:
        return failure.retry_after_s
    return parse_reset("\n".join(x for x in (failure.message, failure.body) if x), now, tz)


@dataclass(frozen=True)
class Backoff:
    """Exponential from base_s, capped per gap at cap_s, jitter factor in [1-jitter, 1+jitter], retry-after
    honoured as a floor but bounded by retry_after_cap_s (opencode model-retry.ts defaults)."""
    base_s: float = 2.0
    cap_s: float = 10.0
    jitter: float = 0.2
    retry_after_cap_s: float = 900.0
    max_retries: int = 10

    def delay(self, retry_index, random, retry_after_s=None):
        gap = min(self.base_s * (2 ** retry_index), self.cap_s)
        gap *= 1 - self.jitter + 2 * self.jitter * random()
        if retry_after_s is not None:
            gap = max(gap, min(retry_after_s, self.retry_after_cap_s))
        return gap


@dataclass(frozen=True)
class Route:
    """Host-configured inference route. The ceiling is per route (provider + model + residency)."""
    route_id: str
    provider: str
    model: str
    ceiling: DataClass
    context_tokens: int | None = None

    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in (self.route_id, self.provider, self.model)):
            raise ProviderPolicyError("Route id, provider and model must be non-empty strings")
        if self.ceiling is None:  # an unset route ceiling must never default to the widest class
            raise ProviderPolicyError("Route ceiling is required")
        object.__setattr__(self, "ceiling", DataClass.parse(self.ceiling))


def eligible_routes(routes, data_class):
    """Routes in host order whose ceiling admits data_class. A lower-ceiling route is never returned."""
    level = DataClass.parse(data_class)
    return tuple(r for r in routes if r.ceiling >= level)


@dataclass(frozen=True)
class Decision:
    action: str  # "call" | "retry" | "wait" | "stop"
    route: Route | None
    delay_s: float = 0.0
    reason: str = ""
    kind: FailureKind | None = None


_FAILOVER = {FailureKind.USAGE_LIMIT, FailureKind.AUTH_FAILED, FailureKind.CONTEXT_OVERFLOW}
_RETRY_SAME = {FailureKind.RATE_LIMITED, FailureKind.TRANSIENT, FailureKind.UNKNOWN}


@dataclass
class FailoverPlanner:
    """Per-request failover state. Usage-limit and auth failures move to the next eligible route;
    context overflow never retries on the same route and only moves to a route with a larger (or
    undeclared) window; rate-limit, transient and unknown failures retry the same route with backoff.
    With no route left, a usage limit with a known reset waits within wait_deadline_s, else stops."""
    routes: tuple
    data_class: object
    clock: Callable[[], float]
    random: Callable[[], float]
    backoff: Backoff = field(default_factory=Backoff)
    wait_deadline_s: float = 3600.0

    def __post_init__(self):
        ids = [r.route_id for r in self.routes]
        if len(set(ids)) != len(ids):
            raise ProviderPolicyError("Route ids must be unique")
        self.level = DataClass.parse(self.data_class)
        self._eligible = list(eligible_routes(self.routes, self.level))
        self._index, self._retries, self._started = 0, 0, self.clock()

    def first(self):
        if not self._eligible:
            return Decision("stop", None, reason="no route ceiling admits data class " + self.level.name)
        return Decision("call", self._eligible[0])

    def on_failure(self, failure):
        if not self._eligible:
            raise ProviderPolicyError("No eligible route was ever chosen")
        kind = classify(failure)
        current = self._eligible[self._index]
        if kind in _RETRY_SAME and self._retries < self.backoff.max_retries:
            delay = self.backoff.delay(self._retries, self.random, failure.retry_after_s)
            self._retries += 1
            return Decision("retry", current, delay, "retry same route", kind)
        if kind in _FAILOVER or kind in _RETRY_SAME:
            for i in range(self._index + 1, len(self._eligible)):
                nxt = self._eligible[i]
                if kind is FailureKind.CONTEXT_OVERFLOW and current.context_tokens and nxt.context_tokens \
                        and nxt.context_tokens <= current.context_tokens:
                    continue
                self._index, self._retries = i, 0
                return Decision("call", nxt, reason="failover after " + kind.value, kind=kind)
            reset = reset_after(failure, self.clock()) if kind is FailureKind.USAGE_LIMIT else None
            if reset is not None:
                elapsed = self.clock() - self._started
                if elapsed + reset <= self.wait_deadline_s:
                    return Decision("wait", current, reset, "usage limit; resume after reset", kind)
                return Decision("stop", None, reason=f"usage limit; resets in {reset:.0f} s ({limit_bucket(reset)})",
                                kind=kind)
            return Decision("stop", None, reason="no eligible route left after " + kind.value, kind=kind)
        return Decision("stop", None, reason="deterministic rejection: " + kind.value, kind=kind)

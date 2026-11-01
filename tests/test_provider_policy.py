import ast
from pathlib import Path
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from adapters.provider_policy import (Backoff, DataClass, FailoverPlanner, FailureKind, ProviderFailure,
                                      ProviderPolicyError, Route, classify, eligible_routes, limit_bucket, parse_reset,
                                      parse_retry_after, reset_after)

ROOT = Path(__file__).resolve().parents[1]
K = FailureKind


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def routes():
    return (Route("anthropic", "anthropic", "claude", "restricted", 200_000),
            Route("openai", "openai", "gpt", "confidential", 400_000),
            Route("qwen-hosted", "runpod", "qwen", "internal", 128_000),
            Route("local", "llama.cpp", "qwen-local", "restricted", 32_000))


def planner(data_class, rs=None, clock=None, **kw):
    return FailoverPlanner(rs or routes(), data_class, clock or Clock(), lambda: 0.5, **kw)


class ClassifierTests(unittest.TestCase):
    def test_closed_set_from_status_body_and_exception(self):
        cases = [
            (ProviderFailure(400, '{"error":{"type":"invalid_request_error","message":"prompt is too long: 210000 tokens"}}'), K.CONTEXT_OVERFLOW),
            (ProviderFailure(400, '{"error":{"code":"context_length_exceeded"}}'), K.CONTEXT_OVERFLOW),
            (ProviderFailure(413, message="413 status code (no body)"), K.CONTEXT_OVERFLOW),
            (ProviderFailure(None, message="Prompt 超长"), K.CONTEXT_OVERFLOW),
            (ProviderFailure(429, '{"error":{"code":"insufficient_quota"}}'), K.USAGE_LIMIT),
            (ProviderFailure(429, message="You have reached your usage limit"), K.USAGE_LIMIT),
            (ProviderFailure(402), K.USAGE_LIMIT),
            (ProviderFailure(401), K.AUTH_FAILED),
            (ProviderFailure(400, message="Incorrect API key provided"), K.AUTH_FAILED),
            (ProviderFailure(400, '{"__type":"com.amazon#ThrottlingException"}'), K.RATE_LIMITED),
            (ProviderFailure(429, message="Rate limit reached"), K.RATE_LIMITED),
            (ProviderFailure(503), K.TRANSIENT),
            (ProviderFailure(529, '{"error":{"type":"overloaded_error"}}'), K.TRANSIENT),
            (ProviderFailure(exception_kind="timeout"), K.TRANSIENT),
            (ProviderFailure(None, '{"error":{"type":"overloaded_error"}}'), K.TRANSIENT),
            (ProviderFailure(400, '{"error":{"message":"bad tool schema"}}'), K.INVALID_REQUEST),
            (ProviderFailure(None, message="weird"), K.UNKNOWN),
            (ProviderFailure(exception_kind="unregistered_kind"), K.UNKNOWN),
        ]
        for failure, kind in cases:
            with self.subTest(failure=failure):
                self.assertIs(classify(failure), kind)

    def test_overflow_lookalikes_are_not_overflow(self):
        self.assertIs(classify(ProviderFailure(429, message="Too many tokens per day, please wait")), K.RATE_LIMITED)
        self.assertIs(classify(ProviderFailure(400, message="max_tokens must be less than 8192")), K.INVALID_REQUEST)
        # A 5xx carrying overflow text is a server fault, not a deterministic client overflow.
        self.assertIs(classify(ProviderFailure(500, message="prompt is too long")), K.TRANSIENT)


class BackoffTests(unittest.TestCase):
    def test_capped_jittered_and_honours_bounded_retry_after(self):
        b = Backoff()
        self.assertEqual([round(b.delay(i, lambda: 0.5), 6) for i in range(5)], [2, 4, 8, 10, 10])
        self.assertAlmostEqual(b.delay(0, lambda: 0.0), 1.6)
        self.assertAlmostEqual(b.delay(9, lambda: 0.999999), 12.0, places=4)
        self.assertEqual(b.delay(0, lambda: 0.5, retry_after_s=30), 30)
        self.assertEqual(b.delay(0, lambda: 0.5, retry_after_s=86_400), 900)

    def test_parse_retry_after(self):
        now = 784_111_777.0  # Sun, 06 Nov 1994 08:49:37 GMT
        self.assertEqual(parse_retry_after("120", now), 120)
        self.assertEqual(parse_retry_after("Sun, 06 Nov 1994 08:50:37 GMT", now), 60)
        self.assertEqual(parse_retry_after("Sun, 06 Nov 1994 08:00:00 GMT", now), 0)
        for bad in (None, "soon", "nan", "inf"):
            self.assertIsNone(parse_retry_after(bad, now))


class RouteCeilingTests(unittest.TestCase):
    def test_route_below_request_class_is_never_chosen(self):
        self.assertEqual([r.route_id for r in eligible_routes(routes(), "confidential")], ["anthropic", "openai", "local"])
        self.assertEqual([r.route_id for r in eligible_routes(routes(), None)], ["anthropic", "local"])
        p = planner("confidential")
        seen = [p.first().route]
        for _ in range(20):
            d = p.on_failure(ProviderFailure(401))
            if d.route is None:
                break
            seen.append(d.route)
        self.assertNotIn("qwen-hosted", [r.route_id for r in seen])
        self.assertTrue(all(r.ceiling >= DataClass.CONFIDENTIAL for r in seen))

    def test_no_admissible_route_stops_and_config_fails_closed(self):
        p = planner("restricted", rs=(Route("q", "runpod", "qwen", "internal"),))
        self.assertEqual(p.first().action, "stop")
        with self.assertRaises(ProviderPolicyError):
            p.on_failure(ProviderFailure(503))
        with self.assertRaises(ProviderPolicyError):
            Route("x", "p", "m", None)
        with self.assertRaises(ProviderPolicyError):
            DataClass.parse("secret-ish")
        with self.assertRaises(ProviderPolicyError):
            planner("public", rs=(Route("a", "p", "m", "public"), Route("a", "p", "n", "public")))


class FailoverTests(unittest.TestCase):
    def test_usage_limit_and_auth_move_to_next_route(self):
        p = planner("internal")
        self.assertEqual(p.first().route.route_id, "anthropic")
        d = p.on_failure(ProviderFailure(429, '{"error":{"code":"insufficient_quota"}}'))
        self.assertEqual((d.action, d.route.route_id, d.kind), ("call", "openai", K.USAGE_LIMIT))
        d = p.on_failure(ProviderFailure(403))
        self.assertEqual((d.action, d.route.route_id), ("call", "qwen-hosted"))

    def test_context_overflow_never_retries_same_route_and_needs_larger_window(self):
        p = planner("restricted")
        p.first()
        d = p.on_failure(ProviderFailure(400, message="prompt is too long"))
        self.assertEqual(d.action, "stop")  # local (32k) is smaller than anthropic (200k)
        p = planner("internal")
        p.first()
        d = p.on_failure(ProviderFailure(400, message="prompt is too long"))
        self.assertEqual((d.action, d.route.route_id), ("call", "openai"))
        self.assertEqual(p.on_failure(ProviderFailure(400, message="prompt is too long")).action, "stop")

    def test_transient_retries_same_route_then_fails_over(self):
        p = planner("restricted", backoff=Backoff(max_retries=2))
        p.first()
        a, b = p.on_failure(ProviderFailure(503)), p.on_failure(ProviderFailure(429, retry_after_s=45))
        self.assertEqual([(x.action, x.route.route_id, x.delay_s) for x in (a, b)],
                         [("retry", "anthropic", 2.0), ("retry", "anthropic", 45)])
        d = p.on_failure(ProviderFailure(503))
        self.assertEqual((d.action, d.route.route_id), ("call", "local"))

    def test_last_route_usage_limit_waits_within_deadline_else_stops(self):
        clock = Clock()
        p = planner("restricted", rs=(Route("a", "anthropic", "claude", "restricted"),), clock=clock, wait_deadline_s=600)
        p.first()
        d = p.on_failure(ProviderFailure(429, message="usage limit", retry_after_s=300))
        self.assertEqual((d.action, d.route.route_id, d.delay_s), ("wait", "a", 300))
        clock.t += 400
        self.assertEqual(p.on_failure(ProviderFailure(429, message="usage limit", retry_after_s=300)).action, "stop")
        self.assertEqual(p.on_failure(ProviderFailure(402)).action, "stop")

    def test_invalid_request_stops_without_retry(self):
        p = planner("public")
        p.first()
        self.assertEqual(p.on_failure(ProviderFailure(400, message="bad schema")).action, "stop")

    def test_module_is_stdlib_only_and_networkless(self):
        allowed = set(sys.stdlib_module_names) - {"socket", "ssl", "http", "urllib", "subprocess", "asyncio"}
        tree = ast.parse((ROOT / "adapters/provider_policy.py").read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                self.assertIn(name.split(".")[0], allowed, name)


if __name__ == "__main__":
    unittest.main()


AGENT_CAP = ("You\u2019ve hit your usage limit. Visit https://chatgpt.com/settings/usage to purchase more credits or try "
             "again at Nov 2nd, 2026 2:38 AM.")
NY = ZoneInfo("America/New_York")


class UsageCapTests(unittest.TestCase):
    """2026-10-27: every Agent account capped for five days; the message has no status and an absolute reset."""

    def test_status_less_usage_cap_is_a_usage_limit_not_transient(self):
        self.assertEqual(classify(ProviderFailure(None, message=AGENT_CAP)), K.USAGE_LIMIT)
        self.assertEqual(classify(ProviderFailure(429, message="Too Many Requests")), K.RATE_LIMITED)
        self.assertEqual(classify(ProviderFailure(None, message="server busy, try again later")), K.TRANSIENT)

    def test_absolute_reset_across_the_daylight_saving_change(self):
        now = datetime(2026, 10, 27, 15, 27, tzinfo=NY).timestamp()
        s = parse_reset(AGENT_CAP, now, NY)
        self.assertEqual(datetime.fromtimestamp(now + s, NY), datetime(2026, 11, 2, 2, 38, tzinfo=NY))
        self.assertAlmostEqual(s / 3600, 132 + 11 / 60, places=3)       # 5 d 11 h 11 min plus the hour clocks go back
        self.assertEqual(limit_bucket(s), "days")

    def test_relative_and_partial_resets(self):
        now = datetime(2026, 12, 30, 23, 0, tzinfo=NY).timestamp()
        self.assertEqual(parse_reset("ERROR: 429 Too Many Requests; try again in 120 seconds", now, NY), 120)
        self.assertEqual(parse_reset("Limit reached. Resets in 2h 30m", now, NY), 9000)
        self.assertEqual(parse_reset("try again in 3 days", now, NY), 3 * 86400)
        self.assertEqual(parse_reset("try again at 1:15 AM", now, NY), 2.25 * 3600)        # tomorrow
        jan = parse_reset("resets on Jan 3rd 9:00 AM", now, NY)                           # no year: next January
        self.assertEqual(datetime.fromtimestamp(now + jan, NY), datetime(2027, 1, 3, 9, 0, tzinfo=NY))
        for text in ("try again later", "try again at 25:00", "resets at Foo 3 9:00", ""):
            self.assertIsNone(parse_reset(text, now, NY), text)

    def test_buckets(self):
        self.assertEqual([limit_bucket(x) for x in (None, 60, 900, 901, 6 * 3600, 6 * 3600 + 1)],
                         [None, "minutes", "minutes", "hours", "hours", "days"])

    def test_reset_after_prefers_the_transport_value(self):
        self.assertEqual(reset_after(ProviderFailure(429, message=AGENT_CAP, retry_after_s=42), 0, NY), 42)

    def test_planner_waits_for_a_short_cap_and_stops_on_a_long_one(self):
        clock = Clock(datetime(2026, 10, 27, 15, 27, tzinfo=NY).timestamp())
        one = (Route("only", "openai", "gpt", "restricted"),)
        p = planner("internal", one, clock)
        d = p.on_failure(ProviderFailure(None, message="You have hit your usage limit; try again in 10 minutes"))
        self.assertEqual((d.action, d.delay_s), ("wait", 600))
        p = planner("internal", one, clock)
        d = p.on_failure(ProviderFailure(None, message=AGENT_CAP))
        self.assertEqual(d.action, "stop")
        self.assertIn("(days)", d.reason)

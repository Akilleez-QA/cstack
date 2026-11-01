import io
import json
import unittest

from foundation_film_bridge.server import Bridge, LIMITS, decode_frame, serve


class RequirementLimitsTests(unittest.TestCase):
    def test_req_film_012_input_limits(self):
        """REQ-FILM-012: accept each input limit and reject one unit beyond it."""
        cases = {
            "frame": (
                b"{}" + b" " * (LIMITS["inputFrameBytes"] - 2),
                b"{}" + b" " * (LIMITS["inputFrameBytes"] - 1),
                {},
                "Input frame exceeds bridge byte limit",
            ),
            "depth": (
                b"[" * LIMITS["jsonDepth"] + b"]" * LIMITS["jsonDepth"],
                b"[" * (LIMITS["jsonDepth"] + 1) + b"]" * (LIMITS["jsonDepth"] + 1),
                json.loads("[" * LIMITS["jsonDepth"] + "]" * LIMITS["jsonDepth"]),
                "JSON nesting exceeds bridge limit",
            ),
            "nodes": (
                json.dumps([0] * (LIMITS["jsonNodes"] - 1)).encode(),
                json.dumps([0] * LIMITS["jsonNodes"]).encode(),
                [0] * (LIMITS["jsonNodes"] - 1),
                "JSON node count exceeds bridge limit",
            ),
            "string": (
                json.dumps("x" * LIMITS["stringCharacters"]).encode(),
                json.dumps("x" * (LIMITS["stringCharacters"] + 1)).encode(),
                "x" * LIMITS["stringCharacters"],
                "JSON string exceeds bridge limit",
            ),
        }
        for sign in ("", "-"):
            cases["integer" + sign] = (
                (sign + "9" * LIMITS["integerDigits"]).encode(),
                (sign + "1" + "0" * LIMITS["integerDigits"]).encode(),
                int(sign + "9" * LIMITS["integerDigits"]),
                "JSON integer exceeds bridge limit",
            )
        for label, (accepted, rejected, expected, message) in cases.items():
            with self.subTest(limit=label):
                self.assertEqual(decode_frame(accepted), expected)
                self.assertEqual(Bridge().handle(rejected), {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32002, "message": message},
                })

    def test_req_film_012_stream_frame_limit(self):
        """REQ-FILM-012: enforce the byte limit on the bridge's input stream."""
        ping = b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
        frame = ping + b" " * (LIMITS["inputFrameBytes"] - len(ping))
        for excess in (0, 1):
            with self.subTest(excess_bytes=excess):
                source = io.BytesIO(frame + b" " * excess + b"\n" + ping + b"\n")
                sink = io.BytesIO()
                status = serve(source, sink)
                replies = [json.loads(line) for line in sink.getvalue().splitlines()]
                if excess:
                    self.assertEqual(status, 2)
                    self.assertEqual(len(replies), 1)
                    self.assertEqual(replies[0]["error"]["code"], -32002)
                else:
                    self.assertEqual(status, 0)
                    self.assertEqual(replies, [{"jsonrpc": "2.0", "id": 1, "result": {}}] * 2)

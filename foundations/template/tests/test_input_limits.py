import io
import json
import unittest

from foundation_template_bridge.server import LIMITS, WireError, decode_frame, serve


class InputLimitTests(unittest.TestCase):
    """REQ-TPL-007: reject inputs beyond every advertised input limit."""

    def assert_limit_rejected(self, frame):
        with self.assertRaises(WireError) as caught:
            decode_frame(frame)
        self.assertEqual(caught.exception.code, -32002)

    def test_req_tpl_007_frame_bytes(self):
        frame = b"0" + b" " * (LIMITS["inputFrameBytes"] - 1)
        self.assertEqual(decode_frame(frame), 0)
        self.assert_limit_rejected(frame + b" ")

    def test_req_tpl_007_stream_frame_bytes(self):
        request = b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
        frame = request.ljust(LIMITS["inputFrameBytes"], b" ")
        for extra, expected_status in ((b"", 0), (b" ", 2)):
            with self.subTest(extra_bytes=len(extra)):
                sink = io.BytesIO()
                status = serve(io.BytesIO(frame + extra + b"\n"), sink)
                self.assertEqual(status, expected_status)
                reply = json.loads(sink.getvalue())
                if extra:
                    self.assertEqual(reply["error"]["code"], -32002)
                else:
                    self.assertEqual(reply, {"jsonrpc": "2.0", "id": 1, "result": {}})

    def test_req_tpl_007_depth(self):
        depth = LIMITS["jsonDepth"]
        frame = b"[" * depth + b"0" + b"]" * depth
        value = decode_frame(frame)
        for _ in range(depth):
            self.assertEqual(len(value), 1)
            value = value[0]
        self.assertEqual(value, 0)
        self.assert_limit_rejected(b"[" + frame + b"]")

    def test_req_tpl_007_nodes(self):
        value = [None] * (LIMITS["jsonNodes"] - 1)
        self.assertEqual(decode_frame(json.dumps(value).encode()), value)
        self.assert_limit_rejected(json.dumps(value + [None]).encode())

    def test_req_tpl_007_string_characters(self):
        text = "x" * LIMITS["stringCharacters"]
        for value, oversized in ((text, text + "x"), ({text: 0}, {text + "x": 0})):
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(decode_frame(json.dumps(value).encode()), value)
                self.assert_limit_rejected(json.dumps(oversized).encode())

    def test_req_tpl_007_integer_digits(self):
        digits = b"9" * LIMITS["integerDigits"]
        for sign in (b"", b"-"):
            with self.subTest(sign=sign):
                self.assertEqual(decode_frame(sign + digits), int(sign + digits))
                self.assert_limit_rejected(sign + digits + b"9")

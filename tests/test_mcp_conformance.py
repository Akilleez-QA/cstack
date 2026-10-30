"""MCP conformance of the stdio server (parts-wall MCP chop, items S2-S4, S7-S10, S12), in process."""
import io
import json
import sys
import unittest
from pathlib import Path

from tests.aor_fixtures import DOMAIN, HAVE_CRYPTO, NO_CRYPTO, write_witnessed_config
from tests.test_aor_session import SessionCase

GOLDEN = Path(__file__).resolve().parent / "fixtures/mcp_tools_list.json"
READ_ONLY = {"aor", "ledger"}


def setUpModule():
    # Discovery must not make Scheduled's host-only tools look like they run inside a bot.
    global MAX_FRAME
    from adapters.mcp_stdio_server import MAX_FRAME


def tearDownModule():
    sys.modules.pop("adapters.mcp_stdio_server", None)


class StubSession:
    def aor(self):
        raise KeyError("boom")  # an unexpected, non-contract failure

    def ledger(self, domain=None, last=20):
        return {"head": None, "events": [], "bad": {1, 2}}  # not JSON-serializable: a tool error


class BoundedStream(io.BytesIO):
    largest = 0

    def readline(self, size=-1):
        BoundedStream.largest = max(BoundedStream.largest, size)
        return super().readline(size)


def frames(*messages):
    return b"".join((m if type(m) is bytes else json.dumps(m).encode()) + b"\n" for m in messages)


def run(*messages, session=None, initialize=True):
    from adapters.mcp_stdio_server import McpServer

    first = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}] if initialize else []
    out = io.StringIO()
    McpServer(session or StubSession()).serve(BoundedStream(frames(*first, *messages)), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    return replies[1:] if initialize else replies


def call(ident, name, arguments=None):
    params = {"name": name, **({} if arguments is None else {"arguments": arguments})}
    return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": params}


PING = {"jsonrpc": "2.0", "id": 99, "method": "ping"}


class ConformanceTests(unittest.TestCase):
    def test_golden_tools_list(self):
        """Any change to a tool's name, schema or annotations must update tests/fixtures/mcp_tools_list.json."""
        [listed] = run({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(listed["result"], json.loads(GOLDEN.read_text()))
        for tool in listed["result"]["tools"]:
            hints = tool["annotations"]
            self.assertEqual(hints["readOnlyHint"], tool["name"] in READ_ONLY, tool["name"])
            self.assertEqual(hints["destructiveHint"], tool["name"] == "execute", tool["name"])

    def test_unexpected_exceptions_are_internal_errors_and_serving_continues(self):
        crash, unserializable, ping = run(call(1, "aor", {}), call(2, "ledger", {"domain": DOMAIN}), PING)
        self.assertEqual((crash["id"], crash["error"]["code"]), (1, -32603))
        self.assertTrue(unserializable["result"]["isError"])
        self.assertEqual(ping["result"], {})

    def test_unknown_tool_and_non_object_arguments_are_invalid_params(self):
        replies = run(call(1, "nope", {}), call(2, "aor", []), call(3, "aor", "x"), PING)
        self.assertEqual([r["error"]["code"] for r in replies[:3]], [-32602] * 3)
        self.assertEqual(replies[3]["id"], 99)

    def test_null_id_is_never_answered_and_bad_ids_are_invalid_requests(self):
        replies = run({"jsonrpc": "2.0", "id": None, "method": "ping"},
                      {"jsonrpc": "2.0", "id": True, "method": "ping"},
                      {"jsonrpc": "2.0", "id": 1.5, "method": "ping"}, PING)
        self.assertEqual([(r["id"], r.get("error", {}).get("code")) for r in replies],
                         [(None, -32600), (None, -32600), (99, None)])

    def test_not_initialized_has_its_own_code(self):
        [reply] = run({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, initialize=False)
        self.assertEqual(reply["error"]["code"], -32000)

    def test_oversized_frame_is_refused_with_a_bounded_read(self):
        BoundedStream.largest = 0
        oversized, ping = run(b'{"x":"' + b"a" * (3 * MAX_FRAME) + b'"}', PING)
        self.assertEqual((oversized["error"]["code"], ping["id"]), (-32600, 99))
        self.assertEqual(BoundedStream.largest, MAX_FRAME + 2)


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class AnchorFailureTests(SessionCase):
    def test_an_anchor_that_cannot_be_saved_never_hides_or_crashes_execute(self):
        write_witnessed_config(self.state)
        session = self.open()
        _, decision = self.run_to_execute(session)
        (self.state / "alpha/anchors.tmp").mkdir()  # every later anchor save now fails with an OSError
        result = session.execute(DOMAIN, decision["decision_id"])
        self.assertEqual((result["status"], result["anchor_warning"]), ("executed", "ledger anchor not saved: "
                                                                                    "IsADirectoryError"))
        [crash, ping] = run(call(1, "start_goal", {"domain": DOMAIN, "objective": "x", "acceptance_criteria": ["y"]}),
                            PING, session=session)
        self.assertEqual((crash["error"]["code"], ping["id"]), (-32603, 99))



if __name__ == "__main__":
    unittest.main()

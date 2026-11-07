import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from adapters.relay_outbox import RelayStore

CONTEXT = multiprocessing.get_context("fork")


def click(root, go):
    store = RelayStore(root)
    go.wait()
    store.send("auto", "hello", client_id="click-1")


class RelayOutboxFailures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = RelayStore(str(self.root))

    def tear_outbox(self):
        with open(self.store.outbox, "a") as stream:
            stream.write('{"id": "m-torn", "at": 1, "te')

    def test_a_retried_click_from_several_processes_sends_once(self):
        for trial in range(10):
            root = self.root / str(trial)
            root.mkdir()
            go = CONTEXT.Event()
            clicks = [CONTEXT.Process(target=click, args=(str(root), go)) for _ in range(4)]
            for process in clicks:
                process.start()
            go.set()
            for process in clicks:
                process.join()
            self.assertEqual(len(RelayStore(str(root)).messages()), 1)

    def test_a_torn_outbox_tail_does_not_stop_the_relay(self):
        first = self.store.send("auto", "first")
        self.tear_outbox()
        self.assertEqual([m["id"] for m in self.store.pending()], [first["id"]])
        self.assertEqual(self.store.unreadable(), 1)

    def test_the_message_after_a_torn_tail_is_kept(self):
        self.store.send("auto", "first")
        self.tear_outbox()
        after = self.store.send("auto", "second")
        self.assertIn(after["id"], [m["id"] for m in self.store.messages()])
        self.assertEqual(self.store.send("auto", "x", client_id="c")["id"], self.store.send("auto", "x", client_id="c")["id"])

    def test_a_torn_receipt_does_not_lose_the_next_receipt(self):
        message = self.store.send("auto", "first")
        self.store.receipt(message["id"], "claimed")
        with open(self.store.receipts, "a") as stream:
            stream.write('{"id": "' + message["id"] + '", "sta')
        self.store.receipt(message["id"], "failed", note="no session")
        self.assertEqual(self.store.pending(), [])

    def test_an_unreadable_outbox_raises_and_is_not_read_as_empty(self):
        os.mkdir(self.store.outbox)
        with self.assertRaises(OSError):
            self.store.messages()

    def test_a_missing_outbox_is_empty(self):
        self.assertEqual(self.store.messages(), [])
        self.assertEqual(self.store.unreadable(), 0)

    def test_a_line_that_is_not_an_object_counts_as_unreadable(self):
        Path(self.store.outbox).write_text('[1]\n{"id": "m-1", "at": 1}\n')
        self.assertEqual(json.dumps([m["id"] for m in self.store.messages()]), '["m-1"]')
        self.assertEqual(self.store.unreadable(), 1)


if __name__ == "__main__":
    unittest.main()

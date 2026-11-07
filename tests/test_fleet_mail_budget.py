import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from adapters.fleet_mail import SendBudget
from poodo_core.models import ContractError

CONTEXT = multiprocessing.get_context("fork")


def takes(path, go, allowed):
    budget = SendBudget(path, 20, lambda: 1000)
    go.wait()
    for _ in range(10):
        if budget.take()[0]:
            with allowed.get_lock():
                allowed.value += 1


class SendBudgetFailures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "budget.json"

    def budget(self, limit=2):
        return SendBudget(self.path, limit, lambda: 1000)

    def test_an_emptied_budget_file_refuses_instead_of_starting_over(self):
        budget = self.budget()
        budget.take()
        budget.take()
        budget.remember({"nonce-a": 7})
        self.path.write_text("")
        with self.assertRaises(ContractError):
            budget.take()
        with self.assertRaises(ContractError):
            budget.remember({"nonce-a": 8})

    def test_a_state_that_cannot_be_synced_is_not_counted_and_the_last_one_stays(self):
        budget = self.budget()
        budget.take()
        before = self.path.read_bytes()
        with mock.patch("adapters.fleet_mail.os.fsync", side_effect=OSError(5, "I/O error")):
            with self.assertRaises(OSError):
                budget.take()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(budget.status()["used"], 1)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir() if not p.name.endswith(".lock")), ["budget.json"])

    def test_a_missing_file_is_a_fresh_budget(self):
        self.assertEqual(self.budget().status()["used"], 0)

    def test_takes_from_several_processes_never_pass_the_limit(self):
        go, allowed = CONTEXT.Event(), CONTEXT.Value("i", 0)
        workers = [CONTEXT.Process(target=takes, args=(self.path, go, allowed)) for _ in range(4)]
        for worker in workers:
            worker.start()
        go.set()
        for worker in workers:
            worker.join()
        self.assertEqual(allowed.value, 20)
        self.assertEqual(SendBudget(self.path, 20, lambda: 1000).status()["used"], 20)

    def test_the_budget_file_and_its_lock_are_private(self):
        self.budget().take()
        for path in (self.path, self.path.with_name(self.path.name + ".lock")):
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()

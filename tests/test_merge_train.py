"""merge_train.consider: drafts are never offered for merge, even when clean and in scope."""
import argparse
import importlib.util
import pathlib
import unittest
from unittest import mock

TOOL = pathlib.Path(__file__).resolve().parent.parent / 'tools' / 'merge_train.py'
SPEC = importlib.util.spec_from_file_location('merge_train', TOOL)
train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(train)

ARGS = argparse.Namespace(dry_run=True, policy='all')
PR = {'number': 7, 'headRefName': 'worker/20261027-x', 'baseRefName': 'main'}


def detail(**over):
    d = {'files': [{'path': 'upstream/game/x.md'}], 'body': 'Local checks\n- `true` -> ok',
         'mergeable': 'MERGEABLE', 'mergeStateStatus': 'CLEAN', 'baseRefName': 'main', 'state': 'OPEN', 'isDraft': False}
    d.update(over)
    return d


class DraftTests(unittest.TestCase):
    def consider(self, d):
        with mock.patch.object(train, 'pr_detail', return_value=d), \
             mock.patch.object(train, 'in_scope', return_value=True), \
             mock.patch.object(train, 'has_checks', return_value=True):
            return train.consider(PR, {}, set(), {}, ARGS)

    def test_draft_is_skipped(self):
        self.assertEqual(self.consider(detail(isDraft=True)), ('skip', 'draft'))

    def test_ready_pr_is_offered(self):
        self.assertEqual(self.consider(detail()), ('merged', ''))


if __name__ == '__main__':
    unittest.main()

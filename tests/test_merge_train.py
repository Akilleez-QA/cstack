"""merge_train.consider: drafts are never offered, and a PR merges only on CI GitHub recorded for its head commit."""
import argparse
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

TOOL = pathlib.Path(__file__).resolve().parent.parent / 'tools' / 'merge_train.py'
SPEC = importlib.util.spec_from_file_location('merge_train', TOOL)
train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(train)

ARGS = argparse.Namespace(dry_run=True, policy='all')
PR = {'number': 7, 'headRefName': 'worker/20261027-x', 'baseRefName': 'main'}
CLAIM = 'Local checks\n- `python -m unittest` -> ok\nAll checks PASS'


def detail(**over):
    d = {'files': [{'path': 'upstream/game/x.md'}], 'body': CLAIM,
         'mergeable': 'MERGEABLE', 'mergeStateStatus': 'CLEAN', 'baseRefName': 'main', 'state': 'OPEN', 'isDraft': False}
    d.update(over)
    return d


def run(name, conclusion='SUCCESS', status='COMPLETED'):
    return {'__typename': 'CheckRun', 'name': name, 'status': status, 'conclusion': conclusion, 'workflowName': 'ci'}


GREEN = [run('test'), run('secrets')]


class Train(unittest.TestCase):
    def consider(self, d, rollup=GREEN, head='abc123'):
        with mock.patch.object(train, 'pr_detail', return_value=d), \
             mock.patch.object(train, 'in_scope', return_value=True), \
             mock.patch.object(train, 'gh', return_value='{"headRefOid": "%s", "statusCheckRollup": %s}'
                               % (head, json.dumps(rollup))):
            return train.consider(PR, {}, set(), {}, ARGS)

    def test_draft_is_skipped(self):
        self.assertEqual(self.consider(detail(isDraft=True)), ('skip', 'draft'))

    def test_ready_pr_with_recorded_green_ci_is_offered(self):
        self.assertEqual(self.consider(detail()), ('merged', ''))

    def test_E1_a_body_that_claims_checks_passed_is_never_evidence(self):
        # Ten seeded PRs whose bodies all claim the checks passed; none has passing CI recorded on its head commit.
        seeded = (
            [], [run('test')], [run('secrets')], [run('test', 'FAILURE'), run('secrets')],
            [run('test', None, 'IN_PROGRESS'), run('secrets')], [run('test', None, 'QUEUED'), run('secrets')],
            [run('test', 'CANCELLED'), run('secrets')], [run('test', 'TIMED_OUT'), run('secrets')],
            GREEN + [run('extra', 'FAILURE')],
            [run('test', 'SKIPPED'), run('secrets')],
        )
        verdicts = [self.consider(detail(), rollup) for rollup in seeded]
        self.assertEqual([v[0] for v in verdicts], ['skip'] * 10, verdicts)

    def test_a_pending_status_context_blocks_the_merge(self):
        self.assertEqual(self.consider(detail(), GREEN + [{'__typename': 'StatusContext', 'context': 'x', 'state': 'PENDING'}])[0],
                         'skip')

    def test_a_pr_that_changes_ci_is_left_for_review(self):
        verdict = self.consider(detail(files=[{'path': '.github/workflows/ci.yml'}]))
        self.assertEqual(verdict, ('skip', 'changes CI itself (.github/); needs review'))

    def test_the_merge_is_pinned_to_the_checked_head_commit(self):
        args = argparse.Namespace(dry_run=False, policy='all')
        done = mock.Mock(returncode=0, stderr='')
        with mock.patch.object(train, 'pr_detail', return_value=detail()), \
             mock.patch.object(train, 'in_scope', return_value=True), \
             mock.patch.object(train, 'wait_mergeable', return_value=detail()), \
             mock.patch.object(train, 'head_checks', return_value=('abc123', None)), \
             mock.patch.object(train.subprocess, 'run', return_value=done) as merge:
            self.assertEqual(train.consider(PR, {}, set(), {}, args), ('merged', ''))
        self.assertEqual(merge.call_args.args[0], ['gh', 'pr', 'merge', '7', '--squash', '--match-head-commit', 'abc123'])


if __name__ == '__main__':
    unittest.main()

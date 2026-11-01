import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from adapters import workspace_snapshots as ws

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


class SnapshotCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        git(self.repo, "init", "-q", "-b", "main")
        self.write(".gitignore", "*.log\n")
        self.write("a.txt", "a1\n")
        self.write("src/b.txt", "b1\n")
        for args in (("config", "user.name", "t"), ("config", "user.email", "t@x.invalid"), ("add", "-A"),
                     ("commit", "-q", "-m", "init")):
            git(self.repo, *args)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def read(self, name):
        return (self.repo / name).read_text()

    def user_state(self):
        index = hashlib.sha256((self.repo / ".git/index").read_bytes()).hexdigest()
        return (index, git(self.repo, "rev-parse", "HEAD"), git(self.repo, "symbolic-ref", "HEAD"),
                git(self.repo, "for-each-ref", "refs/heads", "refs/tags", "refs/stash"),
                git(self.repo, "stash", "list"))


class Capture(SnapshotCase):
    def test_capture_leaves_index_head_branches_and_stash_unchanged(self):
        self.write("a.txt", "a2\n")
        self.write("new.txt", "n\n")
        git(self.repo, "add", "a.txt")  # staged change must survive untouched
        before = self.user_state()
        receipt = ws.capture(self.repo, label="t")
        self.assertEqual(self.user_state(), before)
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["ref"].startswith("refs/cstack/snapshots/"))
        self.assertEqual(git(self.repo, "branch", "--list").split(), ["*", "main"])
        files = git(self.repo, "ls-tree", "-r", "--name-only", receipt["tree"]).split()
        self.assertEqual(sorted(files), [".gitignore", "a.txt", "new.txt", "src/b.txt"])

    def test_ignored_files_are_not_captured_or_deleted(self):
        self.write("debug.log", "noise\n")
        snap = ws.capture(self.repo)
        self.assertNotIn("debug.log", git(self.repo, "ls-tree", "-r", "--name-only", snap["tree"]))
        self.write("a.txt", "a2\n")
        ws.capture(self.repo)
        ws.restore(self.repo, snap["snapshot_id"])
        self.assertEqual(self.read("debug.log"), "noise\n")

    def test_caps_submodules_and_nested_repos_are_refused(self):
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.capture(self.repo, max_bytes=4)
        self.assertEqual(ctx.exception.receipt["reason"], "size_cap_exceeded")
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.capture(self.repo, max_files=1)
        self.assertEqual(ctx.exception.receipt["reason"], "file_cap_exceeded")
        nested = self.repo / "vendor/inner"
        nested.mkdir(parents=True)
        git(nested, "init", "-q")
        git(nested, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "x")
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.capture(self.repo)
        self.assertEqual(ctx.exception.receipt["reason"], "nested_repository_unsupported")
        self.write(".gitmodules", "")
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.capture(self.repo)
        self.assertEqual(ctx.exception.receipt["reason"], "submodules_unsupported")
        self.assertEqual(ws.list_snapshots(self.repo), [])


class RestoreAndDiff(SnapshotCase):
    def test_untracked_files_are_captured_and_restored(self):
        self.write("notes/todo.txt", "keep me\n")
        snap = ws.capture(self.repo)
        (self.repo / "notes/todo.txt").unlink()
        self.write("a.txt", "a2\n")
        self.write("stray.txt", "s\n")
        ws.capture(self.repo)
        receipt = ws.restore(self.repo, snap["snapshot_id"])
        self.assertTrue(receipt["verified"])
        self.assertEqual(self.read("notes/todo.txt"), "keep me\n")
        self.assertEqual(self.read("a.txt"), "a1\n")
        self.assertFalse((self.repo / "stray.txt").exists())
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.repo, "rev-parse", "main"))

    def test_partial_restore_touches_only_selected_paths(self):
        snap = ws.capture(self.repo)
        self.write("a.txt", "a2\n")
        self.write("src/b.txt", "b2\n")
        self.write("src/c.txt", "c\n")
        ws.capture(self.repo)
        receipt = ws.restore(self.repo, snap["snapshot_id"], paths=["src"])
        self.assertEqual((receipt["written"], receipt["deleted_count"], receipt["verified"]), (1, 1, True))
        self.assertEqual(self.read("a.txt"), "a2\n")
        self.assertEqual(self.read("src/b.txt"), "b1\n")
        self.assertFalse((self.repo / "src/c.txt").exists())
        with self.assertRaises(ws.SnapshotRefused):
            ws.restore(self.repo, snap["snapshot_id"], paths=["../escape"])

    def test_restore_refuses_unsnapshotted_changes_unless_forced(self):
        snap = ws.capture(self.repo)
        self.write("a.txt", "unsaved work\n")
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.restore(self.repo, snap["snapshot_id"])
        self.assertEqual(ctx.exception.receipt["reason"], "unsnapshotted_changes")
        self.assertEqual(ctx.exception.receipt["pending"]["modified"], ["a.txt"])
        self.assertEqual(self.read("a.txt"), "unsaved work\n")
        receipt = ws.restore(self.repo, snap["snapshot_id"], force=True)
        self.assertTrue(receipt["forced"] and receipt["verified"])
        self.assertEqual(self.read("a.txt"), "a1\n")

    def test_diff_between_snapshots_and_against_worktree(self):
        first = ws.capture(self.repo)
        self.write("a.txt", "a2\n")
        self.write("new.txt", "n\n")
        (self.repo / "src/b.txt").unlink()
        second = ws.capture(self.repo)
        d = ws.diff(self.repo, first["snapshot_id"], second["snapshot_id"])
        self.assertEqual((d["added"], d["modified"], d["deleted"]), (["new.txt"], ["a.txt"], ["src/b.txt"]))
        self.write("later.txt", "l\n")
        live = ws.diff(self.repo, second["snapshot_id"])
        self.assertEqual((live["to"], live["added_count"], live["modified_count"]), ("worktree", 1, 0))
        with self.assertRaises(ws.SnapshotRefused) as ctx:
            ws.diff(self.repo, "00000000000000000000-000000000000")
        self.assertEqual(ctx.exception.receipt["reason"], "unknown_snapshot")


class Prune(SnapshotCase):
    def test_prune_removes_only_old_snapshot_refs(self):
        ids = []
        for i in range(4):
            self.write("a.txt", "v%d\n" % i)
            ids.append(ws.capture(self.repo)["snapshot_id"])
        heads = git(self.repo, "for-each-ref", "refs/heads")
        receipt = ws.prune(self.repo, keep=2)
        self.assertEqual((receipt["removed"], receipt["kept"]), (ids[:2], ids[2:]))
        self.assertEqual([s["snapshot_id"] for s in ws.list_snapshots(self.repo)], ids[2:])
        self.assertEqual(git(self.repo, "for-each-ref", "refs/heads"), heads)
        self.assertEqual(ws.prune(self.repo, keep=0)["removed"], ids[2:])
        with self.assertRaises(ws.SnapshotRefused):
            ws.prune(self.repo, keep=-1)


class SnapshotStep(SnapshotCase):
    def run_step(self, *command):
        return subprocess.run([sys.executable, "-B", str(ROOT / "tools/snapshot_step.py"), str(self.repo), "--",
                               *command], capture_output=True, text=True, timeout=120)

    def test_step_captures_before_and_after_and_reports_the_diff(self):
        script = "import pathlib; pathlib.Path('a.txt').write_text('edited\\n'); pathlib.Path('made.txt').write_text('m\\n')"
        result = self.run_step(sys.executable, "-c", script)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["ok"])
        self.assertEqual((receipt["diff"]["modified"], receipt["diff"]["added"]), (["a.txt"], ["made.txt"]))
        undo = ws.restore(self.repo, receipt["before"])
        self.assertTrue(undo["verified"])
        self.assertEqual(self.read("a.txt"), "a1\n")
        self.assertFalse((self.repo / "made.txt").exists())

    def test_step_passes_through_failure_and_refuses_unsnapshottable_repo(self):
        result = self.run_step(sys.executable, "-c", "import sys; print('noise'); sys.exit(5)")
        self.assertEqual(result.returncode, 5)
        self.assertEqual(json.loads(result.stdout)["exit_code"], 5)
        self.assertIn("noise", result.stderr)
        self.write(".gitmodules", "")
        result = self.run_step(sys.executable, "-c", "open('ran.txt', 'w')")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["refusal"]["reason"], "submodules_unsupported")
        self.assertFalse((self.repo / "ran.txt").exists())


if __name__ == "__main__":
    unittest.main()

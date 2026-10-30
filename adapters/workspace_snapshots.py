"""Workspace snapshots: per-step capture, diff and restore of a git working tree (endoforge.activate).

A snapshot is a parentless commit of the whole working tree (tracked and untracked, .gitignore
respected) written through a private GIT_INDEX_FILE under refs/cstack/snapshots/<worktree-key>/<id>.
The user's index, HEAD, branches and stash are never written. Patterns from parts-wall parts
oss-opencode-shadow-git-snapshots and oss-t3code-hidden-ref-checkpoints. Ignored files, the git dir
and submodules are out of scope: a rollback aid, not a sandbox or backup. Each operation returns a
receipt dict for a POODO ledger event; a refusal raises SnapshotRefused carrying its receipt.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path, PurePosixPath

SCHEMA = "cstack.workspace-snapshot/0.1"
REF_ROOT = "refs/cstack/snapshots"
MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 50_000
LIST_CAP = 200  # paths listed per change kind in a receipt; counts are always exact
_ID = re.compile(r"^\d{20}-[0-9a-f]{12}$")
_SCRUB = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE",
          "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX", "GIT_COMMON_DIR")
_IDENT = {"GIT_AUTHOR_NAME": "cstack-snapshots", "GIT_AUTHOR_EMAIL": "snapshots@cstack.invalid",
          "GIT_COMMITTER_NAME": "cstack-snapshots", "GIT_COMMITTER_EMAIL": "snapshots@cstack.invalid"}


class SnapshotRefused(Exception):
    def __init__(self, operation, reason, **detail):
        super().__init__(reason)
        self.receipt = _receipt(operation, ok=False, reason=reason, **detail)


def _receipt(operation, **fields):
    return {"schema": SCHEMA, "operation": operation, **fields}


def _git(top, *args, index=None, data=None, check=True):
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update(_IDENT, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_LITERAL_PATHSPECS="1")
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    r = subprocess.run(["git", "-C", str(top), *args], input=data, capture_output=True, env=env, timeout=300)
    if check and r.returncode:
        raise RuntimeError("git %s failed: %s" % (args[0], r.stderr.decode(errors="replace").strip()[:500]))
    return r.stdout


def _toplevel(repo, op):
    try:
        out = _git(repo, "rev-parse", "--show-toplevel")
    except (RuntimeError, OSError):
        raise SnapshotRefused(op, "not_a_git_worktree", repo=str(repo)) from None
    return Path(out.decode().strip()).resolve()


def _prefix(top):
    return "%s/%s/" % (REF_ROOT, hashlib.sha256(str(top).encode()).hexdigest()[:16])


def _write_tree(top, op, max_bytes, max_files):
    """Write the current working tree as a git tree object. Touches no ref and not the user's index."""
    if (top / ".gitmodules").exists():
        raise SnapshotRefused(op, "submodules_unsupported", repo=str(top))
    listed = set(_git(top, "ls-files", "-z", "-c", "-o", "--exclude-standard").split(b"\0")) - {b""}
    if len(listed) > max_files:
        raise SnapshotRefused(op, "file_cap_exceeded", files=len(listed), max_files=max_files)
    size = 0
    for name in listed:
        try:
            size += os.lstat(top / os.fsdecode(name)).st_size
        except FileNotFoundError:
            pass
    if size > max_bytes:
        raise SnapshotRefused(op, "size_cap_exceeded", bytes=size, max_bytes=max_bytes)
    with tempfile.TemporaryDirectory(prefix="cstack-snap-") as tmp:
        index = Path(tmp, "index")
        user_index = top / _git(top, "rev-parse", "--git-path", "index").decode().strip()
        if user_index.is_file():
            shutil.copy2(user_index, index)
        _git(top, "add", "-A", index=index)
        tree = _git(top, "write-tree", index=index).decode().strip()
    if any(e.startswith(b"160000 ") for e in _git(top, "ls-tree", "-r", "-z", tree).split(b"\0")):
        raise SnapshotRefused(op, "nested_repository_unsupported", repo=str(top))
    return tree, len(listed), size


def _changes(top, old, new, paths=None):
    out = _git(top, "diff-tree", "-r", "-z", "--no-renames", "--name-status", old, new, "--", *(paths or ()))
    parts = out.split(b"\0")
    changes = {"added": [], "modified": [], "deleted": []}
    for status, name in zip(parts[0::2], parts[1::2]):
        kind = {b"A": "added", b"D": "deleted"}.get(status[:1], "modified")
        changes[kind].append(os.fsdecode(name))
    return changes


def _summary(changes):
    out = {k + "_count": len(v) for k, v in changes.items()}
    out.update({k: v[:LIST_CAP] for k, v in changes.items()})
    out["truncated"] = any(len(v) > LIST_CAP for v in changes.values())
    return out


def list_snapshots(repo):
    top = _toplevel(repo, "list")
    out = _git(top, "for-each-ref", "--sort=refname", "--format=%(refname) %(objectname) %(tree)", _prefix(top))
    rows = [line.split(" ") for line in out.decode().splitlines() if line]
    return [{"snapshot_id": ref.rsplit("/", 1)[1], "ref": ref, "commit": c, "tree": t} for ref, c, t in rows]


def _resolve(top, op, snapshot_id):
    if not isinstance(snapshot_id, str) or not _ID.match(snapshot_id):
        raise SnapshotRefused(op, "bad_snapshot_id", snapshot_id=str(snapshot_id))
    for snap in list_snapshots(top):
        if snap["snapshot_id"] == snapshot_id:
            return snap
    raise SnapshotRefused(op, "unknown_snapshot", snapshot_id=snapshot_id)


def capture(repo, *, label=None, max_bytes=MAX_BYTES, max_files=MAX_FILES):
    """Record the full working tree. Returns a receipt whose snapshot_id names the snapshot."""
    top = _toplevel(repo, "capture")
    tree, files, size = _write_tree(top, "capture", max_bytes, max_files)
    head = _git(top, "rev-parse", "-q", "--verify", "HEAD", check=False).decode().strip() or None
    meta = json.dumps({"schema": SCHEMA, "worktree": str(top), "head": head, "label": label}, sort_keys=True)
    commit = _git(top, "commit-tree", tree, "-m", "cstack workspace snapshot\n\n" + meta).decode().strip()
    snapshot_id = "%020d-%s" % (time.time_ns(), commit[:12])
    ref = _prefix(top) + snapshot_id
    _git(top, "update-ref", "-m", "cstack snapshot", ref, commit, "")  # "" = ref must not exist yet
    return _receipt("capture", ok=True, repo=str(top), snapshot_id=snapshot_id, ref=ref, commit=commit,
                    tree=tree, head=head, files=files, bytes=size, label=label)


def diff(repo, snapshot_a, snapshot_b=None, *, max_bytes=MAX_BYTES, max_files=MAX_FILES):
    """File-level changes from snapshot_a to snapshot_b, or to the current worktree when b is None."""
    top = _toplevel(repo, "diff")
    a = _resolve(top, "diff", snapshot_a)
    b_tree = _resolve(top, "diff", snapshot_b)["tree"] if snapshot_b else _write_tree(top, "diff", max_bytes, max_files)[0]
    return _receipt("diff", ok=True, repo=str(top), from_snapshot=snapshot_a, to=snapshot_b or "worktree",
                    **_summary(_changes(top, a["tree"], b_tree)))


def _clean_paths(paths):
    clean = []
    for p in paths:
        pure = PurePosixPath(str(p))
        if not str(p) or pure.is_absolute() or ".." in pure.parts or (pure.parts and pure.parts[0] == ".git"):
            raise SnapshotRefused("restore", "bad_path", path=str(p))
        clean.append(str(pure))
    return clean


def restore(repo, snapshot_id, paths=None, *, force=False, max_bytes=MAX_BYTES, max_files=MAX_FILES):
    """Make the worktree (or just `paths`) match a snapshot. Refuses unrecorded changes unless force."""
    top = _toplevel(repo, "restore")
    snap = _resolve(top, "restore", snapshot_id)
    paths = _clean_paths(paths) if paths is not None else None
    if paths == []:
        raise SnapshotRefused("restore", "empty_path_list")
    current = _write_tree(top, "restore", max_bytes, max_files)[0]
    if not force and current not in {s["tree"] for s in list_snapshots(top)}:
        pending = _summary(_changes(top, snap["tree"], current))
        raise SnapshotRefused("restore", "unsnapshotted_changes", snapshot_id=snapshot_id, worktree_tree=current,
                              hint="capture() first, or pass force=True", pending=pending)
    changes = _changes(top, current, snap["tree"], paths)
    for name in changes["deleted"]:
        target = top / name
        if target.is_symlink() or target.is_file():
            target.unlink()
        parent = target.parent
        while parent != top and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    write = changes["added"] + changes["modified"]
    if write:
        with tempfile.TemporaryDirectory(prefix="cstack-snap-") as tmp:
            index = Path(tmp, "index")
            _git(top, "read-tree", snap["tree"], index=index)
            _git(top, "checkout-index", "-f", "-z", "--stdin", index=index,
                 data=b"".join(os.fsencode(n) + b"\0" for n in write))
    after = _write_tree(top, "restore", max_bytes, max_files)[0]
    remaining = _changes(top, after, snap["tree"], paths)
    return _receipt("restore", ok=True, repo=str(top), snapshot_id=snapshot_id, paths=paths, forced=force,
                    worktree_tree_before=current, written=len(write),
                    verified=not any(remaining.values()), **_summary(changes))


def prune(repo, keep):
    """Delete all but the newest `keep` snapshot refs for this worktree. Objects are left to git gc."""
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 0:
        raise SnapshotRefused("prune", "bad_keep", keep=str(keep))
    top = _toplevel(repo, "prune")
    snaps = list_snapshots(top)
    doomed = snaps[:len(snaps) - keep] if keep else snaps
    for snap in doomed:
        _git(top, "update-ref", "-d", snap["ref"], snap["commit"])
    return _receipt("prune", ok=True, repo=str(top), keep=keep, removed=[s["snapshot_id"] for s in doomed],
                    kept=[s["snapshot_id"] for s in snaps[len(doomed):]])

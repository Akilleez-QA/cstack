import os
import sys

try:
    import fcntl
except ImportError:
    fcntl = None

FULL_FSYNC = getattr(fcntl, "F_FULLFSYNC", None) if fcntl else None
DIRECTORY_FLAG = getattr(os, "O_DIRECTORY", None)


def _full_sync(fd):
    if FULL_FSYNC is not None:
        try:
            fcntl.fcntl(fd, FULL_FSYNC)
            return "full_fsync"
        except OSError:
            pass
    os.fsync(fd)
    return "fsync"


def sync_file(fd):
    if FULL_FSYNC is not None:
        return _full_sync(fd)
    os.fsync(fd)
    return "fsync"


def sync_data(fd):
    if FULL_FSYNC is not None:
        return _full_sync(fd)
    datasync = getattr(os, "fdatasync", None)
    if datasync is not None:
        datasync(fd)
        return "fdatasync"
    os.fsync(fd)
    return "fsync"


def sync_dir(path, nofollow=False):
    if DIRECTORY_FLAG is None or sys.platform == "win32":
        return "skipped"
    fd = os.open(path, os.O_RDONLY | DIRECTORY_FLAG | (os.O_NOFOLLOW if nofollow else 0))
    try:
        return sync_file(fd)
    finally:
        os.close(fd)

"""Open a private SQLite database file safely (ADR 003): a 0600 regular file owned by this user, never through a
symlink, in WAL mode with synchronous=FULL, and safe when several processes create it at the same time."""
import os
import sqlite3
import stat
import time
from pathlib import Path

from poodo_core.models import ContractError


def open_private_db(path: Path) -> tuple[sqlite3.Connection, int]:
    """Open or create a 0600 regular file owned by this user, never through a symlink, in WAL mode."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as error:
        raise ContractError(f"Refusing ledger path {path}: {error.strerror}") from None
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ContractError(f"Refusing {path}: it must be a regular 0600 file owned by this user")
    db = sqlite3.connect(path, isolation_level=None, timeout=30)
    for attempt in range(50):
        try:
            if db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal":
                break
        except sqlite3.OperationalError:
            pass
        time.sleep(0.02 * (attempt + 1))
    else:
        db.close()
        os.close(fd)
        raise ContractError("Could not switch the database to WAL mode")
    db.execute("PRAGMA synchronous=FULL")
    return db, fd

import atexit
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import threading
import time

SCHEMA = "memguard-dump/1"
SIGNAL = "SIGUSR2"
REFRESH_SECONDS = 2.0
NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")

_lock = threading.RLock()
_listening = []
_registered = []
_previous = None


def directory(env=None):
    env = os.environ if env is None else env
    state = env.get("XDG_STATE_HOME") or ""
    if not state.startswith("/"):
        state = os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(state) / "memguard" / "dump-list.d"


def enabled(env=None):
    env = os.environ if env is None else env
    flag = env.get("ENDOFORGE_DUMP_LIST")
    if flag == "0":
        return False
    if flag == "1":
        return True
    return directory(env).is_dir()


def write_atomic(folder, name, text):
    temp = Path(folder) / f".{name}.{os.urandom(6).hex()}.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(text.encode())
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        temp.unlink(missing_ok=True)
        raise
    os.close(fd)
    try:
        os.rename(temp, Path(folder) / name)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _on_signal(number, frame):
    for holder in list(_listening):
        holder.shed_now()


class Inert:
    enabled = False
    refused = None
    path = None
    bytes = 0
    writes = 0
    sheds = 0

    def refresh(self, force=False):
        pass

    def shed_now(self):
        pass

    def close(self):
        pass


class Holder:
    def __init__(self, name, priority, measure, shed=None, pid=None, listen=None, folder=None, refresh_seconds=REFRESH_SECONDS):
        self.pid = os.getpid() if pid is None else pid
        self.name, self.priority, self.measure_fn, self.shed_fn = name, priority, measure, shed
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.folder / f"{self.pid}-{name}.json"
        self.refresh_seconds = refresh_seconds
        self.enabled = True
        self.bytes = self.writes = self.sheds = self.errors = 0
        self.last, self.checked, self.timer, self.closed, self.shedding = -1, 0.0, None, False, False
        self.listen = self.pid == os.getpid() if listen is None else listen
        if self.listen:
            _listen(self)
        _registered.append(self)
        self.refresh(True)

    def measure(self):
        try:
            self.bytes = max(0, int(self.measure_fn() or 0))
        except Exception:
            self.errors += 1
            self.bytes = 0
        return self.bytes

    def write(self, value):
        record = dict(schema=SCHEMA, pid=self.pid, name=self.name, priority=self.priority, sheddable_bytes=value,
                      signal=SIGNAL, updated=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
        try:
            write_atomic(self.folder, self.path.name, json.dumps(record) + "\n")
            self.writes += 1
            self.last = value
        except OSError:
            self.errors += 1

    def refresh(self, force=False):
        with _lock:
            if self.closed:
                return
            if not force:
                wait = self.refresh_seconds - (time.monotonic() - self.checked)
                if wait > 0:
                    if self.timer is None:
                        self.timer = threading.Timer(wait, self._trailing)
                        self.timer.daemon = True
                        self.timer.start()
                    return
            self.checked = time.monotonic()
            value = self.measure()
            if not force and value == self.last:
                return
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
            self.write(value)

    def _trailing(self):
        with _lock:
            self.timer = None
        self.refresh()

    def shed_now(self):
        if self.closed or self.shedding:
            return
        self.shedding = True
        try:
            self.sheds += 1
            outcome = None
            if self.shed_fn is not None:
                try:
                    outcome = self.shed_fn()
                except Exception:
                    self.errors += 1
            if outcome is not False:
                self.refresh(True)
        finally:
            self.shedding = False

    def close(self):
        with _lock:
            if self.closed:
                return
            self.closed = True
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
        if self in _registered:
            _registered.remove(self)
        if self in _listening:
            _unlisten(self)


def _listen(holder):
    global _previous
    if not _listening:
        _previous = signal.signal(signal.SIGUSR2, _on_signal)
    _listening.append(holder)


def _unlisten(holder):
    global _previous
    _listening.remove(holder)
    if not _listening and threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGUSR2, _previous if _previous is not None else signal.SIG_DFL)
        _previous = None


@atexit.register
def _remove_all():
    for holder in list(_registered):
        holder.close()


def register(name, priority, measure, shed=None, pid=None, listen=None, folder=None, env=None, refresh_seconds=REFRESH_SECONDS, enable=None):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("holder name must match [A-Za-z0-9_.-]{1,64}")
    if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 199:
        raise ValueError("priority must be an integer from 0 to 199")
    if not callable(measure) or (shed is not None and not callable(shed)):
        raise ValueError("measure and shed must be callable")
    on = (folder is not None or enabled(env)) if enable is None else enable
    if not on:
        return Inert()
    listening = (os.getpid() if pid is None else pid) == os.getpid() if listen is None else listen
    if listening and not _listening:
        current = signal.getsignal(signal.SIGUSR2)
        if current not in (signal.SIG_DFL, None):
            refused = Inert()
            refused.refused = "sigusr2-claimed"
            return refused
    return Holder(name, priority, measure, shed, pid, listen, folder if folder is not None else directory(env), refresh_seconds)

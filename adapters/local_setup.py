"""One machine's Cstack setup: the private state folder, the device name and a durable witnessed ledger."""
from dataclasses import dataclass, field
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess

DEVICE_FILE = "device.json"
LEDGER_FILE = "ledger.json"
DEVICE_SCHEMA = "cstack.device/0.1"
LOCAL_WITNESSES = ("local-witness-1", "local-witness-2")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
INIT = "python -B tools/cstack_init.py"


class SetupError(Exception):
    pass


def default_state_root():
    return Path.home() / ".local/state/cstack"


def init_command(state_root):
    state_root = Path(state_root)
    return INIT if state_root == default_state_root() else f"{INIT} --state-root {state_root}"


def tailnet_hostname(which=shutil.which, run=subprocess.run):
    if which("tailscale") is None:
        return None
    try:
        status = json.loads(run(["tailscale", "status", "--json", "--self"], capture_output=True, text=True,
                                timeout=10, check=True).stdout)
        name = status["Self"]["DNSName"].split(".")[0].lower()
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return name if NAME.fullmatch(name) else None


def computer_name(gethostname=socket.gethostname):
    label = gethostname().split(".")[0].lower()
    return re.sub(r"[^a-z0-9-]+", "-", label).strip("-")[:63] or "local"


def recorded_device(state_root):
    path = Path(state_root) / DEVICE_FILE
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text())
        name = record["hostname"]
        if record.get("schema") != DEVICE_SCHEMA or type(name) is not str or not NAME.fullmatch(name):
            raise ValueError(name)
    except (OSError, ValueError, KeyError, TypeError):
        raise SetupError(f"{path} is damaged. Run `{init_command(state_root)} --device NAME` to record this "
                         "machine's device name again.") from None
    return name


def resolve_device(state_root, tailnet=None):
    name = recorded_device(state_root) or (tailnet or tailnet_hostname)()
    if name is None:
        raise SetupError(f"This machine has no Cstack device name yet. Run `{init_command(state_root)}` once; "
                         "it records one, with or without Tailscale.")
    return name


def require_durable(state_root):
    if not (Path(state_root) / LEDGER_FILE).is_file():
        raise SetupError(
            f"Cstack is not set up in {state_root}: there is no durable ledger, so everything this bot does would "
            f"be lost when the server stops. Run `{init_command(state_root)}` once, then start the server again. "
            "For a throwaway development session only, add --allow-memory-ledger.")


@dataclass
class Report:
    state_root: Path
    write: bool
    lines: list = field(default_factory=list)
    device: str | None = None
    bots: tuple = ()
    local_witnesses: bool = False

    def add(self, status, text):
        self.lines.append((status, text))

    @property
    def problems(self):
        return [text for status, text in self.lines if status == "problem"]


def _private_dir(path, report, label):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not report.write:
            report.add("problem", f"{label} {path} is missing. Run `{init_command(report.state_root)}`.")
            return False
        os.mkdir(path, 0o700)
        os.chmod(path, 0o700)
        report.add("created", f"{label} {path}, private to you")
        return True
    if not stat.S_ISDIR(info.st_mode):
        report.add("problem", f"{label} {path} is not a plain folder (it is a link or a file). Move it aside and "
                              "run init again.")
        return False
    if info.st_uid != os.getuid():
        report.add("problem", f"{label} {path} belongs to another user. Use a state folder of your own.")
        return False
    if info.st_mode & 0o077:
        if report.write:
            os.chmod(path, 0o700)
            report.add("fixed", f"{label} {path} was open to other users; it is now private to you")
        else:
            report.add("problem", f"{label} {path} is open to other users. Run init to make it private.")
    return True


def _private_file(path, report, label, *, fixable):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        report.add("problem", f"{label} {path} is not a plain file of yours (it is a link, a folder or another "
                              "user's). Move it aside and run init again.")
        return False
    if info.st_mode & 0o077:
        if fixable and report.write:
            os.chmod(path, 0o600)
            report.add("fixed", f"{label} {path} was readable by other users; it is now private to you")
        elif fixable:
            report.add("problem", f"{label} {path} is readable by other users. Run init to make it private.")
        else:
            report.add("problem", f"{label} {path} is readable by other users, so it may have been copied. Delete "
                                  "it and run init again to make a new one; a new key starts a new ledger writer.")
            return False
    return True


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path, report, label):
    if not _private_file(path, report, label, fixable=True):
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        report.add("problem", f"{label} {path} is not valid JSON. Move it aside and run init again.")
        return None


def _key(L, path, report, label):
    if os.path.lexists(path):
        if not _private_file(path, report, f"Signing key for {label}", fixable=False):
            return None
        try:
            return L.load_key(str(path))
        except (L.LedgerError, OSError, ValueError):
            report.add("problem", f"Signing key for {label} {path} is damaged. Move it aside and run init again.")
            return None
    if not report.write:
        report.add("problem", f"Signing key for {label} is missing. Run `{init_command(report.state_root)}`.")
        return None
    key = L.Ed25519PrivateKey.generate()
    L.save_key(key, str(path))
    report.add("created", f"Signing key for {label}, readable only by you")
    return key


def _device(state_root, fleet, flag, tailnet, gethostname, report):
    names = [device.hostname for device in fleet.devices]
    try:
        recorded = recorded_device(state_root)
    except SetupError as error:
        report.add("problem", str(error))
        recorded = None
    if flag is not None:
        if not NAME.fullmatch(flag):
            report.add("problem", f"--device {flag!r} is not a device name: use lowercase letters, digits and "
                                  "hyphens.")
            return recorded
        name, source = flag, "chosen with --device"
    elif recorded is not None:
        name, source = recorded, "recorded earlier"
    else:
        detected, source = tailnet(), "this machine's Tailscale name"
        if detected is None:
            detected, source = computer_name(gethostname), "this computer's name; Tailscale is not in use"
        name = detected
        if name not in names and len(names) == 1:
            name, source = names[0], f"the only device in the bot list; {detected!r} is not listed there"
    if name not in names:
        report.add("problem", f"This machine is called {name!r}, but the bot list has no device by that name. Add "
                              f"a devices entry for {name!r} to aors/fleet.json, or run init again with --device "
                              f"NAME, one of: {', '.join(names) or 'none listed'}.")
        return name
    if recorded == name:
        report.add("ok", f"Device name {name} ({source})")
    elif report.write:
        _write_json(state_root / DEVICE_FILE, {"schema": DEVICE_SCHEMA, "hostname": name})
        report.add("created", f"Device name {name} ({source})")
    else:
        report.add("problem", f"This machine's device name is not recorded yet. Run `{init_command(state_root)}`.")
    return name


def _ledger(state_root, bots, L, report):
    config_path = state_root / LEDGER_FILE
    config, write = None, report.write
    if os.path.lexists(config_path):
        config = _read_json(config_path, report, "Ledger settings")
        if config is None:
            return
        if type(config) is not dict or not all(type(config.get(k)) is str for k in ("node", "log", "roster")) \
                or type(config.get("writers")) is not dict:
            report.add("problem", f"Ledger settings {config_path} are incomplete. Move the file aside and run init "
                                  "again.")
            return
    node = config["node"] if config else (report.device if report.device and NAME.fullmatch(report.device)
                                          else "local")
    config = config or {"node": node, "log": f"ledger/{node}.jsonl", "roster": "ledger/roster.json", "writers": {}}
    config_changed = not config_path.exists()
    ledger_dir = state_root / "ledger"
    if not _private_dir(ledger_dir, report, "Ledger folder"):
        return
    roster_path, roster_changed = state_root / config["roster"], False
    if os.path.lexists(roster_path):
        roster = _read_json(roster_path, report, "Ledger roster")
        if roster is None:
            return
        try:
            L.load_roster(str(roster_path))
            if type(roster.get("writers")) is not dict:
                raise ValueError("writers")
        except (L.LedgerError, OSError, ValueError, KeyError, TypeError, AttributeError):
            report.add("problem", f"Ledger roster {roster_path} is damaged. Move the ledger folder aside and run "
                                  "init again to start a new ledger.")
            return
    else:
        if not write:
            report.add("problem", f"Ledger roster is missing. Run `{init_command(state_root)}`.")
            return
        witnesses = {}
        if _private_dir(ledger_dir / "witnesses", report, "Witness key folder"):
            for name in LOCAL_WITNESSES:
                key = _key(L, ledger_dir / "witnesses" / f"{name}.key", report, f"witness {name}")
                if key is not None:
                    witnesses[name] = L.pub_hex(key)
        if len(witnesses) < 2:
            return
        roster, roster_changed = {"quorum": 2, "witnesses": witnesses, "writers": {}}, True
    report.local_witnesses = set(roster["witnesses"]) <= set(LOCAL_WITNESSES)
    keys_ready = _private_dir(ledger_dir / "keys", report, "Bot key folder")
    for slug in bots:
        entry = config["writers"].get(slug)
        if entry is not None and not (type(entry) is dict and type(entry.get("writer")) is str
                                      and type(entry.get("key")) is str):
            report.add("problem", f"Ledger settings list bot {slug} without a usable writer and key.")
            continue
        if entry is None and not keys_ready:
            continue
        writer, key_rel = (entry["writer"], entry["key"]) if entry else (slug, f"ledger/keys/{slug}.key")
        key = _key(L, state_root / key_rel, report, f"bot {slug}")
        if key is None:
            continue
        bound, want = roster["writers"].get(writer), {"pub": L.pub_hex(key), "node": config["node"]}
        bound = {k: bound.get(k) for k in want} if type(bound) is dict else bound
        if bound is None:
            if not write:
                report.add("problem", f"Bot {slug} is not in the ledger roster yet. Run `{init_command(state_root)}`.")
                continue
            roster["writers"][writer], roster_changed = want, True
        elif bound != want:
            report.add("problem", f"The signing key for bot {slug} does not match the ledger roster. Init never "
                                  "replaces keys or roster entries: restore the original key, or move the ledger "
                                  "folder and ledger.json aside to start a new ledger.")
            continue
        if entry is None:
            if not write:
                report.add("problem", f"Bot {slug} has no ledger writer yet. Run `{init_command(state_root)}`.")
                continue
            config["writers"][slug], config_changed = {"writer": slug, "key": key_rel}, True
    if write and roster_changed:
        _write_json(roster_path, roster)
        report.add("created", f"Ledger roster {roster_path} (public keys only)")
    if write and config_changed:
        _write_json(config_path, config)
        report.add("created", f"Ledger settings {config_path}")
    _verify_log(state_root / config["log"], config["node"], roster, L, report)


def _verify_log(log_path, node, roster, L, report):
    logs = [path for path in (log_path, *sorted(log_path.with_suffix("").glob("*/*.jsonl"))) if path.is_file()]
    if not logs:
        report.add("ok", "Ledger is ready; its files are created when a bot first records something")
        return
    entries = 0
    for path in logs:
        try:
            entries += len(L.Log(str(path), node, roster).entries)
        except (L.LedgerError, OSError, ValueError, KeyError, TypeError) as error:
            report.add("problem", f"The ledger file {path} failed verification ({error}). Keep the file: it is the "
                                  "record. Do not run bots until it is explained.")
            return
    report.add("ok", f"Ledger verified: {len(logs)} file(s), {entries} signed entries, every chain intact")


def _bot_state(state_root, slug, report):
    folder = state_root / slug
    if not _private_dir(folder, report, f"State folder for bot {slug}"):
        return
    anchors = folder / "anchors.json"
    if os.path.lexists(anchors):
        value = _read_json(anchors, report, f"Ledger anchors for bot {slug}")
        if value is not None and (type(value) is not dict or any(not k.startswith(slug + ".") for k in value)):
            report.add("problem", f"Ledger anchors {anchors} do not belong to bot {slug}. Move the file aside.")
    elif report.write:
        _write_json(anchors, {})
        report.add("created", f"Ledger anchors for bot {slug}")
    else:
        report.add("problem", f"Ledger anchors for bot {slug} are missing. Run `{init_command(state_root)}`.")


def setup(state_root, fleet_path, *, device=None, write=True, tailnet=None, gethostname=None):
    from adapters.aor_registry import load_fleet
    from poodo_core import ContractError

    state_root = Path(state_root).expanduser()
    report = Report(state_root, write)
    if write:
        state_root.parent.mkdir(parents=True, exist_ok=True)
    if not _private_dir(state_root, report, "State folder"):
        return report
    try:
        fleet = load_fleet(fleet_path)
    except (OSError, ValueError, ContractError) as error:
        report.add("problem", f"The bot list {fleet_path} could not be read: {error}")
        return report
    report.bots = tuple(bot.slug for bot in fleet.bots)
    report.device = _device(state_root, fleet, device, tailnet or tailnet_hostname,
                            gethostname or socket.gethostname, report)
    if write and report.problems:
        return report
    if importlib.util.find_spec("cryptography") is None:
        report.add("problem", "The ledger needs the Python package 'cryptography'. Install it with "
                              "`pip install -r requirements.txt`, then run init again.")
        return report
    from adapters.witnessed_ledger import ledger_lib
    _ledger(state_root, report.bots, ledger_lib(), report)
    for slug in report.bots:
        _bot_state(state_root, slug, report)
    return report

"""Fleet mail (AGENTS.md "Fleet mail"): bots message each other through labelled GitHub issues, not through the owner.

A bot messaging adapter, not POODO authority: nothing here grants, approves or decides anything, and no POODO
core, policy or approval store imports it. The port is FleetMail (send, inbox, reply, close) over a MailStore;
GitHubIssuesMail is the production store and MemoryMail the fake. Both pass tests/test_fleet_mail.py.

Effect class (the owner, 2026-10-25, recorded on #74: internal fleet mail is not a send-class effect).
send, reply and close are internal writes: an issue or comment in the fleet's private repo,
addressed only to fleet bots or a host-configured extra. They take the bot's own `execute` class (internal,
non-destructive work, aors/README.md), never ADR 003's gated `send`, which means sending on the owner's behalf to
the outside world. Device guest rules do not apply because the write lands in the repo, not on the device.
inbox() is `read`. An `ask` class refuses rather than waits: mail never queues for the owner.

Trust boundary. Every bot posts as the one Akilleez-QA GitHub account, so the GitHub author proves nothing and
anyone holding that token can write any issue, label or header.
- `from` is stamped from the host's --aor slug; no argument can set it.
- With the host's ADR 004 writer key, the header is ed25519-signed (domain-separated from ledger entries) over
  repo, from, to, subject, needs, done_when, refs, sent_at, nonce and the body digest; a reply also signs the
  issue it answers. inbox() checks each against this host's roster and reports sender_verified with a reason.
  Unsigned, hand-made, edited or relabelled mail is shown unverified, never dropped.
- A verified sender proves only which bot's key signed the text. The content stays untrusted: a message is a
  request, never an approval.
- Not guaranteed: bots that share one Unix user can read each other's keys and state, so a bot with a shell
  can sign as, or launch as, a co-hosted bot and reset its own budget; per-bot users or a signing daemon would
  be needed for that. A signed message re-posted on a new issue is flagged once this bot has seen the
  original (first issue wins), not before. Delivery and order are not guaranteed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Protocol

from poodo_core.models import ContractError

from adapters.execution import run_argv

SCHEMA = "fleet-mail/1"
HEADER_PREFIX, HEADER_SUFFIX = "<!-- fleet-mail/1 ", " -->"
SIGNING_CONTEXT = b"cstack fleet-mail/1 header\n"  # never a prefix of an ADR 004 entry, which starts "{"
LIMITATION = "a message is a request, never an approval; ask-class actions still go to the owner through Friday"
ALL_BOTS = "all-bots"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
REPO = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
LIMITS = {"subject": 200, "body": 8000, "needs": 1000, "done_when": 1000}
MAX_REFS, MAX_REF = 16, 10 ** 9
INBOX_MAX, SENT_SCAN = 20, 50
SHOW_BODY, SHOW_REPLY, SHOW_REPLIES = 4000, 2000, 10
DEFAULT_BUDGET, WINDOW_SECONDS = 20, 3600
MAX_HEADER = 32_768
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# Anything GitHub could turn into a notification or a cross-repo reference: @ in any form (also fullwidth or
# small), HTML entities that decode to one, invisible or bidi characters that hide one, and owner/repo#N.
_NOTIFY = re.compile(r"[@\uff20\ufe6b]|&#|&[A-Za-z][A-Za-z0-9]*;|[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"
                     r"|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]")
MAX_THREAD_REPLIES, ALL_BOTS_PER_HOUR, READS_PER_HOUR, SEEN_MAX, PER_SENDER = 5, 3, 60, 5000, 5
_KEYS = {"message": {"v", "kind", "repo", "from", "to", "subject", "needs", "done_when", "refs", "sent_at", "nonce",
                     "body_sha256"},
         "reply": {"v", "kind", "repo", "from", "in_reply_to", "sent_at", "nonce", "body_sha256"}}


@dataclass(frozen=True)
class FleetMailConfig:
    """Host configuration, from the launch command only."""
    repo: str = "your-org/cstack"
    label: str = "fleet-mail"
    to_prefix: str = "to:"
    extras: tuple[str, ...] = ("claude-code",)
    budget_per_hour: int = DEFAULT_BUDGET
    gh: str | None = None


def check_extras(extras, fleet_slugs):
    """Extras are non-fleet recipients such as claude-code; never the owner, an address, or a fleet slug alias."""
    for extra in extras:
        if type(extra) is not str or not SLUG.match(extra) or "owner" in extra or extra == ALL_BOTS:
            raise ContractError(f"Fleet mail extra recipient {extra!r} is not allowed")
        if extra in fleet_slugs:
            raise ContractError(f"Fleet mail extra recipient {extra!r} is already a fleet bot")
    return tuple(extras)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _wire(header):
    """Canonical JSON that cannot close the HTML comment it sits in."""
    return canonical(header).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strict(text):
    def pairs(items):
        if len({k for k, _ in items}) != len(items):
            raise ValueError("duplicate key")
        return dict(items)

    def bad(_):
        raise ValueError("non-finite number")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


def _text(name, value, *, single_line=False):
    if type(value) is not str:
        raise ContractError(f"{name} must be a string")
    value = value.replace("\r\n", "\n").strip()
    if not value or len(value) > LIMITS[name]:
        raise ContractError(f"{name} must be 1..{LIMITS[name]} characters")
    if _CONTROL.search(value) or (single_line and "\n" in value):
        raise ContractError(f"{name} contains control characters" + (" or a newline" if single_line else ""))
    if _NOTIFY.search(value):
        raise ContractError(f"{name} contains an @, an HTML entity, an invisible character or a cross-repo "
                            "reference; fleet mail never notifies anyone outside the fleet")
    return value


def _number(value):
    if type(value) is not int or not 1 <= value <= MAX_REF:
        raise ContractError("number must be an issue number")
    return value


def _human(header):
    signed = "signed" if "sig" in header else "unsigned"
    if header["kind"] == "reply":
        return f"**From:** `{header['from']}` ({signed}), replying to #{header['in_reply_to']}"
    refs = " ".join(f"#{n}" for n in header["refs"]) or "none"
    return (f"**From:** `{header['from']}` ({signed}) **To:** `{header['to']}`\n**Needs:** {header['needs']}\n"
            f"**Done when:** {header['done_when']}\n**Refs:** {refs}\n**Sent:** {header['sent_at']}")


def render(header, body):
    return f"{HEADER_PREFIX}{_wire(header)}{HEADER_SUFFIX}\n{_human(header)}\n\n{body}"


def parse(text):
    """(header or None, body, problem or None) from an issue or comment body; never raises on bad input."""
    text = (text if type(text) is str else "").replace("\r\n", "\n")
    first, _, rest = text.partition("\n")
    if not (first.startswith(HEADER_PREFIX) and first.endswith(HEADER_SUFFIX)) or len(first) > MAX_HEADER:
        return None, text.strip(), "no fleet-mail/1 header (hand-made issue or comment)"
    try:
        header = _strict(first[len(HEADER_PREFIX):-len(HEADER_SUFFIX)])
        _check_header(header)
    except (ValueError, TypeError, KeyError, ContractError):
        return None, text.strip(), "malformed fleet-mail/1 header"
    human = _human(header) + "\n\n"
    if not rest.startswith(human):
        return header, rest.strip(), "the human-readable From/Needs lines were edited"
    return header, rest[len(human):].strip(), None


def _check_header(h):
    if type(h) is not dict or h.get("v") != SCHEMA or h.get("kind") not in _KEYS:
        raise ContractError("not a fleet-mail/1 header")
    keys = _KEYS[h["kind"]]
    if not keys <= set(h) <= keys | {"sig"}:
        raise ContractError("header fields")
    strings = ["repo", "from", "sent_at", "nonce", "body_sha256"] + (
        ["to", "subject", "needs", "done_when"] if h["kind"] == "message" else [])
    if any(type(h[k]) is not str or len(h[k]) > 8192 for k in strings) or not SLUG.match(h["from"]) \
            or (h["kind"] == "message" and not SLUG.match(h["to"])):
        raise ContractError("header field types")
    if "sig" in h and (type(h["sig"]) is not str or len(h["sig"]) > 200):
        raise ContractError("header signature")
    if h["kind"] == "message":
        if type(h["refs"]) is not list or len(h["refs"]) > MAX_REFS or any(type(n) is not int for n in h["refs"]):
            raise ContractError("header refs")
    elif type(h["in_reply_to"]) is not int:
        raise ContractError("header in_reply_to")


def _signed_bytes(header):
    return SIGNING_CONTEXT + canonical({k: v for k, v in header.items() if k != "sig"}).encode("ascii")


def message_digest(header):
    return hashlib.sha256(_signed_bytes(header)).hexdigest()


class MailStore(Protocol):
    """Dumb transport. Issues are {number, title, body, labels, state: open|closed, author, comments}; comments are
    [{body, author}], or None when the store could not fetch them within its bounds."""
    def create(self, title: str, body: str, labels: tuple[str, ...]) -> int: ...
    def comment(self, number: int, body: str) -> None: ...
    def close(self, number: int) -> None: ...
    def list_open(self, labels: tuple[str, ...], limit: int) -> list[dict]: ...
    def view(self, number: int) -> dict: ...


class MemoryMail:
    """The fake store, for the replaceability pattern. Not durable."""
    def __init__(self, author="Akilleez-QA"):
        self.author, self.issues, self._next = author, {}, 1

    def create(self, title, body, labels):
        number, self._next = self._next, self._next + 1
        self.issues[number] = {"number": number, "title": title, "body": body, "labels": list(labels),
                               "state": "open", "author": self.author, "comments": []}
        return number

    def _get(self, number):
        if number not in self.issues:
            raise ContractError(f"Issue #{number} not found")
        return self.issues[number]

    def comment(self, number, body):
        self._get(number)["comments"].append({"body": body, "author": self.author})

    def close(self, number):
        self._get(number)["state"] = "closed"

    def list_open(self, labels, limit):
        found = [i for n, i in sorted(self.issues.items(), reverse=True)
                 if i["state"] == "open" and all(label in i["labels"] for label in labels)]
        return copy.deepcopy(found[:limit])

    def view(self, number):
        return copy.deepcopy(self._get(number))


def host_env(environ=os.environ):
    """The gh process sees only what it needs to find its own login; GH_REPO and friends never pass through."""
    keep = ("HOME", "PATH", "LANG", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
            "GH_CONFIG_DIR", "GH_TOKEN", "GITHUB_TOKEN")
    env = {k: environ[k] for k in keep if k in environ}
    return {**env, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1", "GH_PAGER": "cat"}


class GitHubIssuesMail:
    """gh with a fixed argv through adapters/execution.run_argv: no shell, a deadline, bounded output.

    The repo and gh path are host configuration. Every value is passed as --flag=value, issue numbers are
    formatted integers, labels are validated slugs, and bodies go through stdin (--body-file=-), so no message
    text ever becomes a gh argument.
    """
    FIELDS = "number,title,body,labels,state,author"
    OUTPUT_CAP = 8 << 20

    def __init__(self, repo, gh_path, *, env=None, timeout_seconds=20.0):
        if type(repo) is not str or not REPO.match(repo):
            raise ContractError("Fleet mail repo must be owner/name")
        if type(gh_path) is not str or not os.path.isabs(gh_path) or not os.access(gh_path, os.X_OK):
            raise ContractError("Fleet mail needs an absolute, executable gh path")
        self._repo, self._gh_path = repo, gh_path
        self._env = host_env() if env is None else dict(env)
        self._timeout = timeout_seconds

    def _gh(self, *args, stdin=b"", cap=1 << 20):
        result = run_argv((self._gh_path, *args), stdin=stdin, timeout_seconds=self._timeout, stdout_cap=cap,
                          env=self._env)
        if result.status != "completed" or result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace").strip()[:300]
            raise ContractError(f"gh {' '.join(args[:2])} failed ({result.status}, exit {result.returncode}): "
                                f"{detail}")
        return result.stdout

    def _repo_flag(self):
        return f"--repo={self._repo}"

    def create(self, title, body, labels):
        out = self._gh("issue", "create", self._repo_flag(), f"--title={title}", "--body-file=-",
                       *(f"--label={label}" for label in labels), stdin=body.encode("utf-8")).decode("utf-8", "replace")
        match = re.search(r"https://github\.com/" + re.escape(self._repo) + r"/issues/([0-9]{1,10})\s*\Z", out,
                          re.IGNORECASE)
        if not match:
            raise ContractError("gh issue create did not print this repo's issue URL")
        return int(match.group(1))

    def comment(self, number, body):
        self._gh("issue", "comment", str(_number(number)), self._repo_flag(), "--body-file=-",
                 stdin=body.encode("utf-8"))

    def close(self, number):
        self._gh("issue", "close", str(_number(number)), self._repo_flag())

    def list_open(self, labels, limit):
        args = ("issue", "list", self._repo_flag(), "--state=open", *(f"--label={label}" for label in labels),
                f"--limit={int(limit)}")
        try:
            raw = self._gh(*args, f"--json={self.FIELDS},comments", cap=self.OUTPUT_CAP)
            with_comments = True
        except ContractError as error:
            if "resource_rejected" not in str(error):
                raise
            raw, with_comments = self._gh(*args, f"--json={self.FIELDS}", cap=self.OUTPUT_CAP), False
        issues = self._decode(raw)
        if type(issues) is not list:
            raise ContractError("gh issue list did not return a list")
        return [self._issue(i, with_comments) for i in issues[:limit]]

    def view(self, number):
        raw = self._gh("issue", "view", str(_number(number)), self._repo_flag(), f"--json={self.FIELDS},comments",
                       cap=self.OUTPUT_CAP)
        return self._issue(self._decode(raw), True)

    @staticmethod
    def _decode(raw):
        try:
            return _strict(raw.decode("utf-8"))
        except ValueError:
            raise ContractError("gh returned malformed JSON") from None

    @staticmethod
    def _issue(raw, with_comments):
        def login(who):
            return who.get("login") if type(who) is dict and type(who.get("login")) is str else None

        if type(raw) is not dict or type(raw.get("number")) is not int or type(raw.get("labels")) is not list:
            raise ContractError("gh returned an issue in an unexpected shape")
        comments = None
        if with_comments and type(raw.get("comments")) is list:
            comments = [{"body": c.get("body") if type(c.get("body")) is str else "", "author": login(c.get("author"))}
                        for c in raw["comments"] if type(c) is dict]
        return {"number": raw["number"], "title": raw.get("title") if type(raw.get("title")) is str else "",
                "body": raw.get("body") if type(raw.get("body")) is str else "",
                "labels": [lab["name"] for lab in raw["labels"] if type(lab) is dict and type(lab.get("name")) is str],
                "state": str(raw.get("state", "")).lower(), "author": login(raw.get("author")), "comments": comments}


class SendBudget:
    """Per-bot mail state under the bot's state dir, locked: host-set sends+replies per rolling hour, a smaller
    all-bots allowance, an inbox read rate, and the signed nonces this bot has seen (first issue wins).

    A bot with a shell on its host can delete this file; the budget bounds a bot driven through MCP, not one
    that already runs arbitrary commands as the host user (see the trust boundary above)."""
    def __init__(self, path, limit, clock):
        if type(limit) is not int or not 0 <= limit <= 1000:
            raise ContractError("Fleet mail budget must be 0..1000 per hour")
        self._path, self._limit, self._clock = Path(path), limit, clock

    def _locked(self, update):
        try:
            fd = os.open(self._path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except OSError as error:
            raise ContractError(f"Fleet mail budget file refused: {error.strerror}") from None
        with os.fdopen(fd, "r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            raw = handle.read()
            try:
                state = {"sent": [], "all_bots": [], "reads": [], "refused": 0, "refusal_logged": 0, "seen": {},
                         **(json.loads(raw) if raw else {})}
                now = self._clock()
                for key in ("sent", "all_bots", "reads"):
                    state[key] = [t for t in state[key] if type(t) is int and t > now - WINDOW_SECONDS]
                if type(state["refused"]) is not int or type(state["refusal_logged"]) is not int \
                        or type(state["seen"]) is not dict:
                    raise TypeError
            except (ValueError, TypeError, KeyError):
                raise ContractError("Fleet mail budget file is unreadable; refusing to send") from None
            result = update(state, now)
            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(state))
            return result

    def take(self, all_bots=False):
        """(allowed, first refusal in this window)."""
        def update(state, now):
            if len(state["sent"]) >= self._limit or (all_bots and len(state["all_bots"]) >= ALL_BOTS_PER_HOUR):
                state["refused"] += 1
                first = state["refusal_logged"] <= now - WINDOW_SECONDS
                if first:
                    state["refusal_logged"] = now
                return False, first
            state["sent"].append(now)
            if all_bots:
                state["all_bots"].append(now)
            return True, False
        return self._locked(update)

    def read(self):
        def update(state, now):
            if len(state["reads"]) >= READS_PER_HOUR:
                return False
            state["reads"].append(now)
            return True
        if not self._locked(update):
            raise ContractError(f"Fleet mail inbox rate exhausted: {READS_PER_HOUR} reads per hour")

    def remember(self, nonces):
        """{nonce: issue number} of verified messages; returns the nonces first seen on a different issue."""
        def update(state, now):
            seen, clashes = state["seen"], set()
            for nonce, number in nonces.items():
                if seen.setdefault(nonce, number) != number:
                    clashes.add(nonce)
            for stale in list(seen)[:max(0, len(seen) - SEEN_MAX)]:
                del seen[stale]
            return clashes
        return self._locked(update)

    def status(self):
        return self._locked(lambda state, now: {"limit": self._limit, "used": len(state["sent"]),
                                                "all_bots_limit": ALL_BOTS_PER_HOUR,
                                                "all_bots_used": len(state["all_bots"]),
                                                "window_seconds": WINDOW_SECONDS, "refused": state["refused"]})


def roster_signers(state_root, fleet_slugs):
    """{fleet slug: public key hex} from <state_root>/ledger.json and its ADR 004 roster (host configuration).

    A slug is bound to the writer ledger.json names for it, else to a roster writer of the same name.
    """
    from adapters.witnessed_ledger import ledger_lib
    state_root = Path(state_root)
    config = json.loads((state_root / "ledger.json").read_text())
    roster = ledger_lib().load_roster(state_root / config["roster"])
    writers = roster.get("writers", {})
    names = {slug: slug for slug in fleet_slugs}
    names.update({slug: w["writer"] for slug, w in config.get("writers", {}).items()
                  if slug in fleet_slugs and type(w) is dict and type(w.get("writer")) is str})
    return {slug: writers[name]["pub"] for slug, name in names.items()
            if type(writers.get(name)) is dict and type(writers[name].get("pub")) is str}


class FleetMail:
    def __init__(self, store, *, me, fleet_slugs, config, state_dir, shields_up, write_class, read_class="allow",
                 clock=None, ledger=None, key_path=None, signers=None):
        """All arguments are host configuration from bootstrap. key_path is this bot's ADR 004 writer key;
        signers maps fleet slugs to roster public keys for verification."""
        if not SLUG.match(me) or me not in fleet_slugs:
            raise ContractError("Fleet mail sender must be a fleet bot")
        if not REPO.match(config.repo) or not SLUG.match(config.label) or not re.fullmatch(r"[a-z-]{1,16}:",
                                                                                          config.to_prefix):
            raise ContractError("Invalid fleet mail host configuration")
        self._store, self.me, self._config = store, me, config
        self._recipients = (set(fleet_slugs) | {ALL_BOTS} | set(check_extras(config.extras, set(fleet_slugs)))) - {me}
        self._shields_up, self._write_class, self._read_class = shields_up, write_class, read_class
        self._clock = clock or (lambda: int(time.time()))
        self._ledger, self._signers = ledger, dict(signers or {})
        self._budget = SendBudget(Path(state_dir) / "fleet-mail-budget.json", config.budget_per_hour, self._clock)
        self._key = self._lib = None
        if key_path is not None:
            from adapters.witnessed_ledger import ledger_lib  # lazy: cryptography only when a key is configured
            self._lib = ledger_lib()
            try:
                self._key = self._lib.load_key(str(key_path))
            except (self._lib.LedgerError, OSError, ValueError) as error:
                raise ContractError(f"Fleet mail writer key refused: {error}") from None
            if self._signers.get(me) != self._lib.pub_hex(self._key):
                raise ContractError("Fleet mail writer key is not this bot's roster key")
        elif self._signers:
            from adapters.witnessed_ledger import ledger_lib
            self._lib = ledger_lib()

    # -- shared checks ------------------------------------------------------------------------------------
    def _writable(self, what):
        if self._shields_up():
            raise ContractError(f"Shields are up: fleet mail {what} is refused until the host lowers them")
        if self._write_class != "allow":
            raise ContractError(f"Fleet mail {what} needs this bot's execute class to be allow (it is "
                                f"{self._write_class}); mail never waits for an approval")

    def _spend(self, what, all_bots=False):
        allowed, first_refusal = self._budget.take(all_bots)
        if not allowed:
            if first_refusal:
                self._record({"action": "fleet_mail_refused", "reason": "send budget exhausted", "attempt": what})
            raise ContractError(f"Fleet mail budget exhausted: {self._config.budget_per_hour} sends+replies per hour, "
                                f"{ALL_BOTS_PER_HOUR} of them to all-bots")

    def _record(self, data):
        """Ledger observation: issue number and message digest, never the body."""
        if self._ledger is None:
            return None
        try:
            self._ledger.append("observation", data)
        except (ContractError, OSError) as error:
            return f"ledger observation not recorded: {error}"
        return None

    def _stamp(self, header):
        if self._key is not None:
            header["sig"] = self._lib.sign(self._key, _signed_bytes(header))
        return header

    def _base(self, kind, body):
        return {"v": SCHEMA, "kind": kind, "repo": self._config.repo, "from": self.me,
                "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._clock())),
                "nonce": secrets.token_hex(8), "body_sha256": _sha(body)}

    def _labels(self, issue):
        return set(issue.get("labels") or ())

    def _is_mail(self, issue):
        if self._config.label not in self._labels(issue):
            raise ContractError(f"Issue #{issue.get('number')} is not fleet mail")

    def _verify(self, header, body, problem, *, number=None, labels=(), addressed_to=None):
        if header is None or problem:
            return False, problem
        if header["repo"].lower() != self._config.repo.lower():
            return False, "the header names a different repo"
        if header["kind"] == "message":
            if self._config.to_prefix + header["to"] not in labels:
                return False, "the labels do not carry the header's recipient"
            if addressed_to is not None and header["to"] not in addressed_to:
                return False, "the signed header names another recipient; a to: label was added separately"
        elif header["in_reply_to"] != number:
            return False, "the reply was signed for a different issue"
        if _sha(body) != header["body_sha256"]:
            return False, "the body differs from the signed digest"
        if "sig" not in header:
            return False, "unsigned: the sender's host has no ADR 004 writer key configured"
        if not self._signers:
            return False, "this host has no ADR 004 roster, so it cannot verify signatures"
        pub = self._signers.get(header["from"])
        if pub is None:
            return False, "the claimed sender has no key in this host's roster"
        if not self._lib.ok_sig(pub, header["sig"], _signed_bytes(header)):
            return False, "the signature does not verify"
        return True, "ed25519 signature verified against this host's ADR 004 roster"

    # -- operations ---------------------------------------------------------------------------------------
    def send(self, to, subject, body, needs, done_when, refs=()):
        self._writable("send")
        if type(to) is not str or to not in self._recipients:
            raise ContractError("Fleet mail goes only to a fleet bot slug, all-bots or a host-configured extra "
                                "(never the owner, never an outside address, never yourself)")
        subject = _text("subject", subject, single_line=True)
        body, needs, done_when = _text("body", body), _text("needs", needs), _text("done_when", done_when)
        if type(refs) not in (list, tuple) or len(refs) > MAX_REFS:
            raise ContractError(f"refs must be a list of at most {MAX_REFS} issue numbers")
        refs = [_number(n) for n in refs]
        self._spend("send", all_bots=to == ALL_BOTS)
        header = self._stamp({**self._base("message", body), "to": to, "subject": subject, "needs": needs,
                              "done_when": done_when, "refs": refs})
        number = self._store.create(f"[{to}] {subject}", render(header, body),
                                    (self._config.label, self._config.to_prefix + to))
        digest = message_digest(header)
        warning = self._record({"action": "fleet_mail_send", "number": number, "to": to, "message_sha256": digest})
        result = {"number": number, "from": self.me, "to": to, "sent_at": header["sent_at"],
                  "signed": "sig" in header, "message_sha256": digest}
        return {**result, "ledger_warning": warning} if warning else result

    def reply(self, number, body):
        self._writable("reply")
        number, body = _number(number), _text("body", body)
        issue = self._store.view(number)
        self._is_mail(issue)
        if issue.get("state") != "open":
            raise ContractError(f"Issue #{number} is closed")
        original, _, _ = parse(issue.get("body"))
        mine = {self._config.to_prefix + self.me, self._config.to_prefix + ALL_BOTS}
        if not (mine & self._labels(issue) or (original is not None and original["from"] == self.me)):
            raise ContractError(f"Issue #{number} is not addressed to {self.me} or sent by it")
        if issue.get("comments") is None:
            raise ContractError(f"Issue #{number}'s replies could not be read within bounds")
        thread = self._thread(issue)
        if thread and thread[-1] == self.me:
            raise ContractError("A bot cannot reply to its own message; wait for the other side")
        sender = original is not None and original["from"] == self.me
        cap = 1 if original is not None and original["to"] == ALL_BOTS and not sender else MAX_THREAD_REPLIES
        if thread[1:].count(self.me) >= cap:
            raise ContractError(f"Reply cap reached: {cap} per bot on this thread")
        self._spend("reply")
        header = self._stamp({**self._base("reply", body), "in_reply_to": number})
        self._store.comment(number, render(header, body))
        digest = message_digest(header)
        warning = self._record({"action": "fleet_mail_reply", "number": number, "message_sha256": digest})
        result = {"number": number, "from": self.me, "signed": "sig" in header, "message_sha256": digest}
        return {**result, "ledger_warning": warning} if warning else result

    def _thread(self, issue):
        """Senders of the stamped posts in a thread, oldest first. With a roster, only posts that verify count,
        so a hand-made comment cannot unlock a self-reply."""
        senders = []
        for i, text in enumerate([issue.get("body"), *(c.get("body") for c in issue["comments"])]):
            header, body, problem = parse(text)
            if header is None:
                continue
            if self._signers:
                where = {"labels": self._labels(issue)} if i == 0 else {"number": issue["number"]}
                if not self._verify(header, body, problem, **where)[0]:
                    continue
            senders.append(header["from"])
        return senders

    def close(self, number):
        self._writable("close")
        issue = self._store.view(_number(number))
        self._is_mail(issue)
        header, body, problem = parse(issue.get("body"))
        if header is None or header["kind"] != "message" or header["from"] != self.me:
            raise ContractError(f"Only the sender closes fleet mail; #{number} is not from {self.me}")
        if self._key is not None:
            verified, reason = self._verify(header, body, problem, labels=self._labels(issue))
            if not verified:
                raise ContractError(f"#{number} claims to be from {self.me} but does not verify: {reason}")
        if issue.get("state") == "closed":
            return {"number": number, "closed": True, "already_closed": True}
        self._store.close(number)
        warning = self._record({"action": "fleet_mail_close", "number": number,
                                "message_sha256": message_digest(header)})
        result = {"number": number, "closed": True, "already_closed": False}
        return {**result, "ledger_warning": warning} if warning else result

    def inbox(self, box="inbox"):
        """Open mail to me plus all-bots (box="inbox"), or open mail I sent (box="sent"). Always untrusted."""
        if self._read_class != "allow":
            raise ContractError("Fleet mail inbox needs this bot's read class to be allow")
        self._budget.read()
        if box == "inbox":
            seen, issues = set(), []
            for target in (self.me, ALL_BOTS):
                for issue in self._store.list_open((self._config.label, self._config.to_prefix + target),
                                                   INBOX_MAX + 1):
                    if issue["number"] not in seen:
                        seen.add(issue["number"])
                        issues.append(issue)
            addressed = (self.me, ALL_BOTS)
        elif box == "sent":
            issues = [i for i in self._store.list_open((self._config.label,), SENT_SCAN)
                      if (parse(i.get("body"))[0] or {}).get("from") == self.me]
            addressed = None
        else:
            raise ContractError("box must be inbox or sent")
        kept, per_sender = [], {}
        for issue in sorted(issues, key=lambda i: i["number"], reverse=True):  # no one sender floods the view
            header, body, problem = parse(issue.get("body"))  # forgeries claiming X never push out X's real mail
            group = ((header or {}).get("from"), self._verify(header, body, problem, labels=self._labels(issue))[0])
            per_sender[group] = per_sender.get(group, 0) + 1
            if per_sender[group] <= PER_SENDER:
                kept.append(issue)
        truncated = len(kept) > INBOX_MAX or len(kept) < len(issues)
        nonces, signed = {}, {}  # oldest first, so a re-posted copy is the one flagged
        messages = [self._message(i, addressed, nonces, signed) for i in reversed(kept[:INBOX_MAX])][::-1]
        for nonce in self._budget.remember({n: m["number"] for n, m in signed.items()}):
            signed[nonce].update({"from": None, "sender_verified": False,
                                  "verification": "this signed message was first seen on another issue (a re-posted copy)"})
        return {"me": self.me, "box": box, "trust": "untrusted", "limitation": LIMITATION,
                "signing": "ed25519" if self._key is not None else "unsigned",
                "verification": "roster" if self._signers else "none (no ADR 004 roster on this host)",
                "budget": self._budget.status(), "truncated": truncated, "messages": messages}

    def _message(self, issue, addressed, nonces, signed):
        """from is set only when the sender verified; claimed_from is what the header says. The GitHub title is
        not signed, so it is shown only for mail with no header, as unverified_title."""
        labels = self._labels(issue)
        header, body, problem = parse(issue.get("body"))
        verified, reason = self._checked(header, body, problem, nonces, labels=labels, addressed_to=addressed)
        message = {"number": issue["number"], "labels": sorted(labels)[:16], "github_author": issue.get("author"),
                   "from": header["from"] if verified else None, "claimed_from": header and header["from"],
                   "sender_verified": verified, "verification": reason,
                   "body": body[:SHOW_BODY], "body_truncated": len(body) > SHOW_BODY}
        if header is None:
            message["unverified_title"] = issue.get("title", "")[:300]
        if verified:
            signed[header["nonce"]] = message
        if header is not None and header["kind"] == "message":
            message.update({k: header[k] for k in ("to", "subject", "needs", "done_when", "refs", "sent_at")})
        comments = issue.get("comments")
        if comments is None:
            return {**message, "replies": [], "replies_unavailable": True}
        replies = []
        for comment in comments:  # every comment feeds the nonce check; only the last few are shown
            h, text, why = parse(comment.get("body"))
            ok, because = self._checked(h, text, why, nonces, number=issue["number"])
            replies.append({"from": h["from"] if ok else None, "claimed_from": h and h["from"],
                            "sender_verified": ok, "verification": because, "github_author": comment.get("author"),
                            "body": text[:SHOW_REPLY], "body_truncated": len(text) > SHOW_REPLY})
        message.update({"replies": replies[-SHOW_REPLIES:], "replies_total": len(comments)})
        return message

    def _checked(self, header, body, problem, nonces, **where):
        verified, reason = self._verify(header, body, problem, **where)
        if verified:
            if header["nonce"] in nonces:
                return False, "this signed nonce appeared earlier in this listing (a re-posted copy)"
            nonces[header["nonce"]] = True
        return verified, reason

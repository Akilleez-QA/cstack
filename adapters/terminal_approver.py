import json
import os
from pathlib import Path
import time
from uuid import uuid4

from adapters.wire import decode
from poodo_core import ApprovalRecord, ContractError


APPROVER = "cli-owner"


class TerminalApprover:
    def __init__(self, mode="deny", *, state_root=None):
        if mode not in ("deny", "terminal") and not mode.startswith("file:"):
            raise ContractError("Unsupported approver mode")
        self.mode = mode
        self.records = {}
        self.answers = {}
        self.state_root = Path(state_root or os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "cstack/cli-approvals"
        if mode.startswith("file:"):
            with open(mode[5:], "rb") as source:
                raw = source.read(65_537)
            if len(raw) > 65_536:
                raise ContractError("Approval file exceeds budget")
            self.answers = decode(raw)
            if type(self.answers) is not dict or any(v not in ("approve", "deny") for v in self.answers.values()):
                raise ContractError("Approval file must map request digests to approve or deny")

    def prepare(self, request):
        answer = self.answers.get(request.sha256, "deny")
        if self.mode == "terminal":
            try:
                with open("/dev/tty", "r") as terminal, open("/dev/tty", "w") as prompt:
                    prompt.write(f"Approve {request.decision_id} {request.capability_id}.{request.operation} "
                                   f"goal={request.goal_id}@{request.goal_revision} sha256={request.sha256}\n"
                                   f"{json.dumps(request.to_dict(), ensure_ascii=True)}\nType approve to allow: ")
                    prompt.flush()
                    answer = terminal.readline(32).strip()
            except (OSError, EOFError):
                answer = "deny"
        self.records[request.decision_id] = ApprovalRecord(
            "cli-" + uuid4().hex, request.decision_id, request.sha256, request.goal_id,
            request.goal_revision, APPROVER, "approved" if answer == "approve" else "declined", int(time.time()) + 300)

    def lookup(self, decision_id):
        return self.records.get(decision_id)

    def consume(self, approval_id):
        if not any(r.approval_id == approval_id and r.verdict == "approved" for r in self.records.values()):
            return False
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.state_root / approval_id, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(self.state_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return True

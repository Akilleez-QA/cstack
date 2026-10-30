"""Conservative local Lean adapter for a tiny closed-arithmetic profile.

This is NOT an arbitrary-Lean sandbox or an independent kernel replay checker.
Only trusted installed native Lean binaries may be used outside test_mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

VERSION = "0.1.0"
PROFILE = "closed-arithmetic-v1"
MAX_SOURCE_BYTES = 32768
ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_']{0,79}\Z")


@dataclass(frozen=True)
class LeanRequest:
    source_path: str
    theorem_name: str


class SourceRejected(ValueError):
    pass


def _strip_comments(source: str) -> str:
    """Handle Lean line/nested block comments, not its full lexical grammar.

    Strings, quoted identifiers, macros, Unicode identifiers and arbitrary Lean
    constructs are deliberately rejected later rather than imperfectly parsed.
    """
    output: list[str] = []
    index = 0
    depth = 0
    while index < len(source):
        pair = source[index:index + 2]
        if depth:
            if pair == "/-":
                depth += 1
                index += 2
            elif pair == "-/":
                depth -= 1
                index += 2
            else:
                output.append("\n" if source[index] == "\n" else " ")
                index += 1
        elif pair == "/-":
            depth = 1
            output.append(" ")
            index += 2
        elif pair == "--":
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
            output.append(" ")
        else:
            output.append(source[index])
            index += 1
    if depth:
        raise SourceRejected("unterminated block comment")
    return "".join(output)


class _ArithmeticParser:
    """A grammar allowlist, not a claim to parse arbitrary Lean."""
    TOKEN = re.compile(r"\s+|[0-9]+|Nat\b|Int\b|<=|>=|!=|[()+*:\-=<>≤≥≠]")

    def __init__(self, statement: str):
        self.tokens: list[str] = []
        self.position = 0
        self.domains: set[str] = set()
        offset = 0
        while offset < len(statement):
            match = self.TOKEN.match(statement, offset)
            if match is None:
                raise SourceRejected("only closed Nat/Int numerals, +, -, *, parentheses, and one relation are allowed")
            token = match.group()
            if not token.isspace():
                if token.isdigit() and len(token) > 256:
                    raise SourceRejected("a numeral exceeds the 256-digit profile limit")
                self.tokens.append(token)
            offset = match.end()
        if len(self.tokens) > 512:
            raise SourceRejected("statement exceeds the 512-token profile limit")

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, token: str) -> None:
        if self.peek() != token:
            raise SourceRejected(f"expected {token!r} in restricted arithmetic statement")
        self.position += 1

    def primary(self, depth: int) -> None:
        if depth > 64:
            raise SourceRejected("expression nesting exceeds profile limit")
        token = self.peek()
        if token == "-":
            self.position += 1
            self.primary(depth + 1)
        elif token == "(":
            self.position += 1
            self.expression(depth + 1)
            if self.peek() == ":":
                self.position += 1
                domain = self.peek()
                if domain not in ("Nat", "Int"):
                    raise SourceRejected("type annotations must be Nat or Int")
                self.domains.add(domain)
                self.position += 1
            self.take(")")
        elif token is not None and token.isdigit():
            self.position += 1
        else:
            raise SourceRejected("expected a numeral or parenthesized arithmetic expression")

    def product(self, depth: int) -> None:
        self.primary(depth)
        while self.peek() == "*":
            self.position += 1
            self.primary(depth)

    def expression(self, depth: int) -> None:
        self.product(depth)
        while self.peek() in ("+", "-"):
            self.position += 1
            self.product(depth)

    def parse(self) -> str:
        self.expression(0)
        if self.peek() not in ("=", "!=", "≠", "<", ">", "<=", ">=", "≤", "≥"):
            raise SourceRejected("a single equality or order relation is required")
        self.position += 1
        self.expression(0)
        if self.peek() is not None:
            raise SourceRejected("extra tokens after restricted arithmetic statement")
        if len(self.domains) != 1:
            raise SourceRejected("one explicit domain, Nat or Int, must be annotated; mixing domains is unsupported")
        return next(iter(self.domains))


def validate_source(source: str, theorem_name: str) -> dict[str, str]:
    """Return reviewed-profile metadata or reject before starting a process."""
    if not isinstance(theorem_name, str) or not _NAME.fullmatch(theorem_name):
        raise SourceRejected("theorem_name must be a simple ASCII identifier")
    stripped = _strip_comments(source)
    if re.search(r"\b(?:sorry|admit|sorryAx)\b", stripped):
        raise SourceRejected("sorry/admit/sorryAx placeholders are forbidden")
    match = re.fullmatch(r"\s*theorem\s+([A-Za-z][A-Za-z0-9_']{0,79})\s*:\s*(.*?)\s*:=\s*by\s+(rfl|decide)\s*", stripped, re.DOTALL)
    if match is None:
        raise SourceRejected("profile requires exactly one import-free theorem with proof by rfl or decide")
    if match.group(1) != theorem_name:
        raise SourceRejected("the declared theorem does not match theorem_name")
    statement = match.group(2)
    domain = _ArithmeticParser(statement).parse()
    return {"theorem_name": theorem_name, "encoded_statement": statement.strip(),
            "domain": domain, "proof_method": match.group(3), "profile": PROFILE}


def _hash_file(path: Path) -> str:
    result = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class LeanAdapter:
    def __init__(self, workspace: str | Path, executable: str | Path | None = None,
                 timeout_seconds: float = 10, *, test_mode: bool = False):
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be finite and in (0, 120]")
        if type(test_mode) is not bool:
            raise ValueError("test_mode must be boolean")
        self.executable = str(executable) if executable is not None else None
        self.timeout_seconds = timeout_seconds
        self.test_mode = test_mode

    def status(self) -> dict[str, Any]:
        """Inspect availability without executing a binary or installing anything."""
        candidate = self.executable if self.executable is not None else shutil.which("lean")
        if not candidate:
            return {"status": "unavailable", "available": False, "reason": "Lean is not installed or not on PATH", "executable": None}
        try:
            path = Path(candidate).resolve(strict=True)
            if not path.is_file() or not os.access(path, os.X_OK):
                raise ValueError("configured Lean path is not an executable file")
            if not self.test_mode:
                # Elan shims may download toolchains. Do not invoke them here.
                elan = path.parent / ("elan.exe" if os.name == "nt" else "elan")
                if path.stem == "elan" or (elan.exists() and (path.samefile(elan) or _hash_file(path) == _hash_file(elan))):
                    raise ValueError("Elan proxy is not invoked; configure an already-installed toolchain's direct Lean binary")
                with path.open("rb") as handle:
                    magic = handle.read(4)
                if magic not in (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe") and not magic.startswith(b"MZ"):
                    raise ValueError("only a trusted native Lean executable is supported; scripts require test_mode")
            return {"status": "available", "available": True, "reason": None, "executable": str(path), "test_mode": self.test_mode}
        except (OSError, ValueError, RuntimeError) as error:
            return {"status": "unavailable", "available": False, "reason": str(error), "executable": candidate}

    def verify(self, request: LeanRequest) -> dict[str, Any]:
        receipt: dict[str, Any] = {
            "schema_version": "1.0", "kind": "lean_verification", "status": "rejected",
            "request": {"source_path": request.source_path, "theorem_name": request.theorem_name} if isinstance(request, LeanRequest) else None,
            "backend": {"name": "Lean", "version": None, "adapter_version": VERSION, "test_mode": self.test_mode},
            "result": None, "error": None, "stdout": "", "stderr": "", "exit_code": None,
            "version_stdout": "", "version_stderr": "", "command": None,
            "scope": {"profile": PROFILE, "formal_proof": False,
                      "claim": "Only the recorded, closed arithmetic Lean statement, not a user-language theorem.",
                      "trust": ["Trusted native Lean binary and its installed core library", "Lean kernel and this adapter", "Host OS and source profile parser"],
                      "limitations": ["Not an arbitrary-code sandbox", "No independent kernel replay or comparator", "No universal, real, rational, or imported-library statements", "Hashes are integrity checks, not signatures"]},
            "artifacts": {"source_sha256": None, "checked_source_sha256": None,
                          "stdout_sha256": None, "stderr_sha256": None,
                          "executable_sha256": None, "backend_source_sha256": _hash_file(Path(__file__))},
        }
        try:
            if not isinstance(request, LeanRequest) or not isinstance(request.source_path, str):
                raise SourceRejected("request must be a LeanRequest with a string source_path")
            source_path = (self.workspace / request.source_path).resolve(strict=True)
            if not source_path.is_relative_to(self.workspace) or not source_path.is_file() or source_path.suffix != ".lean":
                raise SourceRejected("source must be a .lean file contained in the workspace")
            if source_path.stat().st_size > MAX_SOURCE_BYTES:
                raise SourceRejected("Lean source exceeds the 32768-byte profile limit")
            data = source_path.read_bytes()
            if len(data) > MAX_SOURCE_BYTES:
                raise SourceRejected("Lean source exceeds the 32768-byte profile limit")
            source = data.decode("utf-8", errors="strict")
            receipt["artifacts"]["source_sha256"] = sha256(data).hexdigest()
            metadata = validate_source(source, request.theorem_name)
            receipt["scope"].update(metadata)
            # Execute exactly the snapshotted bytes, not a mutable path read later.
            checked_source = source + "\n#print axioms " + request.theorem_name + "\n"
            receipt["checked_source"] = checked_source
            receipt["artifacts"]["checked_source_sha256"] = sha256(checked_source.encode("utf-8")).hexdigest()
        except (SourceRejected, OSError, UnicodeError, ValueError, RuntimeError) as error:
            receipt["error"] = {"code": "source_rejected", "message": str(error)}
            return receipt

        availability = self.status()
        if not availability["available"]:
            receipt["status"] = "unavailable"
            receipt["error"] = {"code": "backend_unavailable", "message": availability["reason"]}
            return receipt
        executable = availability["executable"]
        try:
            receipt["artifacts"]["executable_sha256"] = _hash_file(Path(executable))
            with tempfile.TemporaryDirectory(prefix=".lean-check-", dir=self.workspace) as cwd:
                # Do not pass secrets, LEAN_PATH, dynamic-library overrides, or Elan
                # selection to the child. This is hygiene, not an OS sandbox.
                environment = {"PATH": os.defpath, "HOME": cwd, "LANG": "C.UTF-8"}
                if os.name == "nt" and "SYSTEMROOT" in os.environ:
                    environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
                version = subprocess.run([executable, "--version"], cwd=cwd, env=environment,
                                         capture_output=True, timeout=self.timeout_seconds, check=False)
                receipt["version_stdout"] = version.stdout.decode("utf-8", errors="replace")
                receipt["version_stderr"] = version.stderr.decode("utf-8", errors="replace")
                if version.returncode != 0 or (not self.test_mode and not re.search(r"Lean \(version 4\.", receipt["version_stdout"])):
                    receipt["status"] = "unavailable"
                    receipt["error"] = {"code": "backend_version_failed", "message": "backend did not report a successful Lean 4 version"}
                    return receipt
                receipt["backend"]["version"] = receipt["version_stdout"].strip()
                command = [executable, "--stdin"]
                receipt["command"] = command
                process = subprocess.run(command, input=checked_source.encode("utf-8"),
                                         cwd=cwd, env=environment, capture_output=True,
                                         timeout=self.timeout_seconds, check=False)
                receipt["stdout"] = process.stdout.decode("utf-8", errors="replace")
                receipt["stderr"] = process.stderr.decode("utf-8", errors="replace")
                receipt["exit_code"] = process.returncode
            if _hash_file(Path(executable)) != receipt["artifacts"]["executable_sha256"]:
                raise SourceRejected("backend executable changed during verification")
            stdout = receipt["stdout"].strip()
            no_axioms = f"'{request.theorem_name}' does not depend on any axioms"
            list_match = re.fullmatch(r"'" + re.escape(request.theorem_name) + r"' depends on axioms:\s*\[([^\]]*)\]", stdout, re.DOTALL)
            if stdout == no_axioms:
                axioms: list[str] | None = []
            elif list_match:
                axioms = [part.strip() for part in list_match.group(1).split(",") if part.strip()]
            else:
                axioms = None
            if process.returncode != 0:
                receipt["status"] = "failed"
                receipt["error"] = {"code": "lean_failed", "message": "Lean returned a nonzero exit code"}
            elif receipt["stderr"].strip() or axioms is None:
                receipt["status"] = "failed"
                receipt["error"] = {"code": "unrecognized_diagnostics", "message": "expected only one recognized axiom report and no other diagnostics"}
            elif not set(axioms).issubset(ALLOWED_AXIOMS):
                receipt["status"] = "failed"
                receipt["error"] = {"code": "disallowed_axioms", "message": "the theorem depends on axioms outside the core allowlist"}
            else:
                receipt["status"] = "simulated" if self.test_mode else "passed"
                receipt["scope"]["formal_proof"] = not self.test_mode
                receipt["result"] = {"accepted": not self.test_mode, "axioms": axioms,
                                     "simulation_only": self.test_mode,
                                     "encoded_statement": metadata["encoded_statement"]}
        except subprocess.TimeoutExpired as error:
            receipt["status"] = "timeout"
            receipt["stdout"] = (error.stdout or b"").decode("utf-8", errors="replace")
            receipt["stderr"] = (error.stderr or b"").decode("utf-8", errors="replace")
            receipt["error"] = {"code": "timeout", "message": "Lean subprocess exceeded the configured timeout"}
        except (OSError, SourceRejected) as error:
            receipt["status"] = "failed"
            receipt["error"] = {"code": "backend_error", "message": str(error)}
        finally:
            receipt["artifacts"]["stdout_sha256"] = sha256(receipt["stdout"].encode("utf-8")).hexdigest()
            receipt["artifacts"]["stderr_sha256"] = sha256(receipt["stderr"].encode("utf-8")).hexdigest()
        return receipt

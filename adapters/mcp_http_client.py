"""Host-fixed MCP 2025-11-25 Streamable HTTP client, JSON and POST SSE responses.

No redirects, retries, stream resumption or legacy HTTP+SSE fallback. Authentication
is copied only from the host environment. Each invocation owns a fresh session.
"""
from dataclasses import dataclass
import http.client
import ipaddress
import os
import queue
import re
import socket
import threading
import time
from urllib.parse import urlsplit

from .mcp_stdio_client import (McpStdioCapability, PROTOCOL_REVISION, _ENV_NAME, _Session,
                               _Stop, decode_frame)
from .wire import WireFailure

CONTRACT_VERSION = "mcp-http-client/" + PROTOCOL_REVISION


@dataclass(frozen=True)
class McpHttpServerConfig:
    url: str
    inherit_env: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.url) is not str:
            raise ValueError("URL must be a string")
        u = urlsplit(self.url)
        port = u.port
        try:
            loopback = ipaddress.ip_address(u.hostname).is_loopback if u.hostname else False
        except ValueError:
            loopback = False
        if (not u.hostname or u.username is not None or u.password is not None
                or u.fragment or any(ord(c) <= 32 or ord(c) >= 127 for c in self.url)
                or u.scheme not in ("http", "https") or (u.scheme == "http" and not loopback)
                or port == 0):
            raise ValueError("Expected an absolute HTTPS URL (HTTP only to literal loopback for tests)")
        if (type(self.inherit_env) is not tuple or len(self.inherit_env) > 1
                or any(type(n) is not str or not _ENV_NAME.fullmatch(n) for n in self.inherit_env)):
            raise ValueError("inherit_env must contain at most one host bearer environment name")


class _HttpSession(_Session):
    def __init__(self, owner, cancellation):
        self.owner, self.cancellation = owner, cancellation
        self.deadline = time.monotonic() + owner._timeout
        self.pending, self.frames = None, 0
        self.session_id, self.response, self.connection = None, None, None
        self.bytes_read = 0
        self.connections, self.responses, self.sockets = [], [], []
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        names = owner._server.inherit_env
        if names:
            token = os.environ.get(names[0])
            if not token or not re.fullmatch(r"[\x21-\x7e]+", token):
                raise _Stop("unavailable", "mcp_server_unavailable")
            self.headers["Authorization"] = "Bearer " + token

    def _check(self):
        if self.cancellation is not None and self.cancellation.is_set():
            raise _Stop("cancelled", "mcp_cancelled")
        if time.monotonic() >= self.deadline:
            raise _Stop("timed_out", "mcp_timed_out")

    def close(self):
        for sock in self.sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for conn in self.connections:
            conn.close()
        for response in self.responses:
            response.close()
        self.headers.clear()

    def _io(self, fn):
        self._check()
        done = queue.Queue(maxsize=1)

        def run():
            try:
                done.put((True, fn()))
            except Exception as error:
                done.put((False, error))

        threading.Thread(target=run, daemon=True).start()
        while True:
            self._check()
            try:
                ok, value = done.get(timeout=min(0.025, max(0.001, self.deadline - time.monotonic())))
            except queue.Empty:
                continue
            self._check()
            if ok:
                return value
            if isinstance(value, (TimeoutError, socket.timeout)):
                raise _Stop("timed_out", "mcp_timed_out")
            if isinstance(value, (OSError, http.client.HTTPException)):
                raise _Stop("unavailable", "mcp_server_unavailable")
            if isinstance(value, _Stop):
                raise value
            raise WireFailure("HTTP transport failed")

    def write(self, frame):
        msg = decode_frame(frame)
        u = urlsplit(self.owner._server.url)
        cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        try:
            conn = cls(u.hostname, u.port, timeout=max(0.001, self.deadline - time.monotonic()))
        except OSError:
            raise _Stop("unavailable", "mcp_server_unavailable") from None
        self.connection = conn
        self.connections.append(conn)
        connect = conn.connect

        def guarded_connect():
            self._check()
            connect()
            self.sockets.append(conn.sock)
            try:
                self._check()
            except _Stop:
                conn.close()
                raise

        conn.connect = guarded_connect
        headers = dict(self.headers)
        if self.session_id is not None:
            headers["Mcp-Session-Id"] = self.session_id
        if msg.get("method") != "initialize":
            headers["MCP-Protocol-Version"] = PROTOCOL_REVISION

        def send():
            conn.connect()
            conn.request("POST", (u.path or "/") + ("?" + u.query if u.query else ""), frame, headers)
            response = conn.getresponse()
            self.responses.append(response)
            return response

        response = self._io(send)
        if not 200 <= response.status < 300:
            response.close()
            raise _Stop("unavailable", "mcp_server_unavailable")
        if "id" not in msg or "method" not in msg:
            response.close()
            conn.close()
            if response.status != 202:
                raise WireFailure("Expected notification acceptance")
            return 0
        if msg["method"] == "initialize":
            sid = response.getheader("Mcp-Session-Id")
            if sid is not None and (not 1 <= len(sid) <= 1024 or not re.fullmatch(r"[\x21-\x7e]+", sid)):
                response.close()
                raise WireFailure("Invalid session id")
            self.session_id = sid
        self.response = response
        self.media = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if self.media not in ("application/json", "text/event-stream"):
            raise WireFailure("Unsupported response media type")
        return 0

    def _read(self, line=False):
        limit = self.owner.RESPONSE_FRAME_CAP + 1 - self.bytes_read
        data = self._io(lambda: self.response.readline(limit) if line else self.response.read(limit))
        self.bytes_read += len(data)
        if self.bytes_read > self.owner.RESPONSE_FRAME_CAP:
            raise _Stop("resource_rejected", "mcp_response_frame_cap")
        return data

    def _frame(self):
        self.frames += 1
        if self.frames > self.owner.MAX_FRAMES:
            raise _Stop("resource_rejected", "mcp_frame_count_cap")
        self.bytes_read = 0
        if self.media == "application/json":
            raw = self._read()
        else:
            fields = []
            while True:
                line = self._read(True)
                if not line:
                    raise WireFailure("SSE ended without a response")
                line = line.rstrip(b"\r\n")
                if not line:
                    if fields and b"\n".join(fields):
                        break
                    fields.clear()
                    continue
                if line.startswith(b"data:"):
                    fields.append(line[5:].removeprefix(b" "))
            raw = b"\n".join(fields)
        return decode_frame(raw), 1


class McpHttpCapability(McpStdioCapability):
    SERVER_CONFIG = McpHttpServerConfig
    CONTRACT_VERSION = CONTRACT_VERSION

    def _open_session(self, cancellation):
        return _HttpSession(self, cancellation)

    def _close_session(self, session):
        session.close()

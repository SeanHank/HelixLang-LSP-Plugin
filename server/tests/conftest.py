"""Shared fixtures: a FakeClient that speaks the LSP wire protocol in-memory."""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pytest
from helixlang_lsp.jsonrpc import Dispatcher
from helixlang_lsp.server import HelixLspServer


class FakeClient:
    """In-memory LSP client: sends framed messages, collects responses."""

    def __init__(self) -> None:
        self.inbox = io.StringIO()
        self.outbox = io.StringIO()
        self._req_id = 0

    def _send(self, msg: dict[str, Any]) -> None:
        body = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        data = body.encode("utf-8")
        self.inbox.write(f"Content-Length: {len(data)}\r\n\r\n{body}")

    def send_raw(self, body: str) -> None:
        self.inbox.write(f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}")

    def request(self, method: str, params: dict[str, Any] | None = None) -> int:
        self._req_id += 1
        self._send({"jsonrpc": "2.0", "id": self._req_id, "method": method,
                    "params": params or {}})
        return self._req_id

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def read_messages(self) -> list[dict[str, Any]]:
        data = self.inbox.getvalue()
        msgs: list[dict[str, Any]] = []
        while data:
            m = re.match(r"Content-Length: (\d+)\r\n\r\n", data)
            if not m:
                break
            n = int(m.group(1))
            if len(data) < m.end() + n:
                break
            msgs.append(json.loads(data[m.end():m.end() + n]))
            data = data[m.end() + n:]
        self.inbox.seek(0)
        self.inbox.truncate()
        return msgs

    def responses(self, server: HelixLspServer, debounce_ms: int = 0) -> list[dict[str, Any]]:
        """Dispatch everything in the inbox and return all outbound messages."""
        dispatcher = Dispatcher(server, writer=lambda _m: None)
        pushed: list[dict[str, Any]] = []
        if debounce_ms <= 0:
            server._settings["helix.lsp.diagnostics.debounceMs"] = 0
        for msg in self.read_messages():
            for outbound in dispatcher.dispatch(msg):
                pushed.append(outbound)
        return pushed


@pytest.fixture
def server() -> HelixLspServer:
    srv = HelixLspServer()
    srv._settings["helix.lsp.diagnostics.debounceMs"] = 0
    return srv


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def helix_text() -> str:
    return (
        "#config table=standard\n"
        "#promoter name=p_lac strength=0.8\n"
        "#gene name=lacZ promoter=p_lac\n"
        "ATG GCT GGT TAA\n"
        "#end\n"
    )

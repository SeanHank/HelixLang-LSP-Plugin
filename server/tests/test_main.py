"""In-process tests for the CLI entry points (``main.py`` / ``__main__.py``).

The subprocess smoke tests in ``test_cli.py`` validate the real transports but
run outside the coverage process; these tests exercise the same entry points
in-process so the argument parsing, transport dispatch, and the module entry
point stay measured by the coverage gate.
"""

from __future__ import annotations

import io
import json
import runpy
import socket
import sys
import threading
import time
import types

import helixlang_lsp.main as main
import pytest


def _frame(msg: dict) -> bytes:
    body = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def test_build_parser_defaults():
    args = main._build_parser().parse_args([])
    assert args.stdio is False
    assert args.host is None and args.port is None
    assert args.trace is None
    assert args.loglevel == "WARNING"


def test_main_stdio_with_fake_server(monkeypatch):
    class FakeServer:
        def __init__(self, on_log) -> None:
            self.on_log = on_log

        def run(self, reader, writer) -> int:
            return 42

    monkeypatch.setattr(main, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main.main([]) == 42


def test_main_stdio_trace_wires_transcript(monkeypatch, tmp_path):
    trace = tmp_path / "trace.jsonl"

    class FakeServer:
        def __init__(self, on_log) -> None:
            self.on_log = on_log
            self._trace = None

        def run(self, reader, writer) -> int:
            assert self._trace is not None
            self._trace({"jsonrpc": "2.0", "method": "x/y"})
            return 0

    monkeypatch.setattr(main, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main.main(["--trace", str(trace)]) == 0
    assert json.loads(trace.read_text().strip())["method"] == "x/y"


def test_trace_writer(tmp_path):
    path = tmp_path / "t.jsonl"
    writer = main._trace_writer(str(path))
    writer({"jsonrpc": "2.0", "method": "a/b", "id": 3})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["method"] == "a/b"


def test_serve_tcp_with_fake_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class FakeServer:
        def __init__(self, on_log) -> None:
            self.on_log = on_log

        def run(self, reader, writer) -> int:
            return 7

    result: dict = {}

    def target() -> None:
        result["code"] = main._serve_tcp(FakeServer(None), "127.0.0.1", port)

    t = threading.Thread(target=target)
    t.start()
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                conn = socket.create_connection(("127.0.0.1", port), timeout=2)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        conn.close()
    finally:
        t.join(timeout=5)
    assert result.get("code") == 7


def test_run_module_entry_smoke(monkeypatch, tmp_path):
    """``python -m helixlang_lsp`` end-to-end in-process via the real server."""
    trace = tmp_path / "trace.jsonl"
    inbox = io.BytesIO(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"rootUri": "file:///tmp"}}))
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=inbox))
    outbox = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=outbox))
    # runpy replaces argv[0] with the module name and keeps the rest, so do not
    # include "-m helixlang_lsp" here.
    monkeypatch.setattr(sys, "argv", ["dummy", "--trace", str(trace)])
    with pytest.raises(SystemExit) as ei:
        runpy.run_module("helixlang_lsp", run_name="__main__")
    assert ei.value.code == 1  # EOF without shutdown
    assert b"Content-Length:" in outbox.getvalue()
    assert trace.read_text(encoding="utf-8").splitlines()

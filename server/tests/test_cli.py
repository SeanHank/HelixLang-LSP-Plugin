"""End-to-end CLI smoke tests over the stdio/TCP transports.

Launches ``python -m helixlang_lsp`` as a real subprocess and speaks framed
JSON-RPC over its pipes. This exercises the actual entry point (``main.py``),
argument parsing, the run loop, and binary framing — the parts the in-memory
conformance harness (``conftest.FakeClient``) does not reach.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time

from helixlang_lsp.uri import path_to_uri


def _connect_with_retry(host: str, port: int, *, timeout: float = 10) -> socket.socket:
    """Connect to a freshly spawned server, retrying until it starts listening."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return socket.create_connection((host, port), timeout=5)
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


def _frame(msg: dict) -> bytes:
    body = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def _read_frames(raw: bytes) -> list[dict]:
    frames: list[dict] = []
    data = raw
    while data:
        end = data.find(b"\r\n\r\n")
        if end < 0:
            break
        header = data[:end].decode("utf-8", errors="replace")
        length = 0
        for line in header.split("\r\n"):
            key, _, value = line.partition(":")
            if key.strip().lower() == "content-length":
                length = int(value.strip())
        body_start = end + 4
        if len(data) < body_start + length:
            break
        frames.append(json.loads(data[body_start:body_start + length]))
        data = data[body_start + length:]
    return frames


def _run_stdio(*messages: dict, args: list[str] | None = None) -> tuple[list[dict], int]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "helixlang_lsp", *((args) or []), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    for msg in messages:
        proc.stdin.write(_frame(msg))
    proc.stdin.close()
    out = proc.stdout.read()
    proc.stderr.read()  # drain; trace/logs otherwise block the pipe
    code = proc.wait(timeout=20)
    return _read_frames(out), code


def _session_messages(text: str = "") -> list[dict]:
    msgs: list[dict] = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"rootUri": path_to_uri("/tmp")}},
        {"jsonrpc": "2.0", "method": "initialized"},
    ]
    if text:
        msgs.append({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                     "params": {"textDocument": {"uri": path_to_uri("/tmp/t.helix"),
                                                 "languageId": "helix", "version": 1,
                                                 "text": text}}})
    msgs += [
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
        {"jsonrpc": "2.0", "method": "exit"},
    ]
    return msgs


def test_stdio_initialize_handshake_and_clean_exit():
    frames, code = _run_stdio(*_session_messages())
    assert code == 0
    results = [f for f in frames if "result" in f]
    assert len(results) == 2
    init = results[0]
    assert init["id"] == 1
    assert init["result"]["serverInfo"]["name"] == "helixlang-lsp"
    caps = init["result"]["capabilities"]
    assert caps["textDocumentSync"]["change"] == 2
    assert results[1]["result"] is None  # shutdown response


def test_stdio_full_session_publishes_diagnostics():
    text = "#gene name=g\nATG GGGG TAA\n#end\n"
    frames, code = _run_stdio(*_session_messages(text))
    assert code == 0
    methods = [f.get("method") for f in frames]
    assert "textDocument/publishDiagnostics" in methods
    diag = next(f for f in frames if f.get("method") == "textDocument/publishDiagnostics")
    codes = {d["code"] for d in diag["params"]["diagnostics"]}
    assert "lex" in codes


def test_stdio_trace_writes_jsonl_transcript(tmp_path):
    trace = tmp_path / "trace.jsonl"
    frames, code = _run_stdio(*_session_messages(),
                              args=["--trace", str(trace), "--loglevel", "DEBUG"])
    assert code == 0
    assert len(frames) >= 2
    lines = trace.read_text(encoding="utf-8").splitlines()
    assert lines, "trace transcript is empty"
    entry = json.loads(lines[0])
    assert "method" in entry or "id" in entry or "result" in entry or "error" in entry


def test_stdio_exit_without_shutdown_returns_nonzero():
    # Server must exit non-zero when the stream closes before a shutdown.
    proc = subprocess.Popen(
        [sys.executable, "-m", "helixlang_lsp", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {}}))
    proc.stdin.close()
    proc.stdout.read()
    proc.stderr.read()
    assert proc.wait(timeout=20) != 0


def test_tcp_transport_handshake():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-m", "helixlang_lsp", "--host", "127.0.0.1",
         "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        with _connect_with_retry("127.0.0.1", port) as conn:
            for msg in _session_messages():
                conn.sendall(_frame(msg))
            conn.shutdown(socket.SHUT_WR)
            raw = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk
        code = proc.wait(timeout=20)
        proc.stdout.read()
        proc.stderr.read()
        assert code == 0
        frames = _read_frames(raw)
        results = [f for f in frames if "result" in f]
        assert results and results[0]["result"]["serverInfo"]["name"] == "helixlang-lsp"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

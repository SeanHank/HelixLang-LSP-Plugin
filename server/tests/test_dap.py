"""Tests for the DAP adapter (P1)."""

from __future__ import annotations

import io

from helixlang_lsp.dap import DapSession, HelixDebugAdapter

VALID = (
    "#gene name=g\n"
    "ATG GCT GGT TAA\n"
    "#end\n"
)


def _session() -> tuple[DapSession, HelixDebugAdapter]:
    adapter = HelixDebugAdapter()
    return DapSession(adapter), adapter


def test_initialize_capabilities():
    session, adapter = _session()
    caps = adapter.handle_initialize({})
    assert caps["capabilities"]["supportsConfigurationDoneRequest"] is True


def test_launch_and_threads():
    session, adapter = _session()
    adapter.handle_initialize({})
    adapter.handle_launch({"program": VALID})
    threads = adapter.handle_threads({})
    assert threads["threads"][0]["name"] == "main"


def test_breakpoints_and_stack():
    session, adapter = _session()
    adapter.handle_launch({"program": VALID})
    resp = adapter.handle_setBreakpoints(
        {"source": {"name": "x.helix"}, "breakpoints": [{"line": 2}]})
    assert resp["breakpoints"][0]["line"] == 2
    assert resp["breakpoints"][0]["verified"] is True
    stack = adapter.handle_stackTrace({})
    assert stack["stackFrames"]


def test_variables_scopes():
    session, adapter = _session()
    adapter.handle_launch({"program": VALID})
    adapter.handle_continue({})
    scopes = adapter.handle_scopes({"frameId": 1})
    names = [s["name"] for s in scopes["scopes"]]
    assert names == ["Cell", "GRN", "Stack"]
    vars_ = adapter.handle_variables({"variablesReference": 1})
    keys = {v["name"] for v in vars_["variables"]}
    assert {"x", "y", "energy", "alive"} <= keys


def test_evaluate():
    session, adapter = _session()
    adapter.handle_launch({"program": VALID})
    result = adapter.handle_evaluate({"expression": "energy"})
    assert "result" in result


def test_step_commands():
    session, adapter = _session()
    adapter.handle_launch({"program": VALID})
    for cmd in ("next", "stepIn", "stepOut", "continue"):
        handler = getattr(adapter, "handle_" + cmd)
        assert handler({}) is not None


def test_continue_emits_stopped_event():
    """Continue/hit-breakpoint reports a `stopped` event before the response."""
    adapter = HelixDebugAdapter()
    out = io.BytesIO()
    from helixlang_lsp.jsonrpc import read_message_binary, write_message_binary

    adapter._writer = lambda m: write_message_binary(out, m)
    adapter.handle_launch({"program": VALID})
    adapter.handle_setBreakpoints(
        {"source": {"name": "x.helix"}, "breakpoints": [{"line": 2}]})
    adapter.handle_continue({})
    out.seek(0)
    msg = read_message_binary(out)
    assert msg["type"] == "event"
    assert msg["event"] == "stopped"
    assert msg["body"]["reason"] == "breakpoint"


def test_continue_emits_terminated_without_breakpoints():
    """Without breakpoints the program runs to HALT and reports `terminated`."""
    adapter = HelixDebugAdapter()
    out = io.BytesIO()
    from helixlang_lsp.jsonrpc import read_message_binary, write_message_binary

    adapter._writer = lambda m: write_message_binary(out, m)
    adapter.handle_launch({"program": VALID})
    adapter.handle_configurationDone({})
    out.seek(0)
    msg = read_message_binary(out)
    assert msg["type"] == "event"
    assert msg["event"] == "terminated"


def test_dap_session_wire_roundtrip():
    session, adapter = _session()
    inbox = io.BytesIO()
    from helixlang_lsp.jsonrpc import write_message_binary

    write_message_binary(inbox, {"seq": 1, "type": "request", "command": "initialize",
                                 "arguments": {}})
    write_message_binary(inbox, {"seq": 2, "type": "request", "command": "threads"})
    inbox.seek(0)
    out = io.BytesIO()
    session.run(inbox, out)

    out.seek(0)
    from helixlang_lsp.jsonrpc import read_message_binary

    resp1 = read_message_binary(out)
    assert resp1["type"] == "response"
    assert resp1["success"] is True
    assert "capabilities" in resp1["body"]
    resp2 = read_message_binary(out)
    assert resp2["body"]["threads"][0]["id"] == 1


def test_unknown_command_returns_error():
    session, adapter = _session()
    inbox = io.BytesIO()
    from helixlang_lsp.jsonrpc import write_message_binary

    write_message_binary(inbox, {"seq": 1, "type": "request", "command": "nope"})
    inbox.seek(0)
    out = io.BytesIO()
    session.run(inbox, out)
    out.seek(0)
    from helixlang_lsp.jsonrpc import read_message_binary

    resp = read_message_binary(out)
    assert resp["success"] is False
    assert resp["error"]["id"] == -32601


def test_dap_cli_mode_serves_a_session(tmp_path):
    """`python -m helixlang_lsp --dap --dap-port-file <file>` serves one session."""
    import os
    import socket
    import subprocess
    import sys
    import time

    port_file = tmp_path / "dap-port"
    server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "PYTHONPATH": server_dir}
    proc = subprocess.Popen(
        [sys.executable, "-m", "helixlang_lsp", "--dap", "--dap-port", "0",
         "--dap-port-file", str(port_file)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=server_dir, env=env)
    try:
        port = None
        for _ in range(100):
            if port_file.exists():
                port = int(port_file.read_text().strip())
                break
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert port is not None, "DAP server did not write its port file"

        from helixlang_lsp.jsonrpc import read_message_binary, write_message_binary

        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            reader = sock.makefile("rb")
            writer = sock.makefile("wb")

            def req(seq: int, command: str, args=None) -> dict:
                write_message_binary(writer, {"seq": seq, "type": "request",
                                              "command": command,
                                              "arguments": args or {}})
                writer.flush()
                return read_message_binary(reader)

            caps = req(1, "initialize")
            assert caps["success"] is True
            assert caps["body"]["capabilities"]["supportsConfigurationDoneRequest"] is True
            launch = req(2, "launch", {"program": VALID})
            assert launch["success"] is True
            bps = req(3, "setBreakpoints",
                      {"source": {"name": "x.helix"}, "breakpoints": [{"line": 2}]})
            assert bps["body"]["breakpoints"][0]["line"] == 2
            write_message_binary(writer, {"seq": 4, "type": "request",
                                          "command": "configurationDone",
                                          "arguments": {}})
            writer.flush()
            event = read_message_binary(reader)
            assert event["type"] == "event"
            assert event["event"] == "stopped"
            assert event["body"]["reason"] == "breakpoint"
            done = read_message_binary(reader)
            assert done["success"] is True
            stack = req(5, "stackTrace")
            assert stack["body"]["stackFrames"]
            scopes = req(6, "scopes", {"frameId": 1})
            assert [s["name"] for s in scopes["body"]["scopes"]] == ["Cell", "GRN", "Stack"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

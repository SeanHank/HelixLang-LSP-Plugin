"""Full-coverage tests for protocol.py, dap.py, and main.py.

Exercises every uncovered branch: serialization edge cases, DAP session
lifecycle, variable inspection, source reading, and CLI entry points.
"""

from __future__ import annotations

import io
import json
import socket
import sys
import threading
import time
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from helixlang_lsp import main as main_mod
from helixlang_lsp.dap import (
    DapBreakpoint,
    DapSession,
    HelixDebugAdapter,
    _fmt,
    _read_source,
    _uri_of,
    _var,
)
from helixlang_lsp.protocol import (
    CodeAction,
    CompletionItem,
    CompletionList,
    Diagnostic,
    DiagnosticRelatedInformation,
    DocumentSymbol,
    FoldingRange,
    Hover,
    InlayHint,
    Location,
    LocationLink,
    MarkupContent,
    Position,
    Range,
    SemanticTokens,
    SymbolInformation,
    TextEdit,
    WorkspaceEdit,
    encode_semantic_tokens,
)

VALID = (
    "#gene name=g\n"
    "ATG GCT GGT TAA\n"
    "#end\n"
)


def _pos(line: int = 0, c: int = 0) -> Position:
    return Position(line=line, character=c)


def _range(l1: int = 0, c1: int = 0, l2: int = 0, c2: int = 10) -> Range:
    return Range(start=_pos(l1, c1), end=_pos(l2, c2))


def _loc(uri: str = "file:///x.helix") -> Location:
    return Location(uri=uri, range=_range())


# ======================================================================
# protocol.py tests
# ======================================================================

def test_diagnostic_related_information_to_dict():
    ri = DiagnosticRelatedInformation(location=_loc("file:///a.helix"), message="see here")
    d = ri.to_dict()
    assert d["message"] == "see here"
    assert d["location"]["uri"] == "file:///a.helix"


def test_diagnostic_to_dict_with_related_information():
    ri = DiagnosticRelatedInformation(location=_loc(), message="note")
    diag = Diagnostic(range=_range(), message="err", related_information=[ri])
    d = diag.to_dict()
    assert len(d["relatedInformation"]) == 1
    assert d["relatedInformation"][0]["message"] == "note"


def test_diagnostic_to_dict_with_severity_and_code():
    diag = Diagnostic(range=_range(), message="x", severity=1, code="E001")
    d = diag.to_dict()
    assert d["severity"] == 1
    assert d["code"] == "E001"


def test_diagnostic_to_dict_with_data():
    diag = Diagnostic(range=_range(), message="x", data={"k": "v"})
    d = diag.to_dict()
    assert d["data"] == {"k": "v"}


def test_diagnostic_to_dict_minimal():
    diag = Diagnostic(range=_range(), message="x")
    d = diag.to_dict()
    assert "severity" not in d
    assert "code" not in d
    assert "relatedInformation" not in d
    assert "data" not in d


def test_hover_to_dict_with_range():
    h = Hover(contents=MarkupContent(kind="markdown", value="hi"), range=_range())
    d = h.to_dict()
    assert "range" in d


def test_hover_to_dict_without_range():
    h = Hover(contents=MarkupContent(kind="plaintext", value="hi"))
    d = h.to_dict()
    assert "range" not in d


def test_completion_item_to_dict_all_fields():
    te = TextEdit(range=_range(), new_text="new")
    ci = CompletionItem(
        label="x", kind=3, detail="d", documentation="doc",
        insert_text="ins", sort_text="st", text_edit=te)
    d = ci.to_dict()
    assert d["label"] == "x"
    assert d["kind"] == 3
    assert d["detail"] == "d"
    assert d["documentation"] == "doc"
    assert d["insertText"] == "ins"
    assert d["sortText"] == "st"
    assert d["textEdit"]["newText"] == "new"


def test_completion_item_doc_as_markup():
    mc = MarkupContent(kind="markdown", value="**bold**")
    ci = CompletionItem(label="y", documentation=mc)
    d = ci.to_dict()
    assert d["documentation"]["kind"] == "markdown"


def test_completion_item_minimal():
    ci = CompletionItem(label="z")
    d = ci.to_dict()
    assert d == {"label": "z"}


def test_completion_list_to_dict():
    items = [CompletionItem(label="a"), CompletionItem(label="b")]
    cl = CompletionList(is_incomplete=True, items=items)
    d = cl.to_dict()
    assert d["isIncomplete"] is True
    assert len(d["items"]) == 2


def test_document_symbol_to_dict_with_children():
    child = DocumentSymbol(
        name="child", detail=None, kind=12,
        range=_range(), selection_range=_range())
    parent = DocumentSymbol(name="parent", detail="pd", kind=5, range=_range(),
                            selection_range=_range(), children=[child])
    d = parent.to_dict()
    assert d["detail"] == "pd"
    assert len(d["children"]) == 1
    assert d["children"][0]["name"] == "child"


def test_document_symbol_no_children():
    sym = DocumentSymbol(name="leaf", detail=None, kind=1, range=_range(), selection_range=_range())
    d = sym.to_dict()
    assert "children" not in d
    assert "detail" not in d


def test_symbol_information_to_dict_with_container():
    si = SymbolInformation(name="fn", kind=12, location=_loc(), container_name="mod")
    d = si.to_dict()
    assert d["containerName"] == "mod"


def test_symbol_information_to_dict_no_container():
    si = SymbolInformation(name="fn", kind=12, location=_loc())
    d = si.to_dict()
    assert "containerName" not in d


def test_folding_range_all_optional_fields():
    fr = FoldingRange(start_line=0, end_line=10, start_character=5, end_character=20, kind="region")
    d = fr.to_dict()
    assert d["startCharacter"] == 5
    assert d["endCharacter"] == 20
    assert d["kind"] == "region"


def test_folding_range_no_optionals():
    fr = FoldingRange(start_line=0, end_line=5)
    d = fr.to_dict()
    assert "startCharacter" not in d
    assert "endCharacter" not in d
    assert "kind" not in d


def test_encode_semantic_tokens_single_line():
    tokens = [(0, 0, 3, 0, 0), (0, 5, 4, 2, 0)]
    result = encode_semantic_tokens(tokens)
    assert result == [0, 0, 3, 0, 0, 0, 5, 4, 2, 0]


def test_encode_semantic_tokens_multi_line():
    tokens = [(0, 0, 3, 0, 0), (2, 5, 4, 2, 0)]
    result = encode_semantic_tokens(tokens)
    assert result == [0, 0, 3, 0, 0, 2, 5, 4, 2, 0]


def test_encode_semantic_tokens_empty():
    assert encode_semantic_tokens([]) == []


def test_workspace_edit_to_dict():
    te = TextEdit(range=_range(), new_text="fix")
    we = WorkspaceEdit(changes={"file:///a.helix": [te]})
    d = we.to_dict()
    assert "file:///a.helix" in d["changes"]
    assert d["changes"]["file:///a.helix"][0]["newText"] == "fix"


def test_workspace_edit_empty():
    we = WorkspaceEdit()
    d = we.to_dict()
    assert d["changes"] == {}


def test_code_action_to_dict_all_fields():
    we = WorkspaceEdit(changes={"file:///x.helix": []})
    ca = CodeAction(title="fix", kind="quickfix", edit=we,
                    command={"title": "run", "command": "my.ext"})
    d = ca.to_dict()
    assert d["kind"] == "quickfix"
    assert "edit" in d
    assert d["command"]["command"] == "my.ext"


def test_code_action_minimal():
    ca = CodeAction(title="do")
    d = ca.to_dict()
    assert "kind" not in d
    assert "edit" not in d
    assert "command" not in d


def test_inlay_hint_to_dict_all_fields():
    ih = InlayHint(position=_pos(1, 5), label="int", kind=1,
                   padding_right=True, tooltip="the type", data={"extra": 1})
    d = ih.to_dict()
    assert d["kind"] == 1
    assert d["paddingRight"] is True
    assert d["tooltip"] == "the type"
    assert d["data"] == {"extra": 1}


def test_inlay_hint_minimal():
    ih = InlayHint(position=_pos(), label="?")
    d = ih.to_dict()
    assert "kind" not in d
    assert "paddingRight" not in d
    assert "tooltip" not in d
    assert "data" not in d


def test_location_link_with_origin():
    ll = LocationLink(
        target_uri="file:///a.helix",
        target_range=_range(0, 0, 1, 0),
        target_selection_range=_range(0, 0, 0, 5),
        origin_selection_range=_range(0, 0, 0, 3))
    d = ll.to_dict()
    assert d["targetUri"] == "file:///a.helix"
    assert "originSelectionRange" in d


def test_location_link_no_origin():
    ll = LocationLink(
        target_uri="file:///a.helix",
        target_range=_range(),
        target_selection_range=_range())
    d = ll.to_dict()
    assert "originSelectionRange" not in d


def test_semantic_tokens_to_dict():
    st = SemanticTokens(data=[1, 0, 3, 0, 0])
    d = st.to_dict()
    assert d["data"] == [1, 0, 3, 0, 0]


def test_location_to_dict():
    loc = Location(uri="file:///a.helix", range=_range())
    d = loc.to_dict()
    assert d["uri"] == "file:///a.helix"
    assert "start" in d["range"]


def test_markup_content_to_dict():
    mc = MarkupContent(kind="plaintext", value="hello")
    d = mc.to_dict()
    assert d["kind"] == "plaintext"
    assert d["value"] == "hello"


# ======================================================================
# dap.py tests — adapter
# ======================================================================

def test_emit_event_with_writer():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter.emit_event("stopped", {"reason": "bp"})
    assert len(events) == 1
    assert events[0]["type"] == "event"
    assert events[0]["event"] == "stopped"
    assert events[0]["body"]["reason"] == "bp"


def test_emit_event_no_body_with_writer():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter.emit_event("terminated")
    assert events[0]["body"] == {}


def test_emit_event_no_writer():
    adapter = HelixDebugAdapter()
    adapter.emit_event("stopped", {"reason": "bp"})
    assert adapter._writer is None


def test_handle_launch_fails_on_invalid_program():
    adapter = HelixDebugAdapter()
    with pytest.raises(RuntimeError, match="launch failed"):
        adapter.handle_launch({"program": "xyz!!!"})


def test_handle_launch_with_empty_params():
    adapter = HelixDebugAdapter()
    with pytest.raises(RuntimeError, match="launch failed"):
        adapter.handle_launch({"program": "!!!bad!!!"})


def test_handle_disconnect():
    adapter = HelixDebugAdapter()
    adapter._debugger = MagicMock()
    adapter.handle_disconnect(None)
    assert adapter._debugger is None


def test_handle_setBreakpoints_with_existing_bps():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter.handle_setBreakpoints(
        {"source": {"name": "x.helix"}, "breakpoints": [{"line": 2}]})
    resp = adapter.handle_setBreakpoints(
        {"source": {"name": "x.helix"}, "breakpoints": [{"line": 3}]})
    assert resp["breakpoints"][0]["line"] == 3
    assert resp["breakpoints"][0]["verified"] is True


def test_handle_setBreakpoints_empty():
    adapter = HelixDebugAdapter()
    resp = adapter.handle_setBreakpoints(None)
    assert resp["breakpoints"] == []


def test_handle_stackTrace_no_debugger_fallback():
    adapter = HelixDebugAdapter()
    st = adapter.handle_stackTrace({})
    assert st["stackFrames"][0]["name"] == "<main>"
    assert st["stackFrames"][0]["line"] == 1


def test_handle_stackTrace_no_frames_fallback():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter.handle_continue({})
    st = adapter.handle_stackTrace({})
    assert st["stackFrames"][0]["name"] == "<main>"


def test_handle_stackTrace_with_non_empty_frames():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    fake_debugger = MagicMock()
    fake_debugger.get_call_stack.return_value = [{"gene": "my_gene"}]
    fake_debugger.get_state().line = 5
    adapter._debugger = fake_debugger
    st = adapter.handle_stackTrace({})
    assert len(st["stackFrames"]) == 1
    assert st["stackFrames"][0]["name"] == "my_gene"


def test_handle_variables_cell():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    state = adapter._debugger.get_state()
    state.cell_state = {"x": 1, "alive": True}
    vars_ = adapter.handle_variables({"variablesReference": 1})
    names = {v["name"] for v in vars_["variables"]}
    assert "alive" in names


def test_handle_variables_grn():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    vars_ = adapter.handle_variables({"variablesReference": 2})
    assert "variables" in vars_


def test_handle_variables_stack():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    vars_ = adapter.handle_variables({"variablesReference": 3})
    assert "variables" in vars_


def test_handle_variables_unknown_ref():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter._debugger.get_state().cell_state = {}
    vars_ = adapter.handle_variables({"variablesReference": 99})
    assert vars_["variables"] == []


def test_handle_variables_no_debugger():
    adapter = HelixDebugAdapter()
    vars_ = adapter.handle_variables({"variablesReference": 1})
    assert vars_["variables"] == []


def test_handle_variables_none_params():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter._debugger.get_state().cell_state = {"a": 1}
    vars_ = adapter.handle_variables(None)
    assert vars_["variables"]


def test_handle_evaluate_no_session():
    adapter = HelixDebugAdapter()
    with pytest.raises(RuntimeError, match="no active session"):
        adapter.handle_evaluate({"expression": "x"})


def test_handle_evaluate_inspect_raises():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    original = adapter._debugger.inspect

    def raising(expr):
        raise ValueError("bad expr")

    adapter._debugger.inspect = raising
    with pytest.raises(RuntimeError, match="cannot evaluate"):
        adapter.handle_evaluate({"expression": "bad"})
    adapter._debugger.inspect = original


def test_handle_evaluate_none_params():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    result = adapter.handle_evaluate(None)
    assert "result" in result


def test_handle_pause():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    result = adapter.handle_pause({})
    assert result == {}
    assert events[0]["event"] == "stopped"
    assert events[0]["body"]["reason"] == "pause"


def test_handle_next_no_debugger():
    adapter = HelixDebugAdapter()
    result = adapter.handle_next({})
    assert result["allThreadsContinued"] is True


def test_handle_stepIn_no_debugger():
    adapter = HelixDebugAdapter()
    result = adapter.handle_stepIn({})
    assert result["allThreadsContinued"] is True


def test_handle_stepOut_no_debugger():
    adapter = HelixDebugAdapter()
    result = adapter.handle_stepOut({})
    assert result["allThreadsContinued"] is True


def test_line_of_state_no_debugger():
    adapter = HelixDebugAdapter()
    assert adapter._line_of_state() == 1


def test_line_of_state_with_debugger():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    line = adapter._line_of_state()
    assert line >= 1


def test_fmt_dict():
    assert _fmt({"a": 1}) == '{"a": "1"}'


def test_fmt_list():
    assert _fmt([1, 2]) == "[1, 2]"


def test_fmt_tuple():
    assert _fmt((1,)) == "[1]"


def test_fmt_str():
    assert _fmt("hello") == "hello"


def test_fmt_nested_dict():
    assert '"a"' in _fmt({"a": {"b": 1}})


def test_fmt_nested_list():
    assert "2" in _fmt([1, [2, 3]])


def test_read_source_empty():
    assert _read_source("") == ""


def test_read_source_inline():
    assert _read_source("ATG GCT") == "ATG GCT"


def test_read_source_real_file(tmp_path):
    p = tmp_path / "test.hx"
    p.write_text("file content")
    assert _read_source(str(p)) == "file content"


def test_var_helper():
    d = _var("x", 42)
    assert d["name"] == "x"
    assert d["value"] == "42"
    assert d["type"] == "int"


def test_var_helper_dict():
    d = _var("d", {"k": "v"})
    assert "k" in d["value"]


def test_var_helper_list():
    d = _var("l", [1, 2])
    assert "[" in d["value"]


def test_uri_of():
    u = _uri_of("/tmp/test.hx")
    assert u.startswith("file://")


# ======================================================================
# dap.py tests — DapSession transport
# ======================================================================

def test_dap_session_writer_mode():
    adapter = HelixDebugAdapter()
    session = DapSession(adapter)
    reader = MagicMock()
    reader.read_message.side_effect = [
        {"seq": 1, "command": "initialize", "arguments": {}},
        None,
    ]
    writer = MagicMock()
    result = session.run(reader, writer)
    assert result == 0
    assert writer.write_message.call_count >= 1


def test_dap_session_handler_exception():
    adapter = HelixDebugAdapter()
    session = DapSession(adapter)

    def bad_handler(_params):
        raise ValueError("oops")

    adapter.handle_bad = bad_handler
    responses: list[dict] = []
    session._handle({"seq": 5, "command": "bad"}, lambda m: responses.append(m))
    assert len(responses) == 1
    assert responses[0]["success"] is False
    assert "oops" in responses[0]["error"]["message"]


def test_dap_session_respond_with_error():
    session = DapSession(HelixDebugAdapter())
    responses: list[dict] = []
    session._respond(lambda m: responses.append(m), 1, None,
                     {"id": -1, "message": "fail"})
    assert responses[0]["success"] is False
    assert responses[0]["error"]["id"] == -1


def test_dap_session_respond_with_result():
    session = DapSession(HelixDebugAdapter())
    responses: list[dict] = []
    session._respond(lambda m: responses.append(m), 1, {"key": "val"}, None)
    assert responses[0]["success"] is True
    assert responses[0]["body"]["key"] == "val"


def test_dap_session_run_none_msg():
    adapter = HelixDebugAdapter()
    session = DapSession(adapter)
    reader = MagicMock()
    reader.read_message.return_value = None
    writer = MagicMock()
    result = session.run(reader, writer)
    assert result == 0


def test_continue_loop_no_debugger():
    adapter = HelixDebugAdapter()
    assert adapter._continue_loop() is None


def test_continue_loop_runs_to_halt():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    bp = adapter._continue_loop()
    assert bp is None


def test_continue_loop_hits_breakpoint():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter.handle_setBreakpoints(
        {"source": {"name": "x.helix"}, "breakpoints": [{"line": 2}]})
    bp = adapter._continue_loop()
    assert bp is not None
    assert bp.line == 2


def test_continue_loop_no_breakpoint_match():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    state = adapter._debugger.get_state()
    adapter._breakpoints = [DapBreakpoint(line=state.line + 999, verified=True, id=1)]
    bp = adapter._continue_loop()
    assert bp is None


def test_emit_outcome_none_bp():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter._emit_outcome(None)
    assert events[0]["event"] == "terminated"


def test_emit_outcome_with_bp():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter._emit_outcome(DapBreakpoint(line=1, verified=True, id=1))
    assert events[0]["event"] == "stopped"
    assert events[0]["body"]["hitBreakpointIds"] == [1]


def test_emit_step_no_debugger():
    adapter = HelixDebugAdapter()
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter._emit_step("step")
    assert events[0]["event"] == "terminated"


def test_emit_step_with_no_vm_frames():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    adapter.handle_continue({})
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter._emit_step("step")
    assert events[0]["event"] == "terminated"


def test_emit_step_with_vm_frames():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    fake_debugger = MagicMock()
    fake_debugger.vm.frames = [1]
    adapter._debugger = fake_debugger
    events: list[dict] = []
    adapter._writer = lambda m: events.append(m)
    adapter._emit_step("step")
    assert events[0]["event"] == "stopped"
    assert events[0]["body"]["reason"] == "step"


def test_launch_with_target_param():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"target": VALID})
    assert adapter._program is not None


def test_handle_next_with_debugger():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    result = adapter.handle_next({})
    assert result["allThreadsContinued"] is True


def test_handle_stepIn_with_debugger():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    result = adapter.handle_stepIn({})
    assert result["allThreadsContinued"] is True


def test_handle_stepOut_with_debugger():
    adapter = HelixDebugAdapter()
    adapter.handle_launch({"program": VALID})
    result = adapter.handle_stepOut({})
    assert result["allThreadsContinued"] is True


# ======================================================================
# main.py tests
# ======================================================================

def test_main_dap_mode(monkeypatch):
    called: dict[str, Any] = {}

    def fake_serve_dap(port, port_file):
        called["port"] = port
        called["port_file"] = port_file
        return 5

    monkeypatch.setattr(main_mod, "_serve_dap", fake_serve_dap)
    code = main_mod.main(["--dap", "--dap-port", "9000", "--dap-port-file", "/tmp/pf"])
    assert code == 5
    assert called["port"] == 9000
    assert called["port_file"] == "/tmp/pf"


def test_main_stdio_mode(monkeypatch):
    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            return 42

    monkeypatch.setattr(main_mod, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main_mod.main([]) == 42


def test_main_tcp_mode(monkeypatch):
    called: dict[str, Any] = {}

    def fake_serve_tcp(server, host, port):
        called["host"] = host
        called["port"] = port
        return 7

    monkeypatch.setattr(main_mod, "_serve_tcp", fake_serve_tcp)
    code = main_mod.main(["--host", "127.0.0.1", "--port", "8080"])
    assert code == 7
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8080


def test_main_trace_mode(monkeypatch, tmp_path):
    trace = tmp_path / "t.jsonl"

    class FakeServer:
        def __init__(self, on_log=None):
            self._trace = None

        def run(self, reader, writer):
            self._trace({"method": "x"})
            return 0

    monkeypatch.setattr(main_mod, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    code = main_mod.main(["--trace", str(trace)])
    assert code == 0
    line = trace.read_text().strip()
    assert json.loads(line)["method"] == "x"


def test_serve_stdio_keyboard_interrupt(monkeypatch):
    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            raise KeyboardInterrupt()

    monkeypatch.setattr(main_mod, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main_mod.main([]) == 0


def test_serve_tcp_in_process():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            return 9

    result: dict[str, Any] = {}

    def target():
        result["code"] = main_mod._serve_tcp(FakeServer(), "127.0.0.1", port)

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
    assert result.get("code") == 9


def test_serve_dap_direct():
    reader = MagicMock()
    reader.read_message.return_value = None
    writer = MagicMock()
    fake_conn = MagicMock()
    fake_conn.makefile.side_effect = lambda mode: reader if "r" in mode else writer

    with patch("helixlang_lsp.main.socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.accept.return_value = (fake_conn, ("127.0.0.1", 1))
        mock_sock.getsockname.return_value = ("127.0.0.1", 12345)
        result = main_mod._serve_dap(0, None)
    assert result == 0


def test_serve_dap_with_port_file(tmp_path):
    port_file = str(tmp_path / "port.txt")
    reader = MagicMock()
    reader.read_message.return_value = None
    writer = MagicMock()
    fake_conn = MagicMock()
    fake_conn.makefile.side_effect = lambda mode: reader if "r" in mode else writer

    with patch("helixlang_lsp.main.socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.accept.return_value = (fake_conn, ("127.0.0.1", 1))
        mock_sock.getsockname.return_value = ("127.0.0.1", 12345)
        main_mod._serve_dap(0, port_file)
    content = open(port_file).read()
    assert content.strip() == "12345"


def test_trace_writer_creates_file(tmp_path):
    path = tmp_path / "trace.jsonl"
    rec = main_mod._trace_writer(str(path))
    rec({"seq": 1, "method": "test"})
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["method"] == "test"


def test_build_parser_all_flags():
    p = main_mod._build_parser()
    a = p.parse_args([
        "--stdio", "--host", "0.0.0.0", "--port", "5000",
        "--dap", "--dap-port", "6000", "--dap-port-file", "/tmp/dp",
        "--trace", "/tmp/t.jsonl", "--loglevel", "DEBUG",
    ])
    assert a.stdio is True
    assert a.host == "0.0.0.0"
    assert a.port == 5000
    assert a.dap is True
    assert a.dap_port == 6000
    assert a.dap_port_file == "/tmp/dp"
    assert a.trace == "/tmp/t.jsonl"
    assert a.loglevel == "DEBUG"


def test_main_loglevel_configures_logging(monkeypatch):
    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            return 0

    monkeypatch.setattr(main_mod, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main_mod.main(["--loglevel", "INFO"]) == 0


def test_main_unknown_loglevel():
    with pytest.raises(SystemExit):
        main_mod.main(["--loglevel", "INVALID"])


def test_serve_stdio_direct(monkeypatch):
    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            return 11

    monkeypatch.setattr(main_mod, "HelixLspServer", FakeServer)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main_mod._serve_stdio(FakeServer()) == 11


def test_serve_stdio_keyboard_interrupt_direct(monkeypatch):
    class FakeServer:
        def __init__(self, on_log=None):
            pass

        def run(self, reader, writer):
            raise KeyboardInterrupt()

    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO()))
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=io.BytesIO()))
    assert main_mod._serve_stdio(FakeServer()) == 0

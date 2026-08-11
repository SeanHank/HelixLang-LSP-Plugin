"""Conformance tests: drive the server through its LSP wire protocol.

Uses ``FakeClient`` to speak framed JSON-RPC: initialize, open, type, assert
``publishDiagnostics``, then request each feature and assert result shapes.
"""

from __future__ import annotations


def _open_session(client, server, text, uri="file:///test.helix", version=1):
    """Send initialize + didOpen, return the publishDiagnostics payload."""
    client.request("initialize", {"rootUri": "file:///tmp"})
    client.notify("initialized")
    client.notify("textDocument/didOpen", {
        "textDocument": {"uri": uri, "languageId": "helix", "version": version,
                         "text": text}})
    out = client.responses(server)
    init = next(o for o in out if "result" in o and "capabilities" in o["result"])
    diag = next((o for o in out if o.get("method") == "textDocument/publishDiagnostics"),
                None)
    return init, diag


def test_initialize_capabilities(client, server):
    client.request("initialize", {"rootUri": "file:///tmp"})
    out = client.responses(server)
    result = out[0]["result"]
    caps = result["capabilities"]
    assert result["serverInfo"]["name"] == "helixlang-lsp"
    assert caps["textDocumentSync"]["change"] == 2
    assert caps["textDocumentSync"]["openClose"] is True
    assert caps["hoverProvider"] is True
    assert caps["semanticTokensProvider"]["full"] is True
    assert caps["semanticTokensProvider"]["legend"]["tokenTypes"][0] == "keyword"
    assert caps["completionProvider"]["triggerCharacters"] == ["#", "=", ">"]


def test_didOpen_publishes_zero_diagnostics(client, server, helix_text):
    _init, diag = _open_session(client, server, helix_text)
    assert diag is not None
    assert diag["method"] == "textDocument/publishDiagnostics"
    assert diag["params"]["uri"] == "file:///test.helix"
    assert diag["params"]["diagnostics"] == []


def test_didOpen_publishes_errors(client, server):
    text = "#gene name=g\nATG GGGG TAA\n#end\n"
    _init, diag = _open_session(client, server, text)
    codes = {d["code"] for d in diag["params"]["diagnostics"]}
    assert "lex" in codes
    d = diag["params"]["diagnostics"][0]
    assert d["source"] == "helix"
    assert "className" in d["data"]


def test_didChange_incremental_edit(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    # insert 'GGGG' after 'ATG ' on line 3 -> DNA length error
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": "file:///test.helix", "version": 2},
        "contentChanges": [
            {"range": {"start": {"line": 3, "character": 4},
                       "end": {"line": 3, "character": 4}},
             "text": "GGGG "}]})
    out = client.responses(server)
    diag = next(o for o in out if o.get("method") == "textDocument/publishDiagnostics")
    codes = {d["code"] for d in diag["params"]["diagnostics"]}
    assert "lex" in codes


def test_didChange_full_text_replace(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": "file:///test.helix", "version": 2},
        "contentChanges": [{"text": "#gene name=g\nATG GGGG TAA\n#end\n"}]})
    out = client.responses(server)
    diag = next(o for o in out if o.get("method") == "textDocument/publishDiagnostics")
    assert any(d["code"] == "lex" for d in diag["params"]["diagnostics"])


def test_hover_request(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/hover",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "position": {"line": 3, "character": 4}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert "OP_BUILD_PROTEIN" in result["contents"]["value"]


def test_definition_request(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/definition",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "position": {"line": 2, "character": 30}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert result[0]["range"]["start"]["line"] == 1


def test_completion_request(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/completion",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "position": {"line": 0, "character": 1}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    labels = [i["label"] for i in result["items"]]
    assert "gene" in labels


def test_document_symbol_request(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/documentSymbol",
                   {"textDocument": {"uri": "file:///test.helix"}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    names = [s["name"] for s in result]
    assert "lacZ" in names and "p_lac" in names


def test_semantic_tokens_request(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/semanticTokens/full",
                   {"textDocument": {"uri": "file:///test.helix"}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert len(result["data"]) % 5 == 0


def test_formatting_request(client, server):
    text = "#gene name=g\nATG  GCT\tGGT TAA\n#end\n"
    _init, _diag = _open_session(client, server, text)
    client.request("textDocument/formatting",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "options": {"tabSize": 4, "insertSpaces": True}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert result[0]["newText"] == "#gene name=g\nATG GCT GGT TAA\n#end\n"


def test_unknown_method_returns_error(client, server):
    client.request("bogus/method", {})
    out = client.responses(server)
    resp = next(o for o in out if "error" in o)
    assert resp["error"]["code"] == -32601


def test_shutdown_then_exit(client, server):
    client.request("shutdown")
    client.notify("exit")
    out = client.responses(server)
    resp = next(o for o in out if "result" in o)
    assert resp["result"] is None
    assert server.shutdown_requested


def test_full_message_roundtrip_through_framing(client, server, helix_text):
    """End-to-end: bytes out of the client equal what read_message parses."""
    import io

    from helixlang_lsp.jsonrpc import read_message, write_message

    stream = io.StringIO()
    write_message(stream, {"jsonrpc": "2.0", "method": "x/y", "params": {"a": 1}})
    stream.seek(0)
    assert read_message(stream) == {"jsonrpc": "2.0", "method": "x/y", "params": {"a": 1}}


def test_workspace_symbol_after_scan(client, server):
    server._workspace._index["file:///tmp/other.helix"] = {}
    client.request("workspace/symbol", {"query": "lacZ"})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert result == []


def test_server_run_loop_exit_code(client, server):
    """run() on an empty stream exits 1 (no shutdown)."""
    import io

    code = server.run(io.StringIO(), io.StringIO())
    assert code == 1


def test_server_run_loop_shutdown_returns_zero(client, server):
    import io

    stream = io.StringIO()
    from helixlang_lsp.jsonrpc import write_message

    write_message(stream, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {}})
    write_message(stream, {"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
    stream.seek(0)
    out = io.StringIO()
    code = server.run(stream, out)
    assert code == 0


def test_didSave_publishes_diagnostics(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.notify("textDocument/didSave",
                  {"textDocument": {"uri": "file:///test.helix"}})
    out = client.responses(server)
    assert any(o.get("method") == "textDocument/publishDiagnostics" for o in out)


def test_didClose_removes_document(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.notify("textDocument/didClose",
                  {"textDocument": {"uri": "file:///test.helix"}})
    client.request("textDocument/hover",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "position": {"line": 3, "character": 4}})
    out = client.responses(server)
    assert next(o for o in out if "result" in o)["result"] is None


def test_didChange_unknown_document_is_noop(client, server):
    client.request("initialize", {"rootUri": "file:///tmp"})
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": "file:///unknown.helix", "version": 2},
        "contentChanges": [{"text": "x"}]})
    out = client.responses(server)
    assert not any(o.get("method") == "textDocument/publishDiagnostics" for o in out)


def test_feature_requests_on_unopened_document(client, server):
    client.request("initialize", {"rootUri": "file:///tmp"})
    uri = "file:///never-opened.helix"
    td = {"textDocument": {"uri": uri}}
    pos = {"line": 0, "character": 0}
    client.request("textDocument/hover", {**td, "position": pos})
    client.request("textDocument/completion", {**td, "position": pos})
    client.request("textDocument/definition", {**td, "position": pos})
    client.request("textDocument/references", {**td, "position": pos})
    client.request("textDocument/documentSymbol", td)
    client.request("textDocument/foldingRange", td)
    client.request("textDocument/semanticTokens/full", td)
    client.request("textDocument/codeAction", {
        **td, "range": {"start": pos, "end": {"line": 0, "character": 1}},
        "context": {"diagnostics": []}})
    client.request("textDocument/formatting",
                   {**td, "options": {"tabSize": 4, "insertSpaces": True}})
    client.request("textDocument/inlayHint", {
        **td, "range": {"start": pos, "end": {"line": 0, "character": 1}}})
    out = client.responses(server)
    results = {o["id"]: o["result"] for o in out if "result" in o}
    assert results[2] is None                       # hover
    assert results[3] == {"isIncomplete": False, "items": []}
    assert results[4] is None                       # definition
    assert results[5] == []                         # references
    assert results[6] == []                         # documentSymbol
    assert results[7] == []                         # foldingRange
    assert results[8] == {"data": []}               # semanticTokens
    assert results[9] == []                         # codeAction
    assert results[10] == []                        # formatting
    assert results[11] == []                        # inlayHint


def test_execute_command_disassemble(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("workspace/executeCommand", {
        "command": "helix.disassemble", "arguments": ["file:///test.helix"]})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert isinstance(result, str) and result


def test_execute_command_no_arguments(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("workspace/executeCommand", {
        "command": "helix.disassemble", "arguments": []})
    out = client.responses(server)
    assert next(o for o in out if "result" in o)["result"] == ""


def test_validate_run_vm_runs_runtime_check(client, server, helix_text):
    server._settings["helix.lsp.validate.runVm"] = True
    _init, _diag = _open_session(client, server, helix_text)
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": "file:///test.helix", "version": 2},
        "contentChanges": [{"text": helix_text}]})
    out = client.responses(server)
    assert any(o.get("method") == "textDocument/publishDiagnostics" for o in out)


def test_did_change_configuration_updates_settings(client, server):
    client.request("initialize", {"rootUri": "file:///tmp"})
    client.notify("workspace/didChangeConfiguration", {
        "settings": {"helix.lsp.diagnostics.debounceMs": 5,
                     "not.a.setting": 1}})
    client.responses(server)
    assert server._settings["helix.lsp.diagnostics.debounceMs"] == 5
    assert "not.a.setting" not in server._settings


def test_initialize_root_resolution_variants(server):
    server.handle_initialize({"rootUri": "file:///tmp"})
    assert server._workspace.root == "/tmp"
    server.handle_initialize({"workspaceFolders": [{"uri": "file:///proj"}]})
    assert server._workspace.root == "/proj"
    server.handle_initialize({"rootPath": "/raw"})
    assert server._workspace.root == "/raw"
    server.handle_initialize({})
    assert server._workspace.root is None


def test_did_change_schedules_debounced_analysis(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    server._settings["helix.lsp.diagnostics.debounceMs"] = 60000
    client.notify("textDocument/didChange", {
        "textDocument": {"uri": "file:///test.helix", "version": 2},
        "contentChanges": [{"text": helix_text}]})
    out = client.responses(server, debounce_ms=60000)
    assert out == []  # scheduled, not published synchronously


def test_exit_requested_property(server):
    assert server.exit_requested is False


def test_config_ticks_and_range_edit_helpers():
    from helixlang_lsp.server import _apply_range_edit, _config_ticks

    assert _config_ticks("#config ticks=100") == 100
    assert _config_ticks("#config ticks=abc") == 0
    assert _config_ticks("no ticks here") == 0
    assert _apply_range_edit(
        "abc", {"start": {"line": 99, "character": 0},
                "end": {"line": 99, "character": 0}}, "X") == "abcX"


def test_hover_on_annotation_line(client, server, helix_text):
    _init, _diag = _open_session(client, server, helix_text)
    client.request("textDocument/hover",
                   {"textDocument": {"uri": "file:///test.helix"},
                    "position": {"line": 0, "character": 0}})
    out = client.responses(server)
    result = next(o for o in out if "result" in o)["result"]
    assert "**#config**" in result["contents"]["value"]

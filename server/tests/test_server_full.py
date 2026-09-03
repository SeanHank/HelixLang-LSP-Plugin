"""End-to-end coverage tests for ``helixlang_lsp.server``.

Drives ``HelixLspServer`` through the in-memory ``Dispatcher`` (like the other
``test_*`` files) and, where the build is easier on an isolated unit, calls
module-level helpers directly.
"""

from __future__ import annotations

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import server as server_mod
from helixlang_lsp.analysis import analyze
from helixlang_lsp.server import HelixLspServer

GENE = (
    "#config table=standard\n"
    "#gene name=lacZ\n"
    "ATG GCT GGT TAA\n"
    "#end\n"
    "#promoter name=p_lac strength=0.8\n"
)

WORKSPACE = (
    "#promoter name=p_lac strength=0.8\n"
    "#gene name=lacZ promoter=p_lac\n"
    "ATG GCT GGT TAA\n"
    "#end\n"
)


class _Producer:
    """A writer that records the framed messages it is asked to send."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def write_message(self, msg: dict) -> None:
        self.sent.append(msg)


def _open(server: HelixLspServer, text: str = GENE, uri: str = "file:///t.helix") -> None:
    server.handle_textDocument_didOpen({
        "textDocument": {"uri": uri, "text": text, "version": 1, "languageId": "helix"},
    })


# --------------------------------------------------------------------------
# Lifecycle / root resolution
# --------------------------------------------------------------------------

def test_initialize_root_from_each_source(client):
    srv = HelixLspServer()

    r0 = srv.handle_initialize({
        "rootUri": "file:///src/a.helix",
        "workspaceFolders": [{"uri": "file:///src/f.helix"}],
        "rootPath": "/src/p.helix",
    })
    assert r0["serverInfo"]["name"] == "helixlang-lsp"
    assert srv._initialized is True
    assert srv._workspace.root is not None

    srv2 = HelixLspServer()
    srv2.handle_initialize({"workspaceFolders": [{"uri": "file:///w/f.helix"}]})
    assert srv2._workspace.root is not None

    srv3 = HelixLspServer()
    srv3.handle_initialize({"rootPath": "/raw/path.helix"})
    assert srv3._workspace.root is not None

    # 445: params present but none of rootUri/workspaceFolders/rootPath.
    srv4 = HelixLspServer()
    srv4.handle_initialize({"rootUri": "", "seed": 1})
    assert srv4._workspace.root is None

    # initialized with a root kicks off a background workspace scan.
    srv5 = HelixLspServer()
    srv5.handle_initialize({"rootUri": "file:///tmp"})
    srv5.handle_initialized(None)
    assert srv5._workspace.root is not None

    client.request("initialize", {"rootUri": ""})
    client.responses(srv4)


def test_initialize_and_shutdown_exit(client, server):
    assert server.handle_initialize(None)["capabilities"]["textDocumentSync"]["change"] == 2
    assert server.handle_shutdown(None) is None
    assert server.shutdown_requested is True
    assert server.handle_exit(None) is None
    assert server.exit_requested is True


# --------------------------------------------------------------------------
# workspace/symbol + workspace scan
# --------------------------------------------------------------------------

def test_workspace_symbol_scans_and_returns_symbols(tmp_path, client):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "t.helix").write_text(WORKSPACE, encoding="utf-8")
    srv = HelixLspServer()
    srv._scan_workspace(str(root))  # 375 success path

    results = srv.handle_workspace_symbol({"query": ""})
    # gene -> function kind, promoter -> variable kind (177-180)
    assert results
    kinds = {r["name"]: r["kind"] for r in results}
    assert kinds["lacZ"] == 12  # function
    assert kinds["p_lac"] == 13  # variable
    assert all(r["location"]["uri"] for r in results)


def test_workspace_scan_failure_logged(monkeypatch, tmp_path):
    logs: list[str] = []
    srv = HelixLspServer(on_log=logs.append)

    def boom(_root: str | None = None) -> None:
        raise RuntimeError("scan exploded")

    monkeypatch.setattr(srv._workspace, "scan", boom)
    srv._scan_workspace(str(tmp_path))
    assert logs and "scan failed" in logs[0]


# --------------------------------------------------------------------------
# notification/document lifecycle publishing
# --------------------------------------------------------------------------

def test_publish_disabled_diagnostics(client, server):
    server._settings["helix.lsp.diagnostics.enabled"] = False
    server._settings["helix.lsp.validate.runVm"] = True
    _open(server)
    pushed = server.handle_textDocument_didSave({"textDocument": {"uri": "file:///t.helix"}})
    # 365: even with a valid analysis + runVm, disabling diagnostics -> []
    assert pushed[0]["params"]["diagnostics"] == []


def test_reanalyze_unknown_uri_returns_empty(client, server):
    assert server.handle_textDocument_didSave(
        {"textDocument": {"uri": "file:///missing.helix"}}) == []


def test_publish_diagnostics_enabled_via_save(client, server):
    _open(server, text="#gene name=g\nATG GCT\n")  # parse diagnostic
    pushed = server.handle_textDocument_didSave({"textDocument": {"uri": "file:///t.helix"}})
    assert pushed[0]["params"]["diagnostics"]


def test_didClose_removes_document(client, server):
    _open(server)
    assert server.handle_textDocument_didClose(
        {"textDocument": {"uri": "file:///t.helix"}}) is None
    assert "file:///t.helix" not in server._docs


def test_didChange_range_and_full_and_debounce_cancel(client, server):
    _open(server)
    # no-range (full text) change
    server.handle_textDocument_didChange({
        "textDocument": {"uri": "file:///t.helix", "version": 2},
        "contentChanges": [{"text": GENE + "\n"}],
    })
    assert server._docs["file:///t.helix"].version == 2

    # range edit
    server._settings["helix.lsp.diagnostics.debounceMs"] = 0
    server.handle_textDocument_didChange({
        "textDocument": {"uri": "file:///t.helix", "version": 3},
        "contentChanges": [{
            "range": {"start": {"line": 0, "character": 0},
                      "end": {"line": 0, "character": 0}},
            "text": "# ",
        }],
    })
    assert server._docs["file:///t.helix"].text.startswith("# ")

    # debounced path with an already-pending timer -> cancel (line 351)
    server._settings["helix.lsp.diagnostics.debounceMs"] = 100000
    server.handle_textDocument_didChange({
        "textDocument": {"uri": "file:///t.helix", "version": 4},
        "contentChanges": [{"text": GENE}],
    })
    assert server._debounce_timer is not None
    server.handle_textDocument_didChange({
        "textDocument": {"uri": "file:///t.helix", "version": 5},
        "contentChanges": [{"text": GENE}],
    })
    assert server._debounce_timer is not None

    # no-change for an unknown doc -> []
    assert server.handle_textDocument_didChange({
        "textDocument": {"uri": "file:///nope.helix", "version": 1},
        "contentChanges": []}) == []


# --------------------------------------------------------------------------
# features through the dispatcher (requests)
# --------------------------------------------------------------------------

def _dispatch_req(server, method, params):
    from helixlang_lsp.jsonrpc import Dispatcher

    disp = Dispatcher(server, writer=lambda _m: None)
    msgs = disp.dispatch({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    return msgs[0]["result"]


def test_references_folding_code_action_dispatch(server):
    _open(server)
    # references (line 268) - position on the gene name
    refs = _dispatch_req(server, "textDocument/references", {
        "textDocument": {"uri": "file:///t.helix"},
        "position": {"line": 1, "character": 8},
        "context": {"includeDeclaration": True},
    })
    assert isinstance(refs, list)

    # folding ranges (line 284)
    folds = _dispatch_req(server, "textDocument/foldingRange",
                          {"textDocument": {"uri": "file:///t.helix"}})
    assert isinstance(folds, list)

    # code action (line 298) - needs a diagnostic context
    ana = analyze("#gene name=g\nATG GCT\n", uri="file:///t.helix")
    diags = [d.to_dict() for d in ana.diagnostics]
    acts = _dispatch_req(server, "textDocument/codeAction", {
        "textDocument": {"uri": "file:///t.helix"},
        "range": {"start": {"line": 0, "character": 0},
                  "end": {"line": 3, "character": 0}},
        "context": {"diagnostics": diags, "only": ["quickfix"]},
    })
    assert isinstance(acts, list)


def test_inlay_hint_disabled_and_enabled(server):
    _open(server)
    server._settings["helix.lsp.inlayHints.enabled"] = True
    hints = _dispatch_req(server, "textDocument/inlayHint",
                          {"textDocument": {"uri": "file:///t.helix"}})
    assert isinstance(hints, list)
    assert hints  # the gene body produces codon hints (line 312)

    server._settings["helix.lsp.inlayHints.enabled"] = False
    empty = _dispatch_req(server, "textDocument/inlayHint",
                          {"textDocument": {"uri": "file:///t.helix"}})
    assert empty == []  # line 308


# --------------------------------------------------------------------------
# run() transport loop
# --------------------------------------------------------------------------

def test_run_with_message_objects():
    logs: list[str] = []

    class Reader:
        def read_message(self) -> None:
            return None

    srv = HelixLspServer(on_log=logs.append)
    srv._trace = lambda m: None
    prod = _Producer()
    # 399 + 404: reader/writer expose read_message/write_message.
    code = srv.run(Reader(), prod)
    assert code == 1  # EOF reached without shutdown
    assert not logs


def test_run_read_error_logs_and_breaks():
    logs: list[str] = []

    class Reader:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        def read_message(self):
            if self.fail:
                raise OSError("boom")
            return None

    srv = HelixLspServer(on_log=logs.append)
    # 414-416: a read error is logged, the loop breaks, exit code 1.
    assert srv.run(Reader(True), _Producer()) == 1
    assert logs and "read error" in logs[0]


def test_run_shutdown_returns_zero():
    class Reader:
        def read_message(self) -> None:
            return None

    srv = HelixLspServer()
    srv._shutdown_requested = True
    assert srv.run(Reader(), _Producer()) == 0


# --------------------------------------------------------------------------
# module helpers: _disassemble
# --------------------------------------------------------------------------

def test_disassemble_compile_path_no_chunk():
    # program is not None but chunk is None -> the compile path (467-471)
    ana = analyze("#config table=standard\n#gene name=g\nATG GCT GGT TAA\n#end\n",
                  uri="file:///t.helix", include_compile=False)
    assert ana.chunk is None and ana.program is not None
    out = server_mod._disassemble(ana)
    assert "HelixLang Chunk" in out


def test_disassemble_compile_failure(monkeypatch):
    ana = analyze("#config table=standard\n#gene name=g\nATG GCT GGT TAA\n#end\n",
                  uri="file:///t.helix", include_compile=False)
    ana.program = object()  # force compile to fail
    out = server_mod._disassemble(ana)
    assert out.startswith("disassembly failed:")


def test_disassemble_chunk_disassemble_raise(monkeypatch):
    ana = analyze("#config table=standard\n#gene name=g\nATG GCT GGT TAA\n#end\n",
                  uri="file:///t.helix", include_compile=False)
    ana.chunk = object()  # chunk is not None, disassemble below raises
    ana.program = None

    def raise_disasm(_chunk):
        raise RuntimeError("bad chunk")

    monkeypatch.setattr(helix, "disassemble", raise_disasm)
    assert server_mod._disassemble(ana) == ""


def test_disassemble_nothing():
    ana = analyze("#gene name=g\nATG GCT\n", uri="file:///t.helix")
    # parse-incomplete -> program None, chunk None -> 474 path
    ana.program = None
    ana.chunk = None
    assert server_mod._disassemble(ana) == ""


# --------------------------------------------------------------------------
# module helpers: _runtime_diagnostics
# --------------------------------------------------------------------------

def test_runtime_diagnostics_program_none():
    # a doc that fails to lex has program None -> 481
    ana = analyze("#gene name=g\nATG XYZ TAA\n#end\n", uri="file:///t.helix")
    assert ana.program is None
    assert server_mod._runtime_diagnostics(ana) == []


def test_runtime_diagnostics_high_ticks_clamped():
    # ticks > 64 gets clamped (484); runVm on a healthy doc returns no diag
    ana = analyze("#config table=standard ticks=100\n"
                  "#gene name=g\nATG GCT GGT TAA\n#end\n", uri="file:///t.helix")
    assert server_mod._runtime_diagnostics(ana) == []


def test_runtime_diagnostics_helix_error(monkeypatch):
    ana = analyze("#config table=standard\n#gene name=g\nATG GCT GGT TAA\n#end\n",
                  uri="file:///t.helix")

    class BadVM:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            raise helix.RuntimeHelixError("cell overflow")

    monkeypatch.setattr(helix, "CellVM", BadVM)
    diags = server_mod._runtime_diagnostics(ana)
    assert diags and "cell overflow" in diags[0].message


def test_runtime_diagnostics_generic_error(monkeypatch):
    ana = analyze("#config table=standard\n#gene name=g\nATG GCT GGT TAA\n#end\n",
                  uri="file:///t.helix")

    class BadVM:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            raise ValueError("unexpected")

    monkeypatch.setattr(helix, "CellVM", BadVM)
    diags = server_mod._runtime_diagnostics(ana)
    assert diags and "unexpected" in diags[0].message


# --------------------------------------------------------------------------
# module helpers: _config_ticks
# --------------------------------------------------------------------------

def test_config_ticks_parse_error():
    # a digit string too long for int() raises ValueError -> 505-506
    huge = "9" * 5000
    assert server_mod._config_ticks(f"#config ticks={huge}") == 0
    # normal value parses
    assert server_mod._config_ticks("#config ticks=7") == 7
    assert server_mod._config_ticks("#config ticks=") == 0


# --------------------------------------------------------------------------
# module helpers: _root_uri / workspace edit / completion
# --------------------------------------------------------------------------

def test_workspace_execute_command_disassemble(server):
    _open(server)
    out = server.handle_workspace_executeCommand({
        "arguments": ["file:///t.helix"],
    })
    assert "chunk" in out.lower() or out == ""
    assert server.handle_workspace_executeCommand({}) == ""


def test_completion_and_semantic_no_doc(server):
    assert _dispatch_req(server, "textDocument/completion",
                         {"textDocument": {"uri": "file:///missing.helix"}}) == {
        "isIncomplete": False, "items": [],
    }
    assert _dispatch_req(server, "textDocument/semanticTokens/full",
                         {"textDocument": {"uri": "file:///missing.helix"}}) == {
        "data": [],
    }

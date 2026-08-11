"""The Helix LSP server: lifecycle, document cache, analysis orchestration.

Owns the LSP handshake (doc/03 §4), the per-document cache keyed by
``(uri, version)`` (§7.2), settings (§11), debounced re-analysis, and every
feature handler. ``run()`` drives a reader thread + worker loop (§3.2).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import uri as uri_mod
from helixlang_lsp.analysis import Analysis, Workspace, analyze
from helixlang_lsp.features import (
    code_actions as ca_mod,
)
from helixlang_lsp.features import (
    completion as completion_mod,
)
from helixlang_lsp.features import (
    definitions as definitions_mod,
)
from helixlang_lsp.features import (
    document_symbols as document_symbols_mod,
)
from helixlang_lsp.features import (
    folding as folding_mod,
)
from helixlang_lsp.features import (
    formatting as formatting_mod,
)
from helixlang_lsp.features import (
    hover as hover_mod,
)
from helixlang_lsp.features import (
    inlay_hints as inlay_hints_mod,
)
from helixlang_lsp.features import (
    references as references_mod,
)
from helixlang_lsp.features import (
    semantic_tokens as semantic_tokens_mod,
)
from helixlang_lsp.protocol import (
    CompletionList,
    Diagnostic,
    Location,
    Position,
    Range,
    SemanticTokens,
    SymbolInformation,
    SymbolKind,
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "helix.lsp.diagnostics.enabled": True,
    "helix.lsp.diagnostics.debounceMs": 200,
    "helix.lsp.validate.runVm": False,
    "helix.lsp.completion.triggerOnCodons": True,
    "helix.lsp.semanticTokens.enabled": True,
    "helix.lsp.inlayHints.enabled": True,
    "helix.lsp.formatting.alignEquals": False,
}

_CAPABILITIES = {
    "textDocumentSync": {
        "openClose": True,
        "change": 2,
        "save": {"includeText": False},
    },
    "hoverProvider": True,
    "completionProvider": {"triggerCharacters": ["#", "=", ">"]},
    "definitionProvider": True,
    "referencesProvider": True,
    "documentSymbolProvider": True,
    "foldingRangeProvider": True,
    "diagnosticProvider": {
        "interFileDependencies": False,
        "workspaceDiagnostics": False,
    },
    "semanticTokensProvider": {
        "legend": {
            "tokenTypes": ["keyword", "type", "function", "variable", "number",
                           "string", "comment", "operator"],
            "tokenModifiers": ["declaration", "defaultLibrary"],
        },
        "range": False,
        "full": True,
    },
    "codeActionProvider": {"codeActionKinds": ["quickfix"]},
    "documentFormattingProvider": True,
    "inlayHintProvider": True,
    "workspaceSymbolProvider": True,
}


@dataclass(slots=True)
class _Document:
    uri: str
    text: str
    version: int
    language_id: str = "helix"


class HelixLspServer:
    """LSP server exposing ``handle_*`` methods for the JSON-RPC dispatcher."""

    def __init__(self, *, on_log: Callable[[str], None] | None = None):
        self._settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._docs: dict[str, _Document] = {}
        self._analyses: dict[str, tuple[int, Analysis]] = {}
        self._workspace = Workspace()
        self._lock = threading.Lock()
        self._initialized = False
        self._shutdown_requested = False
        self._exit_requested = False
        self._debounce_timer: threading.Timer | None = None
        self._on_log = on_log or (lambda _m: None)
        self._trace: Callable[[dict[str, Any]], None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def handle_initialize(self, params: dict[str, Any] | None) -> dict[str, Any]:
        self._initialized = True
        root = _root_uri(params)
        self._workspace.root = uri_mod.uri_to_path(root) if root else None
        return {
            "capabilities": _CAPABILITIES,
            "serverInfo": {"name": "helixlang-lsp", "version": _version()},
        }

    def handle_initialized(self, _params: dict[str, Any] | None) -> None:
        # notification: kick off the workspace scan on a background thread
        root = self._workspace.root
        if root:
            threading.Thread(target=self._scan_workspace, args=(root,),
                             daemon=True).start()

    def handle_shutdown(self, _params: dict[str, Any] | None) -> None:
        self._shutdown_requested = True
        return None

    def handle_exit(self, _params: dict[str, Any] | None) -> None:
        self._exit_requested = True
        return None

    @property
    def exit_requested(self) -> bool:
        return self._exit_requested

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    # ------------------------------------------------------------------
    # Settings / workspace
    # ------------------------------------------------------------------

    def handle_workspace_didChangeConfiguration(self, params: dict[str, Any] | None) -> None:
        settings = (params or {}).get("settings", {}) or {}
        for key, value in settings.items():
            if key in DEFAULT_SETTINGS:
                self._settings[key] = value
        return None

    def handle_workspace_symbol(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        query = (params or {}).get("query", "")
        results = self._workspace.query(str(query))
        out: list[dict[str, Any]] = []
        for uri, name, sym in results:
            loc_rng = Range(start=Position(line=sym.def_line0, character=0),
                            end=Position(line=sym.def_line0, character=0))
            kind = SymbolKind["function"] if sym.kind == "gene" else SymbolKind["variable"]
            out.append(SymbolInformation(
                name=name, kind=kind, location=Location(uri=uri, range=loc_rng),
            ).to_dict())
        return out

    def handle_workspace_executeCommand(self, params: dict[str, Any] | None) -> str:
        args = (params or {}).get("arguments", []) or []
        uri = str(args[0]) if args else ""
        if uri:
            doc = self._docs.get(uri_mod.normalize_uri(uri))
            if doc is not None:
                ana = self._analysis(doc)
                if ana and ana.program is not None:
                    return _disassemble(ana)
        return ""

    # ------------------------------------------------------------------
    # Text document synchronization
    # ------------------------------------------------------------------

    def handle_textDocument_didOpen(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        td = (params or {}).get("textDocument", {})
        uri = str(td.get("uri", ""))
        text = str(td.get("text", ""))
        version = int(td.get("version", 0))
        self._docs[uri_mod.normalize_uri(uri)] = _Document(
            uri=uri, text=text, version=version,
            language_id=str(td.get("languageId", "helix")))
        return self._reanalyze(uri)

    def handle_textDocument_didChange(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        td = (params or {}).get("textDocument", {})
        uri = str(td.get("uri", ""))
        version = int(td.get("version", 0))
        changes = (params or {}).get("contentChanges", []) or []
        doc = self._docs.get(uri_mod.normalize_uri(uri))
        if doc is None:
            return []
        for change in changes:
            rng = change.get("range")
            new_text = change.get("text", "")
            if rng is not None:
                doc.text = _apply_range_edit(doc.text, rng, new_text)
            else:
                doc.text = new_text
        doc.version = version
        return self._schedule_analysis(uri)

    def handle_textDocument_didSave(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        uri = str((params or {}).get("textDocument", {}).get("uri", ""))
        return self._reanalyze(uri)

    def handle_textDocument_didClose(self, params: dict[str, Any] | None) -> None:
        uri = str((params or {}).get("textDocument", {}).get("uri", ""))
        self._docs.pop(uri_mod.normalize_uri(uri), None)
        self._analyses.pop(uri_mod.normalize_uri(uri), None)
        return None

    # ------------------------------------------------------------------
    # Features
    # ------------------------------------------------------------------

    def handle_textDocument_hover(self, params: dict[str, Any] | None) -> dict[str, Any] | None:
        ana = self._feature_analysis(params)
        if ana is None:
            return None
        return hover_mod.hover(ana.text, ana, params or {})

    def handle_textDocument_completion(self, params: dict[str, Any] | None) -> dict[str, Any]:
        ana = self._feature_analysis(params)
        if ana is None:
            return CompletionList(is_incomplete=False, items=[]).to_dict()
        return completion_mod.completions(ana.text, ana, params or {})

    def handle_textDocument_definition(
        self, params: dict[str, Any] | None
    ) -> list[dict[str, Any]] | None:
        ana = self._feature_analysis(params)
        if ana is None:
            return None
        return definitions_mod.definitions(ana.text, ana, params or {})

    def handle_textDocument_references(
        self, params: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return references_mod.references(ana.text, ana, params or {})

    def handle_textDocument_documentSymbol(
        self, params: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return document_symbols_mod.document_symbols(ana.text, ana, params or {})

    def handle_textDocument_foldingRange(
        self, params: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return folding_mod.folding_ranges(ana.text, ana, params or {})

    def handle_textDocument_semanticTokens_full(
        self, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        ana = self._feature_analysis(params)
        if ana is None:
            return SemanticTokens(data=[]).to_dict()
        return semantic_tokens_mod.semantic_tokens(ana.text, ana, params or {})

    def handle_textDocument_codeAction(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return ca_mod.code_actions(ana.text, ana, params or {})

    def handle_textDocument_formatting(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return formatting_mod.formatting(ana.text, ana, params or {})

    def handle_textDocument_inlayHint(self, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not self._settings.get("helix.lsp.inlayHints.enabled", True):
            return []
        ana = self._feature_analysis(params)
        if ana is None:
            return []
        return inlay_hints_mod.inlay_hints(ana.text, ana, params or {})

    # ------------------------------------------------------------------
    # Analysis plumbing
    # ------------------------------------------------------------------

    def _analysis(self, doc: _Document) -> Analysis | None:
        key = doc.uri
        cached = self._analyses.get(key)
        if cached is not None and cached[0] == doc.version:
            return cached[1]
        ana = analyze(doc.text, uri=doc.uri,
                      include_compile=True,
                      table_hint=_table_hint(doc.text))
        with self._lock:
            self._analyses[key] = (doc.version, ana)
        return ana

    def _feature_analysis(self, params: dict[str, Any] | None) -> Analysis | None:
        uri = str(((params or {}).get("textDocument", {}) or {}).get("uri", ""))
        doc = self._docs.get(uri_mod.normalize_uri(uri))
        if doc is None:
            return None
        return self._analysis(doc)

    def _reanalyze(self, uri: str) -> list[dict[str, Any]]:
        key = uri_mod.normalize_uri(uri)
        doc = self._docs.get(key)
        if doc is None:
            return []
        ana = self._analysis(doc)
        return self._publish(key, ana)

    def _schedule_analysis(self, uri: str) -> list[dict[str, Any]]:
        debounce = int(self._settings.get("helix.lsp.diagnostics.debounceMs", 200))
        if debounce <= 0:
            return self._reanalyze(uri)
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                debounce / 1000.0, self._reanalyze, args=[uri])
            self._debounce_timer.daemon = True
            self._debounce_timer.start()
        return []

    def _publish(self, uri: str, ana: Analysis | None) -> list[dict[str, Any]]:
        diagnostics: list[Diagnostic] = []
        if ana is not None and self._settings.get("helix.lsp.diagnostics.enabled", True):
            diagnostics = ana.diagnostics
            if self._settings.get("helix.lsp.validate.runVm", False):
                diagnostics = diagnostics + _runtime_diagnostics(ana)
        if not self._settings.get("helix.lsp.diagnostics.enabled", True):
            diagnostics = []
        return [{
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": [d.to_dict() for d in diagnostics]},
        }]

    def _scan_workspace(self, root: str) -> None:
        try:
            self._workspace.scan(root)
        except Exception as exc:  # noqa: BLE001
            self._on_log(f"workspace scan failed: {exc}")

    # ------------------------------------------------------------------
    # Transport loop
    # ------------------------------------------------------------------

    def run(self, reader: Any, writer: Any) -> int:
        """Serve messages from ``reader`` until EOF; return the exit code.

        ``reader``/``writer`` are text streams, binary streams, or objects with
        ``read_message``/``write_message`` (e.g. DAP sessions).
        """
        from helixlang_lsp.jsonrpc import (
            Dispatcher,
            read_message,
            read_message_binary,
            write_message,
            write_message_binary,
        )

        binary = hasattr(reader, "readinto")

        if hasattr(reader, "read_message"):
            read = reader.read_message
        else:
            read = lambda: (read_message_binary(reader) if binary  # noqa: E731
                            else read_message(reader))
        if hasattr(writer, "write_message"):
            write = writer.write_message
        else:
            write = lambda m: (write_message_binary(writer, m) if binary  # noqa: E731
                               else write_message(writer, m))

        dispatcher = Dispatcher(self, writer=write)

        while not self._exit_requested:
            try:
                msg = read()
            except Exception as exc:  # noqa: BLE001
                self._on_log(f"read error: {exc}")
                break
            if msg is None:
                break
            if self._trace is not None:
                self._trace(msg)
            for outbound in dispatcher.dispatch(msg):
                write(outbound)

        if self._shutdown_requested:
            return 0
        return 1


# --------------------------------------------------------------------------
# module helpers
# --------------------------------------------------------------------------

def _root_uri(params: dict[str, Any] | None) -> str | None:
    if not params:
        return None
    root = params.get("rootUri")
    if root:
        return str(root)
    folders = params.get("workspaceFolders") or []
    if folders:
        return str(folders[0].get("uri", ""))
    root_path = params.get("rootPath")
    if root_path:
        return uri_mod.path_to_uri(str(root_path))
    return None


def _table_hint(text: str) -> str | None:
    import re

    m = re.search(r"#config[^\n]*\btable=([A-Za-z0-9_]+)", text)
    return m.group(1) if m else None


def _version() -> str:
    from helixlang_lsp import __version__

    return __version__


def _disassemble(ana: Analysis) -> str:
    if ana.chunk is not None:
        try:
            return helix.disassemble(ana.chunk)
        except Exception:  # noqa: BLE001
            pass
    if ana.program is not None:
        try:
            table = helix.get_table(ana.table_name)
            chunk = helix.Compiler(table).compile(ana.program)
            return helix.disassemble(chunk)
        except Exception as exc:  # noqa: BLE001
            return f"disassembly failed: {exc}"
    return ""


def _runtime_diagnostics(ana: Analysis) -> list[Diagnostic]:
    from helixlang_lsp.diagnostics import error_to_diagnostic

    if ana.program is None:
        return []
    ticks = _config_ticks(ana.text)
    if ticks > 64:
        ticks = 64
    try:
        table = helix.get_table(ana.table_name)
        chunk = ana.chunk if ana.chunk is not None else helix.Compiler(table).compile(ana.program)
        vm = helix.CellVM(chunk, ana.program)
        vm.run(max_ticks=ticks)
    except helix.HelixError as exc:
        return [error_to_diagnostic(exc, ana.text, ana.tokens)]
    except Exception as exc:  # noqa: BLE001
        return [error_to_diagnostic(
            helix.RuntimeHelixError(str(exc)), ana.text, ana.tokens)]
    return []


def _config_ticks(text: str) -> int:
    import re

    m = re.search(r"#config[^\n]*\bticks=(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    return 0


def _apply_range_edit(text: str, rng: dict[str, Any], new_text: str) -> str:
    """Apply an incremental LSP edit (UTF-16 range) to ``text``."""
    from helixlang_lsp import positions as p

    start = rng.get("start", {})
    end = rng.get("end", {})
    start_line = int(start.get("line", 0))
    start_char = int(start.get("character", 0))
    end_line = int(end.get("line", 0))
    end_char = int(end.get("character", 0))

    lines = text.split("\n")
    if start_line >= len(lines):
        return text + new_text

    # convert UTF-16 columns to code-point offsets
    s_off = p.utf16_offset_of_line(lines[start_line], start_char) \
        if start_line < len(lines) else 0
    e_off = p.utf16_offset_of_line(lines[end_line], end_char) \
        if end_line < len(lines) else 0

    # compute global char offsets
    start_global = sum(len(line) + 1 for line in lines[:start_line]) + s_off
    end_global = sum(len(line) + 1 for line in lines[:end_line]) + e_off

    return text[:start_global] + new_text + text[end_global:]


__all__ = [
    "DEFAULT_SETTINGS",
    "HelixLspServer",
    "_apply_range_edit",
]

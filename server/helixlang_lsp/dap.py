"""Debug Adapter Protocol adapter wrapping ``helixlang.debugger.HelixDebugger``.

P1 scope (doc/04 §8): breakpoints by source line, step/step-over/step-out,
continue, stack trace, scopes/variables, evaluate. Frames/state are derived
from ``DebugState`` and the call stack.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp.analysis import analyze

SUPPORTED_DEBUGGER_METHODS = [
    "supportsConfigurationDoneRequest",
    "supportsConditionalBreakpoints",
    "supportsSetVariable",
]


@dataclass(slots=True)
class DapBreakpoint:
    line: int
    verified: bool = False
    id: int = 0


class HelixDebugAdapter:
    """A single debug session for one compiled program."""

    def __init__(self) -> None:
        self._program: helix.Program | None = None
        self._chunk: helix.Chunk | None = None
        self._table_name = "standard"
        self._source_text = ""
        self._debugger: Any = None
        self._breakpoints: list[DapBreakpoint] = []
        self._next_id = 1
        self._running = False
        self._writer: Any = None

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------

    def emit_event(self, event: str, body: dict[str, Any] | None = None) -> None:
        """Send a DAP event to the client (no-op when the adapter is used directly)."""
        writer = self._writer
        if writer is None:
            return
        writer({"seq": _next_seq(), "type": "event", "event": event,
                "body": body or {}})

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def handle_initialize(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        return {"capabilities": {
            m: True for m in SUPPORTED_DEBUGGER_METHODS
        }}

    def handle_launch(self, params: dict[str, Any] | None) -> None:
        args = params or {}
        source = args.get("program") or args.get("target") or ""
        text = _read_source(source)
        ana = analyze(text, uri=_uri_of(source), include_compile=True)
        if ana.program is None or ana.chunk is None:
            raise RuntimeError("launch failed: program did not compile")
        self._program = ana.program
        self._chunk = ana.chunk
        self._table_name = ana.table_name
        self._source_text = text
        vm = helix.CellVM(self._chunk, self._program)
        from helixlang.debugger import HelixDebugger

        self._debugger = HelixDebugger(vm, self._program)
        self._debugger.start()

    def handle_configurationDone(self, _params: dict[str, Any] | None) -> None:
        self._emit_outcome(self._continue_loop())

    def handle_disconnect(self, _params: dict[str, Any] | None) -> None:
        self._debugger = None

    # ------------------------------------------------------------------
    # breakpoints
    # ------------------------------------------------------------------

    def handle_setBreakpoints(self, params: dict[str, Any] | None) -> dict[str, Any]:
        dap_breakpoints: list[dict[str, Any]] = []
        source_bps = (params or {}).get("breakpoints", []) or []
        # setBreakpoints replaces the full set for the (single) source.
        self._breakpoints = []
        if self._debugger is not None:
            for bp in list(self._debugger.list_breakpoints()):
                self._debugger.remove_breakpoint(bp)
        for bp in source_bps:
            line = int(bp.get("line", 1))
            db = DapBreakpoint(line=line, verified=True, id=self._next_id)
            self._next_id += 1
            self._breakpoints.append(db)
            if self._debugger is not None:
                self._debugger.set_breakpoint(line=line)
            dap_breakpoints.append(
                {"id": db.id, "line": line, "verified": db.verified})
        return {"breakpoints": dap_breakpoints}

    # ------------------------------------------------------------------
    # execution control
    # ------------------------------------------------------------------

    def handle_continue(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        self._emit_outcome(self._continue_loop())
        return {"allThreadsContinued": True}

    def handle_next(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        if self._debugger is not None:
            self._debugger.step_over()
        self._emit_step("step")
        return {"allThreadsContinued": True}

    def handle_stepIn(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        if self._debugger is not None:
            self._debugger.step()
        self._emit_step("step")
        return {"allThreadsContinued": True}

    def handle_stepOut(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        if self._debugger is not None:
            self._debugger.step_out()
        self._emit_step("step")
        return {"allThreadsContinued": True}

    # ------------------------------------------------------------------
    # inspection
    # ------------------------------------------------------------------

    def handle_stackTrace(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        frames: list[dict[str, Any]] = []
        if self._debugger is not None:
            for entry in self._debugger.get_call_stack():
                frames.append({
                    "id": len(frames) + 1,
                    "name": str(entry.get("gene") or "<main>"),
                    "line": max(self._debugger.get_state().line, 1),
                    "column": 1,
                    "source": {"name": self._source_name(), "path": self._source_path()},
                })
        if not frames:
            frames.append({
                "id": 1, "name": "<main>",
                "line": max(self._line_of_state(), 1), "column": 1,
                "source": {"name": self._source_name(), "path": self._source_path()},
            })
        return {"stackFrames": frames, "totalFrames": len(frames)}

    def handle_scopes(self, params: dict[str, Any] | None) -> dict[str, Any]:
        _frame_id = (params or {}).get("frameId", 1)
        return {"scopes": [
            {"name": "Cell", "variablesReference": 1, "expensive": False},
            {"name": "GRN", "variablesReference": 2, "expensive": False},
            {"name": "Stack", "variablesReference": 3, "expensive": False},
        ]}

    def handle_variables(self, params: dict[str, Any] | None) -> dict[str, Any]:
        ref = int((params or {}).get("variablesReference", 1))
        state = self._debugger.get_state() if self._debugger is not None else None
        if state is None:
            return {"variables": []}
        if ref == 1:
            variables = [_var(k, v) for k, v in sorted(state.cell_state.items())]
        elif ref == 2:
            variables = [_var(k, v) for k, v in sorted(state.grn_state.items())]
        elif ref == 3:
            variables = [_var(f"stack[{i}]", v) for i, v in enumerate(state.stack)]
        else:
            variables = []
        return {"variables": variables}

    def handle_evaluate(self, params: dict[str, Any] | None) -> dict[str, Any]:
        expr = str((params or {}).get("expression", ""))
        if self._debugger is None:
            raise RuntimeError("no active session")
        try:
            value = self._debugger.inspect(expr)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"cannot evaluate {expr!r}: {exc}") from exc
        return {"result": _fmt(value), "variablesReference": 0}

    def handle_threads(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        return {"threads": [{"id": 1, "name": "main"}]}

    def handle_pause(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        self.emit_event("stopped", {"reason": "pause", "threadId": 1,
                                    "allThreadsStopped": True})
        return {}

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _continue_loop(self) -> DapBreakpoint | None:
        """Run until a breakpoint hit (→ matched bp) or HALT (→ ``None``)."""
        if self._debugger is None:
            return None
        while True:
            state = self._debugger.continue_run()
            if state is None:
                return None
            self._current_state = state
            for bp in self._breakpoints:
                if bp.line == state.line:
                    return bp

    def _emit_outcome(self, bp: DapBreakpoint | None) -> None:
        if bp is None:
            self.emit_event("terminated", {})
        else:
            self.emit_event("stopped", {"reason": "breakpoint", "threadId": 1,
                                        "hitBreakpointIds": [bp.id],
                                        "allThreadsStopped": True})

    def _emit_step(self, reason: str) -> None:
        debugger = self._debugger
        if debugger is None or not getattr(debugger.vm, "frames", None):
            self.emit_event("terminated", {})
            return
        self.emit_event("stopped", {"reason": reason, "threadId": 1,
                                    "allThreadsStopped": True})

    def _line_of_state(self) -> int:
        if self._debugger is not None:
            return self._debugger.get_state().line
        return 1

    def _source_name(self) -> str:
        return "program.helix"

    def _source_path(self) -> str:
        return "program.helix"

    _current_state: Any = None


def _var(name: str, value: Any) -> dict[str, Any]:
    return {"name": str(name), "value": _fmt(value), "type": type(value).__name__,
            "variablesReference": 0}


def _fmt(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps({k: _fmt(v) for k, v in value.items()}, sort_keys=True)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    return str(value)


def _read_source(path: str) -> str:
    if not path:
        return ""
    import os

    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return path  # treat as inline source


def _uri_of(path: str) -> str:
    from helixlang_lsp import uri as uri_mod

    return uri_mod.path_to_uri(path)


# --------------------------------------------------------------------------
# DAP transport loop (same framing as LSP)
# --------------------------------------------------------------------------

class DapSession:
    """Frames DAP messages (Content-Length header, JSON body) and dispatches."""

    def __init__(self, adapter: HelixDebugAdapter):
        self.adapter = adapter

    def run(self, reader: Any, writer: Any) -> int:
        from helixlang_lsp.jsonrpc import read_message_binary, write_message_binary

        if hasattr(reader, "read_message"):
            read = reader.read_message
        else:
            read = lambda: read_message_binary(reader)  # noqa: E731
        if hasattr(writer, "write_message"):
            write = writer.write_message
        else:
            write = lambda m: write_message_binary(writer, m)  # noqa: E731

        self.adapter._writer = write

        while True:
            msg = read()
            if msg is None:
                return 0
            self._handle(msg, write)

    def _handle(self, msg: dict[str, Any], write: Any) -> None:
        method = msg.get("command")
        seq = msg.get("seq")
        DapSession._last_command = str(method)
        handler = getattr(self.adapter, "handle_" + str(method), None)
        if handler is None:
            self._respond(write, seq, None,
                          {"id": -32601, "message": f"unknown command: {method}"})
            return
        try:
            result = handler(msg.get("arguments"))
            self._respond(write, seq, result, None)
        except Exception as exc:  # noqa: BLE001
            self._respond(write, seq, None,
                          {"id": 1, "message": str(exc)})

    def _respond(self, write: Any, seq: Any, result: Any, error: Any) -> None:
        resp: dict[str, Any] = {
            "seq": _next_seq(), "type": "response",
            "request_seq": seq, "command": DapSession._last_command,
            "success": error is None,
        }
        if error is not None:
            resp["error"] = error
        else:
            resp["body"] = result or {}
        write(resp)

    _last_command = ""


_next_seq_counter = [0]


def _next_seq() -> int:
    _next_seq_counter[0] += 1
    return _next_seq_counter[0]


__all__ = ["DapSession", "HelixDebugAdapter"]

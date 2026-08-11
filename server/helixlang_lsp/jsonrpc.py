"""JSON-RPC 2.0 transport: LSP framing, message I/O, and dispatch.

Framing follows the LSP spec: a header block terminated by ``\\r\\n\\r\\n``
carrying ``Content-Length: <bytes>``, followed by a UTF-8 JSON body.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any, TextIO

MAX_MESSAGE_BYTES = 64 * 1024 * 1024  # 64 MB hard cap


class JsonRpcError(Exception):
    """A JSON-RPC error that should be returned to the client."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


class ErrorCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_NOT_INITIALIZED = -32002
    REQUEST_CANCELLED = -32800


class LspProtocolError(Exception):
    """Malformed framing (used by the reader)."""


def read_message(stream: TextIO) -> dict[str, Any] | None:
    """Read one LSP message from ``stream`` (or ``None`` at EOF).

    Args:
        stream: a binary-less text stream; CRLF is preserved on Windows.
    """
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == "":
            return None  # EOF
        if line in ("\r\n", "\n"):
            break
        if ":" not in line:
            raise LspProtocolError(f"malformed header line: {line!r}")
        key, _, value = line.partition(":")
        headers[key.strip().lower()] = value.strip()
    if "content-length" not in headers:
        raise LspProtocolError("missing Content-Length header")
    try:
        length = int(headers["content-length"])
    except ValueError as exc:
        raise LspProtocolError("invalid Content-Length") from exc
    if length < 0 or length > MAX_MESSAGE_BYTES:
        raise LspProtocolError(f"Content-Length out of range: {length}")
    body = stream.read(length)
    if len(body) < length:
        return None  # truncated stream
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LspProtocolError(f"invalid JSON body: {exc}") from exc


def write_message(stream: TextIO, message: dict[str, Any]) -> None:
    """Serialize ``message`` to ``stream`` with LSP framing."""
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    data = body.encode("utf-8")
    stream.write(f"Content-Length: {len(data)}\r\n\r\n")
    stream.write(body)
    stream.flush()


# --------------------------------------------------------------------------
# Binary framing (stdio/TCP transports)
# --------------------------------------------------------------------------

def read_message_binary(stream: Any) -> dict[str, Any] | None:
    """Read one framed message from a binary stream (``BufferedReader``)."""
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None  # EOF
        if line in (b"\r\n", b"\n"):
            break
        if b":" not in line:
            raise LspProtocolError(f"malformed header line: {line!r}")
        try:
            text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        except Exception:  # noqa: BLE001
            text = line.decode(errors="replace").rstrip("\r\n")
        key, _, value = text.partition(":")
        headers[key.strip().lower()] = value.strip()
    if "content-length" not in headers:
        raise LspProtocolError("missing Content-Length header")
    try:
        length = int(headers["content-length"])
    except ValueError as exc:
        raise LspProtocolError("invalid Content-Length") from exc
    if length < 0 or length > MAX_MESSAGE_BYTES:
        raise LspProtocolError(f"Content-Length out of range: {length}")
    body = stream.read(length)
    if len(body) < length:
        return None  # truncated stream
    try:
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LspProtocolError(f"invalid JSON body: {exc}") from exc


def write_message_binary(stream: Any, message: dict[str, Any]) -> None:
    """Serialize ``message`` to a binary stream with LSP framing."""
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(data))
    stream.write(data)
    stream.flush()


def _message_type(msg: dict[str, Any]) -> str:
    if "method" in msg and "id" in msg:
        return "request"
    if "method" in msg:
        return "notification"
    if "id" in msg:
        return "response"
    return "invalid"


class Dispatcher:
    """Routes parsed messages to a handler object.

    The handler exposes methods named after LSP methods with ``.`` mapped to
    ``_`` (e.g. ``textDocument/didOpen`` -> ``handle_textDocument_didOpen``).
    Requests return a result (serializable) or raise ``JsonRpcError``.
    """

    def __init__(self, handler: Any, *, writer: Callable[[dict[str, Any]], None] | None = None):
        self.handler = handler
        self.writer = writer or (lambda _: None)
        self._cancelled: set[int] = set()

    def dispatch(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        """Process one message, returning a list of outbound messages.

        Notifications may trigger outbound pushes (e.g. publishDiagnostics).
        """
        out: list[dict[str, Any]] = []
        kind = _message_type(msg)

        if kind == "request":
            msg_id = msg["id"]
            method = msg["method"]
            if msg_id in self._cancelled:
                self._cancelled.discard(msg_id)
                out.append(
                    self._error_response(msg_id, ErrorCodes.REQUEST_CANCELLED, "request cancelled")
                )
                return out
            try:
                result = self._invoke(method, msg.get("params"))
                out.append({"jsonrpc": "2.0", "id": msg_id, "result": result})
            except JsonRpcError as exc:
                out.append(self._error_response(msg_id, exc.code, exc.message, exc.data))
            except Exception as exc:  # noqa: BLE001 - last-resort server guard
                out.append(
                    self._error_response(
                        msg_id, ErrorCodes.INTERNAL_ERROR, f"internal error: {exc}"
                    )
                )

        elif kind == "notification":
            method = msg["method"]
            if method == "$/cancelRequest":
                self._cancelled.add(msg.get("params", {}).get("id"))
                return out
            try:
                result = self._invoke(method, msg.get("params"))
                pushed = result if isinstance(result, list) else [result]
                for item in pushed:
                    if isinstance(item, dict):
                        out.append(item)
            except JsonRpcError as exc:
                self._log_error(exc.message)
            except Exception as exc:  # noqa: BLE001
                self._log_error(f"notification {method} failed: {exc}")

        elif kind == "response":
            # Responses to requests we made (workspace/*) are forwarded to the
            # handler's _on_response callback if present.
            on_response = getattr(self.handler, "_on_response", None)
            if on_response is not None:
                try:
                    on_response(msg)
                except Exception as exc:  # noqa: BLE001
                    self._log_error(f"response handler failed: {exc}")

        else:
            out.append(
                self._error_response(None, ErrorCodes.INVALID_REQUEST, "invalid request")
            )
        return out

    def _invoke(self, method: str, params: Any) -> Any:
        attr = "handle_" + method.replace("/", "_")
        fn = getattr(self.handler, attr, None)
        if fn is None:
            raise JsonRpcError(ErrorCodes.METHOD_NOT_FOUND, f"method not found: {method}")
        return fn(params)

    def _error_response(self, msg_id: Any, code: int, message: str, data: Any = None) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message,
                      **( {"data": data} if data is not None else {})},
        }

    def _log_error(self, message: str) -> None:
        try:
            self.writer(
                {
                    "jsonrpc": "2.0",
                    "method": "window/logMessage",
                    "params": {"type": 2, "message": message},
                }
            )
        except Exception:  # noqa: BLE001
            print(f"[helixlang-lsp] {message}", file=sys.stderr)

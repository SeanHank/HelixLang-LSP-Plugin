"""Unit tests for JSON-RPC 2.0 framing and dispatch."""

from __future__ import annotations

import io
import json

import pytest
from helixlang_lsp.jsonrpc import (
    Dispatcher,
    ErrorCodes,
    JsonRpcError,
    LspProtocolError,
    read_message,
    read_message_binary,
    write_message,
    write_message_binary,
)


class DummyHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def handle_test_method(self, params) -> dict:
        self.calls.append(("test_method", params))
        return {"ok": True}

    def handle_test_fail(self, _params) -> None:
        raise JsonRpcError(ErrorCodes.INVALID_PARAMS, "bad params")

    def handle_textDocument_didOpen(self, params) -> None:
        self.calls.append(("didOpen", params))
        return None


def _frame(msg: dict) -> bytes:
    body = json.dumps(msg).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def test_read_write_roundtrip():
    stream = io.StringIO()
    msg = {"jsonrpc": "2.0", "id": 1, "method": "x", "params": {"a": 1}}
    write_message(stream, msg)
    stream.seek(0)
    assert read_message(stream) == msg


def test_read_multiple_messages():
    stream = io.StringIO()
    for i in range(3):
        write_message(stream, {"jsonrpc": "2.0", "id": i, "result": i})
    stream.seek(0)
    for i in range(3):
        msg = read_message(stream)
        assert msg["id"] == i
    assert read_message(stream) is None


def test_missing_content_length():
    stream = io.StringIO("Content-Type: application/json\r\n\r\n{}")
    with pytest.raises(LspProtocolError):
        read_message(stream)


def test_invalid_content_length():
    stream = io.StringIO("Content-Length: nope\r\n\r\n{}")
    with pytest.raises(LspProtocolError):
        read_message(stream)


def test_invalid_json_body():
    stream = io.StringIO("Content-Length: 4\r\n\r\n{not")
    with pytest.raises(LspProtocolError):
        read_message(stream)


def test_binary_framing_roundtrip():
    stream = io.BytesIO()
    msg = {"jsonrpc": "2.0", "method": "notify", "params": {"s": "héllo"}}
    write_message_binary(stream, msg)
    stream.seek(0)
    assert read_message_binary(stream) == msg


def test_binary_utf8_length_not_corrupted():
    """Content-Length must count bytes, not characters."""
    body = json.dumps({"s": "✓✓✓"}).encode("utf-8")
    stream = io.BytesIO(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    assert read_message_binary(stream)["s"] == "✓✓✓"


def test_dispatch_request():
    handler = DummyHandler()
    dispatcher = Dispatcher(handler)
    out = dispatcher.dispatch({"jsonrpc": "2.0", "id": 5,
                               "method": "test/method",
                               "params": {"x": 1}})
    assert len(out) == 1
    assert out[0]["id"] == 5
    assert out[0]["result"] == {"ok": True}
    assert handler.calls[0] == ("test_method", {"x": 1})


def test_dispatch_method_not_found():
    dispatcher = Dispatcher(DummyHandler())
    out = dispatcher.dispatch({"jsonrpc": "2.0", "id": 1,
                               "method": "no/such/method"})
    assert out[0]["error"]["code"] == ErrorCodes.METHOD_NOT_FOUND


def test_dispatch_raises_jsonrpc_error():
    dispatcher = Dispatcher(DummyHandler())
    out = dispatcher.dispatch({"jsonrpc": "2.0", "id": 2,
                               "method": "test/fail"})
    assert out[0]["error"]["code"] == ErrorCodes.INVALID_PARAMS


def test_dispatch_notification_runs_handler():
    handler = DummyHandler()
    dispatcher = Dispatcher(handler)
    out = dispatcher.dispatch({"jsonrpc": "2.0",
                               "method": "textDocument/didOpen",
                               "params": {"uri": "u"}})
    assert out == []
    assert handler.calls[0][0] == "didOpen"


def test_dispatch_notification_pushes_outbound():
    class PushingHandler:
        def handle_go(self, _p):
            return {"jsonrpc": "2.0", "method": "x/push", "params": {}}

    out = Dispatcher(PushingHandler()).dispatch({"jsonrpc": "2.0", "method": "go"})
    assert out == [{"jsonrpc": "2.0", "method": "x/push", "params": {}}]


def test_cancel_request():
    handler = DummyHandler()
    dispatcher = Dispatcher(handler)
    dispatcher.dispatch({"jsonrpc": "2.0", "id": 9, "method": "test/method"})
    dispatcher.dispatch({"jsonrpc": "2.0", "method": "$/cancelRequest",
                         "params": {"id": 9}})
    out = dispatcher.dispatch({"jsonrpc": "2.0", "id": 9, "method": "test/method"})
    assert out[0]["error"]["code"] == ErrorCodes.REQUEST_CANCELLED


def test_invalid_message():
    out = Dispatcher(DummyHandler()).dispatch({"jsonrpc": "2.0"})
    assert out[0]["error"]["code"] == ErrorCodes.INVALID_REQUEST


def test_jsonrpc_error_to_dict_with_data():
    err = JsonRpcError(ErrorCodes.INVALID_PARAMS, "bad params", data={"k": 1})
    assert err.to_dict() == {"code": -32602, "message": "bad params", "data": {"k": 1}}


def test_read_message_malformed_header():
    with pytest.raises(LspProtocolError):
        read_message(io.StringIO("no-colon-here\r\n\r\n{}"))


def test_read_message_content_length_out_of_range():
    with pytest.raises(LspProtocolError):
        read_message(io.StringIO("Content-Length: -1\r\n\r\n{}"))


def test_read_message_truncated_body():
    assert read_message(io.StringIO("Content-Length: 10\r\n\r\n{short")) is None


def test_read_message_binary_malformed_header():
    with pytest.raises(LspProtocolError):
        read_message_binary(io.BytesIO(b"no-colon-here\r\n\r\n{}"))


def test_read_message_binary_missing_content_length():
    with pytest.raises(LspProtocolError):
        read_message_binary(io.BytesIO(b"Content-Type: application/json\r\n\r\n{}"))


def test_read_message_binary_invalid_content_length():
    with pytest.raises(LspProtocolError):
        read_message_binary(io.BytesIO(b"Content-Length: nope\r\n\r\n{}"))


def test_read_message_binary_content_length_out_of_range():
    with pytest.raises(LspProtocolError):
        read_message_binary(io.BytesIO(b"Content-Length: -1\r\n\r\n{}"))


def test_read_message_binary_truncated_body():
    assert read_message_binary(io.BytesIO(b"Content-Length: 10\r\n\r\n{short")) is None


def test_read_message_binary_invalid_utf8_body():
    body = b"\xff\xfe{not json}"
    stream = io.BytesIO(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    with pytest.raises(LspProtocolError):
        read_message_binary(stream)


def test_dispatch_generic_exception_is_internal_error():
    class Boom:
        def handle_test(self, _p):
            raise RuntimeError("boom")

    out = Dispatcher(Boom()).dispatch({"jsonrpc": "2.0", "id": 1, "method": "test"})
    assert out[0]["error"]["code"] == ErrorCodes.INTERNAL_ERROR
    assert "boom" in out[0]["error"]["message"]


def test_dispatch_notification_generic_exception_logs():
    class Boom:
        def handle_test(self, _p):
            raise RuntimeError("boom")

    logged: list[dict] = []
    disp = Dispatcher(Boom(), writer=lambda m: logged.append(m))
    out = disp.dispatch({"jsonrpc": "2.0", "method": "test"})
    assert out == []
    assert logged and logged[0]["method"] == "window/logMessage"
    assert "boom" in logged[0]["params"]["message"]


def test_dispatch_notification_jsonrpc_exception_logs():
    class Failing:
        def handle_test(self, _p):
            raise JsonRpcError(ErrorCodes.INVALID_PARAMS, "nope")

    logged: list[dict] = []
    disp = Dispatcher(Failing(), writer=lambda m: logged.append(m))
    disp.dispatch({"jsonrpc": "2.0", "method": "test"})
    assert logged[0]["method"] == "window/logMessage"


def test_dispatch_response_forwards_to_on_response():
    class H:
        def __init__(self) -> None:
            self.seen: list[dict] = []

        def _on_response(self, msg) -> None:
            self.seen.append(msg)

    h = H()
    out = Dispatcher(h).dispatch({"jsonrpc": "2.0", "id": 7, "result": {"ok": 1}})
    assert out == []
    assert h.seen[0]["result"] == {"ok": 1}


def test_dispatch_response_handler_error_logs():
    class H:
        def _on_response(self, msg) -> None:
            raise RuntimeError("resp boom")

    logged: list[dict] = []
    disp = Dispatcher(H(), writer=lambda m: logged.append(m))
    disp.dispatch({"jsonrpc": "2.0", "id": 7, "result": {}})
    assert logged[0]["method"] == "window/logMessage"
    assert "resp boom" in logged[0]["params"]["message"]


def test_log_error_falls_back_to_stderr_when_writer_raises(capsys):
    class Boom:
        def handle_test(self, _p):
            raise RuntimeError("boom")

    def broken_writer(_m) -> None:
        raise OSError("writer down")

    disp = Dispatcher(Boom(), writer=broken_writer)
    disp.dispatch({"jsonrpc": "2.0", "method": "test"})
    assert "boom" in capsys.readouterr().err

"""Entry points: ``python -m helixlang_lsp`` / ``helixlang-lsp``.

Transports: stdio (default) or TCP (``--host --port``). Optional ``--trace``
writes a JSONL transcript of every message (doc/03 §2.2).
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
from typing import Any

from helixlang_lsp.server import HelixLspServer

log = logging.getLogger("helixlang_lsp")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="helixlang-lsp",
                                description="HelixLang language server (LSP)")
    p.add_argument("--stdio", action="store_true", help="serve over stdio (default)")
    p.add_argument("--host", type=str, default=None, help="TCP listen host")
    p.add_argument("--port", type=int, default=None, help="TCP listen port")
    p.add_argument("--dap", action="store_true",
                   help="Debug Adapter Protocol mode (single TCP connection)")
    p.add_argument("--dap-port", type=int, default=0,
                   help="TCP listen port for --dap (default: 0 = ephemeral)")
    p.add_argument("--dap-port-file", type=str, default=None,
                   help="write the chosen DAP listen port to FILE")
    p.add_argument("--trace", type=str, default=None,
                   help="write a JSONL transcript of all messages to FILE")
    p.add_argument("--loglevel", type=str, default="WARNING",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="logging level")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.loglevel, logging.WARNING),
                        format="%(levelname)s %(name)s: %(message)s")

    if args.dap:
        return _serve_dap(args.dap_port, args.dap_port_file)

    server = HelixLspServer(on_log=lambda m: log.warning("%s", m))
    if args.trace:
        server._trace = _trace_writer(args.trace)  # noqa: SLF001 - transport hook

    if args.host and args.port:
        return _serve_tcp(server, args.host, args.port)
    return _serve_stdio(server)


def _serve_dap(port: int | None, port_file: str | None) -> int:
    """Run one DAP session over a local TCP connection (doc/04 §8)."""
    from helixlang_lsp.dap import DapSession, HelixDebugAdapter

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port if port is not None else 0))
        listen_port = srv.getsockname()[1]
        log.info("DAP listening on 127.0.0.1:%d", listen_port)
        if port_file:
            with open(port_file, "w", encoding="utf-8") as fh:
                fh.write(str(listen_port))
        srv.listen(1)
        conn, _addr = srv.accept()
        with conn:
            conn.settimeout(0.5)
            session = DapSession(HelixDebugAdapter())
            return session.run(conn.makefile("rb"), conn.makefile("wb"))


def _serve_stdio(server: HelixLspServer) -> int:
    reader = sys.stdin.buffer
    writer = sys.stdout.buffer
    try:
        return server.run(reader, writer)
    except KeyboardInterrupt:
        return 0


def _serve_tcp(server: HelixLspServer, host: str, port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(1)
        log.info("listening on %s:%d", host, port)
        conn, _addr = srv.accept()
        with conn:
            conn.settimeout(0.5)
            return server.run(conn.makefile("rb"), conn.makefile("wb"))


def _trace_writer(path: str):
    fh = open(path, "a", encoding="utf-8")

    def record(msg: dict[str, Any]) -> None:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        fh.flush()

    return record


if __name__ == "__main__":
    sys.exit(main())

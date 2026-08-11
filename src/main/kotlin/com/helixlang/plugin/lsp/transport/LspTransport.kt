package com.helixlang.plugin.lsp.transport

import com.google.gson.JsonObject

/**
 * Transport boundary for LSP messages. All methods are thread-safe; wire
 * activity happens on dedicated background threads (never the EDT).
 *
 * The server is editor-agnostic, so the client core isolates every LSP wiring
 * detail behind this interface (see doc/04 §4.2) — a future LSP4IJ adapter can
 * reuse the same server definition unchanged.
 */
interface LspTransport {
    /** Start the transport (spawn the server process or open the connection). */
    fun start()

    /** Send a JSON-RPC message; serialized by an internal lock. */
    fun send(message: JsonObject)

    /** Register the single consumer of inbound messages (reader thread → consumer). */
    fun setMessageConsumer(consumer: (JsonObject) -> Unit)

    /** Stop the transport: destroy the process, close streams, join the reader thread. */
    fun dispose()
}

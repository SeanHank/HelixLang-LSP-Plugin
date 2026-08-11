package com.helixlang.plugin.lsp

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.protocol.LspConstants
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/**
 * JSON-RPC layer: correlates responses to requests and routes notifications to
 * registered handlers (doc/04 §4.3).
 *
 * - Request IDs are monotonically increasing [Long]s.
 * - A [ConcurrentHashMap] correlates in-flight requests with futures.
 * - Notifications are dispatched to handlers registered by method name.
 * - `$/cancelRequest` and `window/logMessage` are handled natively.
 */
class LspDispatcher(private val send: (JsonObject) -> Unit) {

    private val pending = ConcurrentHashMap<Long, CompletableFuture<JsonObject>>()
    private val handlers = ConcurrentHashMap<String, (JsonObject) -> Unit>()
    private val nextId = AtomicLong(1)

    /** Request a response from the server; completes from the reader thread. */
    fun request(method: String, params: JsonObject?, timeoutMs: Long = 5000): CompletableFuture<JsonObject> {
        val id = nextId.getAndIncrement()
        val future = CompletableFuture<JsonObject>()
        pending[id] = future
        send(LspMessages.request(id, method, params))
        return future.orTimeout(timeoutMs, TimeUnit.MILLISECONDS)
    }

    /** Send a one-way notification. */
    fun notify(method: String, params: JsonObject?) {
        send(LspMessages.notify(method, params))
    }

    /** Register a notification handler (e.g. publishDiagnostics). */
    fun on(method: String, handler: (JsonObject) -> Unit) {
        handlers[method] = handler
    }

    /** Deliver an inbound message from the reader thread. */
    fun dispatch(message: JsonObject) {
        if (message.has("id") && (message.has("result") || message.has("error"))) {
            val id = message.get("id").asLong
            val future = pending.remove(id) ?: return
            future.complete(message)
            return
        }
        val method = message.get("method")?.asString ?: return
        val params = message.get("params")?.asJsonObject
        when (method) {
            LspConstants.CANCEL_REQUEST -> handleCancel(params)
            LspConstants.WINDOW_LOG_MESSAGE -> handleLog(params)
            else -> handlers[method]?.invoke(params ?: JsonObject())
        }
    }

    /** Cancel an in-flight request (used for stale hover/completion). */
    fun cancel(id: Long) {
        pending.remove(id)?.cancel(true)
    }

    /** Number of in-flight requests (for diagnostics/tests). */
    fun inflightCount(): Int = pending.size

    private fun handleCancel(params: JsonObject?) {
        val id = params?.get("id")?.takeIf { it.isJsonPrimitive }
        if (id != null) {
            try {
                cancel(id.asLong)
            } catch (_: UnsupportedOperationException) {
            }
        }
    }

    private fun handleLog(params: JsonObject?) {
        val type = params?.get("type")?.asInt ?: 3
        val msg = params?.get("message")?.asString ?: ""
        when (type) {
            1 -> HelixLspLog.error(msg)
            2 -> HelixLspLog.warn(msg)
            else -> HelixLspLog.info(msg)
        }
    }

    private object LspMessages {
        fun request(id: Long, method: String, params: JsonObject?): JsonObject =
            JsonObject().apply {
                addProperty("jsonrpc", "2.0")
                addProperty("id", id)
                addProperty("method", method)
                params?.let { add("params", it) }
            }

        fun notify(method: String, params: JsonObject?): JsonObject =
            JsonObject().apply {
                addProperty("jsonrpc", "2.0")
                addProperty("method", method)
                params?.let { add("params", it) }
            }
    }
}

/** Minimal logging facade for LSP lifecycle events (doc/02 §9). */
object HelixLspLog {
    private val log = com.intellij.openapi.diagnostic.Logger.getInstance("helixlang-lsp")

    @JvmStatic
    fun info(message: String) = log.info(message)

    @JvmStatic
    fun warn(message: String) = log.warn(message)

    @JvmStatic
    fun error(message: String) = log.error(message)
}

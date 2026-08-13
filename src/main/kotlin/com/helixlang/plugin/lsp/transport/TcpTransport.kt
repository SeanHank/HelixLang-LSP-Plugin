package com.helixlang.plugin.lsp.transport

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.protocol.LspFraming
import com.intellij.openapi.diagnostic.Logger
import java.io.InputStream
import java.net.Socket

/**
 * TCP transport: connects to a server already listening on
 * `helixlang_lsp --host 127.0.0.1 --port <port>`. Useful for troubleshooting the
 * server in isolation and for attaching profilers (doc/04 §4.2).
 */
class TcpTransport(
    private val host: String,
    private val port: Int,
) : LspTransport {

    private val log = Logger.getInstance(TcpTransport::class.java)

    @Volatile private var socket: Socket? = null
    @Volatile private var consumer: ((JsonObject) -> Unit)? = null
    @Volatile private var writer: AsyncFrameWriter? = null
    private var readerThread: Thread? = null

    override fun start() {
        val sock = Socket()
        sock.connect(java.net.InetSocketAddress(host, port), 5000)
        socket = sock
        writer = AsyncFrameWriter(log, sock.getOutputStream()).also { it.start() }
        val thread = Thread(
            { readLoop(sock) },
            "helix-lsp-tcp-reader",
        )
        thread.isDaemon = true
        thread.start()
        readerThread = thread
    }

    private fun readLoop(sock: Socket) {
        try {
            val input: InputStream = sock.getInputStream()
            while (true) {
                val body = LspFraming.readFrame(input) ?: break
                consumer?.invoke(com.google.gson.JsonParser.parseString(body).asJsonObject)
            }
        } catch (t: Throwable) {
            log.warn("LSP TCP reader stopped: ${t.message}")
        }
    }

    override fun send(message: JsonObject) {
        if (socket == null) return
        writer?.enqueue(LspFraming.frame(message.toString()))
    }

    override fun setMessageConsumer(consumer: (JsonObject) -> Unit) {
        this.consumer = consumer
    }

    override fun dispose() {
        writer?.stop()
        try {
            socket?.close()
        } catch (_: Throwable) {
        }
        socket = null
    }
}

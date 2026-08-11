package com.helixlang.plugin.debug

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.openapi.diagnostic.Logger
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * Minimal DAP wire client (doc/04 §8). Content-Length framing over a single
 * TCP connection; requests are correlated by `seq`, events are dispatched to
 * the [listener]. Events arriving before the listener is installed are
 * buffered and replayed, which lets the handshake run before the debug
 * session exists.
 */
class HelixDapClient private constructor(
    private val socket: Socket,
    private val input: InputStream,
    private val output: OutputStream,
) : Closeable {

    private val log = Logger.getInstance(HelixDapClient::class.java)
    private val nextSeq = AtomicInteger(0)
    private val pending = ConcurrentHashMap<Int, CompletableFuture<JsonObject>>()
    private val writeLock = Any()
    private val listenerLock = Any()

    @Volatile
    private var closed = false

    @Volatile
    var listener: ((DapEvent) -> Unit)? = null

    private val bufferedEvents = mutableListOf<DapEvent>()

    private val readThread = Thread({ readLoop() }, "helixlang-dap-read").apply {
        isDaemon = true
    }

    init {
        readThread.start()
    }

    // ------------------------------------------------------------------
    // requests / events
    // ------------------------------------------------------------------

    /** Sends a request and completes when the matching response arrives. */
    fun request(command: String, args: JsonObject? = null): CompletableFuture<JsonObject> {
        val id = nextSeq.incrementAndGet()
        val message = JsonObject().apply {
            addProperty("seq", id)
            addProperty("type", "request")
            addProperty("command", command)
            if (args != null) add("arguments", args)
        }
        val future = CompletableFuture<JsonObject>()
        pending[id] = future
        if (!send(message)) {
            pending.remove(id)
            future.completeExceptionally(IOException("DAP connection closed"))
        }
        return future
    }

    /** Installs the event handler and replays any events buffered meanwhile. */
    fun setEventListener(handler: (DapEvent) -> Unit) {
        val buffered: List<DapEvent>
        synchronized(listenerLock) {
            listener = handler
            buffered = bufferedEvents.toList()
            bufferedEvents.clear()
        }
        buffered.forEach { dispatch(handler, it) }
    }

    private fun dispatch(handler: (DapEvent) -> Unit, event: DapEvent) {
        try {
            handler(event)
        } catch (t: Throwable) {
            log.warn("DAP event handler failed: ${t.message}", t)
        }
    }

    // ------------------------------------------------------------------
    // framing
    // ------------------------------------------------------------------

    private fun readLoop() {
        try {
            while (!closed) {
                val length = readHeader()
                if (length < 0) break
                val body = readBody(length) ?: break
                val message = try {
                    JsonParser.parseString(body).asJsonObject
                } catch (t: Throwable) {
                    log.warn("malformed DAP message: ${t.message}")
                    continue
                }
                handleMessage(message)
            }
        } catch (t: Throwable) {
            if (!closed) {
                log.warn("DAP read loop ended: ${t.message}")
            }
        } finally {
            failPending(IOException("DAP connection closed"))
            close()
        }
    }

    private fun handleMessage(message: JsonObject) {
        when (message.get("type")?.asString) {
            "response" -> {
                val requestSeq = message.get("request_seq")?.asInt ?: return
                val future = pending.remove(requestSeq) ?: return
                if (message.get("success")?.asBoolean ?: false) {
                    future.complete(message.get("body")?.asJsonObject ?: JsonObject())
                } else {
                    val text = message.get("error")?.asJsonObject?.get("message")?.asString
                        ?: message.get("message")?.asString
                        ?: "DAP request failed"
                    future.completeExceptionally(RuntimeException(text))
                }
            }
            "event" -> {
                val name = message.get("event")?.asString ?: return
                val body = message.get("body")?.asJsonObject ?: JsonObject()
                val event = DapEvent(name, body)
                val handler = synchronized(listenerLock) {
                    val current = listener
                    if (current == null) {
                        bufferedEvents += event
                        null
                    } else current
                }
                handler?.let { dispatch(it, event) }
            }
            else -> Unit
        }
    }

    private fun readHeader(): Int {
        var length = -1
        while (true) {
            val line = readLine() ?: return -1
            if (line.isEmpty()) break
            if (line.startsWith("Content-Length:", ignoreCase = true)) {
                length = line.substringAfter(':').trim().toIntOrNull() ?: -1
            }
        }
        return length
    }

    private fun readLine(): String? {
        val sb = StringBuilder()
        while (true) {
            val b = input.read()
            if (b == -1) return if (sb.isEmpty()) null else sb.toString()
            if (b == '\n'.code) return sb.toString()
            if (b != '\r'.code) sb.append(b.toChar())
        }
    }

    private fun readBody(length: Int): String? {
        if (length < 0) return null
        val bytes = ByteArray(length)
        var offset = 0
        while (offset < length) {
            val read = input.read(bytes, offset, length - offset)
            if (read == -1) return null
            offset += read
        }
        return String(bytes, Charsets.UTF_8)
    }

    private fun send(message: JsonObject): Boolean {
        val bytes = message.toString().toByteArray(Charsets.UTF_8)
        synchronized(writeLock) {
            if (closed) return false
            try {
                output.write(
                    "Content-Length: ${bytes.size}\r\n\r\n".toByteArray(Charsets.US_ASCII))
                output.write(bytes)
                output.flush()
                return true
            } catch (t: Throwable) {
                log.warn("DAP write failed: ${t.message}")
                return false
            }
        }
    }

    private fun failPending(error: Throwable) {
        for ((_, future) in pending) {
            future.completeExceptionally(error)
        }
        pending.clear()
    }

    override fun close() {
        synchronized(writeLock) {
            if (closed) return
            closed = true
        }
        failPending(IOException("DAP connection closed"))
        try {
            socket.close()
        } catch (_: Throwable) {
        }
    }

    companion object {
        fun connect(host: String, port: Int, timeoutMs: Int = 5000): HelixDapClient {
            val socket = Socket()
            socket.connect(InetSocketAddress(host, port), timeoutMs)
            socket.tcpNoDelay = true
            return HelixDapClient(
                socket,
                BufferedInputStream(socket.getInputStream()),
                BufferedOutputStream(socket.getOutputStream()),
            )
        }
    }
}

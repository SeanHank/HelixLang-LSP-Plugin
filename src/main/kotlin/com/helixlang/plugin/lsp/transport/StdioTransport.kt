package com.helixlang.plugin.lsp.transport

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.protocol.LspFraming
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.process.ProcessIOExecutorService
import com.intellij.openapi.diagnostic.Logger

/**
 * Default transport: launches the server as a child process and speaks framed
 * JSON-RPC over its stdin/stdout.
 *
 * Command: `<python> -m helixlang_lsp --stdio`. A dedicated reader thread parses
 * `Content-Length` frames from the child's stdout and forwards each message to
 * the registered consumer.
 */
class StdioTransport(
    private val command: GeneralCommandLine,
) : LspTransport {

    private val log = Logger.getInstance(StdioTransport::class.java)

    @Volatile private var process: Process? = null
    @Volatile private var consumer: ((JsonObject) -> Unit)? = null
    @Volatile private var writer: AsyncFrameWriter? = null
    private var readerThread: Thread? = null
    private val framing = LspFraming()

    override fun start() {
        val child = command.createProcess()
        process = child
        ProcessIOExecutorService.INSTANCE.execute { child.waitFor() }
        writer = AsyncFrameWriter(log, child.outputStream).also { it.start() }
        val thread = Thread(
            { readLoop(child) },
            "helix-lsp-reader",
        )
        thread.isDaemon = true
        thread.start()
        readerThread = thread
    }

    private fun readLoop(child: Process) {
        try {
            child.inputStream.buffered().use { input ->
                while (true) {
                    val body = LspFraming.readFrame(input) ?: break
                    consumer?.invoke(parse(body))
                }
            }
        } catch (t: Throwable) {
            log.warn("LSP reader stopped: ${t.message}")
        }
        log.info("LSP process exited, reader loop done")
    }

    private fun parse(body: String): JsonObject {
        return com.google.gson.JsonParser.parseString(body).asJsonObject
    }

    override fun send(message: JsonObject) {
        if (process == null) return
        writer?.enqueue(LspFraming.frame(message.toString()))
    }

    override fun setMessageConsumer(consumer: (JsonObject) -> Unit) {
        this.consumer = consumer
    }

    override fun dispose() {
        val child = process ?: return
        try {
            child.outputStream.close()
        } catch (_: Throwable) {
        }
        writer?.stop()
        try {
            child.destroy()
        } catch (_: Throwable) {
        }
        try {
            readerThread?.join(1000)
        } catch (_: Throwable) {
        }
        process = null
    }
}

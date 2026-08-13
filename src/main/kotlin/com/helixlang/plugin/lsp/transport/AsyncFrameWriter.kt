package com.helixlang.plugin.lsp.transport

import com.intellij.openapi.diagnostic.Logger
import java.io.OutputStream
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Bounded, order-preserving writer for framed LSP messages.
 *
 * [enqueue] returns quickly and never blocks the calling thread (which is often
 * the EDT): the frame is queued and written by a dedicated daemon thread. If the
 * server stops draining its stdin (wedged process, dead child, ...) the queue
 * fills up and further frames are dropped after a short offer timeout instead of
 * freezing the IDE on a blocking pipe write — this was the root cause of the
 * project/plugin-page hang on PyCharm 2022.2.
 */
class AsyncFrameWriter(
    private val log: Logger,
    private val out: OutputStream,
) {

    private val queue = ArrayBlockingQueue<ByteArray>(512)
    private val stopped = AtomicBoolean(false)
    private var thread: Thread? = null

    fun start() {
        stopped.set(false)
        val t = Thread({ loop() }, "helix-lsp-writer")
        t.isDaemon = true
        t.start()
        thread = t
    }

    fun enqueue(bytes: ByteArray) {
        if (stopped.get()) return
        val accepted = try {
            queue.offer(bytes, 100, TimeUnit.MILLISECONDS)
        } catch (_: InterruptedException) {
            false
        }
        if (!accepted) log.warn("LSP write queue full; dropping outbound frame")
    }

    private fun loop() {
        while (true) {
            if (stopped.get()) return
            val bytes = try {
                queue.poll(500, TimeUnit.MILLISECONDS)
            } catch (_: InterruptedException) {
                return
            }
            if (bytes == null) continue
            try {
                out.write(bytes)
                out.flush()
            } catch (t: Throwable) {
                log.warn("LSP write failed: ${t.message}")
                stopped.set(true)
                queue.clear()
                return
            }
        }
    }

    fun stop() {
        stopped.set(true)
        queue.clear()
        thread?.let {
            it.interrupt()
            try {
                it.join(1000)
            } catch (_: InterruptedException) {
            }
        }
        thread = null
    }
}

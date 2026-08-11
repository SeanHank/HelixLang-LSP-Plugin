package com.helixlang.plugin.lsp.protocol

import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.charset.StandardCharsets

/**
 * Framing parser for the LSP `Content-Length: <n>\r\n\r\n<body>` protocol.
 *
 * A small state machine that is tolerant of header order, ignores unknown
 * headers, and enforces a hard cap (default 64 MB) so a malicious or buggy
 * peer cannot exhaust memory.
 */
class LspFraming(private val maxBodyBytes: Int = 64 * 1024 * 1024) {

    private enum class State { HEADERS, BODY }
    private var state = State.HEADERS
    private val headerBuf = ByteArrayOutputStream()
    private var contentLength = -1
    private var bodyRead = 0
    private val bodyBuf = ByteArrayOutputStream()

    /**
     * Feed a chunk of bytes read from the transport. Returns a list of complete
     * JSON bodies (already decoded) that became available in this chunk, in order.
     */
    fun feed(data: ByteArray, length: Int = data.size): List<String> {
        val out = mutableListOf<String>()
        var offset = 0
        while (offset < length) {
            if (state == State.HEADERS) {
                val line = readHeaderLine(data, offset, length)
                if (line == null) {
                    // need more bytes for a complete header line
                    if (headerBuf.size() > 64 * 1024) {
                        throw IllegalStateException("LSP header line exceeds 64 KiB")
                    }
                    return out
                }
                offset += line.consumed
                val trimmed = line.text.trim()
                if (trimmed.isEmpty()) {
                    if (contentLength < 0) {
                        throw IllegalStateException("missing Content-Length header")
                    }
                    state = State.BODY
                    bodyRead = 0
                } else {
                    val colon = trimmed.indexOf(':')
                    if (colon > 0) {
                        val key = trimmed.substring(0, colon).trim().lowercase()
                        val value = trimmed.substring(colon + 1).trim()
                        if (key == "content-length") {
                            contentLength = value.toIntOrNull()
                                ?: throw IllegalStateException("invalid Content-Length: $value")
                            if (contentLength < 0 || contentLength > maxBodyBytes) {
                                throw IllegalStateException(
                                    "Content-Length out of range: $contentLength")
                            }
                        }
                    }
                }
            } else {
                val available = length - offset
                val want = contentLength - bodyRead
                val take = minOf(available, want)
                bodyBuf.write(data, offset, take)
                offset += take
                bodyRead += take
                if (bodyRead == contentLength) {
                    val body = bodyBuf.toString(StandardCharsets.UTF_8.name())
                    bodyBuf.reset()
                    state = State.HEADERS
                    contentLength = -1
                    headerBuf.reset()
                    out.add(body)
                }
            }
        }
        return out
    }

    private class HeaderLine(val text: String, val consumed: Int)

    private fun readHeaderLine(data: ByteArray, from: Int, to: Int): HeaderLine? {
        for (i in from until to) {
            if (data[i] == '\n'.code.toByte()) {
                var end = i
                if (end > from && data[end - 1] == '\r'.code.toByte()) end -= 1
                headerBuf.write(data, from, end - from)
                val line = headerBuf.toString(StandardCharsets.UTF_8.name())
                headerBuf.reset()
                return HeaderLine(line, i + 1 - from)
            }
        }
        // no newline yet: buffer the partial line
        headerBuf.write(data, from, to - from)
        return null
    }

    companion object {
        /** Read one complete frame from [input] (blocking), or null at EOF. */
        @JvmStatic
        fun readFrame(input: InputStream, maxBodyBytes: Int = 64 * 1024 * 1024): String? {
            var contentLength = -1
            val headerBuf = ByteArrayOutputStream()
            var inHeaders = true
            while (true) {
                if (inHeaders) {
                    var b = input.read()
                    if (b < 0) return null
                    while (b >= 0) {
                        if (b == '\n'.code) {
                            val line = headerBuf.toString(StandardCharsets.UTF_8.name()).trim()
                            headerBuf.reset()
                            if (line.isEmpty()) {
                                inHeaders = false
                                break
                            }
                            val colon = line.indexOf(':')
                            if (colon > 0 &&
                                line.substring(0, colon).trim().lowercase() == "content-length") {
                                contentLength = line.substring(colon + 1).trim().toIntOrNull()
                                    ?: throw IllegalStateException("invalid Content-Length")
                                if (contentLength > maxBodyBytes) {
                                    throw IllegalStateException("Content-Length too large")
                                }
                            }
                        } else if (b != '\r'.code) {
                            headerBuf.write(b)
                        }
                        b = input.read()
                    }
                    if (!inHeaders && contentLength < 0) {
                        throw IllegalStateException("missing Content-Length header")
                    }
                } else {
                    val body = ByteArray(contentLength)
                    var read = 0
                    while (read < contentLength) {
                        val n = input.read(body, read, contentLength - read)
                        if (n < 0) return null // truncated frame / EOF
                        read += n
                    }
                    return String(body, StandardCharsets.UTF_8)
                }
            }
        }

        /** Encode a JSON body into a `Content-Length` framed byte array. */
        @JvmStatic
        fun frame(body: String): ByteArray {
            val payload = body.toByteArray(StandardCharsets.UTF_8)
            val header = "Content-Length: ${payload.size}\r\n\r\n".toByteArray(StandardCharsets.US_ASCII)
            val out = ByteArray(header.size + payload.size)
            System.arraycopy(header, 0, out, 0, header.size)
            System.arraycopy(payload, 0, out, header.size, payload.size)
            return out
        }
    }
}

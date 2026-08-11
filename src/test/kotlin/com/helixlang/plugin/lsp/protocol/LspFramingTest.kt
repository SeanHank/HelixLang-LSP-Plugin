package com.helixlang.plugin.lsp.protocol

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import java.io.ByteArrayInputStream
import java.nio.charset.StandardCharsets

class LspFramingTest {

    @Test
    fun `parses a simple framed message`() {
        val body = """{"jsonrpc":"2.0","method":"x/y","params":{}}"""
        val framed = LspFraming.frame(body)
        assertEquals("Content-Length: ${body.toByteArray().size}\r\n\r\n",
            framed.decodeToString().substringBefore(body))
        val result = LspFraming.readFrame(ByteArrayInputStream(framed))
        assertEquals(body, result)
    }

    @Test
    fun `state machine reassembles chunked frames`() {
        val body = """{"jsonrpc":"2.0","id":1,"result":{"a":1}}"""
        val framed = LspFraming.frame(body)
        val framing = LspFraming()
        val bodies = mutableListOf<String>()
        // feed byte by byte
        for (b in framed) {
            bodies += framing.feed(byteArrayOf(b))
        }
        assertEquals(listOf(body), bodies)
    }

    @Test
    fun `state machine handles two frames in one chunk`() {
        val body1 = """{"a":1}"""
        val body2 = """{"b":2}"""
        val framing = LspFraming()
        val chunk = LspFraming.frame(body1) + LspFraming.frame(body2)
        assertEquals(listOf(body1, body2), framing.feed(chunk))
    }

    @Test
    fun `throws on missing content-length`() {
        val garbage = "nonsense\r\n\r\n{}".toByteArray(StandardCharsets.UTF_8)
        assertThrows(IllegalStateException::class.java) {
            LspFraming.readFrame(ByteArrayInputStream(garbage))
        }
    }

    @Test
    fun `throws on oversized frame`() {
        val framing = LspFraming(maxBodyBytes = 16)
        val body = """{"payload":"this body is longer than sixteen bytes"}"""
        assertThrows(IllegalStateException::class.java) {
            framing.feed(LspFraming.frame(body))
        }
    }

    @Test
    fun `counts content-length in bytes not characters`() {
        val body = "héllo JSON" // non-ASCII
        val framed = LspFraming.frame(body)
        assertEquals("Content-Length: ${body.toByteArray(StandardCharsets.UTF_8).size}\r\n\r\n",
            framed.decodeToString().substringBefore(body))
    }
}

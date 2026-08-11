package com.helixlang.plugin.lsp.protocol

import com.google.gson.JsonParser
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class LspMessagesTest {

    @Test
    fun `initialize request carries rootUri and capabilities`() {
        val msg = LspMessages.initialize("file:///workspace")
        assertEquals("2.0", msg.get("jsonrpc").asString)
        assertEquals("initialize", msg.get("method").asString)
        assertTrue(msg.get("id").isJsonPrimitive)
        assertEquals("file:///workspace", msg.getAsJsonObject("params").get("rootUri").asString)
        assertTrue(msg.getAsJsonObject("params").has("capabilities"))
    }

    @Test
    fun `didOpen carries language id version and text`() {
        val msg = LspMessages.didOpen("file:///t.helix", "#gene name=g\n", 1)
        val td = msg.getAsJsonObject("params").getAsJsonObject("textDocument")
        assertEquals("helix", td.get("languageId").asString)
        assertEquals(1, td.get("version").asInt)
        assertEquals("#gene name=g\n", td.get("text").asString)
    }

    @Test
    fun `didChange carries a utf16 range delta`() {
        val range = LspMessages.RangeLsp(0, 3, 0, 6)
        val msg = LspMessages.didChange("file:///t.helix", 2, range, "TAA")
        val changes = msg.getAsJsonObject("params").getAsJsonArray("contentChanges")
        assertEquals(1, changes.size())
        val change = changes[0].asJsonObject
        assertEquals("TAA", change.get("text").asString)
        assertEquals(3, change.getAsJsonObject("range").getAsJsonObject("start").get("character").asInt)
    }

    @Test
    fun `full document replacement drops the range`() {
        val msg = LspMessages.didChange("file:///t.helix", 2, null, "NEW")
        val change = msg.getAsJsonObject("params").getAsJsonArray("contentChanges")[0].asJsonObject
        assertTrue(!change.has("range"))
    }

    @Test
    fun `shutdown uses id 2 and exit is a notification`() {
        val shutdown = LspMessages.shutdown()
        assertEquals(2, shutdown.get("id").asLong)
        assertTrue(!shutdown.has("params"))
        val exit = LspMessages.exit()
        assertEquals("exit", exit.get("method").asString)
        assertTrue(!exit.has("id"))
    }

    @Test
    fun `every built message parses as json`() {
        val messages = listOf(
            LspMessages.initialize("file:///x"),
            LspMessages.initialized(),
            LspMessages.didOpen("file:///x", "ATG TAA"),
            LspMessages.didChange("file:///x", 1, null, "T"),
            LspMessages.didSave("file:///x", "ATG"),
            LspMessages.didClose("file:///x"),
            LspMessages.requestPosition("textDocument/hover", "file:///x", 2, 3),
            LspMessages.requestFull("textDocument/documentSymbol", "file:///x"),
        )
        for (m in messages) {
            JsonParser.parseString(m.toString()) // no exception == valid JSON
        }
    }
}

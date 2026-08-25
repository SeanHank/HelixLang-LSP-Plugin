package com.helixlang.plugin.lsp.protocol

import com.google.gson.JsonParser
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class LspMessagesTest {

    @Test
    fun `initialize params carry rootUri and capabilities`() {
        val params = LspMessages.initialize("file:///workspace")
        assertEquals("file:///workspace", params.get("rootUri").asString)
        assertTrue(params.has("capabilities"))
        assertTrue(params.has("processId"))
    }

    @Test
    fun `didOpen params carry language id version and text`() {
        val params = LspMessages.didOpen("file:///t.helix", "#gene name=g\n", 1)
        val td = params.getAsJsonObject("textDocument")
        assertEquals("helix", td.get("languageId").asString)
        assertEquals(1, td.get("version").asInt)
        assertEquals("#gene name=g\n", td.get("text").asString)
    }

    @Test
    fun `didChange params carry a utf16 range delta`() {
        val range = LspMessages.RangeLsp(0, 3, 0, 6)
        val params = LspMessages.didChange("file:///t.helix", 2, range, "TAA")
        val changes = params.getAsJsonArray("contentChanges")
        assertEquals(1, changes.size())
        val change = changes[0].asJsonObject
        assertEquals("TAA", change.get("text").asString)
        assertEquals(3, change.getAsJsonObject("range").getAsJsonObject("start").get("character").asInt)
    }

    @Test
    fun `full document replacement drops the range`() {
        val params = LspMessages.didChange("file:///t.helix", 2, null, "NEW")
        val change = params.getAsJsonArray("contentChanges")[0].asJsonObject
        assertTrue(!change.has("range"))
    }

    @Test
    fun `requestPosition params carry uri and position`() {
        val params = LspMessages.requestPosition("file:///x", 2, 3)
        assertEquals("file:///x", params.getAsJsonObject("textDocument").get("uri").asString)
        assertEquals(2, params.getAsJsonObject("position").get("line").asInt)
        assertEquals(3, params.getAsJsonObject("position").get("character").asInt)
    }

    @Test
    fun `requestFull params carry only textDocument`() {
        val params = LspMessages.requestFull("file:///x")
        assertEquals("file:///x", params.getAsJsonObject("textDocument").get("uri").asString)
    }

    @Test
    fun `every built params parses as json`() {
        val paramsList = listOf(
            LspMessages.initialize("file:///x"),
            LspMessages.didOpen("file:///x", "ATG TAA"),
            LspMessages.didChange("file:///x", 1, null, "T"),
            LspMessages.didSave("file:///x", "ATG"),
            LspMessages.didClose("file:///x"),
            LspMessages.requestPosition("file:///x", 2, 3),
            LspMessages.requestFull("file:///x"),
        )
        for (p in paramsList) {
            JsonParser.parseString(p.toString()) // no exception == valid JSON
        }
    }
}

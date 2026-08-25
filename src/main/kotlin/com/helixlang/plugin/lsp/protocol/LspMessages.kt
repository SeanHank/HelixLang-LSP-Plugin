package com.helixlang.plugin.lsp.protocol

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/**
 * Builders for LSP request/notification **params** (Gson-backed; the platform
 * bundles Gson on the 222 baseline).
 *
 * Each method returns only the `params` object — [com.helixlang.plugin.lsp.LspDispatcher]
 * handles the outer JSON-RPC envelope (id, method, jsonrpc).
 */
object LspMessages {

    fun response(id: Long, result: JsonObject?): JsonObject =
        JsonObject().apply {
            addProperty("jsonrpc", "2.0")
            addProperty("id", id)
            result?.let { add("result", it) }
        }

    fun initialize(rootUri: String): JsonObject = JsonObject().apply {
        add("processId", com.google.gson.JsonNull.INSTANCE)
        addProperty("rootUri", rootUri)
        add("capabilities", JsonObject())
    }

    fun didOpen(uri: String, text: String, version: Int = 1): JsonObject =
        textDocumentParams(uri) {
            addProperty("languageId", "helix")
            addProperty("version", version)
            addProperty("text", text)
        }

    fun didChange(uri: String, version: Int, range: RangeLsp?, text: String): JsonObject {
        val change = JsonObject()
        range?.let { change.add("range", it.toJson()) }
        change.addProperty("text", text)
        val params = textDocumentParams(uri) {
            addProperty("version", version)
        }
        params.add("contentChanges", JsonArray().apply { add(change) })
        return params
    }

    fun didSave(uri: String, text: String): JsonObject =
        textDocumentParams(uri) {
            addProperty("text", text)
        }

    fun didClose(uri: String): JsonObject =
        textDocumentParams(uri)

    fun requestPosition(uri: String, line: Int, character: Int): JsonObject {
        val params = textDocumentParams(uri)
        params.add("position", JsonObject().apply {
            addProperty("line", line)
            addProperty("character", character)
        })
        return params
    }

    fun requestFull(uri: String): JsonObject =
        textDocumentParams(uri)

    /** Data class mirror of an LSP range (used to build didChange deltas). */
    class RangeLsp(val startLine: Int, val startCharacter: Int,
                   val endLine: Int, val endCharacter: Int) {
        fun toJson(): JsonObject = JsonObject().apply {
            add("start", pos(startLine, startCharacter))
            add("end", pos(endLine, endCharacter))
        }

        private fun pos(line: Int, character: Int): JsonObject = JsonObject().apply {
            addProperty("line", line)
            addProperty("character", character)
        }
    }

    private fun textDocumentParams(uri: String, block: JsonObject.() -> Unit = {}): JsonObject =
        JsonObject().apply {
            add("textDocument", JsonObject().apply {
                addProperty("uri", uri)
                block()
            })
        }
}

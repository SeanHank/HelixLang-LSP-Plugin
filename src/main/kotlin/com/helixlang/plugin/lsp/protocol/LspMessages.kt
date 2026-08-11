package com.helixlang.plugin.lsp.protocol

import com.google.gson.JsonArray
import com.google.gson.JsonObject

/**
 * Builders for LSP JSON-RPC messages (Gson-backed; the platform bundles Gson
 * on the 222 baseline).
 */
object LspMessages {

    fun request(id: Long, method: String, params: JsonObject?): JsonObject =
        JsonObject().apply {
            addProperty("jsonrpc", "2.0")
            addProperty("id", id)
            addProperty("method", method)
            params?.let { add("params", it) }
        }

    fun response(id: Long, result: JsonObject?): JsonObject =
        JsonObject().apply {
            addProperty("jsonrpc", "2.0")
            addProperty("id", id)
            result?.let { add("result", it) }
        }

    fun notify(method: String, params: JsonObject?): JsonObject =
        JsonObject().apply {
            addProperty("jsonrpc", "2.0")
            addProperty("method", method)
            params?.let { add("params", it) }
        }

    fun initialize(rootUri: String): JsonObject {
        val params = JsonObject().apply {
            add("processId", com.google.gson.JsonNull.INSTANCE)
            addProperty("rootUri", rootUri)
            add("capabilities", JsonObject())
        }
        return request(1, LspConstants.INITIALIZE, params)
    }

    fun initialized(): JsonObject = notify(LspConstants.INITIALIZED, null)

    fun shutdown(): JsonObject = request(2, LspConstants.SHUTDOWN, null)

    fun exit(): JsonObject = notify(LspConstants.EXIT, null)

    fun didOpen(uri: String, text: String, version: Int = 1): JsonObject =
        notify(LspConstants.DID_OPEN, textDocumentParams(uri) {
            addProperty("languageId", "helix")
            addProperty("version", version)
            addProperty("text", text)
        })

    fun didChange(uri: String, version: Int, range: RangeLsp?, text: String): JsonObject {
        val change = JsonObject()
        range?.let { change.add("range", it.toJson()) }
        change.addProperty("text", text)
        val params = textDocumentParams(uri) {
            addProperty("version", version)
        }
        params.add("contentChanges", JsonArray().apply { add(change) })
        return notify(LspConstants.DID_CHANGE, params)
    }

    fun didSave(uri: String, text: String): JsonObject =
        notify(LspConstants.DID_SAVE, textDocumentParams(uri) {
            addProperty("text", text)
        })

    fun didClose(uri: String): JsonObject =
        notify(LspConstants.DID_CLOSE, textDocumentParams(uri))

    fun requestPosition(method: String, uri: String, line: Int, character: Int): JsonObject {
        val params = textDocumentParams(uri)
        params.add("position", JsonObject().apply {
            addProperty("line", line)
            addProperty("character", character)
        })
        return request(nextId(method), method, params)
    }

    fun requestFull(method: String, uri: String): JsonObject =
        request(nextId(method), method, textDocumentParams(uri))

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

    private var idCounter = 100L

    private fun nextId(method: String): Long {
        idCounter += 1
        return idCounter
    }

    private fun textDocumentParams(uri: String, block: JsonObject.() -> Unit = {}): JsonObject =
        JsonObject().apply {
            add("textDocument", JsonObject().apply {
                addProperty("uri", uri)
                block()
            })
        }
}
